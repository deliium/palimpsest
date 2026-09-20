"""Persist occurrence and cause context on world_events.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-21

Adds nullable JSONB columns for event cause and occurrence context so
replay/perception audience decisions survive SQL round trips. Legacy rows
retain NULL values; context is never fabricated for older schemas.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE world_events
            ADD COLUMN cause JSONB,
            ADD COLUMN occurrence JSONB
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE world_events
            DROP COLUMN IF EXISTS occurrence,
            DROP COLUMN IF EXISTS cause
        """
    )
