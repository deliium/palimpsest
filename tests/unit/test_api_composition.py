"""API composition exposes persistence factories without connecting."""

from __future__ import annotations

import pytest

import api.dependencies as dependencies
from api.app import DatabaseResourcesLike, create_app
from infrastructure.settings import Settings, load_settings

pytestmark = pytest.mark.unit


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
