"""REST simulation control route behavior."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from api.app import DatabaseResourcesLike, DisposableEngine, create_app
from api.simulation_manager import SimulationManager, TickExecutionResult
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings
from simulation.memory_run_control import InMemoryRunControlRepository

pytestmark = pytest.mark.unit

_PAYLOAD = b'{"schema_version":"runner-config-v2"}'
_FINGERPRINT = hashlib.sha256(_PAYLOAD).hexdigest()
_B64 = base64.b64encode(_PAYLOAD).decode("ascii")


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = FakeEngine()


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _settings(**overrides: object) -> Settings:
    return load_settings(env_file=False, **overrides)


def _app(manager: SimulationManager, settings: Settings | None = None) -> FastAPI:
    return create_app(
        settings=settings or _settings(),
        database_factory=lambda _s: FakeResources(),
        simulation_manager=manager,
        attach_default_manager=False,
    )


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _manager() -> SimulationManager:
    async def executor(run_id: str) -> TickExecutionResult:
        del run_id
        return TickExecutionResult(ticks_committed=1)

    return SimulationManager(
        settings=_settings(),
        run_control=InMemoryRunControlRepository(),
        tick_executor=executor,
    )


async def test_create_start_tick_status_flow(logging_sandbox: None) -> None:
    app = _app(_manager())
    async with running_client(app) as client:
        created = await client.post(
            "/v1/simulations",
            json={
                "run_id": "run-1",
                "config_fingerprint": _FINGERPRINT,
                "config_payload_b64": _B64,
            },
        )
        assert created.status_code == 201
        assert created.json()["lifecycle_state"] == "configured"
        started = await client.post("/v1/simulations/run-1/start")
        assert started.status_code == 200
        assert started.json()["lifecycle_state"] == "ready"
        tick = await client.post("/v1/simulations/run-1/tick")
        assert tick.status_code == 200
        assert tick.json()["ticks_committed"] == 1
        status = await client.get("/v1/simulations/run-1")
        assert status.status_code == 200
        assert status.json()["run_id"] == "run-1"


async def test_auth_required_blocks_without_credential(logging_sandbox: None) -> None:
    strong = "z" * 32
    settings = _settings(
        api_auth_required=True,
        api_control_credential=strong,
        api_inspection_credential=strong,
        api_agent_visible_credential=strong,
    )
    manager = SimulationManager(
        settings=settings,
        run_control=InMemoryRunControlRepository(),
    )
    app = _app(manager, settings=settings)
    async with running_client(app) as client:
        response = await client.get("/v1/simulations")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "missing_credential"
        ok = await client.get(
            "/v1/simulations", headers={"x-palimpsest-token": strong}
        )
        assert ok.status_code == 200


async def test_query_string_secret_rejected(logging_sandbox: None) -> None:
    app = _app(_manager())
    async with running_client(app) as client:
        response = await client.get("/v1/simulations?token=nope")
        assert response.status_code == 400
        assert response.json()["code"] == "query_string_secret"


@pytest.mark.integration
async def test_api_simulation_lifecycle_integration_stub() -> None:
    """PostgreSQL lifecycle proofs live in Task 21."""
    pytest.skip("integration stub reserved for Task 21")
