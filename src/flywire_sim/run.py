"""Command-line entry point for the propagation simulation.

Run as::

    python -m flywire_sim.run --source-type EPG --source-side left --steps 40

Examples::

    # stimulate every left-hemisphere EPG neuron and watch the circuit respond
    python -m flywire_sim.run --source-type EPG --source-side left --steps 40

    # stimulate two specific neurons and save the full time series
    python -m flywire_sim.run \\
        --source-id 720575940604481062 --source-id 720575940626306321 \\
        --steps 60 --out runs/two_epg.json

    # compare against the dataset's own (predicted) neurotransmitter signs
    python -m flywire_sim.run --source-type EPG --nt-policy predicted

The CLI prints a per-step summary table and a short report. Nothing here talks
to a network: the API layer is a separate phase and consumes the same
:class:`~flywire_sim.result.SimulationResult` object.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .graph import DEFAULT_CIRCUIT, load_graph
from .model import LIFParameters, LIFSimulation
from .result import SimulationResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m flywire_sim.run",
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    source = parser.add_argument_group("stimulus source (at least one selector required)")
    source.add_argument(
        "--source-id",
        type=int,
        action="append",
        dest="source_ids",
        metavar="ROOT_ID",
        help="FlyWire root_id to stimulate; repeatable.",
    )
    source.add_argument(
        "--source-type",
        action="append",
        dest="source_types",
        metavar="CELL_TYPE",
        help="Cell type to stimulate, e.g. EPG or Delta7; repeatable.",
    )
    source.add_argument(
        "--source-side",
        choices=("left", "right"),
        default=None,
        help="Restrict the source selection to one hemisphere.",
    )
    source.add_argument(
        "--source-limit",
        type=int,
        default=None,
        help="Stimulate at most this many of the selected neurons "
        "(deterministic: the first N in graph order).",
    )

    stim = parser.add_argument_group("stimulus shape")
    stim.add_argument("--amplitude", type=float, default=1.0, help="Injected current per step.")
    stim.add_argument("--stim-start", type=int, default=1, help="First step of the stimulus.")
    stim.add_argument("--stim-duration", type=int, default=6, help="Stimulus length in steps.")

    model = parser.add_argument_group("model parameters (all dimensionless, see model.py)")
    defaults = LIFParameters()
    model.add_argument("--steps", type=int, default=50, help="Number of update steps.")
    model.add_argument("--threshold", type=float, default=defaults.threshold)
    model.add_argument("--leak", type=float, default=defaults.leak)
    model.add_argument("--gain", type=float, default=defaults.gain)
    model.add_argument("--refractory-steps", type=int, default=defaults.refractory_steps)
    model.add_argument("--trace-decay", type=float, default=defaults.trace_decay)
    model.add_argument("--v-min", type=float, default=defaults.v_min)
    model.add_argument(
        "--noise-std",
        type=float,
        default=defaults.noise_std,
        help="Gaussian current noise; 0 keeps the run fully deterministic.",
    )
    model.add_argument("--seed", type=int, default=defaults.seed)
    model.add_argument(
        "--weight-normalisation",
        choices=("in-degree", "global-max", "none"),
        default=defaults.weight_normalisation,
    )

    data = parser.add_argument_group("data")
    data.add_argument("--circuit", default=DEFAULT_CIRCUIT)
    data.add_argument("--data-dir", type=Path, default=None)
    data.add_argument(
        "--nt-policy",
        choices=("known-first", "predicted"),
        default="known-first",
        help="How each neuron's excitatory/inhibitory sign is decided. "
        "'known-first' prefers the literature transmitter (Turner-Evans et al. "
        "2020) and is the simulation default; 'predicted' reproduces the "
        "dataset's automatic predictions.",
    )

    out = parser.add_argument_group("output")
    out.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the full time series as JSON (the format the backend streams).",
    )
    out.add_argument(
        "--out-csv",
        type=Path,
        default=None,
        help="Write the time series in long format (one row per step and neuron).",
    )
    out.add_argument("--json", action="store_true", help="Print the report as JSON.")
    out.add_argument("--quiet", action="store_true", help="Suppress the per-step table.")
    return parser


def _report(result: SimulationResult, graph, stimulus) -> dict:
    """Human-facing summary of a finished run."""
    fired = result.neurons_that_fired()
    types = Counter(graph.graph.nodes[n]["cell_type"] for n in fired)
    first = result.first_spike_step()
    first_by_type: dict[str, int] = {}
    for nid, step in first.items():
        cell_type = graph.graph.nodes[nid]["cell_type"]
        first_by_type[cell_type] = min(first_by_type.get(cell_type, step), step)

    summaries = result.summaries()
    peak = max(summaries, key=lambda s: s["n_spiked"]) if summaries else {}
    total_spikes = int(result.spike_matrix().sum())

    stimulated = set(stimulus.targets)
    downstream = [n for n in fired if n not in stimulated]

    return {
        "steps": result.n_steps,
        "neurons": result.n_neurons,
        "stimulated_neurons": len(stimulated),
        "neurons_that_fired": len(fired),
        "downstream_neurons_that_fired": len(downstream),
        "fraction_of_circuit_recruited": round(len(fired) / max(result.n_neurons, 1), 4),
        "total_spikes": total_spikes,
        "neurons_fired_by_cell_type": dict(sorted(types.items())),
        "first_spike_step_by_cell_type": dict(sorted(first_by_type.items())),
        "peak_step": peak.get("step"),
        "peak_n_spiked": peak.get("n_spiked"),
        "final_total_activation": round(summaries[-1]["total_activation"], 6) if summaries else 0.0,
        "numerically_finite": result.is_finite(),
        "max_abs_membrane": round(
            max((s["max_abs_membrane"] for s in summaries), default=0.0), 6
        ),
    }


def _print_table(result: SimulationResult, stream) -> None:
    print(
        f"{'step':>5}  {'spiked':>7}  {'total_act':>10}  {'max_act':>8}  {'mean_V':>8}",
        file=stream,
    )
    for s in result.summaries():
        print(
            f"{s['step']:>5}  {s['n_spiked']:>7}  {s['total_activation']:>10.3f}  "
            f"{s['max_activation']:>8.3f}  {s['mean_membrane']:>8.4f}",
            file=stream,
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.source_ids and not args.source_types:
        build_parser().error("give at least one of --source-id or --source-type")

    graph = load_graph(args.circuit, data_dir=args.data_dir, nt_policy=args.nt_policy)
    print(
        f"graph: {graph.n_neurons} neurons, {graph.graph.number_of_edges()} connections "
        f"(nt policy: {args.nt_policy})",
        file=sys.stderr,
    )

    params = LIFParameters(
        threshold=args.threshold,
        leak=args.leak,
        gain=args.gain,
        refractory_steps=args.refractory_steps,
        trace_decay=args.trace_decay,
        v_min=args.v_min,
        noise_std=args.noise_std,
        seed=args.seed,
        weight_normalisation=args.weight_normalisation,
    )
    simulation = LIFSimulation(graph, params)

    targets = graph.select(
        root_ids=args.source_ids,
        cell_type=args.source_types,
        side=args.source_side,
    )
    if args.source_limit is not None:
        targets = targets[: args.source_limit]
        if not targets:
            build_parser().error("--source-limit left no neurons selected")

    stimulus = simulation.make_stimulus(
        root_ids=targets,
        amplitude=args.amplitude,
        start=args.stim_start,
        duration=args.stim_duration,
    )
    print(f"stimulating {len(stimulus.targets)} neuron(s)", file=sys.stderr)

    result = simulation.run(stimulus, steps=args.steps)
    report = _report(result, graph, stimulus)

    if args.out:
        print(f"wrote {result.save_json(args.out)}", file=sys.stderr)
    if args.out_csv:
        print(f"wrote {result.save_csv(args.out_csv)}", file=sys.stderr)

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not args.quiet:
            _print_table(result, sys.stdout)
            print(file=sys.stdout)
        for key, value in report.items():
            print(f"{key}: {value}")

    if not result.is_finite():
        print("ERROR: simulation produced non-finite values", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
