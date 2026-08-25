"""``WS /ws/simulate``: the streaming endpoint, and the reason this phase exists.

Protocol
--------
Every message in both directions is a JSON object. Server messages carry a
``type``; client messages carry an ``action``.

Server -> client::

    {"type": "ready",     "protocol_version": 1, "limits": {...}}
    {"type": "header",    ...}          # once per run, before any frame
    {"type": "frame",     ...}          # n_steps + 1 of these, in order
    {"type": "complete",  "report": {...}}
    {"type": "cancelled", "step": 12, "report": {...}}
    {"type": "error",     "error": {"code": ..., "message": ..., "details": ...}}

Client -> server::

    {"action": "start", "request": { ...SimulationRequest... }}
    {"action": "cancel"}

A bare ``SimulationRequest`` object (no ``action``) is also accepted as a start,
so a minimal client can send one object and read frames.

Design decisions worth knowing
------------------------------
*The socket is never closed because of a client mistake.* A bad request gets an
``error`` message and the connection stays open, so the user can fix the form and
run again without a reconnect. Closing on every typo would make the frontend's
job harder for no benefit. The socket closes when the client closes it, or on a
genuine protocol break.

*Runs are sequential per connection, and a second ``start`` mid-run is an error*
(``simulation_in_progress``), not a queued run: silently queueing would leave the
user watching an animation they had already replaced. Send ``cancel`` first.

*Incoming messages are read by a background task* while frames are streaming,
which is what makes ``cancel`` possible at all -- otherwise the server would not
look at the socket until the run it is streaming had finished.

*Frames are computed one step at a time* via ``LIFSimulation.iter_steps``, and
each one is sent as soon as it exists. Nothing waits for the full run. That is
the whole point: the frontend animates step 1 while step 2 is being integrated.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect, WebSocketState

from .deps import registry_of, slots_of
from .errors import ApiError, invalid_request
from .schemas import (
    MAX_AMPLITUDE,
    MAX_FRAME_INTERVAL_MS,
    MAX_SOURCE_ROOT_IDS,
    MAX_STEPS,
    SimulationRequest,
)
from .service import RunSession, prepare_run

router = APIRouter()

PROTOCOL_VERSION = 1

#: Sentinel pushed on the inbox queue when the client goes away.
_DISCONNECTED = object()


@router.websocket("/ws/simulate")
async def simulate_stream(websocket: WebSocket) -> None:
    """Stream a propagation, one message per time step, as it is computed.

    See the module docstring for the full protocol. FastAPI does not put
    WebSocket schemas in OpenAPI, so this docstring and
    :class:`~flywire_api.schemas.SimulationRequest` (documented on
    ``POST /api/simulations``, which takes the identical body) are the contract.
    """
    await websocket.accept()
    registry = registry_of(websocket)
    slots = slots_of(websocket)

    inbox: asyncio.Queue[Any] = asyncio.Queue()
    reader = asyncio.create_task(_read_messages(websocket, inbox))

    try:
        await websocket.send_json(
            {
                "type": "ready",
                "protocol_version": PROTOCOL_VERSION,
                "limits": {
                    "max_steps": MAX_STEPS,
                    "max_source_root_ids": MAX_SOURCE_ROOT_IDS,
                    "max_amplitude": MAX_AMPLITUDE,
                    "max_frame_interval_ms": MAX_FRAME_INTERVAL_MS,
                    "max_concurrent_simulations": slots.limit,
                },
            }
        )

        while True:
            message = await inbox.get()
            if message is _DISCONNECTED:
                return

            try:
                command = _parse(message)
            except ApiError as exc:
                await _send_error(websocket, exc)
                continue

            if command["action"] == "cancel":
                await _send_error(
                    websocket,
                    invalid_request(
                        "nothing_to_cancel",
                        "no simulation is running on this connection",
                    ),
                )
                continue

            try:
                prepared = prepare_run(registry, command["request"])
            except ApiError as exc:
                await _send_error(websocket, exc)
                continue

            try:
                with slots.reserve():
                    await _stream_run(websocket, prepared, inbox)
            except ApiError as exc:
                await _send_error(websocket, exc)
                continue
    except WebSocketDisconnect:
        return
    finally:
        reader.cancel()


# --------------------------------------------------------------------------- #
# Streaming one run
# --------------------------------------------------------------------------- #


async def _stream_run(websocket: WebSocket, prepared, inbox: asyncio.Queue) -> None:
    request = prepared.request
    session = RunSession(prepared)
    interval = request.frame_interval_ms / 1000.0

    await websocket.send_json({"type": "header", **prepared.header()})

    cancelled_at: int | None = None
    for frame in session.frames():
        await websocket.send_json({"type": "frame", **frame})

        # Yield to the reader task even with no pacing, so a cancel sent mid-run
        # has a chance to be seen before the run ends.
        await asyncio.sleep(interval)

        control = await _drain(websocket, inbox)
        if control == "cancel":
            cancelled_at = frame["step"]
            break
        if control == "disconnected":
            return

    report = session.report()
    if cancelled_at is not None:
        await websocket.send_json({"type": "cancelled", "step": cancelled_at, "report": report})
    else:
        await websocket.send_json({"type": "complete", "report": report})


async def _drain(websocket: WebSocket, inbox: asyncio.Queue) -> str | None:
    """Consume anything the client sent mid-run. Returns 'cancel', 'disconnected' or None."""
    outcome: str | None = None
    while True:
        try:
            message = inbox.get_nowait()
        except asyncio.QueueEmpty:
            return outcome

        if message is _DISCONNECTED:
            return "disconnected"

        try:
            command = _parse(message)
        except ApiError as exc:
            await _send_error(websocket, exc)
            continue

        if command["action"] == "cancel":
            outcome = "cancel"
        else:
            await _send_error(
                websocket,
                ApiError(
                    "simulation_in_progress",
                    "a simulation is already streaming on this connection; send "
                    '{"action": "cancel"} before starting another one',
                    status_code=409,
                ),
            )


# --------------------------------------------------------------------------- #
# Message plumbing
# --------------------------------------------------------------------------- #


async def _read_messages(websocket: WebSocket, inbox: asyncio.Queue) -> None:
    """Background task: push every raw client message onto ``inbox``."""
    try:
        while True:
            inbox.put_nowait(await websocket.receive_text())
    except (WebSocketDisconnect, RuntimeError):
        inbox.put_nowait(_DISCONNECTED)
    except asyncio.CancelledError:
        raise


def _parse(raw: str) -> dict[str, Any]:
    """Turn a raw client message into ``{"action": ..., "request": ...}``.

    Raises:
        ApiError: 422 with the offending field, for malformed JSON, an unknown
            action, or a request body that fails validation.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise invalid_request("invalid_json", f"message is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise invalid_request(
            "invalid_message", "expected a JSON object, e.g. {\"action\": \"start\", ...}"
        )

    action = payload.get("action", "start")
    if action == "cancel":
        return {"action": "cancel", "request": None}
    if action != "start":
        raise invalid_request(
            "unknown_action",
            f"unknown action {action!r}; expected 'start' or 'cancel'",
            received=action,
        )

    body = payload.get("request", {k: v for k, v in payload.items() if k != "action"})
    try:
        return {"action": "start", "request": SimulationRequest.model_validate(body)}
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(p) for p in first.get("loc", ()))
        message = first.get("msg", "request failed validation")
        raise invalid_request(
            "invalid_request",
            f"{location}: {message}" if location else message,
            errors=[
                {
                    "location": [str(p) for p in e.get("loc", ())],
                    "message": e.get("msg"),
                    "type": e.get("type"),
                }
                for e in exc.errors()
            ],
        ) from exc


async def _send_error(websocket: WebSocket, exc: ApiError) -> None:
    if websocket.client_state is WebSocketState.CONNECTED:
        await websocket.send_json(
            {"type": "error", "status": exc.status_code, **exc.to_payload()}
        )
