"""Integrity checks for the curated ring-attractor subgraph in ``data/subgraphs/``.

These tests validate the *committed artefact*, not the extraction code path, so
they run in CI without the 852 MB raw dump. They are deliberately strict: if a
future rebuild silently changes the graph, these fail.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from flywire_data.circuits import RING_ATTRACTOR_CORE
from flywire_data.neurotransmitters import (
    MODULATORY_TRANSMITTERS,
    SIGNED_TRANSMITTERS,
    Polarity,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "subgraphs"
SLUG = RING_ATTRACTOR_CORE.slug

# Expected counts for annotations v2.1.0 + connectivity v783 at threshold >= 5.
EXPECTED_NODES = 153
EXPECTED_EDGES = 2695
EXPECTED_NODES_BY_TYPE = {
    "Delta7": 40,
    "EPG": 47,
    "EPGt": 4,
    "PEG": 20,
    "PEN_a(PEN1)": 20,
    "PEN_b(PEN2)": 22,
}


@pytest.fixture(scope="module")
def nodes() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{SLUG}_nodes.csv")


@pytest.fixture(scope="module")
def edges() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{SLUG}_edges.csv")


@pytest.fixture(scope="module")
def meta() -> dict:
    return json.loads((DATA_DIR / f"{SLUG}_meta.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #


def test_node_count_matches_expectation(nodes):
    assert len(nodes) == EXPECTED_NODES


def test_node_count_is_tractable_for_interactive_simulation(nodes):
    # The MVP constraint: dozens to a few hundred neurons, not the full 140k graph.
    assert 50 <= len(nodes) <= 500


def test_edge_count_matches_expectation(edges):
    assert len(edges) == EXPECTED_EDGES


def test_nodes_per_cell_type(nodes):
    assert nodes["cell_type"].value_counts().sort_index().to_dict() == EXPECTED_NODES_BY_TYPE


def test_only_requested_cell_types_present(nodes):
    assert set(nodes["cell_type"]) == set(RING_ATTRACTOR_CORE.cell_types)


def test_both_hemispheres_represented(nodes):
    # A ring attractor spans both hemispheres; a one-sided graph would mean the
    # side filter or the type match went wrong.
    sides = nodes["side"].value_counts()
    assert set(sides.index) >= {"left", "right"}
    assert sides.min() >= 0.4 * sides.max()


# --------------------------------------------------------------------------- #
# Referential integrity
# --------------------------------------------------------------------------- #


def test_root_ids_are_unique(nodes):
    assert not nodes["root_id"].duplicated().any()


def test_root_ids_look_like_flywire_ids(nodes):
    # FlyWire 783 root IDs are 18-digit int64 values.
    assert nodes["root_id"].dtype.kind == "i"
    assert nodes["root_id"].astype(str).str.len().eq(18).all()


def test_no_duplicate_edges(edges):
    assert not edges.duplicated(["pre_root_id", "post_root_id"]).any()


def test_no_self_loops(edges):
    assert not (edges["pre_root_id"] == edges["post_root_id"]).any()


def test_all_edge_endpoints_are_known_nodes(nodes, edges):
    known = set(nodes["root_id"])
    assert set(edges["pre_root_id"]) <= known
    assert set(edges["post_root_id"]) <= known


def test_no_orphan_nodes(nodes, edges):
    connected = set(edges["pre_root_id"]) | set(edges["post_root_id"])
    assert set(nodes["root_id"]) - connected == set()


def test_graph_is_recurrent(edges):
    # The scientific point of choosing this circuit: it must actually be
    # recurrent, otherwise propagation is a trivial feed-forward cascade.
    forward = set(zip(edges["pre_root_id"], edges["post_root_id"]))
    reciprocal = {(a, b) for a, b in forward if (b, a) in forward}
    assert len(reciprocal) > 0.2 * len(forward)


# --------------------------------------------------------------------------- #
# Weights
# --------------------------------------------------------------------------- #


def test_every_edge_meets_synapse_threshold(edges):
    assert edges["syn_count"].min() >= RING_ATTRACTOR_CORE.synapse_threshold


def test_synapse_counts_are_positive_integers(edges):
    assert edges["syn_count"].dtype.kind == "i"
    assert (edges["syn_count"] > 0).all()


def test_synapse_counts_are_in_a_plausible_range(edges):
    # Dorkenwald et al. report the strongest connection in the whole brain at
    # ~2,400 synapses; anything beyond that would indicate a bad aggregation.
    assert edges["syn_count"].max() <= 2500


def test_signed_weight_is_consistent(edges):
    assert (edges["weight"] == edges["sign"] * edges["syn_count"]).all()


def test_modulatory_edges_carry_zero_weight(edges):
    modulatory = edges[edges["polarity"] == "modulatory"]
    assert (modulatory["weight"] == 0).all()


# --------------------------------------------------------------------------- #
# Excitatory / inhibitory assignment
# --------------------------------------------------------------------------- #


def test_every_node_has_a_polarity(nodes):
    assert nodes["polarity"].notna().all()
    assert set(nodes["polarity"]) <= {p.label for p in Polarity}


def test_sign_matches_polarity_label(nodes):
    expected = {"excitatory": 1, "inhibitory": -1, "modulatory": 0}
    assert (nodes["polarity"].map(expected) == nodes["sign"]).all()


def test_polarity_follows_the_paper_rule(nodes):
    for nt, polarity in SIGNED_TRANSMITTERS.items():
        subset = nodes[nodes["nt_effective"] == nt]
        assert (subset["sign"] == int(polarity)).all(), nt
    modulatory = nodes[nodes["nt_effective"].isin(MODULATORY_TRANSMITTERS)]
    assert (modulatory["sign"] == 0).all()


def test_edge_sign_comes_from_the_presynaptic_neuron(nodes, edges):
    sign_by_node = nodes.set_index("root_id")["sign"]
    assert (edges["pre_root_id"].map(sign_by_node) == edges["sign"]).all()


def test_edge_types_match_node_types(nodes, edges):
    type_by_node = nodes.set_index("root_id")["cell_type"]
    assert (edges["pre_root_id"].map(type_by_node) == edges["pre_type"]).all()
    assert (edges["post_root_id"].map(type_by_node) == edges["post_type"]).all()


def test_delta7_is_inhibitory(nodes):
    # Delta7 provides the global inhibition of the ring attractor
    # (Turner-Evans et al. 2020). A build that makes them excitatory is broken.
    delta7 = nodes[nodes["cell_type"] == "Delta7"]
    assert (delta7["sign"] == -1).mean() > 0.95


def test_epg_and_pen_are_excitatory(nodes):
    excitatory_types = ["EPG", "EPGt", "PEG", "PEN_a(PEN1)", "PEN_b(PEN2)"]
    subset = nodes[nodes["cell_type"].isin(excitatory_types)]
    assert (subset["sign"] == 1).mean() > 0.95


def test_predictions_largely_agree_with_literature(nodes):
    agree = nodes["nt_agrees_with_known"].dropna()
    assert len(agree) >= 0.9 * len(nodes)
    assert agree.mean() > 0.95


def test_disagreements_are_low_confidence(nodes):
    """Where top_nt contradicts the literature, it should be a weak prediction."""
    disagreeing = nodes[nodes["nt_agrees_with_known"] == False]  # noqa: E712
    agreeing = nodes[nodes["nt_agrees_with_known"] == True]  # noqa: E712
    if disagreeing.empty:
        pytest.skip("no disagreements in this build")
    assert disagreeing["top_nt_conf"].max() < agreeing["top_nt_conf"].median()


# --------------------------------------------------------------------------- #
# Missing / corrupt data
# --------------------------------------------------------------------------- #


REQUIRED_NODE_FIELDS = [
    "root_id",
    "cell_type",
    "cell_type_source",
    "side",
    "top_nt",
    "top_nt_conf",
    "nt_effective",
    "sign",
    "polarity",
]
REQUIRED_EDGE_FIELDS = [
    "pre_root_id",
    "post_root_id",
    "syn_count",
    "sign",
    "weight",
    "polarity",
    "pre_type",
    "post_type",
    "neuropils",
]


@pytest.mark.parametrize("column", REQUIRED_NODE_FIELDS)
def test_required_node_columns_have_no_nulls(nodes, column):
    assert column in nodes.columns
    assert nodes[column].notna().all()


@pytest.mark.parametrize("column", REQUIRED_EDGE_FIELDS)
def test_required_edge_columns_have_no_nulls(edges, column):
    assert column in edges.columns
    assert edges[column].notna().all()


def test_confidences_are_probabilities(nodes):
    assert nodes["top_nt_conf"].between(0.0, 1.0).all()


def test_no_neuron_is_flagged_as_a_segmentation_outlier(nodes):
    # `status` flags outlier_seg / outlier_bio neurons; all of ours should be clean.
    if "status" not in nodes.columns:
        pytest.skip("status column absent")
    assert nodes["status"].dropna().empty


def test_neuropils_are_plausible_for_this_circuit(edges):
    seen = {p for entry in edges["neuropils"] for p in entry.split("|")}
    # The head-direction circuit lives in the protocerebral bridge, ellipsoid
    # body, noduli and gall.
    core = {"PB", "EB", "NO", "GA_L", "GA_R"}
    assert core <= seen
    assert edges["n_neuropils"].min() >= 1


# --------------------------------------------------------------------------- #
# Metadata / provenance
# --------------------------------------------------------------------------- #


def test_metadata_counts_match_the_tables(meta, nodes, edges):
    assert meta["counts"]["nodes"] == len(nodes)
    assert meta["counts"]["edges"] == len(edges)
    assert meta["counts"]["total_synapses"] == int(edges["syn_count"].sum())
    assert meta["counts"]["orphan_nodes"] == 0
    assert math.isclose(meta["counts"]["syn_count_median"], edges["syn_count"].median())


def test_metadata_records_provenance(meta):
    connectivity = meta["sources"]["connectivity"]
    assert connectivity["doi"] == "10.5281/zenodo.10676866"
    assert connectivity["version"] == "783.0"
    assert connectivity["md5"] == "f48f972d262323a102aed49af1396b8a"
    assert connectivity["license"] == "CC-BY-4.0"

    annotations = meta["sources"]["annotations"]
    assert annotations["repo"] == "flyconnectome/flywire_annotations"
    assert annotations["tag"] == "v2.1.0"

    assert meta["circuit"]["synapse_threshold"] == RING_ATTRACTOR_CORE.synapse_threshold
    assert any("CC-BY-NC 4.0" in note for note in meta["licensing"])
    assert meta["citations"]
