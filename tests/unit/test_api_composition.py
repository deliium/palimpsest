"""API composition wiring for manager and new dependency factories."""

from __future__ import annotations

import os

import pytest

import api.dependencies as dependencies
from api.app import DatabaseResourcesLike, create_app
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
