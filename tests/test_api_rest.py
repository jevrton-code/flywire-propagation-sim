"""REST API tests: does the HTTP layer hand the frontend the real circuit, and
does it fail loudly when the request is wrong?

Two kinds of assertion live here:

* **Contract**: root ids are strings, arrays are aligned to a single ordering,
  the honesty block (``simplifications``/``disclaimer``) is present. A frontend
  built against these guarantees should not break silently.
* **Ground truth**: the counts come from the committed subgraph (153 neurons,
  2695 connections; see ``data/subgraphs/ring_attractor_core_meta.json``). If
  the API ever starts serving something other than the real data, these fail.
"""

from __future__ import annotations

import pytest

from flywire_api.deps import SimulationSlots
from flywire_api.errors import ApiError

N_NEURONS = 153
N_CONNECTIONS = 2695
CELL_TYPES = {"Delta7", "EPG", "EPGt", "PEG", "PEN_a(PEN1)", "PEN_b(PEN2)"}


def error_of(response) -> dict:
    """The error envelope, asserting the API never returns a bare framework error."""
    body = response.json()
    assert "error" in body, f"expected an error envelope, got {body}"
    assert set(body["error"]) <= {"code", "message", "details"}
    return body["error"]


# --------------------------------------------------------------------------- #
# Meta
# --------------------------------------------------------------------------- #


def test_health_reports_the_committed_circuit(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["default_circuit"] == "ring_attractor_core"
    assert "ring_attractor_core" in body["available_circuits"]


def test_unknown_path_still_uses_the_error_envelope(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert error_of(response)["code"] == "not_found"


# --------------------------------------------------------------------------- #
# Circuit metadata
# --------------------------------------------------------------------------- #


def test_circuit_summary_matches_the_committed_dataset(client):
    body = client.get("/api/circuit").json()
    assert body["circuit"] == "ring_attractor_core"
    assert body["n_neurons"] == N_NEURONS
    assert body["n_connections"] == N_CONNECTIONS
    assert set(body["cell_types"]) == CELL_TYPES
    assert sorted(body["sides"]) == ["left", "right"]
    assert body["synapse_threshold"] == 5


def test_circuit_summary_ships_the_simplifications_and_the_disclaimer(client):
    """The honesty block is part of the contract, not an optional extra."""
    body = client.get("/api/circuit").json()
    assert len(body["simplifications"]) >= 10
    assert any("dimensionless" in s for s in body["simplifications"])
    assert "toy dynamics" in body["disclaimer"]


def test_circuit_summary_carries_citable_provenance(client):
    body = client.get("/api/circuit").json()
    citations = " ".join(body["citations"])
    assert "Dorkenwald" in citations and "10.1038/s41586-024-07558-y" in citations
    assert body["licensing"], "licensing terms must reach the client"


def test_provenance_endpoint_names_the_dataset_version(client):
    body = client.get("/api/circuit/provenance").json()
    connectivity = body["provenance"]["dataset"]["connectivity"]
    assert connectivity["version"] == "783.0"
    assert connectivity["doi"].startswith("10.5281/zenodo")
    assert body["provenance"]["nt_policy"] == "known-first"


def test_nt_policy_changes_the_reported_excitation_inhibition_split(client):
    """The two policies disagree on 2 of the 153 neurons; the API must reflect that."""
    known = client.get("/api/circuit", params={"nt_policy": "known-first"}).json()
    predicted = client.get("/api/circuit", params={"nt_policy": "predicted"}).json()

    assert known["n_inhibitory_neurons"] == 40
    assert known["n_modulatory_neurons"] == 0
    assert predicted["n_inhibitory_neurons"] == 39
    assert predicted["n_modulatory_neurons"] == 1


def test_unknown_circuit_is_a_404_that_lists_the_real_options(client):
    response = client.get("/api/circuit", params={"circuit": "../../etc/passwd"})
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "unknown_circuit"
    assert "ring_attractor_core" in error["details"]["available"]


# --------------------------------------------------------------------------- #
# Neurons and edges
# --------------------------------------------------------------------------- #


def test_neuron_list_is_the_full_circuit_in_canonical_order(client):
    body = client.get("/api/circuit/neurons").json()
    neurons = body["neurons"]
    assert body["n_neurons"] == N_NEURONS == len(neurons)
    assert [n["index"] for n in neurons] == list(range(N_NEURONS))


def test_root_ids_are_strings_because_javascript_cannot_hold_them(client):
    """An 18-digit id parsed as a JS Number loses its last digits. Never send one."""
    neurons = client.get("/api/circuit/neurons").json()["neurons"]
    for neuron in neurons:
        assert isinstance(neuron["root_id"], str)
        assert neuron["root_id"].isdigit()
    assert any(len(n["root_id"]) == 18 for n in neurons)
    assert len({n["root_id"] for n in neurons}) == N_NEURONS


def test_neurons_carry_what_a_visualisation_needs(client):
    neurons = client.get("/api/circuit/neurons").json()["neurons"]
    for neuron in neurons:
        assert neuron["cell_type"] in CELL_TYPES
        assert neuron["side"] in {"left", "right"}
        assert neuron["sign"] in {-1, 0, 1}
        assert neuron["polarity"] in {"excitatory", "inhibitory", "modulatory"}
        position = neuron["position"]
        assert all(isinstance(position[axis], int) for axis in "xyz")


def test_coordinate_space_is_documented_not_assumed(client):
    """Soma coordinates are voxels, not nanometres; the client must be told."""
    space = client.get("/api/circuit/neurons").json()["coordinate_space"]
    assert space["voxel_size_nm"] == [4, 4, 40]
    assert "FlyWire" in space["space"]


def test_neuron_list_can_be_filtered_for_a_picker(client):
    body = client.get("/api/circuit/neurons", params={"cell_type": "EPG", "side": "left"}).json()
    assert body["n_neurons"] == 24
    assert {n["cell_type"] for n in body["neurons"]} == {"EPG"}
    assert {n["side"] for n in body["neurons"]} == {"left"}


def test_edge_list_matches_the_committed_connectome(client):
    body = client.get("/api/circuit/edges").json()
    assert body["n_connections"] == N_CONNECTIONS
    assert body["weight_normalisation"] == "in-degree"

    ids = {n["root_id"] for n in client.get("/api/circuit/neurons").json()["neurons"]}
    for edge in body["edges"]:
        assert edge["pre_root_id"] in ids and edge["post_root_id"] in ids
        # The dataset applies a 5-synapse floor; nothing weaker may appear.
        assert edge["syn_count"] >= 5
        assert edge["weight"] == edge["sign"] * edge["syn_count"]
        assert -1.0 <= edge["normalised_weight"] <= 1.0


def test_edge_indices_agree_with_the_neuron_ordering(client):
    """Edges are given by index so the frontend can avoid a string lookup per edge."""
    neurons = client.get("/api/circuit/neurons").json()["neurons"]
    by_index = {n["index"]: n["root_id"] for n in neurons}
    for edge in client.get("/api/circuit/edges").json()["edges"]:
        assert by_index[edge["pre_index"]] == edge["pre_root_id"]
        assert by_index[edge["post_index"]] == edge["post_root_id"]


def test_edges_can_be_thinned_for_rendering(client):
    body = client.get("/api/circuit/edges", params={"min_syn_count": 50}).json()
    assert 0 < body["n_connections"] < N_CONNECTIONS
    assert all(e["syn_count"] >= 50 for e in body["edges"])


def test_graph_endpoint_is_the_other_three_in_one_response(client):
    body = client.get("/api/circuit/graph").json()
    assert len(body["neurons"]) == N_NEURONS
    assert len(body["edges"]) == N_CONNECTIONS
    assert body["summary"]["n_neurons"] == N_NEURONS
    assert body["summary"]["simplifications"]


# --------------------------------------------------------------------------- #
# Stimulus options
# --------------------------------------------------------------------------- #


def test_cell_type_options_account_for_every_neuron(client):
    body = client.get("/api/circuit/cell-types").json()
    assert {c["cell_type"] for c in body["cell_types"]} == CELL_TYPES
    assert sum(c["count"] for c in body["cell_types"]) == N_NEURONS
    for option in body["cell_types"]:
        assert sum(option["count_by_side"].values()) == option["count"]
        assert len(option["root_ids"]) == option["count"]

    delta7 = next(c for c in body["cell_types"] if c["cell_type"] == "Delta7")
    assert delta7["polarity"] == "inhibitory"


def test_presets_are_runnable_as_sent(client):
    """A preset is a source object the client posts back verbatim; prove it works."""
    presets = client.get("/api/circuit/cell-types").json()["presets"]
    assert presets
    for preset in presets:
        response = client.post(
            "/api/simulations", json={"source": preset["source"], "steps": 2}
        )
        assert response.status_code == 200, (preset["id"], response.json())


def test_model_defaults_expose_the_parameters_and_the_limits(client):
    body = client.get("/api/model/defaults").json()
    assert body["parameters"]["model"] == "discrete-time leaky integrate-and-fire"
    assert body["parameters"]["threshold"] > 0
    assert "dimensionless" in body["parameters"]["units"]
    assert body["limits"]["max_steps"] == 500
    assert body["simplifications"]


# --------------------------------------------------------------------------- #
# Running a simulation
# --------------------------------------------------------------------------- #


def test_simulation_happy_path(client):
    request = {"source": {"cell_types": ["EPG"], "side": "left"}, "steps": 5}
    body = client.post("/api/simulations", json=request).json()

    header = body["header"]
    assert header["n_steps"] == 5
    assert header["n_frames"] == 6 == len(body["frames"])
    assert len(header["neuron_ids"]) == N_NEURONS
    assert len(header["stimulated_root_ids"]) == 24

    assert [f["step"] for f in body["frames"]] == [0, 1, 2, 3, 4, 5]
    for frame in body["frames"]:
        assert len(frame["activation"]) == N_NEURONS
        assert len(frame["spiked"]) == N_NEURONS
        assert len(frame["membrane"]) == N_NEURONS


def test_frame_zero_is_the_resting_state(client):
    body = client.post(
        "/api/simulations", json={"source": {"cell_types": ["EPG"]}, "steps": 2}
    ).json()
    resting = body["frames"][0]
    assert resting["step"] == 0
    assert not any(resting["spiked"])
    assert set(resting["activation"]) == {0.0}


def test_the_stimulated_neurons_fire_first(client):
    """Sanity check that the API stimulates who it says it stimulates."""
    body = client.post(
        "/api/simulations",
        json={"source": {"cell_types": ["EPG"], "side": "left"}, "steps": 3},
    ).json()
    stimulated = set(body["header"]["stimulated_indices"])
    first_step = body["frames"][1]
    fired = {i for i, s in enumerate(first_step["spiked"]) if s}
    assert fired == stimulated


def test_the_response_carries_the_models_own_disclaimer(client):
    metadata = client.post(
        "/api/simulations", json={"source": {"cell_types": ["EPG"]}, "steps": 1}
    ).json()["header"]["metadata"]
    assert metadata["simplifications"]
    assert "toy dynamics" in metadata["disclaimer"]
    assert metadata["parameters"]["model"].startswith("discrete-time")
    assert metadata["graph"]["dataset"]["connectivity"]["version"] == "783.0"


def test_report_summarises_the_run(client):
    report = client.post(
        "/api/simulations",
        json={"source": {"cell_types": ["EPG"], "side": "left"}, "steps": 10},
    ).json()["report"]
    assert report["numerically_finite"] is True
    assert report["stimulated_neurons"] == 24
    assert report["downstream_neurons_that_fired"] > 0
    assert set(report["neurons_fired_by_cell_type"]) <= CELL_TYPES
    assert 0.0 <= report["fraction_of_circuit_recruited"] <= 1.0


def test_include_membrane_false_drops_the_membrane_array(client):
    body = client.post(
        "/api/simulations",
        json={"source": {"cell_types": ["EPG"]}, "steps": 2, "include_membrane": False},
    ).json()
    assert all(frame["membrane"] is None for frame in body["frames"])


def test_delta_frames_reconstruct_the_dense_run_exactly(client):
    """The point of the delta format: same information, fewer bytes."""
    request = {"source": {"cell_types": ["EPG"], "side": "left"}, "steps": 8}
    dense = client.post("/api/simulations", json={**request, "frame_format": "dense"}).json()
    delta = client.post("/api/simulations", json={**request, "frame_format": "delta"}).json()

    assert delta["frames"][0]["format"] == "dense", "frame 0 is the baseline"
    assert all(f["format"] == "delta" for f in delta["frames"][1:])

    activation = list(dense["frames"][0]["activation"])
    for dense_frame, delta_frame in zip(dense["frames"][1:], delta["frames"][1:]):
        for index, value in zip(
            delta_frame["activation"]["indices"], delta_frame["activation"]["values"]
        ):
            activation[index] = value
        assert activation == dense_frame["activation"]
        expected_spikes = [i for i, s in enumerate(dense_frame["spiked"]) if s]
        assert delta_frame["spiked"] == expected_spikes


def test_delta_frames_are_smaller_than_dense_ones(client):
    request = {"source": {"root_ids": ["720575940613829900"]}, "steps": 8}
    dense = client.post("/api/simulations", json={**request, "frame_format": "dense"})
    delta = client.post("/api/simulations", json={**request, "frame_format": "delta"})
    assert len(delta.content) < len(dense.content)


def test_custom_parameters_reach_the_model(client):
    body = client.post(
        "/api/simulations",
        json={
            "source": {"cell_types": ["EPG"]},
            "steps": 2,
            "params": {"threshold": 0.5, "leak": 0.5, "refractory_steps": 1},
        },
    ).json()
    parameters = body["header"]["metadata"]["parameters"]
    assert parameters["threshold"] == 0.5
    assert parameters["leak"] == 0.5
    assert parameters["refractory_steps"] == 1


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #


def test_unknown_root_id_is_a_404_naming_the_offender(client):
    response = client.post(
        "/api/simulations", json={"source": {"root_ids": ["12345"]}, "steps": 2}
    )
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "unknown_neuron"
    assert error["details"]["missing_root_ids"] == ["12345"]


def test_unknown_cell_type_is_a_404_listing_the_real_ones(client):
    response = client.post(
        "/api/simulations", json={"source": {"cell_types": ["EPGx"]}, "steps": 2}
    )
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "unknown_cell_type"
    assert set(error["details"]["available_cell_types"]) == CELL_TYPES


def test_a_selector_that_matches_nothing_is_not_silently_empty(client):
    """Every part of the selector exists, but their intersection is empty."""
    neuron = client.get("/api/circuit/neurons").json()["neurons"][0]
    other_side = "left" if neuron["side"] == "right" else "right"
    response = client.post(
        "/api/simulations",
        json={
            "source": {"root_ids": [neuron["root_id"]], "side": other_side},
            "steps": 2,
        },
    )
    assert response.status_code == 404
    assert error_of(response)["code"] == "empty_selection"


def test_an_empty_source_is_rejected_rather_than_stimulating_everything(client):
    response = client.post("/api/simulations", json={"source": {}, "steps": 2})
    assert response.status_code == 422
    assert "at least one of root_ids" in error_of(response)["message"]


@pytest.mark.parametrize(
    "patch, expected_fragment",
    [
        ({"steps": 0}, "steps"),
        ({"steps": 999999999}, "steps"),
        ({"steps": "many"}, "steps"),
        ({"stimulus": {"amplitude": -1.0}}, "amplitude"),
        ({"stimulus": {"duration": 0}}, "duration"),
        ({"params": {"leak": 2.0}}, "leak"),
        ({"params": {"refractory_steps": -1}}, "refractory_steps"),
        ({"params": {"weight_normalisation": "magic"}}, "weight_normalisation"),
        ({"frame_format": "protobuf"}, "frame_format"),
        ({"frame_interval_ms": 10_000}, "frame_interval_ms"),
        ({"nonsense": 1}, "nonsense"),
    ],
)
def test_out_of_range_inputs_are_422_not_500(client, patch, expected_fragment):
    """Nothing a client can type should reach numpy or hang the server."""
    request = {"source": {"cell_types": ["EPG"]}, "steps": 2, **patch}
    response = client.post("/api/simulations", json=request)
    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "invalid_request"
    assert expected_fragment in str(error)


def test_a_root_id_that_is_not_a_number_is_rejected_clearly(client):
    response = client.post(
        "/api/simulations", json={"source": {"root_ids": ["not-an-id"]}, "steps": 2}
    )
    assert response.status_code == 422
    assert "root_id" in error_of(response)["message"]


def test_a_stimulus_after_the_end_of_the_run_is_rejected(client):
    """Otherwise the run is silently empty and looks like a dead circuit."""
    response = client.post(
        "/api/simulations",
        json={"source": {"cell_types": ["EPG"]}, "steps": 3, "stimulus": {"start": 10}},
    )
    assert response.status_code == 422
    assert "no current would ever be injected" in error_of(response)["message"]


def test_parameter_combinations_the_model_refuses_are_422(client):
    """``v_min > v_reset`` passes every per-field bound but LIFParameters rejects it."""
    response = client.post(
        "/api/simulations",
        json={
            "source": {"cell_types": ["EPG"]},
            "steps": 2,
            "params": {"v_min": -0.5, "v_reset": -1.0},
        },
    )
    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "invalid_parameters"
    assert "v_min" in error["message"]


def test_too_many_concurrent_simulations_is_a_503(client, api_app):
    slots = api_app.state.simulation_slots
    saved = slots.active
    slots.active = slots.limit
    try:
        response = client.post(
            "/api/simulations", json={"source": {"cell_types": ["EPG"]}, "steps": 2}
        )
        assert response.status_code == 503
        assert error_of(response)["code"] == "too_many_simulations"
    finally:
        slots.active = saved


def test_a_missing_dataset_does_not_stop_the_server_from_starting(tmp_path):
    """Better a 404 that says which circuits exist than a crash at boot."""
    from fastapi.testclient import TestClient

    from flywire_api import create_app

    with TestClient(create_app(data_dir=tmp_path)) as isolated:
        health = isolated.get("/api/health").json()
        assert health["status"] == "ok"
        assert health["available_circuits"] == []

        response = isolated.post(
            "/api/simulations", json={"source": {"cell_types": ["EPG"]}, "steps": 2}
        )
        assert response.status_code == 404
        assert error_of(response)["code"] == "unknown_circuit"


def test_simulation_slots_release_even_when_the_run_raises():
    slots = SimulationSlots(limit=1)
    with pytest.raises(RuntimeError):
        with slots.reserve():
            raise RuntimeError("boom")
    assert slots.active == 0

    with slots.reserve():
        with pytest.raises(ApiError) as excinfo:
            with slots.reserve():
                pass
    assert excinfo.value.status_code == 503


# --------------------------------------------------------------------------- #
# Documentation
# --------------------------------------------------------------------------- #


def test_openapi_documents_every_endpoint(client):
    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"])
    assert {
        "/api/health",
        "/api/circuit",
        "/api/circuit/neurons",
        "/api/circuit/edges",
        "/api/circuit/graph",
        "/api/circuit/cell-types",
        "/api/circuit/provenance",
        "/api/model/defaults",
        "/api/simulations",
    } <= paths
    assert "SimulationRequest" in schema["components"]["schemas"]
