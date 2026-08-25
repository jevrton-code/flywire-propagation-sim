"""REST endpoints: static circuit data, model metadata, and a non-streaming run.

The split of responsibility with the WebSocket is deliberate. Everything the
frontend needs *before* a simulation exists -- the node list, the edge list, the
provenance, the parameter defaults -- is a plain cacheable GET here. The
WebSocket carries only the time-varying part.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Query

from flywire_sim.graph import DEFAULT_CIRCUIT
from flywire_sim.model import SIMPLIFICATIONS

from .circuits import DISCLAIMER, LoadedCircuit, model_defaults
from .deps import CircuitDep, RegistryDep, SlotsDep
from .schemas import (
    MAX_AMPLITUDE,
    MAX_SOURCE_ROOT_IDS,
    MAX_STEPS,
    CellTypeListResponse,
    CircuitSummary,
    EdgeListResponse,
    GraphResponse,
    HealthResponse,
    ModelDefaultsResponse,
    NeuronListResponse,
    ProvenanceResponse,
    SimulationRequest,
    SimulationResponse,
)
from .service import RunSession, prepare_run, strongest_source_root_id

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health(registry: RegistryDep) -> dict[str, Any]:
    """Liveness check, plus which subgraphs exist and which are already loaded."""
    return {
        "status": "ok",
        "default_circuit": DEFAULT_CIRCUIT,
        "available_circuits": registry.available(),
        "loaded": registry.loaded_keys,
    }


# --------------------------------------------------------------------------- #
# Circuit
# --------------------------------------------------------------------------- #


@router.get("/circuit", response_model=CircuitSummary, tags=["circuit"])
async def circuit_summary(registry: RegistryDep, params: CircuitDep) -> dict[str, Any]:
    """Counts, citations and the honesty block for the loaded subgraph.

    ``simplifications`` and ``disclaimer`` come straight from
    ``flywire_sim.model.SIMPLIFICATIONS``. They are part of the contract: a
    client that renders this data is expected to show them, not to filter them
    out. The wiring is real FlyWire v783 connectivity; the dynamics are a
    caricature, and the API says so in every place it can.
    """
    return registry.get(params.circuit, params.nt_policy).summary


@router.get("/circuit/neurons", response_model=NeuronListResponse, tags=["circuit"])
async def list_neurons(
    registry: RegistryDep,
    params: CircuitDep,
    cell_type: Annotated[
        list[str] | None, Query(description="Filter by cell type; repeatable.")
    ] = None,
    side: Annotated[str | None, Query(description="Filter by hemisphere.")] = None,
) -> dict[str, Any]:
    """Every neuron in the subgraph, in the canonical array ordering.

    ``index`` is the position of the neuron in every per-neuron array streamed by
    the simulation; ``root_id`` is a **string** because an 18-digit FlyWire id
    does not survive a JavaScript ``Number``. ``position`` is the real soma
    location in FlyWire voxel space -- a physical layout, not a graph layout.

    The filters are for building pickers; they do not change ``index``, which
    always refers to the full circuit.
    """
    circuit = registry.get(params.circuit, params.nt_policy)
    neurons = circuit.neurons
    if cell_type:
        wanted = set(cell_type)
        neurons = [n for n in neurons if n["cell_type"] in wanted]
    if side:
        neurons = [n for n in neurons if n["side"] == side]
    return {
        "circuit": circuit.circuit,
        "nt_policy": circuit.nt_policy,
        "n_neurons": len(neurons),
        "coordinate_space": circuit.summary["coordinate_space"],
        "neurons": neurons,
    }


@router.get("/circuit/edges", response_model=EdgeListResponse, tags=["circuit"])
async def list_edges(
    registry: RegistryDep,
    params: CircuitDep,
    min_syn_count: Annotated[
        int,
        Query(
            ge=0,
            description=(
                "Drop connections weaker than this many synapses. The dataset "
                "already applies a 5-synapse floor; raising it further thins a "
                "dense graph for rendering."
            ),
        ),
    ] = 0,
) -> dict[str, Any]:
    """Every connection, with both raw synapse counts and normalised weights."""
    circuit = registry.get(params.circuit, params.nt_policy)
    edges = circuit.edges
    if min_syn_count:
        edges = [e for e in edges if e["syn_count"] >= min_syn_count]
    return {
        "circuit": circuit.circuit,
        "nt_policy": circuit.nt_policy,
        "n_connections": len(edges),
        "weight_normalisation": "in-degree",
        "edges": edges,
    }


@router.get("/circuit/graph", response_model=GraphResponse, tags=["circuit"])
async def circuit_graph(registry: RegistryDep, params: CircuitDep) -> dict[str, Any]:
    """Summary + neurons + edges in one response, to draw the static graph.

    Convenience only: identical to calling ``/api/circuit``,
    ``/api/circuit/neurons`` and ``/api/circuit/edges`` and stitching the three
    together. For this circuit the whole payload is a few hundred kilobytes.
    """
    circuit = registry.get(params.circuit, params.nt_policy)
    return {
        "summary": circuit.summary,
        "neurons": circuit.neurons,
        "edges": circuit.edges,
    }


@router.get("/circuit/cell-types", response_model=CellTypeListResponse, tags=["circuit"])
async def list_cell_types(registry: RegistryDep, params: CircuitDep) -> dict[str, Any]:
    """Stimulus options: the cell types, the hemispheres, and a few presets.

    Presets are starting points for a source picker, not recommendations about
    biology. Each one is a ``source`` object that can be posted back verbatim.
    """
    circuit = registry.get(params.circuit, params.nt_policy)
    return {
        "circuit": circuit.circuit,
        "nt_policy": circuit.nt_policy,
        "cell_types": circuit.cell_types,
        "sides": circuit.sides,
        "presets": _presets(circuit),
    }


def _presets(circuit: LoadedCircuit) -> list[dict[str, Any]]:
    """Source selections worth offering first, derived from the loaded graph.

    Nothing here is hardcoded against a specific dataset build: each preset is
    only emitted if the cell type is actually present, and the single-neuron
    preset resolves the strongest source at load time.
    """
    available = {c["cell_type"] for c in circuit.cell_types}
    presets: list[dict[str, Any]] = []

    if "EPG" in available:
        presets.append(
            {
                "id": "epg_left",
                "label": "EPG population (left hemisphere)",
                "description": (
                    "The neurons that carry the head-direction bump, one hemisphere "
                    "only. The largest stimulus offered here; with default "
                    "parameters it recruits most of the circuit."
                ),
                "source": {"cell_types": ["EPG"], "side": "left"},
            }
        )
        strongest = strongest_source_root_id(circuit, "EPG")
        if strongest is not None:
            presets.append(
                {
                    "id": "epg_single",
                    "label": "A single EPG neuron",
                    "description": (
                        "The EPG neuron with the largest total outgoing weight in "
                        "this subgraph. A much weaker stimulus: under in-degree "
                        "normalisation one presynaptic partner is a small fraction "
                        "of a target's input, so most of the circuit stays silent."
                    ),
                    "source": {"root_ids": [strongest]},
                }
            )
    if "Delta7" in available:
        presets.append(
            {
                "id": "delta7",
                "label": "Delta7 population (inhibitory)",
                "description": (
                    "The circuit's inhibitory population. Stimulating it drives "
                    "the rest of the network negative instead of recruiting it."
                ),
                "source": {"cell_types": ["Delta7"]},
            }
        )
    return presets


@router.get("/circuit/provenance", response_model=ProvenanceResponse, tags=["circuit"])
async def circuit_provenance(registry: RegistryDep, params: CircuitDep) -> dict[str, Any]:
    """Where the data came from: dataset version, DOIs, licences, citations.

    This is what lets a frontend claim "real connectome data" and back it up
    with a link. The block is passed through from the data layer's metadata
    file; the API does not summarise or edit it.
    """
    circuit = registry.get(params.circuit, params.nt_policy)
    summary = circuit.summary
    return {
        "circuit": circuit.circuit,
        "nt_policy": circuit.nt_policy,
        "provenance": circuit.provenance,
        "citations": summary["citations"],
        "licensing": summary["licensing"],
        "simplifications": summary["simplifications"],
        "disclaimer": summary["disclaimer"],
    }


# --------------------------------------------------------------------------- #
# Model metadata
# --------------------------------------------------------------------------- #


@router.get("/model/defaults", response_model=ModelDefaultsResponse, tags=["simulation"])
async def model_parameter_defaults(slots: SlotsDep) -> dict[str, Any]:
    """Default LIF parameters and the hard limits a request must respect.

    The defaults are engineering choices tuned for legible dynamics on this
    graph, not biological measurements -- ``parameters.units`` says as much.
    """
    return {
        "parameters": model_defaults(),
        "limits": {
            "max_steps": MAX_STEPS,
            "max_source_root_ids": MAX_SOURCE_ROOT_IDS,
            "max_amplitude": MAX_AMPLITUDE,
            "max_concurrent_simulations": slots.limit,
        },
        "simplifications": list(SIMPLIFICATIONS),
        "disclaimer": DISCLAIMER,
    }


# --------------------------------------------------------------------------- #
# Simulation (non-streaming)
# --------------------------------------------------------------------------- #


@router.post(
    "/simulations",
    response_model=SimulationResponse,
    tags=["simulation"],
    responses={
        404: {"description": "Unknown circuit, root_id or cell type."},
        422: {"description": "The request is well-formed JSON but not a runnable request."},
        503: {"description": "Too many simulations already running."},
    },
)
async def run_simulation(
    request: SimulationRequest,
    registry: RegistryDep,
    slots: SlotsDep,
) -> dict[str, Any]:
    """Run a propagation to completion and return every frame at once.

    This is the batch fallback. **For visualisation use ``WS /ws/simulate``**,
    which streams the same header and the same frames as they are computed, so
    the frontend can start animating at step 1 instead of waiting for step N.

    The response is the stream, flattened: the same ``header``, the same
    ``frames`` (honouring ``frame_format``), plus a ``report`` of what happened.
    """
    prepared = prepare_run(registry, request)
    with slots.reserve():
        session = RunSession(prepared)
        frames = await asyncio.to_thread(lambda: list(session.frames()))
        report = await asyncio.to_thread(session.report)
    return {"header": prepared.header(), "frames": frames, "report": report}
