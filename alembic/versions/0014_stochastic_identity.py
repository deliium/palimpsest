"""Persist derivation-v3 stochastic identity on simulation runs.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-29

Observer replay rebuilds SimulationRunConfig from simulation_runs columns.
derivation-v3 rejects a config that omits stochastic_identity, so the column
is stored next to the physical-rules fields. Existing rows stay null.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE simulation_runs
            ADD COLUMN stochastic_identity VARCHAR(128)
        """
    )
    op.execute(
        """
        ALTER TABLE simulation_runs
            ADD CONSTRAINT ck_simulation_runs_stochastic_identity
            CHECK (
                stochastic_identity IS NULL
                OR (
                    char_length(stochastic_identity) BETWEEN 1 AND 128
                    AND stochastic_identity = btrim(stochastic_identity)
                )
            )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE simulation_runs
            DROP CONSTRAINT ck_simulation_runs_stochastic_identity
        """
    )
    op.execute(
        """
        ALTER TABLE simulation_runs
            DROP COLUMN stochastic_identity
        """
    )
