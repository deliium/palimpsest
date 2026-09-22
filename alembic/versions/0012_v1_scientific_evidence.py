"""Alembic revision for scientific evidence, metrics, and unified stream.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-22

Adds append-only goal revisions, action resolutions, claim truth specs,
evidence manifests, immutable metric documents, mutable metric-set lifecycle,
and a unified per-run stream/outbox with monotonic cursors.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.v1_scientific_evidence")
_STABLE_ID_LEN = 128
_SHA256_HEX_LEN = 64
_APPEND_ONLY_TABLES: tuple[str, ...] = (
    "goal_revisions",
    "action_resolutions",
    "claim_truth_specs",
    "evidence_manifests",
    "metric_documents",
    "run_stream_records",
)


def upgrade() -> None:
    _LOG.info(
        "v1_scientific_evidence_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )

    op.execute(
        f"""
        CREATE TABLE evidence_manifests (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            manifest_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            schema_version VARCHAR(64) NOT NULL,
            objective_commit_hash VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            high_water_json JSONB NOT NULL,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            PRIMARY KEY (run_id, manifest_hash),
            CONSTRAINT fk_evidence_manifests_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_evidence_manifests_hash
                CHECK (char_length(manifest_hash) = {_SHA256_HEX_LEN})
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_evidence_manifests_run "
        "ON evidence_manifests (run_id, created_ordinal)"
    )

    op.execute(
        f"""
        CREATE TABLE goal_revisions (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            goal_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            revision BIGINT NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            tick BIGINT NOT NULL,
            schema_version VARCHAR(64) NOT NULL,
            content_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            payload BYTEA NOT NULL,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            PRIMARY KEY (run_id, goal_id, revision),
            CONSTRAINT fk_goal_revisions_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_goal_revisions_nonneg
                CHECK (revision >= 0 AND tick >= 0),
            CONSTRAINT ck_goal_revisions_hash
                CHECK (char_length(content_hash) = {_SHA256_HEX_LEN})
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_goal_revisions_run_tick "
        "ON goal_revisions (run_id, tick, created_ordinal)"
    )

    op.execute(
        f"""
        CREATE TABLE action_resolutions (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            tick BIGINT NOT NULL,
            ordinal BIGINT NOT NULL,
            schema_version VARCHAR(64) NOT NULL,
            content_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            payload BYTEA NOT NULL,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            PRIMARY KEY (run_id, tick, ordinal),
            CONSTRAINT fk_action_resolutions_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_action_resolutions_nonneg
                CHECK (tick >= 0 AND ordinal >= 0),
            CONSTRAINT ck_action_resolutions_hash
                CHECK (char_length(content_hash) = {_SHA256_HEX_LEN})
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_action_resolutions_run "
        "ON action_resolutions (run_id, tick)"
    )

    op.execute(
        f"""
        CREATE TABLE claim_truth_specs (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            claim_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            availability VARCHAR(32) NOT NULL,
            schema_version VARCHAR(64),
            content_hash CHAR({_SHA256_HEX_LEN}),
            payload BYTEA,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            PRIMARY KEY (run_id, claim_id),
            CONSTRAINT fk_claim_truth_specs_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_claim_truth_availability
                CHECK (availability IN ('available', 'unavailable')),
            CONSTRAINT ck_claim_truth_envelope
                CHECK (
                    (
                        availability = 'unavailable'
                        AND schema_version IS NULL
                        AND content_hash IS NULL
                        AND payload IS NULL
                    ) OR (
                        availability = 'available'
                        AND schema_version IS NOT NULL
                        AND content_hash IS NOT NULL
                        AND payload IS NOT NULL
                        AND char_length(content_hash) = {_SHA256_HEX_LEN}
                    )
                )
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_claim_truth_specs_run "
        "ON claim_truth_specs (run_id, created_ordinal)"
    )

    op.execute(
        f"""
        CREATE TABLE metric_sets (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            metric_set_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            lifecycle_state VARCHAR(32) NOT NULL,
            evidence_manifest_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            lifecycle_version BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (run_id, metric_set_id),
            CONSTRAINT fk_metric_sets_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_metric_sets_manifest
                FOREIGN KEY (run_id, evidence_manifest_hash)
                REFERENCES evidence_manifests (run_id, manifest_hash)
                ON DELETE RESTRICT,
            CONSTRAINT ck_metric_sets_lifecycle
                CHECK (lifecycle_state IN (
                    'pending', 'running', 'complete', 'partial', 'failed'
                )),
            CONSTRAINT ck_metric_sets_version
                CHECK (lifecycle_version >= 0),
            CONSTRAINT ck_metric_sets_hash
                CHECK (char_length(evidence_manifest_hash) = {_SHA256_HEX_LEN})
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_metric_sets_lifecycle "
        "ON metric_sets (lifecycle_state)"
    )

    op.execute(
        f"""
        CREATE TABLE metric_documents (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            metric_set_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            metric_family VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            evidence_manifest_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            schema_version VARCHAR(64) NOT NULL,
            content_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            payload BYTEA NOT NULL,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            PRIMARY KEY (run_id, metric_set_id, metric_family),
            CONSTRAINT fk_metric_documents_set
                FOREIGN KEY (run_id, metric_set_id)
                REFERENCES metric_sets (run_id, metric_set_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_metric_documents_manifest
                FOREIGN KEY (run_id, evidence_manifest_hash)
                REFERENCES evidence_manifests (run_id, manifest_hash)
                ON DELETE RESTRICT,
            CONSTRAINT ck_metric_documents_hash
                CHECK (char_length(content_hash) = {_SHA256_HEX_LEN}),
            CONSTRAINT ck_metric_documents_manifest_hash
                CHECK (char_length(evidence_manifest_hash) = {_SHA256_HEX_LEN})
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_metric_documents_run_set "
        "ON metric_documents (run_id, metric_set_id, created_ordinal)"
    )
    op.execute(
        "CREATE INDEX ix_metric_documents_content "
        "ON metric_documents (content_hash)"
    )

    op.execute(
        f"""
        CREATE TABLE run_stream_heads (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL PRIMARY KEY,
            high_water BIGINT NOT NULL DEFAULT 0,
            CONSTRAINT fk_run_stream_heads_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_run_stream_heads_nonneg
                CHECK (high_water >= 0)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE run_stream_records (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            cursor_value BIGINT NOT NULL,
            record_kind VARCHAR(32) NOT NULL,
            schema_version VARCHAR(64) NOT NULL,
            content_hash CHAR({_SHA256_HEX_LEN}) NOT NULL,
            payload BYTEA NOT NULL,
            related_tick BIGINT,
            created_ordinal BIGSERIAL NOT NULL UNIQUE,
            PRIMARY KEY (run_id, cursor_value),
            CONSTRAINT fk_run_stream_records_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_run_stream_records_cursor
                CHECK (cursor_value >= 1),
            CONSTRAINT ck_run_stream_records_kind
                CHECK (record_kind IN (
                    'status', 'eventless_tick', 'event', 'metric',
                    'result', 'recoverable_error', 'completion'
                )),
            CONSTRAINT ck_run_stream_records_hash
                CHECK (char_length(content_hash) = {_SHA256_HEX_LEN}),
            CONSTRAINT ck_run_stream_records_tick
                CHECK (related_tick IS NULL OR related_tick >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_run_stream_records_kind "
        "ON run_stream_records (run_id, record_kind, cursor_value)"
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
        "v1_scientific_evidence_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    _LOG.info(
        "v1_scientific_evidence_migration_start",
        extra={"revision": revision, "operation": "downgrade"},
    )
    for table in reversed(_APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_update ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_delete ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_truncate ON {table}")
    op.execute("DROP TABLE IF EXISTS run_stream_records")
    op.execute("DROP TABLE IF EXISTS run_stream_heads")
    op.execute("DROP TABLE IF EXISTS metric_documents")
    op.execute("DROP TABLE IF EXISTS metric_sets")
    op.execute("DROP TABLE IF EXISTS claim_truth_specs")
    op.execute("DROP TABLE IF EXISTS action_resolutions")
    op.execute("DROP TABLE IF EXISTS goal_revisions")
    op.execute("DROP TABLE IF EXISTS evidence_manifests")
    _LOG.info(
        "v1_scientific_evidence_migration_complete",
        extra={"revision": revision, "operation": "downgrade"},
    )
