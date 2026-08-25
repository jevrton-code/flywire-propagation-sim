"""End-to-end smoke tests: does activation actually travel through the real wiring?

Everything else in the suite could pass on an empty or synthetic graph. These
tests exist to prove the simulation is running on the committed FlyWire
subgraph: stimulate real ``EPG`` neurons, and check that the neurons that light
up next are their real postsynaptic partners in the real connectome.

Expected biology of this circuit (Turner-Evans et al., Neuron 108, 145-163
(2020); Hulse et al., eLife 10, e66039 (2021)): ``EPG`` neurons project onto
``PEN``, ``PEG`` and ``Delta7`` neurons. If stimulating ``EPG`` never reaches any
of those, either the graph is not wired up or the integrator is not using it.
"""

from __future__ import annotations

import numpy as np
import pytest

from flywire_sim import LIFParameters, SimulationGraph, load_graph, simulate

DOWNSTREAM_TYPES = {"PEG", "PEN_a(PEN1)", "PEN_b(PEN2)", "Delta7"}


@pytest.fixture(scope="module")
def graph():
    return load_graph()


def _types_of(graph, neuron_ids) -> set[str]:
    return {graph.graph.nodes[n]["cell_type"] for n in neuron_ids}


# --------------------------------------------------------------------------- #
# Single-neuron stimulation
# --------------------------------------------------------------------------- #


def test_a_single_epg_neuron_activates_its_direct_partners(graph):
    """The core smoke test: one real EPG neuron, a few steps, real neighbours light up.

    ``720575940635461550`` is used because it is the ``EPG`` neuron with the most
    strongly weighted outputs in this subgraph, which makes it the clearest
    single-neuron case. The assertions below are about *which* neurons fire, not
    how many: every neuron recruited must be a genuine postsynaptic partner of
    the stimulated one in the FlyWire graph.
    """
    source = 720575940635461550
    assert source in graph.neuron_ids

    result = simulate(graph, root_ids=[source], steps=10)
    fired = result.neurons_that_fired()
    first = result.first_spike_step()

    assert source in fired, "the stimulated neuron must fire"
    assert first[source] == 1, "a stimulated neuron fires on the step it is stimulated"

    # One synaptic hop takes exactly one step, so everything that fires at step 2
    # must be a genuine postsynaptic partner of the source in the FlyWire graph.
    step_two = [n for n, step in first.items() if step == 2]
    successors = set(graph.graph.successors(source))
    assert step_two, "activation did not leave the stimulated neuron"
    assert set(step_two) <= successors, (
        "a neuron fired one step after the source without being postsynaptic to "
        "it; the weight matrix and the graph disagree"
    )
    assert _types_of(graph, step_two) & DOWNSTREAM_TYPES, (
        f"expected PEG/PEN/Delta7 partners, got {_types_of(graph, step_two)}"
    )
    assert all(step >= 2 for n, step in first.items() if n != source)


def test_most_single_epg_neurons_recruit_at_least_one_partner(graph):
    """Quantifies the honest limitation, so a regression in either direction fails.

    With in-degree normalisation a single presynaptic neuron carries a median 4%
    of its target's synaptic input, so one neuron cannot drive an arbitrary
    partner. Measured with the defaults: 41 of the 47 ``EPG`` neurons recruit at
    least one direct partner and 6 recruit none. The bounds below are loose
    enough to survive parameter retuning but tight enough to catch "nothing
    propagates any more" and "everything explodes now".
    """
    epg = graph.select(cell_type="EPG")
    recruited = []
    for source in epg:
        result = simulate(graph, root_ids=[source], steps=10)
        recruited.append(len([n for n in result.neurons_that_fired() if n != source]))

    with_partners = sum(count > 0 for count in recruited)
    assert with_partners >= 0.7 * len(epg), (
        f"only {with_partners}/{len(epg)} EPG neurons propagated anywhere"
    )


def test_a_neuron_with_no_outgoing_connections_cannot_propagate(graph):
    """Sanity check on the direction of the edges, using the real graph."""
    sinks = [n for n in graph.neuron_ids if graph.graph.out_degree(n) == 0]
    if not sinks:
        pytest.skip("no pure sink neurons in this subgraph")
    result = simulate(graph, root_ids=[sinks[0]], steps=10)
    assert result.neurons_that_fired() == [sinks[0]]


# --------------------------------------------------------------------------- #
# Population stimulation -- the intended use
# --------------------------------------------------------------------------- #


def test_stimulating_the_epg_population_recruits_the_whole_circuit(graph):
    result = simulate(graph, cell_type="EPG", side="left", steps=120)
    fired = result.neurons_that_fired()

    assert len(fired) > 0.8 * graph.n_neurons, (
        f"only {len(fired)}/{graph.n_neurons} neurons fired"
    )
    assert DOWNSTREAM_TYPES <= _types_of(graph, fired), (
        f"missing downstream types: {DOWNSTREAM_TYPES - _types_of(graph, fired)}"
    )


def test_downstream_types_fire_one_step_after_the_source(graph):
    """EPG -> PEN/PEG/Delta7 is a monosynaptic hop, so step 2 with a step-1 source."""
    result = simulate(graph, cell_type="EPG", side="left", steps=60)
    first = result.first_spike_step()

    earliest_by_type: dict[str, int] = {}
    for neuron, step in first.items():
        cell_type = graph.graph.nodes[neuron]["cell_type"]
        earliest_by_type[cell_type] = min(earliest_by_type.get(cell_type, step), step)

    assert earliest_by_type["EPG"] == 1
    for cell_type in DOWNSTREAM_TYPES:
        assert earliest_by_type[cell_type] == 2, cell_type


def test_stimulating_delta7_hyperpolarises_its_real_targets(graph):
    """Delta7 output must subtract on the real edges, not just in a toy graph.

    Stimulating a single Delta7 neuron in isolation should push its postsynaptic
    partners *below* rest and fire none of them. If the sign were dropped
    anywhere between the CSV and the weight matrix, they would depolarise
    instead.
    """
    delta7 = [n for n in graph.neuron_ids if graph.graph.nodes[n]["cell_type"] == "Delta7"]
    source = delta7[0]
    targets = list(graph.graph.successors(source))
    assert targets, "the chosen Delta7 neuron has no outputs"

    result = simulate(graph, root_ids=[source], steps=6)
    assert result.neurons_that_fired() == [source], "inhibition must not recruit anyone"

    membrane = result.membrane_matrix()
    for target in targets:
        trace = membrane[:, result.neuron_ids.index(target)]
        assert trace.min() < 0.0, f"{target} was not hyperpolarised by Delta7 input"


def test_removing_inhibition_synchronises_the_circuit(graph):
    """Inhibition should measurably change the dynamics, not sit there decoratively.

    Note the direction of the effect is deliberately *not* asserted as "more
    spikes". Zeroing Delta7 output makes the circuit fire more synchronously,
    which under a shared refractory period actually shortens the run. What
    matters here is that removing 585 inhibitory edges changes the outcome at
    all -- if it did not, the E/I sign would be doing nothing.
    """
    baseline = simulate(graph, cell_type="EPG", side="left", steps=80)

    disinhibited = load_graph()
    for neuron in list(disinhibited.graph.nodes()):
        if disinhibited.graph.nodes[neuron]["cell_type"] != "Delta7":
            continue
        for _, target in list(disinhibited.graph.out_edges(neuron)):
            disinhibited.graph[neuron][target]["weight"] = 0.0
    rebuilt = SimulationGraph(disinhibited.graph, disinhibited.provenance)
    without_inhibition = simulate(rebuilt, cell_type="EPG", side="left", steps=80)

    assert not np.array_equal(
        baseline.spike_matrix(), without_inhibition.spike_matrix()
    ), "silencing every inhibitory neuron changed nothing"

    baseline_peak = max(s["n_spiked"] for s in baseline.summaries())
    open_loop_peak = max(s["n_spiked"] for s in without_inhibition.summaries())
    assert open_loop_peak >= baseline_peak


def test_propagation_reaches_the_opposite_hemisphere(graph):
    """The head-direction circuit is bilateral; a one-sided stimulus must cross over."""
    result = simulate(graph, cell_type="EPG", side="left", steps=60)
    sides = {graph.graph.nodes[n]["side"] for n in result.neurons_that_fired()}
    assert sides == {"left", "right"}


# --------------------------------------------------------------------------- #
# The output the backend will consume
# --------------------------------------------------------------------------- #


def test_result_shape_is_one_frame_per_step_plus_rest(graph):
    result = simulate(graph, cell_type="EPG", side="left", steps=25)
    assert len(result.steps) == 26
    assert result.n_steps == 25
    assert [s.step for s in result.steps] == list(range(26))
    assert result.steps[0].n_spiked() == 0, "the run must start from rest"
    for state in result.steps:
        assert state.membrane.shape == (graph.n_neurons,)
        assert state.spiked.shape == (graph.n_neurons,)
        assert state.activation.shape == (graph.n_neurons,)


def test_step_payloads_are_json_serialisable_and_aligned(graph):
    import json

    result = simulate(graph, cell_type="EPG", side="left", steps=10)
    payload = json.loads(result.to_json())

    assert payload["n_neurons"] == graph.n_neurons
    assert len(payload["frames"]) == 11
    # 18-digit FlyWire root IDs must be strings: they do not survive a JS Number.
    assert all(isinstance(n, str) for n in payload["neuron_ids"])
    assert all(int(n) in graph.neuron_ids for n in payload["neuron_ids"])
    for frame in payload["frames"]:
        assert len(frame["activation"]) == graph.n_neurons
        assert len(frame["spiked"]) == graph.n_neurons
        assert set(frame["summary"]) >= {"step", "n_spiked", "total_activation"}


def test_long_format_has_one_row_per_step_and_neuron(graph):
    result = simulate(graph, cell_type="EPG", side="left", steps=5)
    frame = result.to_frame()
    assert len(frame) == 6 * graph.n_neurons
    assert set(frame.columns) == {
        "step",
        "root_id",
        "activation",
        "spiked",
        "membrane",
        "input_current",
    }
    assert frame["step"].max() == 5


def test_metadata_travels_with_the_result(graph):
    """The backend serves this verbatim, so the honesty has to be inside it."""
    result = simulate(graph, cell_type="EPG", side="left", steps=5)
    meta = result.metadata

    assert meta["parameters"]["model"].startswith("discrete-time leaky integrate-and-fire")
    assert meta["parameters"]["threshold"] == LIFParameters().threshold
    assert meta["graph"]["nt_policy"] == "known-first"
    assert "Turner-Evans" in meta["graph"]["known_nt_reference"]
    assert meta["graph"]["dataset"]["connectivity"]["doi"] == "10.5281/zenodo.10676866"
    assert len(meta["simplifications"]) >= 8
    assert any("plasticity" in s for s in meta["simplifications"])
    assert any("dimensionless" in s for s in meta["simplifications"])
    assert "not calibrated" in meta["disclaimer"]
    assert meta["stimuli"][0]["targets"]


def test_spike_counts_and_activation_agree(graph):
    result = simulate(graph, cell_type="EPG", side="left", steps=40)
    counts = result.spike_counts()
    assert sum(counts.values()) == int(result.spike_matrix().sum())
    # Any neuron that never spiked must end with a zero activation trace.
    final = result.steps[-1].activation
    for i, neuron in enumerate(result.neuron_ids):
        if counts[neuron] == 0:
            assert final[i] == 0.0


def test_result_saves_to_disk(graph, tmp_path):
    result = simulate(graph, cell_type="EPG", side="left", steps=5)
    json_path = result.save_json(tmp_path / "run.json")
    csv_path = result.save_csv(tmp_path / "run.csv")
    assert json_path.exists() and json_path.stat().st_size > 0
    assert csv_path.exists() and csv_path.stat().st_size > 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_runs_and_reports_propagation(capsys, tmp_path):
    from flywire_sim.run import main

    exit_code = main(
        [
            "--source-type",
            "EPG",
            "--source-side",
            "left",
            "--steps",
            "30",
            "--json",
            "--out",
            str(tmp_path / "out.json"),
        ]
    )
    assert exit_code == 0

    import json

    report = json.loads(capsys.readouterr().out)
    assert report["numerically_finite"] is True
    assert report["downstream_neurons_that_fired"] > 0
    assert report["neurons_that_fired"] > 0
    assert set(report["spikes_by_cell_type"]) >= DOWNSTREAM_TYPES
    assert (tmp_path / "out.json").exists()


def test_cli_accepts_a_single_root_id(capsys):
    from flywire_sim.run import main

    assert main(["--source-id", "720575940635461550", "--steps", "10", "--json"]) == 0
    report = __import__("json").loads(capsys.readouterr().out)
    assert report["stimulated_neurons"] == 1
    assert report["downstream_neurons_that_fired"] > 0


def test_cli_requires_a_source():
    from flywire_sim.run import main

    with pytest.raises(SystemExit):
        main(["--steps", "5"])


def test_cli_reproduces_the_dataset_policy_on_request(capsys):
    from flywire_sim.run import main

    assert main(["--source-type", "EPG", "--steps", "10", "--nt-policy", "predicted", "--json"]) == 0
    assert capsys.readouterr().out


def test_cli_output_is_deterministic(capsys):
    from flywire_sim.run import main

    args = ["--source-type", "EPG", "--source-side", "left", "--steps", "25", "--json"]
    main(args)
    first = capsys.readouterr().out
    main(args)
    second = capsys.readouterr().out
    assert first == second
