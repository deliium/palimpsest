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
from persistence.memory_orm import SUBJECTIVE_MEMORY_TABLES
from persistence.orm import AUTHORITATIVE_TABLES
from persistence.subjective_orm import SUBJECTIVE_AGENT_TABLES

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_HEAD = "0007"

# Mutable lifecycle tables keep access/forgetting updates; reconstruction and
# fragment tables are append-only. Trace content uses a selective trigger.
# Belief/relationship heads are mutable; revision/evidence tables are append-only.
_MUTABLE_SUBJECTIVE_TABLES = frozenset(
    {
        "memory_traces",
        "memory_access_ops",
        "semantic_beliefs",
        "directed_relationships",
    }
)
_APPEND_ONLY_SUBJECTIVE_TABLES = (
    frozenset(SUBJECTIVE_MEMORY_TABLES) | frozenset(SUBJECTIVE_AGENT_TABLES)
) - _MUTABLE_SUBJECTIVE_TABLES


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
    assert script.get_heads() == [_EXPECTED_HEAD]
    assert script.get_current_head() == _EXPECTED_HEAD


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
        assert set(SUBJECTIVE_MEMORY_TABLES).issubset(found)
        assert set(SUBJECTIVE_AGENT_TABLES).issubset(found)


async def test_orm_metadata_matches_migrated_tables(
    database_resources: DatabaseResources,
) -> None:
    import persistence.memory_orm
    import persistence.orm
    import persistence.subjective_orm  # noqa: F401
    from infrastructure.orm import metadata

    expected = (
        set(AUTHORITATIVE_TABLES)
        | set(SUBJECTIVE_MEMORY_TABLES)
        | set(SUBJECTIVE_AGENT_TABLES)
    )
    assert expected <= set(metadata.tables)
    async with session_scope(database_resources.session_factory) as session:
        revision = await session.execute(
            text("SELECT version_num FROM alembic_version")
        )
        assert revision.scalar_one() == _EXPECTED_HEAD


async def test_subjective_memory_tables_are_not_authoritative() -> None:
    overlap = set(SUBJECTIVE_MEMORY_TABLES) & set(AUTHORITATIVE_TABLES)
    assert not overlap


async def test_subjective_agent_tables_are_not_authoritative() -> None:
    overlap = set(SUBJECTIVE_AGENT_TABLES) & set(AUTHORITATIVE_TABLES)
    assert not overlap


async def test_mutable_subjective_tables_lack_full_reject_triggers(
    database_resources: DatabaseResources,
) -> None:
    async with session_scope(database_resources.session_factory) as session:
        for table in sorted(_MUTABLE_SUBJECTIVE_TABLES):
            result = await session.execute(
                text(
                    """
                    SELECT tgname FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    WHERE c.relname = :table
                      AND NOT t.tgisinternal
                      AND tgname LIKE 'trg_%_reject_mutation'
                    """
                ),
                {"table": table},
            )
            assert result.scalars().all() == []


async def test_append_only_subjective_tables_have_reject_triggers(
    database_resources: DatabaseResources,
) -> None:
    async with session_scope(database_resources.session_factory) as session:
        for table in sorted(_APPEND_ONLY_SUBJECTIVE_TABLES):
            result = await session.execute(
                text(
                    """
                    SELECT tgname FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    WHERE c.relname = :table
                      AND NOT t.tgisinternal
                      AND tgname = :tgname
                    """
                ),
                {
                    "table": table,
                    "tgname": f"trg_{table}_reject_mutation",
                },
            )
            assert result.scalars().all() == [f"trg_{table}_reject_mutation"]


async def test_memory_traces_have_selective_content_immutability(
    database_resources: DatabaseResources,
) -> None:
    async with session_scope(database_resources.session_factory) as session:
        result = await session.execute(
            text(
                """
                SELECT tgname FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                WHERE c.relname = 'memory_traces'
                  AND NOT t.tgisinternal
                  AND tgname = 'trg_memory_traces_reject_content_mutation'
                """
            )
        )
        assert result.scalars().all() == ["trg_memory_traces_reject_content_mutation"]
