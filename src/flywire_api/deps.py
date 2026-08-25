"""Shared per-request plumbing: the circuit registry and the concurrency guard."""

from __future__ import annotations

import contextlib
from typing import Annotated, Iterator

from fastapi import Depends, Query, Request, WebSocket

from flywire_sim.graph import DEFAULT_CIRCUIT

from .circuits import CircuitRegistry
from .errors import server_busy
from .schemas import NtPolicy

#: How many runs may be in flight at once. A run is milliseconds of CPU on this
#: circuit, so the cap is not about throughput -- it stops a client from opening
#: fifty sockets and pinning the process, and gives a clear 503 instead of a
#: server that quietly stops responding.
DEFAULT_MAX_CONCURRENT_SIMULATIONS = 4


class SimulationSlots:
    """Counts in-flight runs and refuses new ones past the limit.

    No lock: acquire and release never await, and the event loop is
    single-threaded, so the counter cannot be observed mid-update.
    """

    def __init__(self, limit: int = DEFAULT_MAX_CONCURRENT_SIMULATIONS):
        self.limit = limit
        self.active = 0

    @contextlib.contextmanager
    def reserve(self) -> Iterator[None]:
        if self.active >= self.limit:
            raise server_busy(
                "too_many_simulations",
                f"{self.active} simulations are already running (limit {self.limit}); "
                "retry in a moment",
                limit=self.limit,
                active=self.active,
            )
        self.active += 1
        try:
            yield
        finally:
            self.active -= 1


def get_registry(request: Request) -> CircuitRegistry:
    return request.app.state.registry


def registry_of(websocket: WebSocket) -> CircuitRegistry:
    return websocket.app.state.registry


def get_slots(request: Request) -> SimulationSlots:
    return request.app.state.simulation_slots


def slots_of(websocket: WebSocket) -> SimulationSlots:
    return websocket.app.state.simulation_slots


class CircuitQuery:
    """``?circuit=&nt_policy=`` on every circuit endpoint, documented once."""

    def __init__(
        self,
        circuit: Annotated[
            str,
            Query(description="Slug of the committed subgraph.", max_length=128),
        ] = DEFAULT_CIRCUIT,
        nt_policy: Annotated[
            NtPolicy,
            Query(
                description=(
                    "How each neuron's excitatory/inhibitory sign is decided. "
                    "'known-first' prefers the literature transmitter "
                    "(Turner-Evans et al. 2020) and is the simulation default; "
                    "'predicted' reproduces the dataset's automatic predictions. "
                    "The two disagree on 2 of the 153 neurons."
                )
            ),
        ] = "known-first",
    ):
        self.circuit = circuit
        self.nt_policy = nt_policy


RegistryDep = Annotated[CircuitRegistry, Depends(get_registry)]
SlotsDep = Annotated[SimulationSlots, Depends(get_slots)]
CircuitDep = Annotated[CircuitQuery, Depends(CircuitQuery)]
