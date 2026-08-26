"""Load the curated FlyWire subgraph into a simulation-ready NetworkX graph.

This module is the boundary between the *data* layer (``flywire_data``, which
produced the CSVs in ``data/subgraphs/``) and the *simulation* layer. It reads
the committed CSVs, applies the simulation's neurotransmitter policy, and hands
back a :class:`SimulationGraph`: a ``networkx.DiGraph`` plus the dense signed
weight matrix the integrator actually iterates on.

Nothing here rewrites the dataset. The CSVs stay exactly as the data pipeline
produced them; the policy below is applied *at load time*, in memory, and is
recorded in the simulation metadata so the choice travels with the output.

Neurotransmitter policy ("known-first")
---------------------------------------
The committed dataset was built with ``--nt-source predicted``, i.e. every
neuron's excitatory/inhibitory sign comes from the automatic per-neuron
neurotransmitter prediction of Eckstein et al. (2024), which is what
Dorkenwald et al. (2024) do. That is the right default for a *dataset*: it
reproduces the published pipeline faithfully.

It is not the right default for the *simulation*. Two of the 153 neurons get a
sign that contradicts the established literature, and both are among the three
lowest-confidence predictions in the whole set -- they rank 1st and 3rd of 153
(see ``data/README.md`` §6.3):

* ``720575940617752537`` (``Delta7``) predicted cholinergic at confidence 0.354,
  literature says glutamate -> should be inhibitory;
* ``720575940626306321`` (``PEN_b(PEN2)``) predicted serotonergic at confidence
  0.402, literature says acetylcholine -> should be excitatory.

Delta7 neurons are the source of the global inhibition that keeps a single
activity bump alive in the ring attractor. Letting one of them be excitatory
because of a coin-flip prediction changes the *architecture* of the circuit
being simulated, not just a weight.

So the simulation prefers the literature-established transmitter
(``known_nt_primary``, present for 150/153 neurons, all attributed to
Turner-Evans et al., *Neuron* 108, 145-163 (2020),
https://doi.org/10.1016/j.neuron.2020.08.006) and falls back to the automatic
prediction only for the 3 neurons with no established transmitter (three
``EPGt``, all predicted cholinergic at confidence 0.89-0.91, consistent with the
fourth ``EPGt`` and with the ``EPG`` population).

Result: all 40 ``Delta7`` inhibitory, all other 113 neurons excitatory, zero
modulatory neurons -- the canonical ring-attractor architecture.

The alternative policy ``"predicted"`` is still available via
``load_graph(nt_policy="predicted")``, and every node keeps both the predicted
and the known transmitter as attributes, so the choice stays auditable.

Simplifications inherited from the data layer
---------------------------------------------
These are properties of the dataset, documented at length in
``data/README.md`` §6.2, and the simulation cannot undo them:

1. Connections below 5 synapses are absent.
2. Dale's law: one sign per neuron, applied to all of its outputs.
3. Synaptic strength is the anatomical synapse count; physiological conductance
   is not measured, and inhibitory synapses are not weighted differently.
4. Synapse counts are summed across neuropils into one edge per neuron pair.
5. The circuit is isolated: all input from outside these 153 neurons
   (e.g. the ``ER`` ring neurons carrying visual landmark information) is absent.
6. The graph carries no conduction delays, no membrane time constants and no
   receptor types -- see :mod:`flywire_sim.model` for what the simulation
   invents on top of it and how that is justified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

import networkx as nx
import numpy as np
import pandas as pd

NtPolicy = Literal["known-first", "predicted"]
Normalisation = Literal["in-degree", "global-max", "none"]

DEFAULT_CIRCUIT = "ring_attractor_core"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "subgraphs"

#: Citation for the literature transmitters used by the "known-first" policy.
KNOWN_NT_REFERENCE = (
    "Turner-Evans, D.B., Jensen, K.T., Ali, S. et al. The neuroanatomical "
    "ultrastructure and function of a biological ring attractor. Neuron 108, "
    "145-163 (2020). https://doi.org/10.1016/j.neuron.2020.08.006"
)

#: Same rule as the data layer, restated here so the simulation does not depend
#: on the sign column that the CSV happens to carry.
_SIGN_BY_TRANSMITTER: Mapping[str, int] = {
    "acetylcholine": 1,
    "gaba": -1,
    "glutamate": -1,
    "serotonin": 0,
    "dopamine": 0,
    "octopamine": 0,
}
_LABEL_BY_SIGN = {1: "excitatory", -1: "inhibitory", 0: "modulatory"}


class UnknownNeurotransmitterError(ValueError):
    """The node table names a transmitter we refuse to assign a sign to."""


def _sign_of(transmitter: str) -> int:
    key = (transmitter or "").strip().lower()
    try:
        return _SIGN_BY_TRANSMITTER[key]
    except KeyError:
        raise UnknownNeurotransmitterError(
            f"unrecognised neurotransmitter {transmitter!r}; expected one of "
            f"{sorted(_SIGN_BY_TRANSMITTER)}. Refusing to guess a sign."
        ) from None


# --------------------------------------------------------------------------- #
# SimulationGraph
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GraphProvenance:
    """Where the graph came from and what was assumed while loading it."""

    circuit: str
    nt_policy: str
    n_neurons: int
    n_connections: int
    n_excitatory_neurons: int
    n_inhibitory_neurons: int
    n_modulatory_neurons: int
    nodes_from_known_nt: int
    nodes_from_predicted_nt: int
    nodes_overridden_vs_dataset: list[int]
    known_nt_reference: str
    dataset_meta: dict

    def to_dict(self) -> dict:
        return {
            "circuit": self.circuit,
            "nt_policy": self.nt_policy,
            "nt_policy_note": (
                "Neuron sign prefers the literature-established transmitter "
                "(known_nt_primary) and falls back to the automatic prediction "
                "(top_nt) only where the literature records none."
                if self.nt_policy == "known-first"
                else "Neuron sign follows the automatic per-neuron "
                "neurotransmitter prediction, as in Dorkenwald et al. (2024)."
            ),
            "known_nt_reference": self.known_nt_reference,
            "n_neurons": self.n_neurons,
            "n_connections": self.n_connections,
            "n_excitatory_neurons": self.n_excitatory_neurons,
            "n_inhibitory_neurons": self.n_inhibitory_neurons,
            "n_modulatory_neurons": self.n_modulatory_neurons,
            "nodes_from_known_nt": self.nodes_from_known_nt,
            "nodes_from_predicted_nt": self.nodes_from_predicted_nt,
            "nodes_overridden_vs_dataset": [str(i) for i in self.nodes_overridden_vs_dataset],
            "dataset": self.dataset_meta,
        }


class SimulationGraph:
    """A directed, signed, weighted graph ready to be integrated.

    Holds three views of the same thing, kept consistent by construction:

    * ``.graph`` -- a ``networkx.DiGraph`` for topology queries and for the
      frontend (node attributes include soma coordinates and cell type);
    * ``.neuron_ids`` -- the canonical node ordering used by every array the
      simulation produces;
    * ``.weights`` -- a dense ``(n, n)`` matrix with ``weights[i, j]`` the signed
      strength of the connection *from* ``neuron_ids[i]`` *to* ``neuron_ids[j]``.

    153 neurons means a 153x153 dense matrix: ~187 KB. Dense is the right call
    at this scale; a sparse representation would only matter for the full
    ~140k-neuron connectome, which the MVP explicitly does not load.
    """

    def __init__(self, graph: nx.DiGraph, provenance: GraphProvenance | None = None):
        self.graph = graph
        self.provenance = provenance
        self.neuron_ids: tuple[int, ...] = tuple(graph.nodes())
        self._index = {node: i for i, node in enumerate(self.neuron_ids)}

        n = len(self.neuron_ids)
        weights = np.zeros((n, n), dtype=np.float64)
        for pre, post, data in graph.edges(data=True):
            weights[self._index[pre], self._index[post]] = float(data["weight"])
        self.weights = weights
        self._normalised: dict[str, np.ndarray] = {}

    # -- basics ------------------------------------------------------------ #

    def __len__(self) -> int:
        return len(self.neuron_ids)

    @property
    def n_neurons(self) -> int:
        return len(self.neuron_ids)

    def index_of(self, neuron_id: int) -> int:
        try:
            return self._index[neuron_id]
        except KeyError:
            raise KeyError(f"neuron {neuron_id!r} is not in this graph") from None

    def indices_of(self, neuron_ids: Iterable[int]) -> np.ndarray:
        return np.array([self.index_of(n) for n in neuron_ids], dtype=int)

    def attribute(self, name: str) -> list:
        return [self.graph.nodes[n].get(name) for n in self.neuron_ids]

    @property
    def signs(self) -> np.ndarray:
        return np.array([self.graph.nodes[n]["sign"] for n in self.neuron_ids], dtype=int)

    # -- selection --------------------------------------------------------- #

    def select(
        self,
        *,
        root_ids: Sequence[int] | None = None,
        cell_type: str | Sequence[str] | None = None,
        side: str | None = None,
    ) -> list[int]:
        """Resolve a user-facing neuron selector to a list of ``root_id``.

        Raises:
            KeyError: if an explicit ``root_id`` is not in the graph, or if a
                ``cell_type``/``side`` filter matches nothing. Silently returning
                an empty selection would make a typo look like a dead circuit.
        """
        selected = list(self.neuron_ids)

        if root_ids is not None:
            missing = [r for r in root_ids if r not in self._index]
            if missing:
                raise KeyError(f"root_ids not in graph: {missing}")
            selected = [r for r in selected if r in set(root_ids)]

        if cell_type is not None:
            wanted = {cell_type} if isinstance(cell_type, str) else set(cell_type)
            available = {self.graph.nodes[n]["cell_type"] for n in self.neuron_ids}
            unknown = wanted - available
            if unknown:
                raise KeyError(
                    f"unknown cell_type(s) {sorted(unknown)}; available: {sorted(available)}"
                )
            selected = [n for n in selected if self.graph.nodes[n]["cell_type"] in wanted]

        if side is not None:
            selected = [n for n in selected if self.graph.nodes[n].get("side") == side]

        if not selected:
            raise KeyError(
                f"selector matched no neurons "
                f"(root_ids={root_ids}, cell_type={cell_type}, side={side})"
            )
        return selected

    # -- weights ----------------------------------------------------------- #

    def normalised_weights(self, mode: Normalisation = "in-degree") -> np.ndarray:
        """Return the weight matrix rescaled for numerically sane integration.

        Raw weights are signed synapse counts (5 to 89 here). Feeding those
        straight into a recurrent update makes the dynamics depend on an
        arbitrary anatomical scale, so we rescale. The mode is an explicit,
        recorded modelling choice, not a hidden constant:

        ``"in-degree"`` (default)
            Divide every incoming weight of a neuron by the total absolute
            incoming weight of that neuron, so ``sum_i |w[i, j]| == 1`` for every
            neuron ``j`` that has inputs. Synaptic drive then means "what
            fraction of this neuron's total synaptic input is active right now",
            which makes the firing threshold interpretable as a fraction and
            bounds the per-step input current to [-1, 1] regardless of how many
            synapses a neuron happens to have.
            Cost, stated plainly: this discards absolute differences in total
            synaptic input between neurons. A neuron with 11 incoming synapses
            becomes as easy to drive as one with 697. That is a deliberate
            trade of biological realism for interpretability and stability; use
            ``"global-max"`` if you want the absolute scale preserved.

        ``"global-max"``
            Divide every weight by the largest absolute weight in the graph, so
            weights land in [-1, 1] but relative strengths across the whole
            circuit are preserved. Total drive onto a neuron is then unbounded
            by construction (bounded in practice by its in-degree), so the
            threshold has to be retuned.

        ``"none"``
            Raw signed synapse counts. Provided for inspection; the default
            parameters will not give sensible dynamics with it.
        """
        if mode in self._normalised:
            return self._normalised[mode]

        if mode == "none":
            out = self.weights.copy()
        elif mode == "global-max":
            peak = np.abs(self.weights).max()
            out = self.weights / peak if peak > 0 else self.weights.copy()
        elif mode == "in-degree":
            incoming = np.abs(self.weights).sum(axis=0)  # total |w| onto each neuron
            safe = np.where(incoming > 0, incoming, 1.0)
            out = self.weights / safe
        else:
            raise ValueError(
                f"unknown weight normalisation {mode!r}; "
                f"expected 'in-degree', 'global-max' or 'none'"
            )

        out = np.ascontiguousarray(out, dtype=np.float64)
        self._normalised[mode] = out
        return out

    # -- construction ------------------------------------------------------ #

    @classmethod
    def from_edge_list(
        cls,
        edges: Iterable[tuple[int, int, float]],
        *,
        node_attributes: Mapping[int, Mapping[str, object]] | None = None,
    ) -> "SimulationGraph":
        """Build a graph directly from ``(pre, post, signed_weight)`` triples.

        Used by tests to exercise the integrator on hand-checkable toy circuits.
        Not a path to fabricate connectome data: production loading always goes
        through :func:`load_graph`.
        """
        graph = nx.DiGraph()
        for pre, post, weight in edges:
            for node in (pre, post):
                if node not in graph:
                    attrs = dict((node_attributes or {}).get(node, {}))
                    attrs.setdefault("cell_type", "synthetic")
                    attrs.setdefault("sign", 0)
                    graph.add_node(node, **attrs)
            graph.add_edge(
                pre,
                post,
                weight=float(weight),
                syn_count=abs(float(weight)),
                sign=int(np.sign(weight)),
            )
        return cls(graph)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _effective_transmitter(row: pd.Series, policy: NtPolicy) -> tuple[str, str]:
    """Return ``(transmitter, source)`` for one neuron under ``policy``."""
    predicted = str(row.get("top_nt") or "").strip().lower()
    known = row.get("known_nt_primary")
    known = None if not isinstance(known, str) or not known.strip() else known.strip().lower()

    if policy == "predicted":
        return predicted, "predicted"
    if policy == "known-first":
        if known is not None:
            return known, "known"
        return predicted, "predicted"
    raise ValueError(f"unknown nt_policy {policy!r}; expected 'known-first' or 'predicted'")


def build_graph(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    *,
    nt_policy: NtPolicy = "known-first",
    circuit: str = DEFAULT_CIRCUIT,
    dataset_meta: dict | None = None,
) -> SimulationGraph:
    """Assemble a :class:`SimulationGraph` from the node/edge tables.

    Edge signs are **recomputed** from the presynaptic neuron's effective
    transmitter rather than read from the CSV's ``sign`` column, because the CSV
    was written under the dataset's own policy. Recomputing keeps the graph
    internally consistent under either policy (Dale's law: one sign per neuron,
    applied to all of its outputs -- an assumption inherited from the data layer,
    see ``data/README.md`` §6.2).
    """
    nodes = nodes.copy()
    nodes["root_id"] = nodes["root_id"].astype("int64")

    graph = nx.DiGraph()
    n_from_known = 0
    overridden: list[int] = []

    for _, row in nodes.iterrows():
        transmitter, source = _effective_transmitter(row, nt_policy)
        sign = _sign_of(transmitter)
        n_from_known += source == "known"

        dataset_sign = int(row["sign"]) if "sign" in row and pd.notna(row["sign"]) else None
        if dataset_sign is not None and dataset_sign != sign:
            overridden.append(int(row["root_id"]))

        graph.add_node(
            int(row["root_id"]),
            cell_type=row.get("cell_type"),
            side=row.get("side"),
            soma_x=None if pd.isna(row.get("soma_x")) else int(row["soma_x"]),
            soma_y=None if pd.isna(row.get("soma_y")) else int(row["soma_y"]),
            soma_z=None if pd.isna(row.get("soma_z")) else int(row["soma_z"]),
            top_nt=row.get("top_nt"),
            top_nt_conf=float(row["top_nt_conf"]) if pd.notna(row.get("top_nt_conf")) else None,
            known_nt_primary=(
                row.get("known_nt_primary")
                if isinstance(row.get("known_nt_primary"), str)
                else None
            ),
            nt_effective=transmitter,
            nt_source=source,
            sign=sign,
            polarity=_LABEL_BY_SIGN[sign],
            dataset_sign=dataset_sign,
        )

    known_nodes = set(graph.nodes())
    stray = (set(edges["pre_root_id"]) | set(edges["post_root_id"])) - known_nodes
    if stray:
        raise ValueError(
            f"{len(stray)} edge endpoint(s) are not in the node table, e.g. "
            f"{sorted(stray)[:3]}; refusing to build a graph with dangling edges"
        )

    for _, row in edges.iterrows():
        pre = int(row["pre_root_id"])
        post = int(row["post_root_id"])
        syn_count = int(row["syn_count"])
        sign = graph.nodes[pre]["sign"]
        graph.add_edge(
            pre,
            post,
            syn_count=syn_count,
            sign=sign,
            weight=float(sign * syn_count),
            polarity=_LABEL_BY_SIGN[sign],
            pre_type=graph.nodes[pre]["cell_type"],
            post_type=graph.nodes[post]["cell_type"],
            neuropils=row.get("neuropils"),
            n_neuropils=int(row["n_neuropils"]) if pd.notna(row.get("n_neuropils")) else None,
        )

    signs = [graph.nodes[n]["sign"] for n in graph.nodes()]
    provenance = GraphProvenance(
        circuit=circuit,
        nt_policy=nt_policy,
        n_neurons=graph.number_of_nodes(),
        n_connections=graph.number_of_edges(),
        n_excitatory_neurons=sum(s > 0 for s in signs),
        n_inhibitory_neurons=sum(s < 0 for s in signs),
        n_modulatory_neurons=sum(s == 0 for s in signs),
        nodes_from_known_nt=n_from_known,
        nodes_from_predicted_nt=graph.number_of_nodes() - n_from_known,
        nodes_overridden_vs_dataset=overridden,
        known_nt_reference=KNOWN_NT_REFERENCE,
        dataset_meta=dataset_meta or {},
    )
    return SimulationGraph(graph, provenance)


def load_graph(
    circuit: str = DEFAULT_CIRCUIT,
    *,
    data_dir: Path | str | None = None,
    nt_policy: NtPolicy = "known-first",
) -> SimulationGraph:
    """Read ``<circuit>_{nodes,edges}.csv`` from ``data_dir`` and build the graph.

    Args:
        circuit: slug of the committed subgraph (default ``ring_attractor_core``).
        data_dir: directory holding the CSVs (default ``data/subgraphs/``).
        nt_policy: ``"known-first"`` (default, see module docstring) or
            ``"predicted"`` to reproduce the dataset's own signs.
    """
    directory = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    nodes_path = directory / f"{circuit}_nodes.csv"
    edges_path = directory / f"{circuit}_edges.csv"
    meta_path = directory / f"{circuit}_meta.json"

    for path in (nodes_path, edges_path):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Build it first with "
                f"`python -m flywire_data.build_subgraph --circuit {circuit}`."
            )

    nodes = pd.read_csv(nodes_path)
    edges = pd.read_csv(edges_path)

    dataset_meta: dict = {}
    if meta_path.exists():
        full = json.loads(meta_path.read_text(encoding="utf-8"))
        # Keep the provenance that matters downstream, not the whole blob.
        dataset_meta = {
            "circuit_title": full.get("circuit", {}).get("title"),
            "synapse_threshold": full.get("circuit", {}).get("synapse_threshold"),
            "connectivity": full.get("sources", {}).get("connectivity", {}),
            "annotations": full.get("sources", {}).get("annotations", {}),
            "citations": full.get("citations", []),
            "licensing": full.get("licensing", []),
            "dataset_nt_source": full.get("ei_rule", {}).get("nt_source"),
        }

    return build_graph(
        nodes,
        edges,
        nt_policy=nt_policy,
        circuit=circuit,
        dataset_meta=dataset_meta,
    )
