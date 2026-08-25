"""Tests for loading the FlyWire subgraph into a simulation-ready graph.

Focus: the neurotransmitter policy, the sign bookkeeping, and the weight
normalisation invariants the integrator relies on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flywire_sim.graph import (
    SimulationGraph,
    UnknownNeurotransmitterError,
    build_graph,
    load_graph,
)

# Documented in data/README.md section 6.3: the two neurons whose automatic
# neurotransmitter prediction contradicts the literature, and which the
# simulation's "known-first" policy overrides.
DELTA7_MISPREDICTED = 720575940617752537
PEN_B_MISPREDICTED = 720575940626306321


@pytest.fixture(scope="module")
def graph() -> SimulationGraph:
    return load_graph()


@pytest.fixture(scope="module")
def predicted_graph() -> SimulationGraph:
    return load_graph(nt_policy="predicted")


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #


def test_graph_has_the_expected_size(graph):
    assert graph.n_neurons == 153
    assert graph.graph.number_of_edges() == 2695


def test_graph_is_not_empty_or_disconnected(graph):
    # A silently empty or edgeless graph would make every propagation test
    # vacuously pass, so assert the topology is really there.
    assert graph.weights.shape == (153, 153)
    assert np.count_nonzero(graph.weights) > 2000
    degrees = graph.weights != 0
    assert degrees.sum(axis=1).min() >= 0  # some neurons may be pure sinks
    assert (degrees.sum(axis=0) > 0).all(), "every neuron must have at least one input"


def test_neuron_ids_are_the_canonical_ordering(graph):
    assert len(graph.neuron_ids) == graph.n_neurons
    assert len(set(graph.neuron_ids)) == graph.n_neurons
    for i, nid in enumerate(graph.neuron_ids):
        assert graph.index_of(nid) == i


def test_weight_matrix_matches_the_networkx_edges(graph):
    for pre, post, data in graph.graph.edges(data=True):
        i, j = graph.index_of(pre), graph.index_of(post)
        assert graph.weights[i, j] == pytest.approx(data["weight"])


# --------------------------------------------------------------------------- #
# The "known-first" neurotransmitter policy
# --------------------------------------------------------------------------- #


def test_every_delta7_is_inhibitory_under_known_first(graph):
    """The load-time policy must yield the canonical ring-attractor architecture.

    Delta7 neurons supply the global inhibition of the ring attractor
    (Turner-Evans et al., Neuron 108, 145-163 (2020)). Under the dataset's own
    `predicted` policy one of them comes out excitatory from a 0.354-confidence
    prediction; the simulation's known-first policy must fix that.
    """
    delta7 = [n for n in graph.neuron_ids if graph.graph.nodes[n]["cell_type"] == "Delta7"]
    assert len(delta7) == 40
    assert all(graph.graph.nodes[n]["sign"] == -1 for n in delta7)


def test_every_non_delta7_neuron_is_excitatory_under_known_first(graph):
    others = [n for n in graph.neuron_ids if graph.graph.nodes[n]["cell_type"] != "Delta7"]
    assert len(others) == 113
    assert all(graph.graph.nodes[n]["sign"] == 1 for n in others)


def test_no_modulatory_neurons_survive_the_policy(graph):
    # Zero-weight (modulatory) neurons are dead ends for propagation. Under
    # known-first there should be none left in this circuit.
    assert all(graph.graph.nodes[n]["sign"] != 0 for n in graph.neuron_ids)


def test_policy_overrides_exactly_the_two_documented_neurons(graph):
    overridden = set(graph.provenance.nodes_overridden_vs_dataset)
    assert overridden == {DELTA7_MISPREDICTED, PEN_B_MISPREDICTED}


def test_policy_falls_back_to_prediction_only_where_literature_is_silent(graph):
    from_predicted = [
        n for n in graph.neuron_ids if graph.graph.nodes[n]["nt_source"] == "predicted"
    ]
    # data/README.md section 6.3: 150 of 153 neurons have a literature transmitter.
    assert len(from_predicted) == 3
    assert graph.provenance.nodes_from_known_nt == 150
    for n in from_predicted:
        assert graph.graph.nodes[n]["known_nt_primary"] is None
        assert graph.graph.nodes[n]["cell_type"] == "EPGt"


def test_predicted_policy_still_reproduces_the_dataset(predicted_graph):
    """The alternative policy must reproduce the committed CSV exactly."""
    assert predicted_graph.provenance.nodes_overridden_vs_dataset == []
    assert predicted_graph.graph.nodes[DELTA7_MISPREDICTED]["sign"] == 1
    assert predicted_graph.graph.nodes[PEN_B_MISPREDICTED]["sign"] == 0


def test_policy_changes_the_edge_signs_not_just_the_node_signs(graph, predicted_graph):
    """Dale's law must be re-applied, otherwise the override would be cosmetic."""
    for source in (DELTA7_MISPREDICTED, PEN_B_MISPREDICTED):
        out_known = [d["sign"] for _, _, d in graph.graph.out_edges(source, data=True)]
        out_pred = [d["sign"] for _, _, d in predicted_graph.graph.out_edges(source, data=True)]
        assert out_known, f"{source} has no outgoing edges to check"
        assert set(out_known) != set(out_pred)
    assert all(d["sign"] == -1 for _, _, d in graph.graph.out_edges(DELTA7_MISPREDICTED, data=True))
    assert all(d["sign"] == 1 for _, _, d in graph.graph.out_edges(PEN_B_MISPREDICTED, data=True))


def test_edge_sign_always_comes_from_the_presynaptic_neuron(graph):
    for pre, _, data in graph.graph.edges(data=True):
        assert data["sign"] == graph.graph.nodes[pre]["sign"]
        assert data["weight"] == pytest.approx(data["sign"] * data["syn_count"])


def test_provenance_records_the_policy_and_its_citation(graph):
    payload = graph.provenance.to_dict()
    assert payload["nt_policy"] == "known-first"
    assert "Turner-Evans" in payload["known_nt_reference"]
    assert payload["n_inhibitory_neurons"] == 40
    assert payload["n_excitatory_neurons"] == 113
    assert payload["n_modulatory_neurons"] == 0
    # The dataset provenance must survive into the simulation metadata, so a
    # result can be traced back to the FlyWire release it came from.
    assert payload["dataset"]["connectivity"]["version"] == "783.0"


def test_unknown_transmitter_raises_instead_of_defaulting():
    nodes = pd.DataFrame(
        [
            {
                "root_id": 1,
                "cell_type": "X",
                "top_nt": "unobtainium",
                "known_nt_primary": None,
                "sign": 1,
            }
        ]
    )
    edges = pd.DataFrame(columns=["pre_root_id", "post_root_id", "syn_count", "n_neuropils"])
    with pytest.raises(UnknownNeurotransmitterError):
        build_graph(nodes, edges)


def test_dangling_edge_endpoints_raise():
    nodes = pd.DataFrame(
        [
            {
                "root_id": 1,
                "cell_type": "X",
                "top_nt": "acetylcholine",
                "known_nt_primary": None,
                "sign": 1,
            }
        ]
    )
    edges = pd.DataFrame(
        [{"pre_root_id": 1, "post_root_id": 999, "syn_count": 10, "n_neuropils": 1}]
    )
    with pytest.raises(ValueError, match="not in the node table"):
        build_graph(nodes, edges)


# --------------------------------------------------------------------------- #
# Weight normalisation
# --------------------------------------------------------------------------- #


def test_in_degree_normalisation_makes_incoming_weight_sum_to_one(graph):
    normalised = graph.normalised_weights("in-degree")
    incoming = np.abs(normalised).sum(axis=0)
    # Every neuron in this subgraph has at least one input (no orphans).
    assert np.allclose(incoming, 1.0)


def test_in_degree_normalisation_preserves_sign(graph):
    normalised = graph.normalised_weights("in-degree")
    assert np.array_equal(np.sign(normalised), np.sign(graph.weights))


def test_global_max_normalisation_bounds_weights(graph):
    normalised = graph.normalised_weights("global-max")
    assert np.abs(normalised).max() == pytest.approx(1.0)


def test_normalisation_is_cached_and_not_recomputed(graph):
    assert graph.normalised_weights("in-degree") is graph.normalised_weights("in-degree")


def test_unknown_normalisation_raises(graph):
    with pytest.raises(ValueError, match="unknown weight normalisation"):
        graph.normalised_weights("magic")  # type: ignore[arg-type]


def test_normalisation_handles_a_neuron_with_no_inputs():
    # A pure source neuron has zero incoming weight; dividing by it must not
    # produce NaN or inf.
    graph = SimulationGraph.from_edge_list([(1, 2, 5.0)])
    normalised = graph.normalised_weights("in-degree")
    assert np.isfinite(normalised).all()


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def test_select_by_cell_type(graph):
    epg = graph.select(cell_type="EPG")
    assert len(epg) == 47
    assert all(graph.graph.nodes[n]["cell_type"] == "EPG" for n in epg)


def test_select_by_cell_type_and_side(graph):
    left = graph.select(cell_type="EPG", side="left")
    right = graph.select(cell_type="EPG", side="right")
    assert len(left) + len(right) == 47
    assert set(left).isdisjoint(right)


def test_select_by_root_id(graph):
    target = graph.neuron_ids[0]
    assert graph.select(root_ids=[target]) == [target]


def test_select_rejects_an_unknown_root_id(graph):
    with pytest.raises(KeyError):
        graph.select(root_ids=[1234])


def test_select_rejects_an_unknown_cell_type(graph):
    # Failing loudly matters: a typo silently returning zero neurons would look
    # exactly like a circuit that refuses to activate.
    with pytest.raises(KeyError, match="unknown cell_type"):
        graph.select(cell_type="KenyonCell")


def test_select_rejects_an_empty_match(graph):
    with pytest.raises(KeyError, match="matched no neurons"):
        graph.select(cell_type="EPG", side="middle")


# --------------------------------------------------------------------------- #
# Node attributes the frontend will need
# --------------------------------------------------------------------------- #


def test_nodes_carry_soma_coordinates_and_type(graph):
    for nid in graph.neuron_ids:
        attrs = graph.graph.nodes[nid]
        assert attrs["cell_type"]
        assert attrs["side"] in {"left", "right"}
        assert isinstance(attrs["soma_x"], int)
        assert attrs["polarity"] in {"excitatory", "inhibitory"}
