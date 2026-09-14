"""Enable the pgvector extension. No application tables.

Revision ID: 0001
Revises:
Create Date: 2026-09-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Documented no-op.

    Dropping ``vector`` is unsafe on a PostgreSQL instance that may host
    other databases. Foundation rollback leaves the extension in place.
    """
