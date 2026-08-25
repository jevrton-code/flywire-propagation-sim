"""Extract a curated subgraph from the FlyWire v783 connectome.

Run as::

    python -m flywire_data.build_subgraph

which writes ``<circuit>_nodes.csv``, ``<circuit>_edges.csv`` and
``<circuit>_meta.json`` into ``data/subgraphs/``.

Pipeline:

1. Load the Schlegel et al. neuron annotations and keep the neurons whose
   resolved cell type is one of the circuit's types.
2. Load the v783 proofread connection table (one row per pre/post/neuropil
   triple), keep rows where both partners are in the circuit, and aggregate
   synapse counts across neuropils into one edge per ordered neuron pair.
3. Drop pairs below the synapse threshold (5, the threshold used throughout
   Dorkenwald et al. 2024).
4. Sign each edge by the *presynaptic* neuron's predicted transmitter (Dale's
   law, as assumed by the paper).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather

from . import sources
from .circuits import Circuit, get_circuit
from .neurotransmitters import Polarity, polarity_of, primary_known_transmitter
from .provenance import (
    ANNOTATION_RELEASES,
    CITATIONS,
    CONNECTIVITY,
    DEFAULT_ANNOTATION_VERSION,
    LICENSE_NOTES,
    AnnotationRelease,
)

DEFAULT_OUTPUT_DIR = Path("data/subgraphs")

#: Annotation columns copied into the node table.
_NODE_COLUMNS = [
    "root_id",
    "super_class",
    "cell_class",
    "side",
    "soma_x",
    "soma_y",
    "soma_z",
    "top_nt",
    "top_nt_conf",
    "known_nt",
    "known_nt_source",
    "status",
]

_CONN_COLUMNS = ["pre_pt_root_id", "post_pt_root_id", "neuropil", "syn_count"]


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


def resolve_cell_type(frame: pd.DataFrame, release: AnnotationRelease) -> pd.DataFrame:
    """Add ``cell_type_resolved``/``cell_type_source`` columns.

    Annotation releases moved these cell types between columns: in v2.1.0 the
    central-complex types are only in ``hemibrain_type`` (matched to the hemibrain
    dataset), while from v3.0.0 they were promoted into ``cell_type``. We take the
    first non-empty of the release's ``type_columns`` and record which one it came
    from, so the provenance of every label stays visible.
    """
    resolved = pd.Series("", index=frame.index, dtype="string")
    source = pd.Series("", index=frame.index, dtype="string")
    for column in release.type_columns:
        if column not in frame.columns:
            continue
        values = frame[column].fillna("").astype("string").str.strip()
        fill = (resolved == "") & (values != "")
        resolved = resolved.mask(fill, values)
        source = source.mask(fill, column)
    return frame.assign(cell_type_resolved=resolved, cell_type_source=source)


def select_nodes(
    annotations: Path,
    circuit: Circuit,
    release: AnnotationRelease,
    nt_source: str = "predicted",
) -> pd.DataFrame:
    frame = pd.read_csv(annotations, sep="\t", dtype=str, low_memory=False)
    frame = resolve_cell_type(frame, release)

    # Exact match only. hemibrain_type sometimes holds an ambiguous comma-joined
    # list (e.g. "PFNm,PFNp"); those neurons are not unambiguously typed and are
    # intentionally left out rather than split heuristically.
    selected = frame[frame["cell_type_resolved"].isin(circuit.cell_types)].copy()

    missing = set(circuit.cell_types) - set(selected["cell_type_resolved"])
    if missing:
        raise ValueError(
            f"cell types {sorted(missing)} not found in annotations {release.tag}. "
            f"Columns searched: {release.type_columns}."
        )

    nodes = selected[[c for c in _NODE_COLUMNS if c in selected.columns]].copy()
    nodes["cell_type"] = selected["cell_type_resolved"]
    nodes["cell_type_source"] = selected["cell_type_source"]
    nodes["root_id"] = nodes["root_id"].astype("int64")

    # Literature-established transmitter, where the annotators recorded one.
    known = [primary_known_transmitter(v) for v in nodes.get("known_nt", pd.Series(dtype=str))]
    nodes["known_nt_primary"] = pd.Series(known, index=nodes.index, dtype="string")
    nodes["nt_agrees_with_known"] = pd.Series(
        [
            pd.NA if k is None else bool(k == (t or "").strip().lower())
            for k, t in zip(known, nodes["top_nt"])
        ],
        index=nodes.index,
        dtype="boolean",
    )

    if nt_source == "predicted":
        effective = [(nt or "").strip().lower() for nt in nodes["top_nt"]]
    elif nt_source == "known-first":
        effective = [
            k if k is not None else (t or "").strip().lower()
            for k, t in zip(known, nodes["top_nt"])
        ]
    else:  # pragma: no cover - argparse restricts the choices
        raise ValueError(f"unknown nt_source {nt_source!r}")

    nodes["nt_effective"] = effective
    nodes["nt_source"] = nt_source
    polarities = [polarity_of(nt) for nt in effective]
    nodes["sign"] = [int(p) for p in polarities]
    nodes["polarity"] = [p.label for p in polarities]
    nodes["top_nt_conf"] = pd.to_numeric(nodes["top_nt_conf"], errors="coerce")
    for axis in ("soma_x", "soma_y", "soma_z"):
        if axis in nodes.columns:
            nodes[axis] = pd.to_numeric(nodes[axis], errors="coerce").astype("Int64")

    if nodes["root_id"].duplicated().any():
        raise ValueError("duplicate root_id in annotation selection")

    return nodes.sort_values(["cell_type", "root_id"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Edges
# --------------------------------------------------------------------------- #


def select_edges(
    connectivity: Path, nodes: pd.DataFrame, circuit: Circuit
) -> pd.DataFrame:
    root_ids = pa.array(nodes["root_id"].to_numpy(), type=pa.int64())

    table = feather.read_table(connectivity, columns=_CONN_COLUMNS, memory_map=True)
    mask = pc.and_(
        pc.is_in(table["pre_pt_root_id"], value_set=root_ids),
        pc.is_in(table["post_pt_root_id"], value_set=root_ids),
    )
    within = table.filter(mask).to_pandas()
    del table

    # One row per (pre, post, neuropil) -> one row per (pre, post).
    grouped = (
        within.groupby(["pre_pt_root_id", "post_pt_root_id"], sort=True)
        .agg(
            syn_count=("syn_count", "sum"),
            n_neuropils=("neuropil", "nunique"),
            neuropils=("neuropil", lambda s: "|".join(sorted(set(s)))),
        )
        .reset_index()
        .rename(columns={"pre_pt_root_id": "pre_root_id", "post_pt_root_id": "post_root_id"})
    )

    edges = grouped[grouped["syn_count"] >= circuit.synapse_threshold].copy()

    meta = nodes.set_index("root_id")
    edges["pre_type"] = edges["pre_root_id"].map(meta["cell_type"])
    edges["post_type"] = edges["post_root_id"].map(meta["cell_type"])
    edges["sign"] = edges["pre_root_id"].map(meta["sign"]).astype(int)
    edges["polarity"] = edges["pre_root_id"].map(meta["polarity"])
    # Signed weight ready for the simulation: modulatory transmitters contribute
    # nothing, because the paper asserts no sign for them.
    edges["weight"] = edges["sign"] * edges["syn_count"]
    edges["syn_count"] = edges["syn_count"].astype(int)

    if edges.duplicated(["pre_root_id", "post_root_id"]).any():
        raise ValueError("duplicate (pre, post) pair after aggregation")

    columns = [
        "pre_root_id",
        "post_root_id",
        "syn_count",
        "sign",
        "weight",
        "polarity",
        "pre_type",
        "post_type",
        "n_neuropils",
        "neuropils",
    ]
    return edges[columns].sort_values(["pre_root_id", "post_root_id"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #


def build_metadata(
    circuit: Circuit,
    release: AnnotationRelease,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
) -> dict:
    by_polarity = edges["polarity"].value_counts().to_dict()
    orphans = set(nodes["root_id"]) - (
        set(edges["pre_root_id"]) | set(edges["post_root_id"])
    )
    return {
        "circuit": {
            "slug": circuit.slug,
            "title": circuit.title,
            "cell_types": list(circuit.cell_types),
            "synapse_threshold": circuit.synapse_threshold,
            "rationale": circuit.rationale,
            "references": list(circuit.references),
        },
        "sources": {
            "connectivity": asdict(CONNECTIVITY) | {"url": CONNECTIVITY.record_url},
            "annotations": {
                "repo": release.repo,
                "tag": release.tag,
                "path": release.path,
                "published_at": release.published_at,
                "md5": release.md5,
                "url": release.release_url,
                "type_columns_searched": list(release.type_columns),
                "reference": release.reference,
            },
        },
        "licensing": list(LICENSE_NOTES),
        "citations": list(CITATIONS),
        "ei_rule": {
            "excitatory": ["acetylcholine"],
            "inhibitory": ["gaba", "glutamate"],
            "modulatory_weight_zero": ["serotonin", "dopamine", "octopamine"],
            "quote": (
                "As a rule, we assume that cholinergic neurons are excitatory and "
                "GABAergic and glutamatergic neurons are inhibitory."
            ),
            "quote_source": "Dorkenwald et al., Nature 634, 124-138 (2024)",
            "nt_source": str(nodes["nt_source"].iloc[0]),
            "nodes_with_known_nt": int(nodes["known_nt_primary"].notna().sum()),
            "nodes_predicted_disagreeing_with_known": int(
                (nodes["nt_agrees_with_known"] == False).sum()  # noqa: E712
            ),
        },
        "counts": {
            "nodes": int(len(nodes)),
            "edges": int(len(edges)),
            "total_synapses": int(edges["syn_count"].sum()),
            "orphan_nodes": len(orphans),
            "nodes_by_cell_type": nodes["cell_type"].value_counts().sort_index().to_dict(),
            "nodes_by_polarity": nodes["polarity"].value_counts().to_dict(),
            "nodes_by_side": nodes["side"].value_counts().to_dict(),
            "edges_by_polarity": {k: int(v) for k, v in by_polarity.items()},
            "syn_count_min": int(edges["syn_count"].min()),
            "syn_count_max": int(edges["syn_count"].max()),
            "syn_count_median": float(edges["syn_count"].median()),
        },
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "generator": "flywire_data.build_subgraph",
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build(
    circuit: Circuit,
    release: AnnotationRelease,
    output_dir: Path,
    cache: Path | None = None,
    nt_source: str = "predicted",
) -> dict:
    annotations = sources.annotations_path(release, cache)
    print(f"annotations: {annotations}", file=sys.stderr)
    nodes = select_nodes(annotations, circuit, release, nt_source)
    print(f"selected {len(nodes)} neurons", file=sys.stderr)

    connectivity = sources.connectivity_path(cache)
    print(f"connectivity: {connectivity}", file=sys.stderr)
    edges = select_edges(connectivity, nodes, circuit)
    print(
        f"selected {len(edges)} edges at threshold >={circuit.synapse_threshold}",
        file=sys.stderr,
    )

    metadata = build_metadata(circuit, release, nodes, edges)

    output_dir.mkdir(parents=True, exist_ok=True)
    nodes.to_csv(output_dir / f"{circuit.slug}_nodes.csv", index=False)
    edges.to_csv(output_dir / f"{circuit.slug}_edges.csv", index=False)
    (output_dir / f"{circuit.slug}_meta.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--circuit", default="ring_attractor_core")
    parser.add_argument(
        "--annotations-version",
        default=DEFAULT_ANNOTATION_VERSION,
        choices=sorted(ANNOTATION_RELEASES),
        help="Annotation release tag (default: %(default)s, the version reported "
        "on in Schlegel et al. and Dorkenwald et al., Nature 2024).",
    )
    parser.add_argument(
        "--nt-source",
        default="predicted",
        choices=("predicted", "known-first"),
        help="Which neurotransmitter drives the E/I sign. 'predicted' (default) "
        "uses the per-neuron top_nt prediction, as Dorkenwald et al. do. "
        "'known-first' prefers the literature-established known_nt where the "
        "annotators recorded one. Either way both values are kept in the node "
        "table so the choice stays auditable.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help=f"Where raw dumps live (default: $"
        f"{sources.CACHE_DIR_ENV} or {sources.DEFAULT_CACHE_DIR}).",
    )
    args = parser.parse_args(argv)

    metadata = build(
        get_circuit(args.circuit),
        ANNOTATION_RELEASES[args.annotations_version],
        args.output_dir,
        args.cache_dir,
        args.nt_source,
    )
    json.dump(metadata["counts"], sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
