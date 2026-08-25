"""Loading, caching and JSON-shaping of the connectome subgraph.

The API never rebuilds or reinterprets the connectome: it calls
:func:`flywire_sim.graph.load_graph` and reads node/edge attributes off the
resulting :class:`~flywire_sim.graph.SimulationGraph`. Everything in this module
is presentation-neutral packaging -- ordering, JSON-safe types, degree counts --
not modelling.

Two things worth knowing:

* **Loading is cached per (circuit, nt_policy).** Reading and assembling the
  CSVs takes long enough that doing it per request would be silly, and the
  resulting graph is immutable in practice. The cache is keyed on ``nt_policy``
  too, because that flag changes the sign of two neurons and therefore the
  circuit's architecture (see :mod:`flywire_sim.graph`).
* **The circuit slug is validated against the files that actually exist**
  before it reaches ``load_graph``, which interpolates it into a path. Rejecting
  unknown slugs up front keeps a user-supplied string out of filesystem path
  construction, and gives a 404 that lists the real options instead of a
  ``FileNotFoundError``.
"""

from __future__ import annotations

import threading
from functools import cached_property
from pathlib import Path
from typing import Any

from flywire_sim.graph import DEFAULT_CIRCUIT, DEFAULT_DATA_DIR, SimulationGraph, load_graph
from flywire_sim.model import SIMPLIFICATIONS, LIFParameters

from .errors import not_found

#: Soma coordinates in the node table are FlyWire voxel coordinates, not
#: nanometres. Shipping the conversion factor means the frontend can lay neurons
#: out in physical space without hardcoding a magic number.
COORDINATE_SPACE = {
    "space": "FlyWire (FAFB v14.1) voxel coordinates",
    "voxel_size_nm": [4, 4, 40],
    "note": (
        "Multiply x, y, z by voxel_size_nm to get nanometres. Coordinates are "
        "soma positions from the FlyWire annotation release; they are a "
        "biologically meaningful 3D layout, not a graph-drawing layout."
    ),
}

DISCLAIMER = (
    "Real connectivity (FlyWire v783), toy dynamics. This model shows how activity can "
    "spread through the measured wiring; it is not calibrated against physiological "
    "recordings and does not predict what real neurons do."
)


def available_circuits(data_dir: Path | str | None = None) -> list[str]:
    """Slugs of every subgraph with a committed node table."""
    directory = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    if not directory.is_dir():
        return []
    return sorted(p.name[: -len("_nodes.csv")] for p in directory.glob("*_nodes.csv"))


class LoadedCircuit:
    """A loaded :class:`SimulationGraph` plus its JSON payloads, computed once."""

    def __init__(self, circuit: str, nt_policy: str, graph: SimulationGraph):
        self.circuit = circuit
        self.nt_policy = nt_policy
        self.graph = graph

    # -- neurons ----------------------------------------------------------- #

    @cached_property
    def neurons(self) -> list[dict[str, Any]]:
        """One dict per neuron, in the canonical array ordering.

        ``index`` is the position of this neuron in every per-neuron array the
        simulation streams. The frontend should key its rendering on it and use
        ``root_id`` (a string) only for display and for building requests.
        """
        graph = self.graph.graph
        out = []
        for index, node_id in enumerate(self.graph.neuron_ids):
            attrs = graph.nodes[node_id]
            out.append(
                {
                    "index": index,
                    "root_id": str(node_id),
                    "cell_type": attrs.get("cell_type"),
                    "side": attrs.get("side"),
                    "sign": int(attrs["sign"]),
                    "polarity": attrs.get("polarity"),
                    "neurotransmitter": attrs.get("nt_effective"),
                    "neurotransmitter_source": attrs.get("nt_source"),
                    "position": {
                        "x": attrs.get("soma_x"),
                        "y": attrs.get("soma_y"),
                        "z": attrs.get("soma_z"),
                    },
                    "in_degree": int(graph.in_degree(node_id)),
                    "out_degree": int(graph.out_degree(node_id)),
                    "in_synapses": int(
                        sum(d["syn_count"] for _, _, d in graph.in_edges(node_id, data=True))
                    ),
                    "out_synapses": int(
                        sum(d["syn_count"] for _, _, d in graph.out_edges(node_id, data=True))
                    ),
                }
            )
        return out

    # -- edges ------------------------------------------------------------- #

    @cached_property
    def edges(self) -> list[dict[str, Any]]:
        """One dict per connection, with both endpoints as string ids and indices.

        ``normalised_weight`` is the default ``"in-degree"`` normalisation the
        simulation uses (``flywire_sim.graph.SimulationGraph.normalised_weights``),
        exposed so the frontend can size edges by the strength the model actually
        integrates rather than by raw synapse count. If a run overrides
        ``weight_normalisation``, this value no longer matches what that run used.
        """
        normalised = self.graph.normalised_weights("in-degree")
        index_of = {node: i for i, node in enumerate(self.graph.neuron_ids)}
        out = []
        for pre, post, data in self.graph.graph.edges(data=True):
            i, j = index_of[pre], index_of[post]
            out.append(
                {
                    "pre_root_id": str(pre),
                    "post_root_id": str(post),
                    "pre_index": i,
                    "post_index": j,
                    "syn_count": int(data["syn_count"]),
                    "sign": int(data["sign"]),
                    "weight": float(data["weight"]),
                    "normalised_weight": round(float(normalised[i, j]), 6),
                    "polarity": data.get("polarity"),
                    "pre_type": data.get("pre_type"),
                    "post_type": data.get("post_type"),
                    "neuropils": data.get("neuropils"),
                }
            )
        return out

    # -- stimulus options --------------------------------------------------- #

    @cached_property
    def cell_types(self) -> list[dict[str, Any]]:
        """Selectable cell types, with enough counts to build a source picker."""
        buckets: dict[str, dict[str, Any]] = {}
        for neuron in self.neurons:
            cell_type = neuron["cell_type"]
            bucket = buckets.setdefault(
                cell_type,
                {
                    "cell_type": cell_type,
                    "count": 0,
                    "count_by_side": {},
                    "polarities": set(),
                    "root_ids": [],
                },
            )
            bucket["count"] += 1
            side = neuron["side"] or "unknown"
            bucket["count_by_side"][side] = bucket["count_by_side"].get(side, 0) + 1
            bucket["polarities"].add(neuron["polarity"])
            bucket["root_ids"].append(neuron["root_id"])

        out = []
        for cell_type in sorted(buckets):
            bucket = buckets[cell_type]
            polarities = sorted(bucket["polarities"])
            out.append(
                {
                    "cell_type": cell_type,
                    "count": bucket["count"],
                    "count_by_side": dict(sorted(bucket["count_by_side"].items())),
                    "polarity": polarities[0] if len(polarities) == 1 else "mixed",
                    "root_ids": bucket["root_ids"],
                }
            )
        return out

    @cached_property
    def sides(self) -> list[str]:
        return sorted({n["side"] for n in self.neurons if n["side"]})

    # -- metadata ----------------------------------------------------------- #

    @cached_property
    def provenance(self) -> dict[str, Any]:
        prov = self.graph.provenance
        return prov.to_dict() if prov is not None else {}

    @cached_property
    def summary(self) -> dict[str, Any]:
        prov = self.provenance
        dataset = prov.get("dataset", {})
        return {
            "circuit": self.circuit,
            "title": dataset.get("circuit_title"),
            "nt_policy": self.nt_policy,
            "nt_policy_note": prov.get("nt_policy_note"),
            "n_neurons": self.graph.n_neurons,
            "n_connections": self.graph.graph.number_of_edges(),
            "n_synapses": int(sum(e["syn_count"] for e in self.edges)),
            "n_excitatory_neurons": prov.get("n_excitatory_neurons"),
            "n_inhibitory_neurons": prov.get("n_inhibitory_neurons"),
            "n_modulatory_neurons": prov.get("n_modulatory_neurons"),
            "cell_types": [c["cell_type"] for c in self.cell_types],
            "sides": self.sides,
            "coordinate_space": COORDINATE_SPACE,
            "synapse_threshold": dataset.get("synapse_threshold"),
            "citations": dataset.get("citations", []),
            "licensing": dataset.get("licensing", []),
            "simplifications": list(SIMPLIFICATIONS),
            "disclaimer": DISCLAIMER,
        }


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


class CircuitRegistry:
    """Thread-safe cache of loaded circuits, keyed by ``(circuit, nt_policy)``."""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
        self._cache: dict[tuple[str, str], LoadedCircuit] = {}
        self._lock = threading.Lock()

    def available(self) -> list[str]:
        return available_circuits(self.data_dir)

    def get(self, circuit: str = DEFAULT_CIRCUIT, nt_policy: str = "known-first") -> LoadedCircuit:
        """Return a cached circuit, loading it on first use.

        Raises:
            ApiError: 404 if the slug is not one of the committed subgraphs.
        """
        key = (circuit, nt_policy)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        options = self.available()
        if circuit not in options:
            raise not_found(
                "unknown_circuit",
                f"unknown circuit {circuit!r}; available: {options}",
                requested=circuit,
                available=options,
            )

        with self._lock:
            cached = self._cache.get(key)
            if cached is None:
                graph = load_graph(circuit, data_dir=self.data_dir, nt_policy=nt_policy)
                cached = LoadedCircuit(circuit, nt_policy, graph)
                self._cache[key] = cached
        return cached

    def warm(self, circuit: str = DEFAULT_CIRCUIT, nt_policy: str = "known-first") -> None:
        """Load and pre-compute payloads so the first request is not the slow one."""
        loaded = self.get(circuit, nt_policy)
        _ = loaded.neurons, loaded.edges, loaded.cell_types, loaded.summary

    @property
    def loaded_keys(self) -> list[str]:
        return sorted(f"{c}:{p}" for c, p in self._cache)


def model_defaults() -> dict[str, Any]:
    """Default LIF parameters, as a dict, straight from the simulation package."""
    return LIFParameters().to_dict()
