"""The thin layer between a validated request and :mod:`flywire_sim`.

Nothing here models anything. It resolves a request into the objects the
simulation package already provides (:class:`~flywire_sim.model.LIFSimulation`,
:class:`~flywire_sim.model.Stimulus`), drives ``iter_steps`` one step at a time,
and encodes each :class:`~flywire_sim.result.StepState` for the wire.

Frame encoding, and why ``delta`` exists
----------------------------------------
A dense frame for this circuit is 153 activations + 153 booleans + 153 membrane
values, roughly 3-4 KB of JSON. At 40 steps that is ~150 KB for a whole run,
which is nothing, so **dense is the default** and the frontend can stay simple.

The ``delta`` format is there because dense scales linearly with neuron count
and step count, and this circuit is deliberately the small one. It sends, per
frame, only the entries that changed since the previous frame. On a typical run
most neurons are silent with a fully decayed trace, so the diff is a fraction of
the array. Frame 0 is always sent dense so the client has a baseline to apply
diffs to, and every frame carries its own ``format`` field so a client never has
to infer which it got.

``spiked`` in a delta frame is *not* a diff: it is the list of indices spiking on
that step. Spikes are already sparse (a neuron spikes on a minority of steps),
and "who is firing right now" is what a visualisation actually wants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

import numpy as np

from flywire_sim.model import LIFParameters, LIFSimulation, Stimulus
from flywire_sim.result import SimulationResult, StepState

from .circuits import CircuitRegistry, LoadedCircuit
from .errors import invalid_request, not_found
from .schemas import SimulationRequest

# --------------------------------------------------------------------------- #
# Frame encoding
# --------------------------------------------------------------------------- #


class FrameEncoder:
    """Turns a :class:`StepState` into a JSON-ready frame.

    The dense shape is produced by the simulation package itself
    (``SimulationResult.step_payloads``) rather than re-implemented here, so the
    streaming format and the CLI's ``--out`` JSON cannot drift apart. The delta
    shape is derived from the dense one, which keeps rounding identical.
    """

    def __init__(
        self,
        neuron_ids: tuple[int, ...],
        *,
        include_membrane: bool = True,
        frame_format: str = "dense",
    ):
        self.neuron_ids = neuron_ids
        self.include_membrane = include_membrane
        self.frame_format = frame_format
        self._previous: dict[str, list[float]] = {}

    def encode(self, state: StepState) -> dict[str, Any]:
        dense = SimulationResult(self.neuron_ids, [state]).step_payloads(
            include_membrane=self.include_membrane
        )[0]

        if self.frame_format == "dense" or not self._previous:
            self._previous = {
                "activation": list(dense["activation"]),
                **({"membrane": list(dense["membrane"])} if self.include_membrane else {}),
            }
            return {"format": "dense", **dense}

        frame: dict[str, Any] = {
            "format": "delta",
            "step": dense["step"],
            "activation": self._diff("activation", dense["activation"]),
            "spiked": [i for i, s in enumerate(dense["spiked"]) if s],
            "summary": dense["summary"],
        }
        if self.include_membrane:
            frame["membrane"] = self._diff("membrane", dense["membrane"])
        return frame

    def _diff(self, key: str, current: list[float]) -> dict[str, list]:
        previous = self._previous[key]
        indices = [i for i, (a, b) in enumerate(zip(previous, current)) if a != b]
        self._previous[key] = list(current)
        return {"indices": indices, "values": [current[i] for i in indices]}


# --------------------------------------------------------------------------- #
# Preparing a run
# --------------------------------------------------------------------------- #


@dataclass
class PreparedRun:
    """A validated, ready-to-integrate run. Built before a single step is taken."""

    request: SimulationRequest
    circuit: LoadedCircuit
    simulation: LIFSimulation
    stimulus: Stimulus
    metadata: dict[str, Any]

    def header(self) -> dict[str, Any]:
        indices = self.circuit.graph.indices_of(self.stimulus.targets)
        return {
            "n_neurons": self.circuit.graph.n_neurons,
            "n_steps": self.request.steps,
            "n_frames": self.request.steps + 1,
            "neuron_ids": [str(n) for n in self.circuit.graph.neuron_ids],
            "metadata": self.metadata,
            "frame_format": self.request.frame_format,
            "include_membrane": self.request.include_membrane,
            "stimulated_root_ids": [str(t) for t in self.stimulus.targets],
            "stimulated_indices": [int(i) for i in indices],
        }


def _resolve_parameters(request: SimulationRequest) -> LIFParameters:
    """Apply the client's overrides on top of the package defaults.

    ``LIFParameters.__post_init__`` enforces cross-field invariants that a
    per-field schema cannot (``v_min <= v_reset``, ``v_max > threshold``). Its
    ``ValueError`` is surfaced as a 422 with the original message rather than
    being allowed to become a 500.
    """
    try:
        return LIFParameters(**request.params.overrides())
    except ValueError as exc:
        raise invalid_request("invalid_parameters", str(exc)) from exc


def _resolve_targets(circuit: LoadedCircuit, request: SimulationRequest) -> list[int]:
    """Resolve the source selector, with a specific error for each way it can fail.

    ``SimulationGraph.select`` already refuses to silently return nothing; this
    checks the same conditions first only so the client gets a precise ``code``
    and the list of valid options instead of one generic message.
    """
    graph = circuit.graph
    selector = request.source

    root_ids = selector.as_int_root_ids()
    if root_ids:
        known = set(graph.neuron_ids)
        missing = [str(r) for r in root_ids if r not in known]
        if missing:
            raise not_found(
                "unknown_neuron",
                f"{len(missing)} root_id(s) are not in circuit {circuit.circuit!r}: "
                f"{missing[:5]}{' ...' if len(missing) > 5 else ''}",
                missing_root_ids=missing,
                circuit=circuit.circuit,
            )

    if selector.cell_types:
        available = [c["cell_type"] for c in circuit.cell_types]
        unknown = sorted(set(selector.cell_types) - set(available))
        if unknown:
            raise not_found(
                "unknown_cell_type",
                f"unknown cell_type(s) {unknown}; available: {available}",
                unknown_cell_types=unknown,
                available_cell_types=available,
            )

    try:
        targets = graph.select(
            root_ids=root_ids,
            cell_type=selector.cell_types,
            side=selector.side,
        )
    except KeyError as exc:
        raise not_found(
            "empty_selection",
            f"the source selector matched no neurons in circuit {circuit.circuit!r} "
            f"(root_ids={selector.root_ids}, cell_types={selector.cell_types}, "
            f"side={selector.side})",
            reason=str(exc),
        ) from exc

    if selector.limit is not None:
        targets = targets[: selector.limit]
    return targets


def prepare_run(registry: CircuitRegistry, request: SimulationRequest) -> PreparedRun:
    """Validate a request against real data and build everything the run needs.

    Raises:
        ApiError: 404 for an unknown circuit, neuron or cell type; 422 for
            parameter combinations the model rejects.
    """
    circuit = registry.get(request.circuit, request.nt_policy)
    params = _resolve_parameters(request)
    simulation = LIFSimulation(circuit.graph, params)
    targets = _resolve_targets(circuit, request)

    try:
        stimulus = simulation.make_stimulus(
            root_ids=targets,
            amplitude=request.stimulus.amplitude,
            start=request.stimulus.start,
            duration=request.stimulus.duration,
        )
    except ValueError as exc:
        raise invalid_request("invalid_stimulus", str(exc)) from exc

    metadata = simulation.describe([stimulus], request.steps)
    return PreparedRun(
        request=request,
        circuit=circuit,
        simulation=simulation,
        stimulus=stimulus,
        metadata=metadata,
    )


# --------------------------------------------------------------------------- #
# Running
# --------------------------------------------------------------------------- #


@dataclass
class RunSession:
    """Drives one prepared run and encodes its frames.

    States are kept as they are produced so that :meth:`report` can be computed
    at the end from a real :class:`SimulationResult` -- including for a run that
    was cancelled halfway, which then reports on the steps it did take.
    """

    prepared: PreparedRun
    _states: list[StepState] = field(default_factory=list)

    def frames(self) -> Iterator[dict[str, Any]]:
        request = self.prepared.request
        encoder = FrameEncoder(
            self.prepared.circuit.graph.neuron_ids,
            include_membrane=request.include_membrane,
            frame_format=request.frame_format,
        )
        for state in self.prepared.simulation.iter_steps([self.prepared.stimulus], request.steps):
            self._states.append(state)
            yield encoder.encode(state)

    @property
    def result(self) -> SimulationResult:
        return SimulationResult(
            neuron_ids=self.prepared.circuit.graph.neuron_ids,
            steps=self._states,
            metadata=self.prepared.metadata,
        )

    def report(self) -> dict[str, Any]:
        return build_report(
            self.result,
            self.prepared.circuit,
            self.prepared.stimulus,
        )


def build_report(
    result: SimulationResult,
    circuit: LoadedCircuit,
    stimulus: Stimulus,
) -> dict[str, Any]:
    """Aggregate a finished run into the numbers a UI header wants.

    Pure aggregation over :class:`SimulationResult`'s public accessors: no
    dynamics are recomputed here.
    """
    graph = circuit.graph.graph
    fired = result.neurons_that_fired()
    first = result.first_spike_step()

    fired_by_type: dict[str, int] = {}
    first_by_type: dict[str, int] = {}
    for node_id in fired:
        cell_type = graph.nodes[node_id]["cell_type"]
        fired_by_type[cell_type] = fired_by_type.get(cell_type, 0) + 1
    for node_id, step in first.items():
        cell_type = graph.nodes[node_id]["cell_type"]
        first_by_type[cell_type] = min(first_by_type.get(cell_type, step), step)

    summaries = result.summaries()
    peak = max(summaries, key=lambda s: s["n_spiked"]) if summaries else {}
    stimulated = set(stimulus.targets)

    return {
        "steps": result.n_steps,
        "neurons": result.n_neurons,
        "stimulated_neurons": len(stimulated),
        "neurons_that_fired": len(fired),
        "downstream_neurons_that_fired": len([n for n in fired if n not in stimulated]),
        "fraction_of_circuit_recruited": round(len(fired) / max(result.n_neurons, 1), 4),
        "total_spikes": int(result.spike_matrix().sum()) if result.steps else 0,
        "neurons_fired_by_cell_type": dict(sorted(fired_by_type.items())),
        "first_spike_step_by_cell_type": dict(sorted(first_by_type.items())),
        "peak_step": peak.get("step"),
        "peak_n_spiked": peak.get("n_spiked"),
        "final_total_activation": (
            round(float(summaries[-1]["total_activation"]), 6) if summaries else 0.0
        ),
        "numerically_finite": result.is_finite() if result.steps else True,
        "max_abs_membrane": round(
            float(max((s["max_abs_membrane"] for s in summaries), default=0.0)), 6
        ),
    }


def strongest_source_root_id(circuit: LoadedCircuit, cell_type: str) -> str | None:
    """Root id of the ``cell_type`` neuron with the largest total outgoing weight.

    Used only to offer a sensible single-neuron preset; a single weak neuron
    recruits almost nothing under in-degree normalisation, which looks like a
    broken demo.
    """
    graph = circuit.graph
    candidates = [
        (node_id, float(np.abs(graph.weights[i]).sum()))
        for i, node_id in enumerate(graph.neuron_ids)
        if graph.graph.nodes[node_id]["cell_type"] == cell_type
    ]
    if not candidates:
        return None
    return str(max(candidates, key=lambda pair: pair[1])[0])
