"""Runner pending finalization outbox and attempt state.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-22

Append-only pending subjective finalization records and runner attempt
state for durable recovery. Not part of AUTHORITATIVE_TABLES.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.runner_finalization_outbox")

_STABLE_ID_LEN = 128
_SHA256_HEX_LEN = 64


def upgrade() -> None:
    _LOG.info(
        "runner_finalization_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )
    op.execute(
        f"""
        CREATE TABLE runner_pending_finalizations (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            agent_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            tick BIGINT NOT NULL,
            invocation_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            integrity_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            codec_version VARCHAR(32) NOT NULL,
            payload_json JSONB NOT NULL,
            status VARCHAR(32) NOT NULL,
            created_ordinal BIGSERIAL NOT NULL,
            PRIMARY KEY (run_id, agent_id, invocation_id),
            CONSTRAINT ck_runner_pending_status
                CHECK (status IN ('pending', 'finalized', 'aborted')),
            CONSTRAINT ck_runner_pending_hash
                CHECK (char_length(integrity_hash) = {_SHA256_HEX_LEN}),
            CONSTRAINT fk_runner_pending_run
                FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_runner_pending_ordinal
            ON runner_pending_finalizations (created_ordinal)
        """
    )
    op.execute(
        f"""
        CREATE TABLE runner_attempt_states (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            attempt_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            tick BIGINT NOT NULL,
            phase VARCHAR(64) NOT NULL,
            recovery_required BOOLEAN NOT NULL DEFAULT FALSE,
            integrity_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            codec_version VARCHAR(32) NOT NULL,
            payload_json JSONB NOT NULL,
            created_ordinal BIGSERIAL NOT NULL,
            PRIMARY KEY (run_id, attempt_id),
            CONSTRAINT ck_runner_attempt_hash
                CHECK (char_length(integrity_hash) = {_SHA256_HEX_LEN}),
            CONSTRAINT fk_runner_attempt_run
                FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_runner_attempt_ordinal
            ON runner_attempt_states (created_ordinal)
        """
    )
    _LOG.info(
        "runner_finalization_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    _LOG.info(
        "runner_finalization_migration_start",
        extra={"revision": revision, "operation": "downgrade"},
    )
    op.execute("DROP TABLE IF EXISTS runner_attempt_states")
    op.execute("DROP TABLE IF EXISTS runner_pending_finalizations")
    _LOG.info(
        "runner_finalization_migration_complete",
        extra={"revision": revision, "operation": "downgrade"},
    )
