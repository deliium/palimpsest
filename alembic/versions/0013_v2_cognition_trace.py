"""Alembic revision for durable cognition execution traces.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-23

Adds append-only run-scoped cognition_trace_invocations outside authoritative
replay / EvidenceManifest. Indexed for debugger inspection by
(run_id, tick) and (run_id, agent_id, tick).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.v2_cognition_trace")
_STABLE_ID_LEN = 128
_SHA256_HEX_LEN = 64
_TABLE = "cognition_trace_invocations"


def upgrade() -> None:
    _LOG.info(
        "cognition_trace_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )
    op.execute(
        f"""
        CREATE TABLE {_TABLE} (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            agent_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            tick BIGINT NOT NULL,
            invocation_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            schema_version VARCHAR(64) NOT NULL,
            content_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            payload BYTEA NOT NULL,
            command_kind VARCHAR({_STABLE_ID_LEN}),
            final_confidence DOUBLE PRECISION,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            PRIMARY KEY (run_id, agent_id, tick, invocation_id),
            CONSTRAINT fk_cognition_trace_invocations_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_cognition_trace_invocations_nonneg
                CHECK (tick >= 0),
            CONSTRAINT ck_cognition_trace_invocations_hash
                CHECK (char_length(content_hash) = {_SHA256_HEX_LEN}),
            CONSTRAINT ck_cognition_trace_invocations_confidence
                CHECK (
                    final_confidence IS NULL
                    OR (final_confidence >= 0.0 AND final_confidence <= 1.0)
                )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_cognition_trace_invocations_run_tick "
        f"ON {_TABLE} (run_id, tick)"
    )
    op.execute(
        f"CREATE INDEX ix_cognition_trace_invocations_run_agent_tick "
        f"ON {_TABLE} (run_id, agent_id, tick)"
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_{_TABLE}_reject_update
        BEFORE UPDATE ON {_TABLE}
        FOR EACH ROW
        EXECUTE PROCEDURE reject_history_mutation()
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_{_TABLE}_reject_delete
        BEFORE DELETE ON {_TABLE}
        FOR EACH ROW
        EXECUTE PROCEDURE reject_history_mutation()
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_{_TABLE}_reject_truncate
        BEFORE TRUNCATE ON {_TABLE}
        FOR EACH STATEMENT
        EXECUTE PROCEDURE reject_history_mutation()
        """
    )
    _LOG.info(
        "cognition_trace_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    _LOG.info(
        "cognition_trace_migration_start",
        extra={"revision": revision, "operation": "downgrade"},
    )
    op.execute(f"DROP TRIGGER IF EXISTS trg_{_TABLE}_reject_update ON {_TABLE}")
    op.execute(f"DROP TRIGGER IF EXISTS trg_{_TABLE}_reject_delete ON {_TABLE}")
    op.execute(f"DROP TRIGGER IF EXISTS trg_{_TABLE}_reject_truncate ON {_TABLE}")
    op.execute(f"DROP TABLE IF EXISTS {_TABLE}")
    _LOG.info(
        "cognition_trace_migration_complete",
        extra={"revision": revision, "operation": "downgrade"},
    )
