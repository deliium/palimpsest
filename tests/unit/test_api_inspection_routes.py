"""Inspection, debug gate, and metric route behavior."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from api.app import DatabaseResourcesLike, DisposableEngine, create_app
from api.errors import forbidden
from api.schemas import (
    AvailabilityOut,
    EventCursorIn,
    EventPageOut,
    ExperimentalStateOut,
    MetricCatalogOut,
    ObjectiveWorldOut,
    SubjectivePageOut,
)
from api.services import InspectionService, MetricReadService
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


class StubInspection(InspectionService):
    async def objective_world(self, run_id: str) -> ObjectiveWorldOut:
        return ObjectiveWorldOut(
            run_id=run_id,
            tick=3,
            revision=3,
            availability=AvailabilityOut.AVAILABLE,
            body_count=2,
            location_count=1,
        )

    async def events_page(
        self,
        run_id: str,
        *,
        after: EventCursorIn | None,
        limit: int,
    ) -> EventPageOut:
        del after
        return EventPageOut(
            run_id=run_id,
            limit=limit,
            count=0,
            availability=AvailabilityOut.PARTIAL,
            events=(),
        )

    async def experimental_state(self, run_id: str) -> ExperimentalStateOut:
        return ExperimentalStateOut(
            run_id=run_id,
            experiment_id="exp-1",
            membership_source="assignment",
            has_assignment=True,
            availability=AvailabilityOut.AVAILABLE,
        )

    async def subjective_page(
        self,
        run_id: str,
        owner_id: str,
        *,
        kind: str,
        after: str | None,
        limit: int,
    ) -> SubjectivePageOut:
        del after
        return SubjectivePageOut(
            run_id=run_id,
            owner_id=owner_id,
            limit=limit,
            item_count=0,
            availability=AvailabilityOut.AVAILABLE,
            content_available=False,
            kind=kind,  # type: ignore[arg-type]
        )


class StubMetrics(MetricReadService):
    async def catalog(self, run_id: str) -> MetricCatalogOut:
        return MetricCatalogOut(
            run_id=run_id,
            items=(),
            count=0,
            availability=AvailabilityOut.UNAVAILABLE,
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


def _settings(**overrides: object) -> Settings:
    return load_settings(env_file=False, **overrides)


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or _settings()
    app = create_app(
        settings=resolved,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=resolved,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    app.state.inspection_service = StubInspection()
    app.state.metric_read_service = StubMetrics()
    return app


async def test_objective_and_events_and_experimental(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        world = await client.get("/v1/simulations/run-1/world")
        assert world.status_code == 200
        assert world.json()["body_count"] == 2
        events = await client.get("/v1/simulations/run-1/events")
        assert events.status_code == 200
        assert events.json()["availability"] == "partial"
        experimental = await client.get("/v1/simulations/run-1/experimental")
        assert experimental.status_code == 200
        assert experimental.json()["has_assignment"] is True
        metrics = await client.get("/v1/simulations/run-1/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["count"] == 0


async def test_debug_routes_disabled_by_default(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        response = await client.get("/v1/simulations/run-1/owners/agent-1/memories")
        assert response.status_code == 403
        assert response.json()["code"] == "debug_disabled"


async def test_debug_routes_with_credential(logging_sandbox: None) -> None:
    secret = "d" * 32
    settings = _settings(api_debug_enabled=True, api_debug_credential=secret)
    async with running_client(_app(settings)) as client:
        denied = await client.get("/v1/simulations/run-1/owners/agent-1/beliefs")
        assert denied.status_code == 401
        ok = await client.get(
            "/v1/simulations/run-1/owners/agent-1/relationships",
            headers={"x-palimpsest-token": secret},
        )
        assert ok.status_code == 200
        assert ok.json()["surface"] == "debug"


@pytest.mark.integration
async def test_api_event_pagination_integration_stub() -> None:
    pytest.skip("integration stub reserved for Task 21")


@pytest.mark.integration
async def test_api_debug_scope_integration_stub() -> None:
    pytest.skip("integration stub reserved for Task 21")
