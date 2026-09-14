"""Alembic pgvector bootstrap against a disposable test database."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from infrastructure.database import DatabaseResources, session_scope
from infrastructure.settings import Settings

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def test_upgrade_head_is_idempotent_with_single_revision(
    migrated_test_database: Settings,
) -> None:
    config = _alembic_config()
    command.upgrade(config, "head")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0001"]
    assert script.get_current_head() == "0001"


async def test_vector_extension_exists_without_simulation_tables(
    database_resources: DatabaseResources,
) -> None:
    async with session_scope(database_resources.session_factory) as session:
        extension = await session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        assert extension.scalar_one_or_none() == "vector"
        tables = await session.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        )
        assert tables.scalars().all() == []
