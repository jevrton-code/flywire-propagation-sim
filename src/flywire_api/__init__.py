"""HTTP + WebSocket API over the FlyWire propagation simulation.

This package is a thin transport layer. It loads the connectome subgraph through
:func:`flywire_sim.graph.load_graph`, runs it through
:class:`flywire_sim.model.LIFSimulation`, and packages the result as JSON. No
dynamics, no graph surgery and no neuroscience live here -- if something looks
like modelling, it belongs in :mod:`flywire_sim` instead.

Run it::

    python -m flywire_api.run          # then open http://127.0.0.1:8000/docs

Shape of the API::

    GET  /api/health              service status, which circuits exist
    GET  /api/circuit             counts, citations, simplifications
    GET  /api/circuit/neurons     nodes: id, type, side, sign, soma position
    GET  /api/circuit/edges       connections: synapse counts and weights
    GET  /api/circuit/graph       the three above, in one response
    GET  /api/circuit/cell-types  stimulus options and presets
    GET  /api/circuit/provenance  dataset version, DOIs, licences
    GET  /api/model/defaults      LIF defaults and request limits
    POST /api/simulations         run to completion, return every frame
    WS   /ws/simulate             stream one frame per step, as computed

Two conventions the frontend must respect: ``root_id`` is always a **string**
(18-digit ids overflow a JavaScript ``Number``), and per-neuron values travel as
**arrays aligned to the ordering** sent in the stream header.
"""

from .app import app, create_app
from .circuits import CircuitRegistry, LoadedCircuit
from .errors import ApiError
from .schemas import SimulationRequest, SimulationResponse
from .service import FrameEncoder, PreparedRun, RunSession, prepare_run

__all__ = [
    "ApiError",
    "CircuitRegistry",
    "FrameEncoder",
    "LoadedCircuit",
    "PreparedRun",
    "RunSession",
    "SimulationRequest",
    "SimulationResponse",
    "app",
    "create_app",
    "prepare_run",
]
