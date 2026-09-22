"""Alembic revision for experiment framework records.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-22

Append-only experiment definitions, assignments, and final results.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.experiment_framework")
_STABLE_ID_LEN = 128
_SHA256_HEX_LEN = 64
_APPEND_ONLY_TABLES: tuple[str, ...] = (
    "experiment_definitions",
    "experiment_assignments",
    "experiment_results",
)


def upgrade() -> None:
    _LOG.info(
        "experiment_framework_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )
    op.execute(
        f"""
        CREATE TABLE experiment_definitions (
            experiment_id VARCHAR({_STABLE_ID_LEN}) NOT NULL PRIMARY KEY,
            schema_version VARCHAR(64) NOT NULL,
            payload_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            definition_fingerprint CHAR({_SHA256_HEX_LEN}) NOT NULL,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            CONSTRAINT ck_experiment_definitions_hash
                CHECK (char_length(payload_hash) = {_SHA256_HEX_LEN}),
            CONSTRAINT ck_experiment_definitions_fp
                CHECK (char_length(definition_fingerprint) = {_SHA256_HEX_LEN})
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE experiment_assignments (
            experiment_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            condition_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            seed_ordinal INTEGER NOT NULL,
            replicate_index INTEGER NOT NULL,
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            seed BIGINT NOT NULL,
            config_fingerprint CHAR({_SHA256_HEX_LEN}) NOT NULL,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            PRIMARY KEY (
                experiment_id, condition_id, seed_ordinal, replicate_index
            ),
            CONSTRAINT uq_experiment_assignments_run UNIQUE (run_id),
            CONSTRAINT ck_experiment_assignments_seed
                CHECK (seed >= 0),
            CONSTRAINT ck_experiment_assignments_ords
                CHECK (seed_ordinal >= 0 AND replicate_index >= 0),
            CONSTRAINT fk_experiment_assignments_definition
                FOREIGN KEY (experiment_id)
                REFERENCES experiment_definitions (experiment_id)
                ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE experiment_results (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL PRIMARY KEY,
            experiment_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            condition_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            payload_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            stop_reason VARCHAR(64) NOT NULL,
            ticks_committed BIGINT NOT NULL,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            CONSTRAINT ck_experiment_results_ticks
                CHECK (ticks_committed >= 0),
            CONSTRAINT ck_experiment_results_hash
                CHECK (char_length(payload_hash) = {_SHA256_HEX_LEN}),
            CONSTRAINT fk_experiment_results_run
                FOREIGN KEY (run_id)
                REFERENCES experiment_assignments (run_id)
                ON DELETE RESTRICT
        )
        """
    )
    for table in _APPEND_ONLY_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_reject_update
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE PROCEDURE reject_history_mutation()
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_reject_delete
            BEFORE DELETE ON {table}
            FOR EACH ROW
            EXECUTE PROCEDURE reject_history_mutation()
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_reject_truncate
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT
            EXECUTE PROCEDURE reject_history_mutation()
            """
        )
    _LOG.info(
        "experiment_framework_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    _LOG.info(
        "experiment_framework_migration_start",
        extra={"revision": revision, "operation": "downgrade"},
    )
    for table in reversed(_APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_update ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_delete ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_truncate ON {table}")
    op.execute("DROP TABLE IF EXISTS experiment_results")
    op.execute("DROP TABLE IF EXISTS experiment_assignments")
    op.execute("DROP TABLE IF EXISTS experiment_definitions")
    _LOG.info(
        "experiment_framework_migration_complete",
        extra={"revision": revision, "operation": "downgrade"},
    )
