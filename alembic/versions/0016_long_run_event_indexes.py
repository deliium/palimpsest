"""Additive indexes for long-run observer/event filter queries.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-04

Does not change authoritative column semantics or weaken append-only
triggers. PK ``(run_id, tick, sequence)`` already serves keyset event pages;
``ix_world_snapshots_run_next_tick`` already serves seek. This revision adds
run-scoped composites for optional observer filters by event type / actor /
target.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.long_run_event_indexes")

_INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_world_events_run_event_type", "world_events", ("run_id", "event_type")),
    ("ix_world_events_run_actor_id", "world_events", ("run_id", "actor_id")),
    ("ix_world_events_run_target_id", "world_events", ("run_id", "target_id")),
)


def upgrade() -> None:
    _LOG.info(
        "long_run_event_indexes_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )
    for name, table, columns in _INDEXES:
        cols = ", ".join(columns)
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")
        _LOG.debug(
            "index_created name=%s table=%s columns=%s",
            name,
            table,
            cols,
        )
    _LOG.info(
        "long_run_event_indexes_migration_complete",
        extra={"revision": revision, "index_count": len(_INDEXES)},
    )


def downgrade() -> None:
    _LOG.info(
        "long_run_event_indexes_migration_downgrade",
        extra={"revision": revision, "operation": "downgrade"},
    )
    for name, _table, _columns in reversed(_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")
