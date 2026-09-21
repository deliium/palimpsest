"""Owner-scoped episodic memory tables with optional pgvector embeddings.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-21

Mutable subjective memory is stored separately from append-only authoritative
history. Tables are intentionally omitted from reject_history_mutation triggers.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STABLE_ID_LEN = 128
_MAX_CONCEPT_CHARS = 256
_MAX_LABEL_CHARS = 256
_MAX_PREDICATE_CHARS = 128
_MAX_EMBEDDING_DIM = 4096
_MAX_POLICY_ID_CHARS = 64


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE memory_traces (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            world_revision BIGINT NOT NULL,
            emotional_salience DOUBLE PRECISION NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            source_kind TEXT NOT NULL,
            provenance_source_tick BIGINT NOT NULL,
            observed_source_id VARCHAR({_STABLE_ID_LEN}),
            speaker_id VARCHAR({_STABLE_ID_LEN}),
            created_tick BIGINT NOT NULL,
            source_tick BIGINT NOT NULL,
            last_access_tick BIGINT NOT NULL,
            access_count BIGINT NOT NULL,
            expires_at_tick BIGINT,
            forgotten_at_tick BIGINT,
            location_id VARCHAR({_STABLE_ID_LEN}),
            context_tags TEXT[] NOT NULL DEFAULT '{{}}'::text[],
            supersedes_memory_id VARCHAR({_STABLE_ID_LEN}),
            generation BIGINT NOT NULL DEFAULT 0,
            embedding vector,
            embedding_model TEXT,
            embedding_version TEXT,
            embedding_dimension INTEGER,
            is_active BOOLEAN GENERATED ALWAYS AS (forgotten_at_tick IS NULL) STORED,
            CONSTRAINT pk_memory_traces
                PRIMARY KEY (run_id, owner_id, memory_id),
            CONSTRAINT fk_memory_traces_run
                FOREIGN KEY (run_id)
                REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_memory_traces_world_revision_nonneg
                CHECK (world_revision >= 0),
            CONSTRAINT ck_memory_traces_salience_unit
                CHECK (emotional_salience >= 0.0 AND emotional_salience <= 1.0),
            CONSTRAINT ck_memory_traces_confidence_unit
                CHECK (confidence >= 0.0 AND confidence <= 1.0),
            CONSTRAINT ck_memory_traces_salience_finite
                CHECK (
                    emotional_salience::text <> 'NaN'
                    AND emotional_salience::float8 != 'Infinity'::float8
                    AND emotional_salience::float8 != '-Infinity'::float8
                ),
            CONSTRAINT ck_memory_traces_confidence_finite
                CHECK (
                    confidence::text <> 'NaN'
                    AND confidence::float8 != 'Infinity'::float8
                    AND confidence::float8 != '-Infinity'::float8
                ),
            CONSTRAINT ck_memory_traces_source_kind_closed
                CHECK (source_kind IN ('direct_observation', 'communicated')),
            CONSTRAINT ck_memory_traces_prov_source_tick_nonneg
                CHECK (provenance_source_tick >= 0),
            CONSTRAINT ck_memory_traces_created_tick_nonneg
                CHECK (created_tick >= 0),
            CONSTRAINT ck_memory_traces_source_tick_nonneg
                CHECK (source_tick >= 0),
            CONSTRAINT ck_memory_traces_last_access_tick_nonneg
                CHECK (last_access_tick >= 0),
            CONSTRAINT ck_memory_traces_access_count_nonneg
                CHECK (access_count >= 0),
            CONSTRAINT ck_memory_traces_last_access_after_created
                CHECK (last_access_tick >= created_tick),
            CONSTRAINT ck_memory_traces_expires_after_created
                CHECK (expires_at_tick IS NULL OR expires_at_tick >= created_tick),
            CONSTRAINT ck_memory_traces_forgotten_after_created
                CHECK (
                    forgotten_at_tick IS NULL OR forgotten_at_tick >= created_tick
                ),
            CONSTRAINT ck_memory_traces_source_kind_speaker
                CHECK (
                    (source_kind = 'direct_observation' AND speaker_id IS NULL)
                    OR (source_kind = 'communicated' AND speaker_id IS NOT NULL)
                ),
            CONSTRAINT ck_memory_traces_generation_nonneg
                CHECK (generation >= 0),
            CONSTRAINT ck_memory_traces_lineage_not_self
                CHECK (
                    supersedes_memory_id IS NULL
                    OR supersedes_memory_id <> memory_id
                ),
            CONSTRAINT ck_memory_traces_embedding_metadata
                CHECK (
                    (
                        embedding IS NULL
                        AND embedding_model IS NULL
                        AND embedding_version IS NULL
                        AND embedding_dimension IS NULL
                    )
                    OR (
                        embedding IS NOT NULL
                        AND embedding_model IS NOT NULL
                        AND embedding_version IS NOT NULL
                        AND embedding_dimension IS NOT NULL
                        AND embedding_dimension BETWEEN 1 AND {_MAX_EMBEDDING_DIM}
                        AND embedding_dimension = vector_dims(embedding)
                    )
                ),
            CONSTRAINT ck_memory_traces_embedding_model_len
                CHECK (
                    embedding_model IS NULL
                    OR char_length(embedding_model)
                        BETWEEN 1 AND {_MAX_POLICY_ID_CHARS}
                ),
            CONSTRAINT ck_memory_traces_embedding_version_len
                CHECK (
                    embedding_version IS NULL
                    OR char_length(embedding_version)
                        BETWEEN 1 AND {_MAX_POLICY_ID_CHARS}
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_traces_scope_active_created
            ON memory_traces (run_id, owner_id, is_active, created_tick)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_traces_scope_source_kind
            ON memory_traces (run_id, owner_id, source_kind)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_traces_scope_location
            ON memory_traces (run_id, owner_id, location_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_traces_context_tags
            ON memory_traces USING gin (context_tags)
        """
    )

    op.execute(
        f"""
        CREATE TABLE memory_concepts (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            mention_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            ordinal INTEGER NOT NULL,
            concept TEXT NOT NULL,
            CONSTRAINT pk_memory_concepts
                PRIMARY KEY (run_id, owner_id, memory_id, mention_id),
            CONSTRAINT fk_memory_concepts_trace
                FOREIGN KEY (run_id, owner_id, memory_id)
                REFERENCES memory_traces (run_id, owner_id, memory_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_memory_concepts_ordinal
                UNIQUE (run_id, owner_id, memory_id, ordinal),
            CONSTRAINT ck_memory_concepts_ordinal_nonneg
                CHECK (ordinal >= 0),
            CONSTRAINT ck_memory_concepts_concept_len
                CHECK (char_length(concept) BETWEEN 1 AND {_MAX_CONCEPT_CHARS})
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_concepts_scope_concept
            ON memory_concepts (run_id, owner_id, concept)
        """
    )

    op.execute(
        f"""
        CREATE TABLE memory_entity_mentions (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            mention_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            ordinal INTEGER NOT NULL,
            label TEXT NOT NULL,
            entity_id VARCHAR({_STABLE_ID_LEN}),
            CONSTRAINT pk_memory_entity_mentions
                PRIMARY KEY (run_id, owner_id, memory_id, mention_id),
            CONSTRAINT fk_memory_entity_mentions_trace
                FOREIGN KEY (run_id, owner_id, memory_id)
                REFERENCES memory_traces (run_id, owner_id, memory_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_memory_entity_mentions_ordinal
                UNIQUE (run_id, owner_id, memory_id, ordinal),
            CONSTRAINT ck_memory_entity_mentions_ordinal_nonneg
                CHECK (ordinal >= 0),
            CONSTRAINT ck_memory_entity_mentions_label_len
                CHECK (char_length(label) BETWEEN 1 AND {_MAX_LABEL_CHARS})
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_entity_mentions_scope_entity
            ON memory_entity_mentions (run_id, owner_id, entity_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_entity_mentions_scope_label
            ON memory_entity_mentions (run_id, owner_id, label)
        """
    )

    op.execute(
        f"""
        CREATE TABLE memory_relations (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            relation_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            ordinal INTEGER NOT NULL,
            predicate TEXT NOT NULL,
            subject_kind TEXT NOT NULL,
            subject_mention_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            object_kind TEXT NOT NULL,
            object_mention_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            CONSTRAINT pk_memory_relations
                PRIMARY KEY (run_id, owner_id, memory_id, relation_id),
            CONSTRAINT fk_memory_relations_trace
                FOREIGN KEY (run_id, owner_id, memory_id)
                REFERENCES memory_traces (run_id, owner_id, memory_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_memory_relations_ordinal
                UNIQUE (run_id, owner_id, memory_id, ordinal),
            CONSTRAINT ck_memory_relations_ordinal_nonneg
                CHECK (ordinal >= 0),
            CONSTRAINT ck_memory_relations_predicate_len
                CHECK (
                    char_length(predicate) BETWEEN 1 AND {_MAX_PREDICATE_CHARS}
                ),
            CONSTRAINT ck_memory_relations_subject_kind_closed
                CHECK (subject_kind IN ('concept', 'entity')),
            CONSTRAINT ck_memory_relations_object_kind_closed
                CHECK (object_kind IN ('concept', 'entity'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_relations_scope_predicate
            ON memory_relations (run_id, owner_id, predicate)
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_memory_relation_endpoints()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            subject_ok boolean;
            object_ok boolean;
            mention_collision boolean;
        BEGIN
            IF NEW.subject_kind = 'concept' THEN
                SELECT EXISTS (
                    SELECT 1 FROM memory_concepts c
                    WHERE c.run_id = NEW.run_id
                      AND c.owner_id = NEW.owner_id
                      AND c.memory_id = NEW.memory_id
                      AND c.mention_id = NEW.subject_mention_id
                ) INTO subject_ok;
            ELSE
                SELECT EXISTS (
                    SELECT 1 FROM memory_entity_mentions e
                    WHERE e.run_id = NEW.run_id
                      AND e.owner_id = NEW.owner_id
                      AND e.memory_id = NEW.memory_id
                      AND e.mention_id = NEW.subject_mention_id
                ) INTO subject_ok;
            END IF;

            IF NEW.object_kind = 'concept' THEN
                SELECT EXISTS (
                    SELECT 1 FROM memory_concepts c
                    WHERE c.run_id = NEW.run_id
                      AND c.owner_id = NEW.owner_id
                      AND c.memory_id = NEW.memory_id
                      AND c.mention_id = NEW.object_mention_id
                ) INTO object_ok;
            ELSE
                SELECT EXISTS (
                    SELECT 1 FROM memory_entity_mentions e
                    WHERE e.run_id = NEW.run_id
                      AND e.owner_id = NEW.owner_id
                      AND e.memory_id = NEW.memory_id
                      AND e.mention_id = NEW.object_mention_id
                ) INTO object_ok;
            END IF;

            IF NOT subject_ok OR NOT object_ok THEN
                RAISE EXCEPTION 'relation_endpoint_integrity'
                    USING ERRCODE = 'check_violation';
            END IF;

            SELECT EXISTS (
                SELECT 1 FROM memory_concepts c
                WHERE c.run_id = NEW.run_id
                  AND c.owner_id = NEW.owner_id
                  AND c.memory_id = NEW.memory_id
                  AND c.mention_id = NEW.relation_id
            ) OR EXISTS (
                SELECT 1 FROM memory_entity_mentions e
                WHERE e.run_id = NEW.run_id
                  AND e.owner_id = NEW.owner_id
                  AND e.memory_id = NEW.memory_id
                  AND e.mention_id = NEW.relation_id
            ) INTO mention_collision;

            IF mention_collision THEN
                RAISE EXCEPTION 'relation_id_collides_mention'
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_memory_relations_endpoint_integrity
        BEFORE INSERT OR UPDATE ON memory_relations
        FOR EACH ROW
        EXECUTE PROCEDURE check_memory_relation_endpoints()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_memory_mention_id_unique()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            collision boolean;
        BEGIN
            IF TG_TABLE_NAME = 'memory_concepts' THEN
                SELECT EXISTS (
                    SELECT 1 FROM memory_entity_mentions e
                    WHERE e.run_id = NEW.run_id
                      AND e.owner_id = NEW.owner_id
                      AND e.memory_id = NEW.memory_id
                      AND e.mention_id = NEW.mention_id
                ) INTO collision;
            ELSE
                SELECT EXISTS (
                    SELECT 1 FROM memory_concepts c
                    WHERE c.run_id = NEW.run_id
                      AND c.owner_id = NEW.owner_id
                      AND c.memory_id = NEW.memory_id
                      AND c.mention_id = NEW.mention_id
                ) INTO collision;
            END IF;

            IF collision THEN
                RAISE EXCEPTION 'mention_id_collision'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_memory_concepts_mention_unique
        BEFORE INSERT OR UPDATE ON memory_concepts
        FOR EACH ROW
        EXECUTE PROCEDURE check_memory_mention_id_unique()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_memory_entity_mentions_mention_unique
        BEFORE INSERT OR UPDATE ON memory_entity_mentions
        FOR EACH ROW
        EXECUTE PROCEDURE check_memory_mention_id_unique()
        """
    )

    op.execute(
        f"""
        CREATE TABLE memory_access_ops (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            operation_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            access_tick BIGINT NOT NULL,
            CONSTRAINT pk_memory_access_ops
                PRIMARY KEY (run_id, owner_id, operation_id, memory_id),
            CONSTRAINT fk_memory_access_ops_trace
                FOREIGN KEY (run_id, owner_id, memory_id)
                REFERENCES memory_traces (run_id, owner_id, memory_id)
                ON DELETE CASCADE,
            CONSTRAINT ck_memory_access_ops_access_tick_nonneg
                CHECK (access_tick >= 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_access_ops_scope_operation
            ON memory_access_ops (run_id, owner_id, operation_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memory_access_ops CASCADE")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_memory_entity_mentions_mention_unique "
        "ON memory_entity_mentions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_memory_concepts_mention_unique ON memory_concepts"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_memory_relations_endpoint_integrity "
        "ON memory_relations"
    )
    op.execute("DROP FUNCTION IF EXISTS check_memory_mention_id_unique()")
    op.execute("DROP FUNCTION IF EXISTS check_memory_relation_endpoints()")
    op.execute("DROP TABLE IF EXISTS memory_relations CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_entity_mentions CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_concepts CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_traces CASCADE")
