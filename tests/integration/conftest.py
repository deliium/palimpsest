"""Guarded PostgreSQL fixtures for disposable integration databases."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from infrastructure.database import (
    DatabaseResources,
    create_database_resources,
    dispose_engine,
)
from infrastructure.logging import log_recoverable
from infrastructure.settings import (
    SETTINGS_PREFIX,
    Settings,
    SettingsError,
    load_runtime_settings,
)

ROOT = Path(__file__).resolve().parents[2]
_LOGGER = logging.getLogger("infrastructure.migrations")


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def _is_privilege_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "permission denied",
            "must be owner",
            "must be superuser",
            "must be able to create",
        )
    )


@pytest.fixture(scope="session")
def test_database_settings() -> Settings:
    url = os.environ.get(f"{SETTINGS_PREFIX}TEST_DATABASE_URL")
    if not url:
        if os.environ.get("CI"):
            pytest.fail("CI integration tests require PALIMPSEST_TEST_DATABASE_URL")
        _LOGGER.warning("PALIMPSEST_TEST_DATABASE_URL is not set; skipping integration")
        pytest.skip("PALIMPSEST_TEST_DATABASE_URL is not set")
    try:
        return load_runtime_settings(
            env_file=False,
            database_url=url,
            test_database_url=url,
        )
    except SettingsError as exc:
        pytest.fail(str(exc))


@pytest.fixture(scope="session")
def migrated_test_database(test_database_settings: Settings) -> Iterator[Settings]:
    try:
        command.upgrade(alembic_config(), "head")
    except Exception as exc:
        if _is_privilege_error(exc):
            log_recoverable("pgvector CREATE EXTENSION privilege is not available")
            pytest.skip("CREATE EXTENSION privilege is required")
        raise
    yield test_database_settings


@pytest.fixture
async def database_resources(
    migrated_test_database: Settings,
) -> AsyncIterator[DatabaseResources]:
    resources = create_database_resources(migrated_test_database)
    try:
        yield resources
    finally:
        await dispose_engine(resources.engine)
