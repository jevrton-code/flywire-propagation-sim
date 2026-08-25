"""Application factory.

The app owns exactly two pieces of state: a :class:`CircuitRegistry` (loaded
graphs, cached) and a :class:`SimulationSlots` counter (how many runs are in
flight). Both hang off ``app.state`` and are injected into handlers, so tests can
build an app pointed at a different data directory or with a concurrency limit of
1 without touching module globals.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flywire_sim.graph import DEFAULT_CIRCUIT

from .circuits import CircuitRegistry
from .deps import DEFAULT_MAX_CONCURRENT_SIMULATIONS, SimulationSlots
from .errors import register_error_handlers
from .rest import router as rest_router
from .websocket import router as websocket_router

logger = logging.getLogger(__name__)

DESCRIPTION = """
Streams a simplified activation propagation over a **real subgraph of the FlyWire
connectome** of *Drosophila melanogaster* (Dorkenwald et al., *Nature* 634,
124-138 (2024); connectivity snapshot v783).

* `GET /api/circuit/*` -- the static graph: neurons, connections, provenance,
  citations. Everything needed to draw the circuit before simulating.
* `POST /api/simulations` -- run a propagation and get every frame at once.
* `WS /ws/simulate` -- **the endpoint for visualisation**: same request body,
  but each time step is pushed as soon as it is computed.

**The wiring is real; the dynamics are a caricature.** Every simulation response
carries `metadata.simplifications` and `metadata.disclaimer` listing exactly what
the model leaves out. They are part of the payload on purpose: a client is
expected to show them, not to strip them.

`root_id` values are always **strings** -- 18-digit FlyWire ids do not survive a
JavaScript `Number`.
"""


def create_app(
    *,
    data_dir: Path | str | None = None,
    max_concurrent_simulations: int | None = None,
    warm_default_circuit: bool = True,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Build the API.

    Args:
        data_dir: directory holding the committed subgraph CSVs. Defaults to
            ``$FLYWIRE_API_DATA_DIR``, else the repository's ``data/subgraphs``.
        max_concurrent_simulations: how many runs may be in flight before new
            ones are refused with 503 / ``too_many_simulations``. Defaults to
            ``$FLYWIRE_API_MAX_CONCURRENT``, else 4.
        warm_default_circuit: load the default circuit at startup instead of on
            the first request. Disable in tests that want a cold registry.
        cors_origins: browser origins allowed to call the API. Defaults to
            ``$FLYWIRE_API_CORS_ORIGINS`` (comma-separated), else the usual local
            dev servers, which is what the frontend phase will use.

    The environment fallbacks exist so ``uvicorn flywire_api.app:app --reload``
    stays configurable: ``--reload`` needs an import string, not an app object.
    """
    if data_dir is None:
        data_dir = os.environ.get("FLYWIRE_API_DATA_DIR") or None
    if max_concurrent_simulations is None:
        max_concurrent_simulations = int(
            os.environ.get("FLYWIRE_API_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT_SIMULATIONS)
        )
    if cors_origins is None:
        configured = os.environ.get("FLYWIRE_API_CORS_ORIGINS", "")
        cors_origins = [o.strip() for o in configured.split(",") if o.strip()] or None

    registry = CircuitRegistry(data_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if warm_default_circuit:
            try:
                registry.warm(DEFAULT_CIRCUIT)
                logger.info(
                    "loaded circuit %s: %d neurons, %d connections",
                    DEFAULT_CIRCUIT,
                    registry.get(DEFAULT_CIRCUIT).graph.n_neurons,
                    registry.get(DEFAULT_CIRCUIT).graph.graph.number_of_edges(),
                )
            except Exception:
                # A missing dataset must not stop the process from starting:
                # /api/health still answers and says which circuits it can see,
                # which is a much better diagnostic than a crash at import time.
                logger.exception(
                    "could not preload circuit %s; build it with "
                    "`python -m flywire_data.build_subgraph`",
                    DEFAULT_CIRCUIT,
                )
        yield

    app = FastAPI(
        title="FlyWire propagation simulator API",
        version="0.1.0",
        summary="Activation propagation over a real FlyWire connectome subgraph.",
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "meta", "description": "Health and service metadata."},
            {
                "name": "circuit",
                "description": "The static connectome subgraph and where it came from.",
            },
            {
                "name": "simulation",
                "description": (
                    "Running propagations. Prefer the WebSocket for anything animated."
                ),
            },
        ],
    )

    app.state.registry = registry
    app.state.simulation_slots = SimulationSlots(max_concurrent_simulations)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins
        or ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(rest_router)
    app.include_router(websocket_router)
    return app


app = create_app()
