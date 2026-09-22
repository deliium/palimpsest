"""Append-only trigger enforcement on authoritative and scientific tables."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from infrastructure.database import DatabaseResources, session_scope
from persistence.orm import SCIENTIFIC_EVIDENCE_APPEND_ONLY_TABLES

pytestmark = pytest.mark.integration

_HASH_A = "a" * 64
_HASH_B = "b" * 64

# Registry of append-only scientific evidence tables (Task 7).
_SCIENTIFIC_APPEND_ONLY = SCIENTIFIC_EVIDENCE_APPEND_ONLY_TABLES


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


async def _seed_minimal_history(session: object) -> tuple[str, str, str]:
    execute = session.execute  # type: ignore[attr-defined]
    run_id = _unique("run")
    snap_id = _unique("snap")
    exp_id = _unique("exp")
    await execute(
        text(
            """
            INSERT INTO world_snapshots (
                snapshot_id, run_id, world_id, seed, config_seed, next_tick,
                revision, event_schema_version, projector_version,
                persistence_codec_version, derivation_version, integrity_hash,
                predecessor_commit_hash, canonical_payload
            ) VALUES (
                :snap_id, :run_id, 'world-1', 1, 1, 0,
                0, 2, 'v1', 'v1', 'v1', :hash, NULL, '{}'::jsonb
            )
            """
        ),
        {"snap_id": snap_id, "run_id": run_id, "hash": _HASH_A},
    )
    await execute(
        text(
            """
            INSERT INTO simulation_runs (
                run_id, world_id, seed, config_seed, derivation_version,
                event_schema_version, projector_version,
                persistence_codec_version, bootstrap_snapshot_id
            ) VALUES (
                :run_id, 'world-1', 1, 1, 'v1', 2, 'v1', 'v1', :snap_id
            )
            """
        ),
        {"run_id": run_id, "snap_id": snap_id},
    )
    await execute(
        text(
            """
            INSERT INTO experiments (experiment_id, label)
            VALUES (:exp_id, 'baseline')
            """
        ),
        {"exp_id": exp_id},
    )
    await execute(
        text(
            """
            INSERT INTO experiment_runs (experiment_id, run_id, ordinal)
            VALUES (:exp_id, :run_id, 0)
            """
        ),
        {"exp_id": exp_id, "run_id": run_id},
    )
    await execute(
        text(
            """
            INSERT INTO tick_commits (
                run_id, tick, resulting_tick, base_revision, resulting_revision,
                predecessor_commit_hash, commit_hash, idempotency_key,
                event_count, payload_hash, snapshot_id
            ) VALUES (
                :run_id, 0, 1, 0, 0, NULL, :hash, 'idem-0', 0, :hash, NULL
            )
            """
        ),
        {"run_id": run_id, "hash": _HASH_A},
    )
    return run_id, snap_id, exp_id


async def test_update_delete_truncate_rejected_insert_allowed(
    database_resources: DatabaseResources,
) -> None:
    async with session_scope(database_resources.session_factory) as session:
        run_id, _snap_id, exp_id = await _seed_minimal_history(session)
        await session.commit()

    async with session_scope(database_resources.session_factory) as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text(
                    "UPDATE tick_commits SET event_count = 9 "
                    "WHERE run_id = :run_id AND tick = 0"
                ),
                {"run_id": run_id},
            )
            await session.commit()

    async with session_scope(database_resources.session_factory) as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text("DELETE FROM experiments WHERE experiment_id = :exp_id"),
                {"exp_id": exp_id},
            )
            await session.commit()

    async with session_scope(database_resources.session_factory) as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(text("TRUNCATE world_events"))
            await session.commit()

    async with session_scope(database_resources.session_factory) as session:
        await session.execute(
            text(
                """
                INSERT INTO tick_commits (
                    run_id, tick, resulting_tick, base_revision, resulting_revision,
                    predecessor_commit_hash, commit_hash, idempotency_key,
                    event_count, payload_hash, snapshot_id
                ) VALUES (
                    :run_id, 1, 2, 0, 0, :pred, :hash, 'idem-1', 0, :hash, NULL
                )
                """
            ),
            {"run_id": run_id, "pred": _HASH_A, "hash": _HASH_B},
        )
        await session.commit()
        count = await session.execute(
            text("SELECT count(*) FROM tick_commits WHERE run_id = :run_id"),
            {"run_id": run_id},
        )
        assert count.scalar_one() == 2


async def test_scientific_evidence_append_only_registry(
    database_resources: DatabaseResources,
) -> None:
    """Every Task-7 append-only table has update/delete/truncate reject triggers."""
    async with session_scope(database_resources.session_factory) as session:
        assert _SCIENTIFIC_APPEND_ONLY
        for table in _SCIENTIFIC_APPEND_ONLY:
            for suffix in ("update", "delete", "truncate"):
                tgname = f"trg_{table}_reject_{suffix}"
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
                    {"table": table, "tgname": tgname},
                )
                assert result.scalars().all() == [tgname], table
