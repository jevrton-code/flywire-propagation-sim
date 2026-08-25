"""Numerical-stability, determinism and sanity tests for the LIF propagation model.

Three groups:

1. **Toy circuits** -- hand-checkable graphs (2-3 nodes) where the correct answer
   can be worked out on paper. If the integrator is wrong, these fail first and
   explain why.
2. **Numerical stability** -- on the real 153-neuron graph, including
   deliberately adversarial parameter settings. The claim being tested is that
   the state stays finite and bounded *structurally* (binary spikes + reset +
   clamp), not because the defaults happen to be gentle.
3. **Determinism** -- identical inputs give bit-identical outputs, and noise is
   reproducible from its seed.
"""

from __future__ import annotations

import numpy as np
import pytest

from flywire_sim import (
    LIFParameters,
    LIFSimulation,
    SimulationGraph,
    Stimulus,
    load_graph,
    simulate,
)

STEPS = 120


@pytest.fixture(scope="module")
def graph():
    return load_graph()


@pytest.fixture(scope="module")
def epg_left(graph):
    return graph.select(cell_type="EPG", side="left")


# --------------------------------------------------------------------------- #
# 1. Toy circuits with a known answer
# --------------------------------------------------------------------------- #


def test_three_node_chain_propagates_one_hop_per_step():
    """A -> B -> C, all excitatory. Stimulating A must light B then C, in order.

    With in-degree normalisation a single incoming connection is normalised to
    weight 1.0, so any presynaptic spike is suprathreshold for its only target.
    The expected spike times are therefore exactly step 1, 2, 3.
    """
    graph = SimulationGraph.from_edge_list([(1, 2, 10.0), (2, 3, 10.0)])
    result = simulate(graph, root_ids=[1], steps=6, stim_duration=1)

    assert result.first_spike_step() == {1: 1, 2: 2, 3: 3}
    assert sum(result.spike_counts().values()) == 3


def test_chain_does_not_propagate_backwards():
    """The graph is directed; stimulating the tail must not excite the head."""
    graph = SimulationGraph.from_edge_list([(1, 2, 10.0), (2, 3, 10.0)])
    result = simulate(graph, root_ids=[3], steps=6, stim_duration=1)

    assert result.neurons_that_fired() == [3]


def test_inhibition_cancels_matched_excitation():
    """A(+) and B(-) both project to C with equal strength.

    In-degree normalisation puts C's two inputs at +0.5 and -0.5. Stimulating A
    alone drives C over the 0.2 threshold; stimulating A and B together cancels
    exactly, so C must stay silent. This is the test that would catch a sign
    error in the weight matrix or in the Dale's-law bookkeeping.
    """
    graph = SimulationGraph.from_edge_list([(1, 3, 10.0), (2, 3, -10.0)])

    excited = simulate(graph, root_ids=[1], steps=5, stim_duration=1)
    assert 3 in excited.neurons_that_fired()

    cancelled = simulate(graph, root_ids=[1, 2], steps=5, stim_duration=1)
    assert 3 not in cancelled.neurons_that_fired()


def test_inhibition_can_silence_a_target_outright():
    graph = SimulationGraph.from_edge_list([(1, 3, 5.0), (2, 3, -20.0)])
    result = simulate(graph, root_ids=[1, 2], steps=5, stim_duration=1)
    assert 3 not in result.neurons_that_fired()
    membrane = result.membrane_matrix()[:, result.neuron_ids.index(3)]
    assert membrane.min() < 0.0, "the inhibited neuron should hyperpolarise"


def test_subthreshold_input_summates_over_steps_then_fires():
    """A connection worth less than the threshold on its own must still count.

    Node 3 receives 15 synapses from node 1 and 85 from node 2, so in-degree
    normalisation gives node 1 a weight of exactly 0.15 -- below the 0.25
    threshold used here. One presynaptic spike must not fire it; two consecutive
    ones must, because 0.15 + 0.9 * 0.15 = 0.285 >= 0.25 under the leak.

    This is the test that would catch a leak that silently drops the previous
    membrane value.
    """
    graph = SimulationGraph.from_edge_list([(1, 3, 15.0), (2, 3, 85.0)])
    # refractory_steps=0 so node 1 can fire on every step it is stimulated.
    params = LIFParameters(threshold=0.25, leak=0.9, refractory_steps=0)

    simulation = LIFSimulation(graph, params)
    single = simulation.run(Stimulus(targets=(1,), duration=1), steps=5)
    assert 3 not in single.neurons_that_fired(), "0.15 alone must be subthreshold"

    repeated = simulation.run(Stimulus(targets=(1,), duration=3), steps=6)
    assert 3 in repeated.neurons_that_fired()


def test_refractory_period_blocks_immediate_refiring():
    graph = SimulationGraph.from_edge_list([(1, 2, 10.0)])
    params = LIFParameters(refractory_steps=3)
    simulation = LIFSimulation(graph, params)
    # Continuous strong drive on node 1 for the whole run.
    result = simulation.run(Stimulus(targets=(1,), amplitude=5.0, duration=20), steps=20)

    spikes = result.spike_matrix()[:, result.neuron_ids.index(1)]
    fired_at = np.flatnonzero(spikes)
    gaps = np.diff(fired_at)
    assert gaps.size > 0
    assert gaps.min() >= params.refractory_steps + 1


def test_zero_refractory_allows_firing_every_step():
    graph = SimulationGraph.from_edge_list([(1, 2, 10.0)])
    simulation = LIFSimulation(graph, LIFParameters(refractory_steps=0))
    result = simulation.run(Stimulus(targets=(1,), amplitude=5.0, duration=10), steps=10)
    spikes = result.spike_matrix()[:, result.neuron_ids.index(1)]
    assert spikes[1:11].all()


def test_membrane_resets_after_a_spike():
    graph = SimulationGraph.from_edge_list([(1, 2, 10.0)])
    params = LIFParameters(v_reset=0.0)
    simulation = LIFSimulation(graph, params)
    result = simulation.run(Stimulus(targets=(1,), amplitude=5.0, duration=1), steps=3)

    column = result.neuron_ids.index(1)
    membrane = result.membrane_matrix()[:, column]
    spikes = result.spike_matrix()[:, column]
    assert spikes[1]
    assert membrane[1] == pytest.approx(params.v_reset)


def test_no_stimulus_means_no_activity(graph):
    """A circuit with no input must stay silent -- there is no spontaneous firing."""
    simulation = LIFSimulation(graph)
    result = simulation.run([], steps=20)
    assert result.spike_matrix().sum() == 0
    assert result.activation_matrix().max() == 0.0


# --------------------------------------------------------------------------- #
# 2. Numerical stability on the real graph
# --------------------------------------------------------------------------- #


def test_no_nan_or_inf_over_a_long_run(graph, epg_left):
    result = simulate(graph, root_ids=epg_left, steps=500)
    assert np.isfinite(result.membrane_matrix()).all()
    assert np.isfinite(result.activation_matrix()).all()
    assert result.is_finite()


def test_membrane_stays_within_the_declared_clamp(graph, epg_left):
    params = LIFParameters()
    result = simulate(graph, root_ids=epg_left, steps=STEPS, params=params)
    membrane = result.membrane_matrix()
    assert membrane.min() >= params.v_min - 1e-12
    assert membrane.max() <= params.v_max + 1e-12


def test_activation_trace_stays_in_the_unit_interval(graph, epg_left):
    result = simulate(graph, root_ids=epg_left, steps=STEPS)
    activation = result.activation_matrix()
    assert activation.min() >= 0.0
    assert activation.max() <= 1.0


def test_activation_does_not_grow_without_bound(graph, epg_left):
    """Compare the first and second half of a long run: no runaway growth."""
    result = simulate(graph, root_ids=epg_left, steps=400)
    totals = np.array([s["total_activation"] for s in result.summaries()])
    first_half = totals[: len(totals) // 2].max()
    second_half = totals[len(totals) // 2 :].max()
    assert second_half <= first_half + 1e-9


@pytest.mark.parametrize(
    "params",
    [
        pytest.param(LIFParameters(threshold=0.01, refractory_steps=0), id="hair-trigger"),
        pytest.param(LIFParameters(gain=50.0), id="huge-gain"),
        pytest.param(LIFParameters(leak=1.0, refractory_steps=0), id="perfect-integrator"),
        pytest.param(LIFParameters(weight_normalisation="none"), id="raw-synapse-counts"),
        pytest.param(LIFParameters(weight_normalisation="global-max"), id="global-max"),
        pytest.param(LIFParameters(noise_std=0.5), id="noisy"),
    ],
)
def test_adversarial_parameters_stay_bounded_and_finite(graph, epg_left, params):
    """The bound must come from the model's structure, not from gentle defaults.

    Binary spikes cap the per-step synaptic drive, the reset empties the
    membrane on every spike, and the clamp catches anything else. None of these
    settings should be able to produce NaN, inf, or unbounded growth -- however
    silly the resulting dynamics are.
    """
    result = simulate(graph, root_ids=epg_left, steps=200, params=params, amplitude=10.0)
    membrane = result.membrane_matrix()
    assert np.isfinite(membrane).all()
    assert np.isfinite(result.activation_matrix()).all()
    assert membrane.min() >= params.v_min - 1e-12
    assert membrane.max() <= params.v_max + 1e-12
    assert result.activation_matrix().max() <= 1.0


def test_activity_decays_to_silence_after_the_stimulus_ends(graph, epg_left):
    """With the documented defaults, a transient stimulus gives a transient wave.

    Silence is an absorbing state of this model: with no spikes and no stimulus
    the drive is exactly zero and the membrane decays geometrically, so once the
    circuit goes quiet it stays quiet. The point of this test is that it *does*
    go quiet within a reasonable horizon rather than latching into permanent
    self-sustained firing.
    """
    result = simulate(graph, root_ids=epg_left, steps=300)
    per_step = np.array([s["n_spiked"] for s in result.summaries()])

    assert per_step.sum() > 0, "the stimulus must actually do something"
    assert per_step[-200:].sum() == 0, "activity should have died out"
    assert result.summaries()[-1]["total_activation"] < 1e-6


def test_activity_does_not_die_instantly_either(graph, epg_left):
    """The complementary failure mode: a circuit that swallows every stimulus."""
    result = simulate(graph, root_ids=epg_left, steps=STEPS)
    per_step = np.array([s["n_spiked"] for s in result.summaries()])
    active_steps = int((per_step > 0).sum())
    assert active_steps >= 5, f"activity lasted only {active_steps} steps"
    assert len(result.neurons_that_fired()) > len(epg_left)


def test_saturating_regime_is_still_bounded(graph, epg_left):
    """Documented in model.py: low threshold / no refractoriness saturates.

    That regime is allowed -- but it must saturate, not diverge.
    """
    params = LIFParameters(threshold=0.1, refractory_steps=0)
    result = simulate(graph, root_ids=epg_left, steps=200, params=params)
    per_step = np.array([s["n_spiked"] for s in result.summaries()])

    assert per_step[-20:].sum() > 0, "expected the self-sustaining regime here"
    assert per_step.max() <= graph.n_neurons
    assert np.isfinite(result.membrane_matrix()).all()


def test_stimulating_the_whole_circuit_does_not_blow_up(graph):
    result = simulate(graph, cell_type=list({
        graph.graph.nodes[n]["cell_type"] for n in graph.neuron_ids
    }), steps=200, amplitude=5.0, stim_duration=10)
    assert result.is_finite()
    assert result.activation_matrix().max() <= 1.0


# --------------------------------------------------------------------------- #
# 3. Determinism
# --------------------------------------------------------------------------- #


def test_identical_inputs_give_identical_outputs(graph, epg_left):
    a = simulate(graph, root_ids=epg_left, steps=60)
    b = simulate(graph, root_ids=epg_left, steps=60)
    assert np.array_equal(a.membrane_matrix(), b.membrane_matrix())
    assert np.array_equal(a.spike_matrix(), b.spike_matrix())
    assert np.array_equal(a.activation_matrix(), b.activation_matrix())


def test_default_parameters_involve_no_randomness(graph):
    assert LIFParameters().noise_std == 0.0


def test_noise_is_reproducible_from_its_seed(graph, epg_left):
    params = LIFParameters(noise_std=0.05, seed=7)
    a = simulate(graph, root_ids=epg_left, steps=60, params=params)
    b = simulate(graph, root_ids=epg_left, steps=60, params=params)
    assert np.array_equal(a.spike_matrix(), b.spike_matrix())


def test_different_seeds_give_different_noise(graph, epg_left):
    a = simulate(graph, root_ids=epg_left, steps=60, params=LIFParameters(noise_std=0.05, seed=1))
    b = simulate(graph, root_ids=epg_left, steps=60, params=LIFParameters(noise_std=0.05, seed=2))
    assert not np.array_equal(a.spike_matrix(), b.spike_matrix())


def test_streaming_and_batch_paths_agree(graph, epg_left):
    """iter_steps() is what the backend will consume; it must match run()."""
    simulation = LIFSimulation(graph)
    stimulus = simulation.make_stimulus(root_ids=epg_left)
    streamed = list(simulation.iter_steps([stimulus], steps=40))
    batched = simulation.run(stimulus, steps=40)

    assert len(streamed) == len(batched.steps)
    for a, b in zip(streamed, batched.steps):
        assert a.step == b.step
        assert np.array_equal(a.spiked, b.spiked)
        assert np.array_equal(a.membrane, b.membrane)


# --------------------------------------------------------------------------- #
# Parameter validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kwargs",
    [
        {"threshold": 0.0},
        {"threshold": -1.0},
        {"leak": 1.5},
        {"leak": -0.1},
        {"trace_decay": 1.0},
        {"refractory_steps": -1},
        {"gain": -1.0},
        {"noise_std": -0.1},
        {"v_min": 1.0},
        {"v_max": 0.05},
    ],
)
def test_invalid_parameters_are_rejected(kwargs):
    """A leak > 1 would integrate divergently; better to refuse than to diverge."""
    with pytest.raises(ValueError):
        LIFParameters(**kwargs)


def test_stimulus_validation():
    with pytest.raises(ValueError, match="no targets"):
        Stimulus(targets=())
    with pytest.raises(ValueError, match="1-based"):
        Stimulus(targets=(1,), start=0)
    with pytest.raises(ValueError, match="duration"):
        Stimulus(targets=(1,), duration=0)


def test_negative_step_count_is_rejected(graph):
    simulation = LIFSimulation(graph)
    with pytest.raises(ValueError, match="steps must be >= 0"):
        list(simulation.iter_steps([], steps=-1))


def test_stimulus_window_is_honoured(graph):
    stimulus = Stimulus(targets=(1,), start=4, duration=2)
    assert [stimulus.is_active(t) for t in range(1, 8)] == [
        False,
        False,
        False,
        True,
        True,
        False,
        False,
    ]


def test_delayed_stimulus_delays_the_first_spike(graph, epg_left):
    result = simulate(graph, root_ids=epg_left, steps=30, stim_start=5)
    first = min(result.first_spike_step().values())
    assert first == 5
