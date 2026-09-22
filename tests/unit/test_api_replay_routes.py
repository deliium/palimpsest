"""Replay-to-tick route stable responses."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from api.app import DisposableEngine, create_app
from api.schemas import AvailabilityOut, ReplayRequest, ReplayResultOut
from api.services import ReplayApiService
from api.simulation_manager import SimulationManager
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings
from simulation.memory_run_control import InMemoryRunControlRepository

pytestmark = pytest.mark.unit


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = FakeEngine()


class StubReplay(ReplayApiService):
    async def replay_to_tick(
        self, run_id: str, body: ReplayRequest
    ) -> ReplayResultOut:
        if body.to_tick > 100:
            err = RuntimeError("corruption")
            err.code = "corruption"  # type: ignore[attr-defined]
            raise err
        return ReplayResultOut(
            run_id=run_id,
            status="ok",
            availability=AvailabilityOut.AVAILABLE,
            ticks_replayed=body.to_tick,
            reason_code=None,
        )


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


def _settings() -> Settings:
    return load_settings(env_file=False)


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _app() -> FastAPI:
    settings = _settings()
    app = create_app(
        settings=settings,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=settings,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    app.state.replay_api_service = StubReplay()
    return app


async def test_replay_success(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        response = await client.post(
            "/v1/simulations/run-1/replay", json={"to_tick": 4}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ticks_replayed"] == 4
    assert body["availability"] == "available"


async def test_replay_corruption_stable_code(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        response = await client.post(
            "/v1/simulations/run-1/replay", json={"to_tick": 101}
        )
    assert response.status_code == 422
    assert response.json()["code"] == "replay_corruption"


@pytest.mark.integration
async def test_api_replay_integration_stub() -> None:
    pytest.skip("integration stub reserved for Task 21")
