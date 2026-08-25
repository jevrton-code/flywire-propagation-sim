"""Shared fixtures for the API tests.

The app is built once per session: loading the subgraph is the slow part and it
is immutable once loaded, so every test can share it. Tests that need to poke at
server state (the concurrency counter) restore it afterwards.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from flywire_api import create_app


@pytest.fixture(scope="session")
def api_app():
    return create_app()


@pytest.fixture(scope="session")
def client(api_app):
    # The context manager runs the lifespan, which preloads the default circuit.
    with TestClient(api_app) as test_client:
        yield test_client
