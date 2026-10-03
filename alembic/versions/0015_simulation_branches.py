"""Alembic revision for research simulation branch lineage.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-04

Adds control-plane ``simulation_branches`` genealogy outside
``AUTHORITATIVE_TABLES`` / objective event fold. Parent history is never
rewritten by fork materialization.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.simulation_branches")
_STABLE_ID_LEN = 128
_SHA256_HEX_LEN = 64
_TABLE = "simulation_branches"

_CLOSED_KINDS = (
    "memory_architecture",
    "belief_patch",
    "communication_remove",
    "mortality_disabled",
    "cognitive_budget",
    "agent_architecture",
    "alternate_seed_stream",
)


def upgrade() -> None:
    _LOG.info(
        "simulation_branches_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )
    kinds = ", ".join(f"'{kind}'" for kind in _CLOSED_KINDS)
    op.execute(
        f"""
        CREATE TABLE {_TABLE} (
            child_run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            parent_run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            fork_tick BIGINT NOT NULL,
            intervention_kind TEXT NOT NULL,
            intervention_fingerprint CHAR({_SHA256_HEX_LEN}) NOT NULL,
            intervention_canonical JSONB NOT NULL,
            branch_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            created_as_of_parent_head BIGINT NOT NULL,
            PRIMARY KEY (child_run_id),
            CONSTRAINT fk_simulation_branches_child
                FOREIGN KEY (child_run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_simulation_branches_parent
                FOREIGN KEY (parent_run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_simulation_branches_fork_tick
                CHECK (fork_tick >= 0),
            CONSTRAINT ck_simulation_branches_parent_head
                CHECK (created_as_of_parent_head >= 0),
            CONSTRAINT ck_simulation_branches_fingerprint
                CHECK (char_length(intervention_fingerprint) = {_SHA256_HEX_LEN}),
            CONSTRAINT ck_simulation_branches_kind
                CHECK (intervention_kind IN ({kinds})),
            CONSTRAINT uq_simulation_branches_branch_id
                UNIQUE (branch_id)
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_simulation_branches_parent_run_id "
        f"ON {_TABLE} (parent_run_id)"
    )
    op.execute(
        f"CREATE INDEX ix_simulation_branches_parent_fork "
        f"ON {_TABLE} (parent_run_id, fork_tick)"
    )
    _LOG.info(
        "simulation_branches_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    _LOG.info(
        "simulation_branches_migration_start",
        extra={"revision": revision, "operation": "downgrade"},
    )
    op.execute(f"DROP TABLE IF EXISTS {_TABLE}")
    _LOG.info(
        "simulation_branches_migration_complete",
        extra={"revision": revision, "operation": "downgrade"},
    )
