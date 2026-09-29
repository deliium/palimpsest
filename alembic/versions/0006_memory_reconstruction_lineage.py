"""Append-only reconstruction records and multi-source derivation edges.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-21

Subjective reconstruction provenance is stored separately from append-only
authoritative history. Tables are intentionally omitted from
reject_history_mutation triggers and AUTHORITATIVE_TABLES.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.memory_reconstruction")

_STABLE_ID_LEN = 128
_MAX_POLICY_ID_CHARS = 64


def upgrade() -> None:
    _LOG.info(
        "memory_reconstruction_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )
    op.execute(
        f"""
        CREATE TABLE memory_reconstructions (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            reconstruction_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            created_tick BIGINT NOT NULL,
            generation INTEGER NOT NULL,
            policy_id VARCHAR({_MAX_POLICY_ID_CHARS}) NOT NULL,
            policy_version VARCHAR({_MAX_POLICY_ID_CHARS}) NOT NULL,
            used_provider BOOLEAN NOT NULL,
            fallback_used BOOLEAN NOT NULL,
            prompt_version VARCHAR({_MAX_POLICY_ID_CHARS}) NULL,
            schema_version VARCHAR({_MAX_POLICY_ID_CHARS}) NULL,
            payload_sha256 VARCHAR(64) NOT NULL,
            CONSTRAINT pk_memory_reconstructions
                PRIMARY KEY (run_id, owner_id, reconstruction_id),
            CONSTRAINT fk_memory_reconstructions_run
                FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_reconstruction_created_tick_nonneg
                CHECK (created_tick >= 0),
            CONSTRAINT ck_reconstruction_generation_positive
                CHECK (generation >= 1),
            CONSTRAINT ck_reconstruction_policy_id_bounded
                CHECK (
                    char_length(policy_id) > 0
                    AND char_length(policy_id) <= {_MAX_POLICY_ID_CHARS}
                ),
            CONSTRAINT ck_reconstruction_policy_version_bounded
                CHECK (
                    char_length(policy_version) > 0
                    AND char_length(policy_version) <= {_MAX_POLICY_ID_CHARS}
                ),
            CONSTRAINT ck_reconstruction_payload_sha256_len
                CHECK (char_length(payload_sha256) = 64)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_reconstructions_scope_tick
            ON memory_reconstructions (run_id, owner_id, created_tick)
        """
    )
    op.execute(
        f"""
        CREATE TABLE memory_reconstruction_sources (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            reconstruction_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            source_memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            ordinal INTEGER NOT NULL,
            CONSTRAINT pk_memory_reconstruction_sources
                PRIMARY KEY (
                    run_id, owner_id, reconstruction_id, source_memory_id
                ),
            CONSTRAINT uq_memory_reconstruction_sources_ordinal
                UNIQUE (run_id, owner_id, reconstruction_id, ordinal),
            CONSTRAINT fk_memory_reconstruction_sources_record
                FOREIGN KEY (run_id, owner_id, reconstruction_id)
                REFERENCES memory_reconstructions (
                    run_id, owner_id, reconstruction_id
                )
                ON DELETE RESTRICT,
            CONSTRAINT fk_memory_reconstruction_sources_trace
                FOREIGN KEY (run_id, owner_id, source_memory_id)
                REFERENCES memory_traces (run_id, owner_id, memory_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_reconstruction_source_ordinal_nonneg
                CHECK (ordinal >= 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_reconstruction_sources_source
            ON memory_reconstruction_sources (
                run_id, owner_id, source_memory_id
            )
        """
    )
    op.execute(
        f"""
        CREATE TABLE memory_derivation_sources (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            derived_memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            source_memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            ordinal INTEGER NOT NULL,
            reconstruction_id VARCHAR({_STABLE_ID_LEN}) NULL,
            CONSTRAINT pk_memory_derivation_sources
                PRIMARY KEY (
                    run_id, owner_id, derived_memory_id, source_memory_id
                ),
            CONSTRAINT uq_memory_derivation_sources_ordinal
                UNIQUE (run_id, owner_id, derived_memory_id, ordinal),
            CONSTRAINT fk_memory_derivation_sources_derived
                FOREIGN KEY (run_id, owner_id, derived_memory_id)
                REFERENCES memory_traces (run_id, owner_id, memory_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_memory_derivation_sources_source
                FOREIGN KEY (run_id, owner_id, source_memory_id)
                REFERENCES memory_traces (run_id, owner_id, memory_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_derivation_source_ordinal_nonneg
                CHECK (ordinal >= 0),
            CONSTRAINT ck_derivation_source_no_self
                CHECK (derived_memory_id <> source_memory_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_derivation_sources_source
            ON memory_derivation_sources (run_id, owner_id, source_memory_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_derivation_sources_derived
            ON memory_derivation_sources (
                run_id, owner_id, derived_memory_id, ordinal
            )
        """
    )
    op.execute(
        f"""
        ALTER TABLE memory_derivation_sources
            ADD CONSTRAINT fk_memory_derivation_sources_reconstruction
            FOREIGN KEY (run_id, owner_id, reconstruction_id)
            REFERENCES memory_reconstructions (
                run_id, owner_id, reconstruction_id
            )
            ON DELETE RESTRICT
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_traces_scope_observed_source
            ON memory_traces (run_id, owner_id, observed_source_id)
            WHERE observed_source_id IS NOT NULL
        """
    )
    # Backfill supersedes_memory_id as a single direct derivation edge.
    result = op.get_bind().execute(
        text(
            """
        INSERT INTO memory_derivation_sources (
            run_id, owner_id, derived_memory_id, source_memory_id, ordinal,
            reconstruction_id
        )
        SELECT
            run_id,
            owner_id,
            memory_id,
            supersedes_memory_id,
            0,
            NULL
        FROM memory_traces
        WHERE supersedes_memory_id IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM memory_traces AS parent
              WHERE parent.run_id = memory_traces.run_id
                AND parent.owner_id = memory_traces.owner_id
                AND parent.memory_id = memory_traces.supersedes_memory_id
          )
        ON CONFLICT DO NOTHING
            """
        )
    )
    backfill_count = result.rowcount if result.rowcount is not None else 0
    _LOG.info(
        "memory_reconstruction_backfill_complete",
        extra={
            "revision": revision,
            "table": "memory_derivation_sources",
            "backfill_count": backfill_count,
        },
    )
    # Append-only immutability for reconstruction provenance tables.
    for table in (
        "memory_reconstructions",
        "memory_reconstruction_sources",
        "memory_derivation_sources",
        "memory_concepts",
        "memory_entity_mentions",
        "memory_relations",
    ):
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION reject_{table}_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'append_only_violation:%', TG_TABLE_NAME
                    USING ERRCODE = 'integrity_constraint_violation';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_reject_mutation
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW
                EXECUTE PROCEDURE reject_{table}_mutation()
            """
        )
        _LOG.debug(
            "memory_reconstruction_immutability_trigger",
            extra={"revision": revision, "table": table},
        )
    # Trace content is immutable; access/forgetting metadata may still change.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_memory_traces_content_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.run_id IS DISTINCT FROM OLD.run_id
                OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
                OR NEW.memory_id IS DISTINCT FROM OLD.memory_id
                OR NEW.world_revision IS DISTINCT FROM OLD.world_revision
                OR NEW.emotional_salience IS DISTINCT FROM OLD.emotional_salience
                OR NEW.confidence IS DISTINCT FROM OLD.confidence
                OR NEW.source_kind IS DISTINCT FROM OLD.source_kind
                OR NEW.provenance_source_tick
                    IS DISTINCT FROM OLD.provenance_source_tick
                OR NEW.observed_source_id IS DISTINCT FROM OLD.observed_source_id
                OR NEW.speaker_id IS DISTINCT FROM OLD.speaker_id
                OR NEW.created_tick IS DISTINCT FROM OLD.created_tick
                OR NEW.source_tick IS DISTINCT FROM OLD.source_tick
                OR NEW.location_id IS DISTINCT FROM OLD.location_id
                OR NEW.context_tags IS DISTINCT FROM OLD.context_tags
                OR NEW.supersedes_memory_id
                    IS DISTINCT FROM OLD.supersedes_memory_id
                OR NEW.generation IS DISTINCT FROM OLD.generation
                OR NEW.embedding IS DISTINCT FROM OLD.embedding
                OR NEW.embedding_model IS DISTINCT FROM OLD.embedding_model
                OR NEW.embedding_version IS DISTINCT FROM OLD.embedding_version
                OR NEW.embedding_dimension
                    IS DISTINCT FROM OLD.embedding_dimension
            THEN
                RAISE EXCEPTION 'append_only_violation:memory_traces_content'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_memory_traces_reject_content_mutation
            BEFORE UPDATE ON memory_traces
            FOR EACH ROW
            EXECUTE PROCEDURE reject_memory_traces_content_mutation()
        """
    )
    _LOG.debug(
        "memory_reconstruction_immutability_trigger",
        extra={"revision": revision, "table": "memory_traces"},
    )
    _LOG.info(
        "memory_reconstruction_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_memory_traces_reject_content_mutation "
        "ON memory_traces"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_memory_traces_content_mutation()")
    for table in (
        "memory_relations",
        "memory_entity_mentions",
        "memory_concepts",
        "memory_derivation_sources",
        "memory_reconstruction_sources",
        "memory_reconstructions",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_mutation ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS reject_{table}_mutation()")
    op.execute("DROP INDEX IF EXISTS ix_memory_traces_scope_observed_source")
    op.execute("DROP TABLE IF EXISTS memory_derivation_sources CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_reconstruction_sources CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_reconstructions CASCADE")
