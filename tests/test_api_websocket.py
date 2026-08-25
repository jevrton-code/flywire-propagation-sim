"""WebSocket tests: does the stream deliver the simulation step by step?

The streaming endpoint is the reason the backend exists at all -- the frontend
must be able to animate step 1 while step 2 is still being integrated. These
tests therefore check three things:

1. the **framing** is right (ready -> header -> N+1 frames -> complete, in order);
2. the streamed frames are **identical** to what the batch endpoint returns for
   the same request, so choosing the stream never costs information;
3. client mistakes produce an ``error`` message and leave the socket **usable**,
   because a dropped connection on every typo would be miserable to build against.
"""

from __future__ import annotations

import pytest

N_NEURONS = 153


def collect(ws) -> tuple[dict, list[dict], dict]:
    """Read one run: header, frames, and the terminating message."""
    header = ws.receive_json()
    assert header["type"] == "header", header
    frames = []
    while True:
        message = ws.receive_json()
        if message["type"] == "frame":
            frames.append(message)
            continue
        return header, frames, message


def start(ws, **request) -> None:
    ws.send_json({"action": "start", "request": request})


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_the_server_announces_itself_and_its_limits(client):
    with client.websocket_connect("/ws/simulate") as ws:
        ready = ws.receive_json()
    assert ready["type"] == "ready"
    assert ready["protocol_version"] == 1
    assert ready["limits"]["max_steps"] == 500


def test_a_run_streams_one_frame_per_step_in_order(client):
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        start(ws, source={"cell_types": ["EPG"], "side": "left"}, steps=6)
        header, frames, final = collect(ws)

    assert header["n_steps"] == 6
    assert header["n_frames"] == 7
    assert len(header["neuron_ids"]) == N_NEURONS
    assert all(isinstance(i, str) for i in header["neuron_ids"])

    # 7 frames: the resting state plus one per update step, strictly in order.
    assert [f["step"] for f in frames] == [0, 1, 2, 3, 4, 5, 6]
    assert all(len(f["activation"]) == N_NEURONS for f in frames)
    assert final["type"] == "complete"
    assert final["report"]["steps"] == 6
    assert final["report"]["numerically_finite"] is True


def test_a_bare_request_without_an_action_is_accepted(client):
    """The minimal client: send one object, read frames."""
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        ws.send_json({"source": {"cell_types": ["EPG"]}, "steps": 2})
        _, frames, final = collect(ws)
    assert len(frames) == 3
    assert final["type"] == "complete"


def test_the_stream_matches_the_batch_endpoint_exactly(client):
    """Streaming is a delivery choice, not a different simulation."""
    request = {"source": {"cell_types": ["EPG"], "side": "left"}, "steps": 8}
    batch = client.post("/api/simulations", json=request).json()

    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        start(ws, **request)
        header, frames, final = collect(ws)

    assert header["neuron_ids"] == batch["header"]["neuron_ids"]
    assert header["stimulated_root_ids"] == batch["header"]["stimulated_root_ids"]
    assert final["report"] == batch["report"]
    for streamed, batched in zip(frames, batch["frames"]):
        streamed = {k: v for k, v in streamed.items() if k != "type"}
        assert streamed == batched


def test_the_header_carries_the_simplifications_to_the_client(client):
    """The frontend cannot honestly render this data without them."""
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        start(ws, source={"cell_types": ["EPG"]}, steps=1)
        header, _, _ = collect(ws)
    metadata = header["metadata"]
    assert len(metadata["simplifications"]) >= 10
    assert "toy dynamics" in metadata["disclaimer"]
    assert metadata["graph"]["dataset"]["connectivity"]["version"] == "783.0"


def test_delta_frames_stream_a_dense_baseline_then_diffs(client):
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        start(
            ws,
            source={"cell_types": ["EPG"], "side": "left"},
            steps=6,
            frame_format="delta",
        )
        header, frames, final = collect(ws)

    assert header["frame_format"] == "delta"
    assert frames[0]["format"] == "dense"
    assert all(f["format"] == "delta" for f in frames[1:])

    activation = list(frames[0]["activation"])
    for frame in frames[1:]:
        for index, value in zip(frame["activation"]["indices"], frame["activation"]["values"]):
            activation[index] = value
        assert len(frame["spiked"]) == frame["summary"]["n_spiked"]
    assert final["type"] == "complete"


def test_several_runs_can_share_one_connection(client):
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        for steps in (2, 4):
            start(ws, source={"cell_types": ["EPG"]}, steps=steps)
            _, frames, final = collect(ws)
            assert len(frames) == steps + 1
            assert final["type"] == "complete"


# --------------------------------------------------------------------------- #
# Control messages
# --------------------------------------------------------------------------- #


def test_a_run_can_be_cancelled_midway(client):
    """Pacing is used only to make the race deterministic; cancel works without it."""
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        start(
            ws,
            source={"cell_types": ["EPG"], "side": "left"},
            steps=200,
            frame_interval_ms=20,
        )
        assert ws.receive_json()["type"] == "header"
        ws.receive_json()  # frame 0
        ws.send_json({"action": "cancel"})

        seen = 1
        while True:
            message = ws.receive_json()
            if message["type"] == "frame":
                seen += 1
                continue
            break

    assert message["type"] == "cancelled"
    assert seen < 201, "cancelling must actually stop the run early"
    assert message["step"] == seen - 1
    # A cancelled run still reports on the steps it did take.
    assert message["report"]["steps"] == seen - 1


def test_starting_a_second_run_mid_stream_is_refused_not_queued(client):
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        start(
            ws,
            source={"cell_types": ["EPG"], "side": "left"},
            steps=40,
            frame_interval_ms=20,
        )
        assert ws.receive_json()["type"] == "header"
        ws.receive_json()
        start(ws, source={"cell_types": ["Delta7"]}, steps=3)

        errors, frames = [], 1
        while True:
            message = ws.receive_json()
            if message["type"] == "frame":
                frames += 1
            elif message["type"] == "error":
                errors.append(message)
            else:
                break

    assert message["type"] == "complete", "the running simulation must not be interrupted"
    assert frames == 41
    assert [e["error"]["code"] for e in errors] == ["simulation_in_progress"]


def test_cancelling_when_nothing_runs_is_an_explicit_error(client):
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        ws.send_json({"action": "cancel"})
        message = ws.receive_json()
    assert message["type"] == "error"
    assert message["error"]["code"] == "nothing_to_cancel"


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #


def test_an_unknown_neuron_is_reported_and_the_socket_survives(client):
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        start(ws, source={"root_ids": ["12345"]}, steps=2)
        message = ws.receive_json()

        assert message["type"] == "error"
        assert message["status"] == 404
        assert message["error"]["code"] == "unknown_neuron"
        assert message["error"]["details"]["missing_root_ids"] == ["12345"]

        # The connection is still good: a corrected request runs normally.
        start(ws, source={"cell_types": ["EPG"]}, steps=2)
        _, frames, final = collect(ws)
    assert len(frames) == 3
    assert final["type"] == "complete"


@pytest.mark.parametrize(
    "request_patch, expected_code",
    [
        ({"steps": 10_000}, "invalid_request"),
        ({"steps": -1}, "invalid_request"),
        ({"source": {}}, "invalid_request"),
        ({"source": {"cell_types": ["nope"]}}, "unknown_cell_type"),
        ({"params": {"leak": 5.0}}, "invalid_request"),
        ({"params": {"v_max": 0.1, "threshold": 0.5}}, "invalid_parameters"),
    ],
)
def test_bad_requests_produce_an_error_message_not_a_crash(
    client, request_patch, expected_code
):
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        ws.send_json(
            {
                "action": "start",
                "request": {"source": {"cell_types": ["EPG"]}, "steps": 2, **request_patch},
            }
        )
        message = ws.receive_json()
    assert message["type"] == "error"
    assert message["error"]["code"] == expected_code
    assert message["error"]["message"]


@pytest.mark.parametrize(
    "payload, expected_code",
    [
        ("this is not json", "invalid_json"),
        ("[1, 2, 3]", "invalid_message"),
        ('{"action": "explode"}', "unknown_action"),
    ],
)
def test_malformed_messages_are_rejected_clearly(client, payload, expected_code):
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        ws.send_text(payload)
        message = ws.receive_json()
    assert message["type"] == "error"
    assert message["error"]["code"] == expected_code


def test_the_stream_refuses_to_start_when_all_slots_are_taken(client, api_app):
    slots = api_app.state.simulation_slots
    saved = slots.active
    slots.active = slots.limit
    try:
        with client.websocket_connect("/ws/simulate") as ws:
            ws.receive_json()
            start(ws, source={"cell_types": ["EPG"]}, steps=2)
            message = ws.receive_json()
    finally:
        slots.active = saved

    assert message["type"] == "error"
    assert message["status"] == 503
    assert message["error"]["code"] == "too_many_simulations"


def test_a_run_releases_its_slot_when_it_finishes(client, api_app):
    slots = api_app.state.simulation_slots
    with client.websocket_connect("/ws/simulate") as ws:
        ws.receive_json()
        start(ws, source={"cell_types": ["EPG"]}, steps=2)
        collect(ws)
    assert slots.active == 0
