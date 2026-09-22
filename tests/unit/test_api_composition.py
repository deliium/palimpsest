"""API composition wiring for manager and new dependency factories."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI

import api.dependencies as dependencies
from api.app import DatabaseResourcesLike, create_app
from api.persistence_services import (
    PersistenceInspectionService,
    PersistenceMetricReadService,
    PersistenceReplayApiService,
)
from api.simulation_manager import SimulationManager
from infrastructure.settings import Settings, load_settings
from simulation.memory_run_control import InMemoryRunControlRepository

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


def _settings() -> Settings:
    return load_settings(
        env_file=False,
        database_url=(
            "postgresql+asyncpg://palimpsest:palimpsest@127.0.0.1:5432/palimpsest"
        ),
        test_database_url=(
            "postgresql+asyncpg://palimpsest:palimpsest@127.0.0.1:5432/palimpsest_test"
        ),
    )


class _FakeEngine:
    async def dispose(self) -> None:
        return None


class _FakeResources:
    """Resources with a session_factory so lifespan can attach real facades."""

    def __init__(self) -> None:
        self.engine = _FakeEngine()
        self.session_factory = object()


@asynccontextmanager
async def _lifespan_app(app: FastAPI) -> AsyncIterator[FastAPI]:
    async with app.router.lifespan_context(app):
        yield app


def test_dependency_factories_are_exported_without_connecting() -> None:
    def forbidden(_settings: Settings) -> DatabaseResourcesLike:
        raise AssertionError("create_app must not connect at construction")

    create_app(settings=_settings(), database_factory=forbidden)
    assert hasattr(dependencies, "get_replay_service")
    assert hasattr(dependencies, "get_run_repository")
    assert hasattr(dependencies, "get_tick_journal_repository")
    assert hasattr(dependencies, "get_snapshot_repository")
    assert hasattr(dependencies, "get_experiment_repository")
    assert hasattr(dependencies, "get_simulation_manager")
    assert hasattr(dependencies, "get_run_control_repository")
    assert hasattr(dependencies, "get_stream_repository")
    assert hasattr(dependencies, "get_inspection_service")
    assert hasattr(dependencies, "get_metric_read_service")
    assert hasattr(dependencies, "get_replay_api_service")


def test_create_app_accepts_injected_simulation_manager() -> None:
    manager = SimulationManager(
        settings=_settings(),
        run_control=InMemoryRunControlRepository(),
    )

    def forbidden(_settings: Settings) -> DatabaseResourcesLike:
        raise AssertionError("must not connect")

    app = create_app(
        settings=_settings(),
        database_factory=forbidden,
        simulation_manager=manager,
        attach_default_manager=False,
    )
    assert app.state.simulation_manager is manager
    assert app.title == "Palimpsest"
    assert len(app.routes) >= 5


async def test_lifespan_attaches_persistence_backed_services() -> None:
    app = create_app(
        settings=_settings(),
        database_factory=lambda _s: _FakeResources(),
        attach_default_manager=False,
    )
    async with _lifespan_app(app) as live:
        assert isinstance(live.state.inspection_service, PersistenceInspectionService)
        assert isinstance(live.state.metric_read_service, PersistenceMetricReadService)
        assert isinstance(live.state.replay_api_service, PersistenceReplayApiService)


async def test_lifespan_preserves_injected_service_overrides() -> None:
    from api.services import InspectionService, MetricReadService, ReplayApiService

    app = create_app(
        settings=_settings(),
        database_factory=lambda _s: _FakeResources(),
        attach_default_manager=False,
    )
    stub_inspection = InspectionService()
    stub_metrics = MetricReadService()
    stub_replay = ReplayApiService()
    app.state.inspection_service = stub_inspection
    app.state.metric_read_service = stub_metrics
    app.state.replay_api_service = stub_replay
    async with _lifespan_app(app) as live:
        assert live.state.inspection_service is stub_inspection
        assert live.state.metric_read_service is stub_metrics
        assert live.state.replay_api_service is stub_replay
