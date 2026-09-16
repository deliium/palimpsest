"""Alembic migration head and event-store schema against disposable DBs."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from infrastructure.database import DatabaseResources, session_scope
from infrastructure.settings import Settings
from persistence.orm import AUTHORITATIVE_TABLES

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_upgrade_head_is_idempotent_with_single_revision(
    migrated_test_database: Settings,
) -> None:
    config = _alembic_config(migrated_test_database.database_dsn())
    command.upgrade(config, "head")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0002"]
    assert script.get_current_head() == "0002"


async def test_vector_extension_and_event_store_tables_exist(
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
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version' "
                "ORDER BY tablename"
            )
        )
        found = set(tables.scalars().all())
        assert set(AUTHORITATIVE_TABLES).issubset(found)


async def test_orm_metadata_matches_migrated_tables(
    database_resources: DatabaseResources,
) -> None:
    import persistence.orm  # noqa: F401
    from infrastructure.orm import metadata

    expected = set(AUTHORITATIVE_TABLES)
    assert expected <= set(metadata.tables)
    async with session_scope(database_resources.session_factory) as session:
        revision = await session.execute(
            text("SELECT version_num FROM alembic_version")
        )
        assert revision.scalar_one() == "0002"
