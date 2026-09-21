"""Subjective semantic beliefs and directed relationship history.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-21

Owner-scoped subjective agent models are stored separately from append-only
authoritative history. Tables are intentionally omitted from
reject_history_mutation triggers and AUTHORITATIVE_TABLES. Belief evidence
references memory_traces, never world_events.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.subjective_agent_models")

_STABLE_ID_LEN = 128
_MAX_POLICY = 64
_MAX_PREDICATE = 128
_MAX_CONCEPT = 256
_MAX_TEXT = 512
_MAX_OPERATION = 128

_APPEND_ONLY_TABLES = (
    "semantic_belief_revisions",
    "semantic_belief_evidence",
    "relationship_revisions",
    "relationship_dimension_states",
    "relationship_dimension_evidence",
    "subjective_operations",
)


def upgrade() -> None:
    _LOG.info(
        "subjective_agent_models_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )
    op.execute(
        f"""
        CREATE TABLE semantic_beliefs (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            belief_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            subject_kind VARCHAR(16) NOT NULL,
            subject_agent_id VARCHAR({_STABLE_ID_LEN}) NULL,
            subject_entity_id VARCHAR({_STABLE_ID_LEN}) NULL,
            subject_concept VARCHAR({_MAX_CONCEPT}) NULL,
            predicate VARCHAR({_MAX_PREDICATE}) NOT NULL,
            value_kind VARCHAR(16) NOT NULL,
            value_bool BOOLEAN NULL,
            value_number DOUBLE PRECISION NULL,
            value_text VARCHAR({_MAX_TEXT}) NULL,
            value_agent_id VARCHAR({_STABLE_ID_LEN}) NULL,
            value_entity_id VARCHAR({_STABLE_ID_LEN}) NULL,
            confidence DOUBLE PRECISION NOT NULL,
            support_mass DOUBLE PRECISION NOT NULL,
            contradiction_mass DOUBLE PRECISION NOT NULL,
            activation_state VARCHAR(16) NOT NULL,
            current_revision_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            revision_ordinal INTEGER NOT NULL,
            created_tick BIGINT NOT NULL,
            updated_tick BIGINT NOT NULL,
            policy_id VARCHAR({_MAX_POLICY}) NOT NULL,
            policy_version VARCHAR({_MAX_POLICY}) NOT NULL,
            evidence_support_count INTEGER NOT NULL,
            evidence_contradiction_count INTEGER NOT NULL,
            CONSTRAINT pk_semantic_beliefs
                PRIMARY KEY (run_id, owner_id, belief_id),
            CONSTRAINT fk_semantic_beliefs_run
                FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_sem_belief_ordinal_nonneg CHECK (revision_ordinal >= 0),
            CONSTRAINT ck_sem_belief_created_nonneg CHECK (created_tick >= 0),
            CONSTRAINT ck_sem_belief_tick_order
                CHECK (updated_tick >= created_tick),
            CONSTRAINT ck_sem_belief_conf
                CHECK (confidence >= 0.0 AND confidence <= 1.0),
            CONSTRAINT ck_sem_belief_support
                CHECK (support_mass >= 0.0 AND support_mass <= 1.0),
            CONSTRAINT ck_sem_belief_contradict
                CHECK (contradiction_mass >= 0.0 AND contradiction_mass <= 1.0),
            CONSTRAINT ck_sem_belief_activation
                CHECK (activation_state IN ('candidate', 'active', 'retired')),
            CONSTRAINT ck_sem_belief_subject_kind
                CHECK (subject_kind IN ('agent', 'entity', 'concept')),
            CONSTRAINT ck_sem_belief_value_kind
                CHECK (value_kind IN ('bool', 'number', 'text', 'agent', 'entity')),
            CONSTRAINT ck_sem_belief_evidence_counts
                CHECK (
                    evidence_support_count >= 0
                    AND evidence_contradiction_count >= 0
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_semantic_beliefs_scope_tick
            ON semantic_beliefs (run_id, owner_id, updated_tick)
        """
    )
    op.execute(
        f"""
        CREATE TABLE semantic_belief_revisions (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            belief_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            revision_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            ordinal INTEGER NOT NULL,
            logical_tick BIGINT NOT NULL,
            activation_state VARCHAR(16) NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            support_mass DOUBLE PRECISION NOT NULL,
            contradiction_mass DOUBLE PRECISION NOT NULL,
            previous_revision_id VARCHAR({_STABLE_ID_LEN}) NULL,
            policy_id VARCHAR({_MAX_POLICY}) NOT NULL,
            policy_version VARCHAR({_MAX_POLICY}) NOT NULL,
            claim_canonical TEXT NOT NULL,
            CONSTRAINT pk_semantic_belief_revisions
                PRIMARY KEY (run_id, owner_id, belief_id, revision_id),
            CONSTRAINT uq_sem_belief_rev_ordinal
                UNIQUE (run_id, owner_id, belief_id, ordinal),
            CONSTRAINT fk_sem_belief_rev_belief
                FOREIGN KEY (run_id, owner_id, belief_id)
                REFERENCES semantic_beliefs (run_id, owner_id, belief_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_sem_belief_rev_ordinal CHECK (ordinal >= 0),
            CONSTRAINT ck_sem_belief_rev_tick CHECK (logical_tick >= 0),
            CONSTRAINT ck_sem_belief_rev_activation
                CHECK (activation_state IN ('candidate', 'active', 'retired'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_sem_belief_rev_scope
            ON semantic_belief_revisions (
                run_id, owner_id, belief_id, ordinal
            )
        """
    )
    op.execute(
        f"""
        CREATE TABLE semantic_belief_evidence (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            belief_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            revision_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            ordinal INTEGER NOT NULL,
            memory_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            lineage_root_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            stance VARCHAR(16) NOT NULL,
            contribution DOUBLE PRECISION NOT NULL,
            CONSTRAINT pk_semantic_belief_evidence
                PRIMARY KEY (
                    run_id, owner_id, belief_id, revision_id, ordinal
                ),
            CONSTRAINT uq_sem_belief_ev_memory
                UNIQUE (
                    run_id, owner_id, belief_id, revision_id, memory_id
                ),
            CONSTRAINT fk_sem_belief_ev_rev
                FOREIGN KEY (run_id, owner_id, belief_id, revision_id)
                REFERENCES semantic_belief_revisions (
                    run_id, owner_id, belief_id, revision_id
                )
                ON DELETE RESTRICT,
            CONSTRAINT fk_sem_belief_ev_memory
                FOREIGN KEY (run_id, owner_id, memory_id)
                REFERENCES memory_traces (run_id, owner_id, memory_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_sem_belief_ev_ordinal CHECK (ordinal >= 0),
            CONSTRAINT ck_sem_belief_ev_stance
                CHECK (stance IN ('supporting', 'contradicting')),
            CONSTRAINT ck_sem_belief_ev_contribution
                CHECK (contribution >= 0.0 AND contribution <= 1.0)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE directed_relationships (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            source_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            relationship_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            target_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            activation_state VARCHAR(16) NOT NULL,
            current_revision_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            revision_ordinal INTEGER NOT NULL,
            created_tick BIGINT NOT NULL,
            updated_tick BIGINT NOT NULL,
            policy_id VARCHAR({_MAX_POLICY}) NOT NULL,
            policy_version VARCHAR({_MAX_POLICY}) NOT NULL,
            CONSTRAINT pk_directed_relationships
                PRIMARY KEY (run_id, source_id, relationship_id),
            CONSTRAINT uq_directed_rel_pair
                UNIQUE (run_id, source_id, target_id),
            CONSTRAINT fk_directed_rel_run
                FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_directed_rel_not_self
                CHECK (source_id <> target_id),
            CONSTRAINT ck_directed_rel_ordinal CHECK (revision_ordinal >= 0),
            CONSTRAINT ck_directed_rel_created CHECK (created_tick >= 0),
            CONSTRAINT ck_directed_rel_tick_order
                CHECK (updated_tick >= created_tick),
            CONSTRAINT ck_directed_rel_activation
                CHECK (activation_state IN ('candidate', 'active', 'retired'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_directed_rel_source_tick
            ON directed_relationships (run_id, source_id, updated_tick)
        """
    )
    op.execute(
        f"""
        CREATE TABLE relationship_revisions (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            source_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            relationship_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            revision_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            target_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            ordinal INTEGER NOT NULL,
            logical_tick BIGINT NOT NULL,
            activation_state VARCHAR(16) NOT NULL,
            previous_revision_id VARCHAR({_STABLE_ID_LEN}) NULL,
            policy_id VARCHAR({_MAX_POLICY}) NOT NULL,
            policy_version VARCHAR({_MAX_POLICY}) NOT NULL,
            CONSTRAINT pk_relationship_revisions
                PRIMARY KEY (
                    run_id, source_id, relationship_id, revision_id
                ),
            CONSTRAINT uq_rel_rev_ordinal
                UNIQUE (run_id, source_id, relationship_id, ordinal),
            CONSTRAINT fk_rel_rev_profile
                FOREIGN KEY (run_id, source_id, relationship_id)
                REFERENCES directed_relationships (
                    run_id, source_id, relationship_id
                )
                ON DELETE RESTRICT,
            CONSTRAINT ck_rel_rev_ordinal CHECK (ordinal >= 0),
            CONSTRAINT ck_rel_rev_tick CHECK (logical_tick >= 0),
            CONSTRAINT ck_rel_rev_activation
                CHECK (activation_state IN ('candidate', 'active', 'retired'))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE relationship_dimension_states (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            source_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            relationship_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            revision_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            dimension VARCHAR(32) NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            support_mass DOUBLE PRECISION NOT NULL,
            contradiction_mass DOUBLE PRECISION NOT NULL,
            logical_tick BIGINT NOT NULL,
            policy_id VARCHAR({_MAX_POLICY}) NOT NULL,
            policy_version VARCHAR({_MAX_POLICY}) NOT NULL,
            CONSTRAINT pk_relationship_dimension_states
                PRIMARY KEY (
                    run_id, source_id, relationship_id, revision_id, dimension
                ),
            CONSTRAINT fk_rel_dim_rev
                FOREIGN KEY (
                    run_id, source_id, relationship_id, revision_id
                )
                REFERENCES relationship_revisions (
                    run_id, source_id, relationship_id, revision_id
                )
                ON DELETE RESTRICT,
            CONSTRAINT ck_rel_dim_closed
                CHECK (
                    dimension IN (
                        'trust','fear','affection','debt','respect',
                        'resentment','familiarity','dependency'
                    )
                ),
            CONSTRAINT ck_rel_dim_value
                CHECK (value >= -1.0 AND value <= 1.0),
            CONSTRAINT ck_rel_dim_conf
                CHECK (confidence >= 0.0 AND confidence <= 1.0),
            CONSTRAINT ck_rel_dim_tick CHECK (logical_tick >= 0)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE relationship_dimension_evidence (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            source_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            relationship_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            revision_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            dimension VARCHAR(32) NOT NULL,
            ordinal INTEGER NOT NULL,
            memory_ref VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            lineage_root_ref VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            contribution DOUBLE PRECISION NOT NULL,
            CONSTRAINT pk_relationship_dimension_evidence
                PRIMARY KEY (
                    run_id, source_id, relationship_id, revision_id,
                    dimension, ordinal
                ),
            CONSTRAINT uq_rel_dim_ev_memory
                UNIQUE (
                    run_id, source_id, relationship_id, revision_id,
                    dimension, memory_ref
                ),
            CONSTRAINT fk_rel_dim_ev_state
                FOREIGN KEY (
                    run_id, source_id, relationship_id, revision_id, dimension
                )
                REFERENCES relationship_dimension_states (
                    run_id, source_id, relationship_id, revision_id, dimension
                )
                ON DELETE RESTRICT,
            CONSTRAINT ck_rel_dim_ev_ordinal CHECK (ordinal >= 0),
            CONSTRAINT ck_rel_dim_ev_contribution
                CHECK (contribution >= 0.0 AND contribution <= 1.0)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE subjective_operations (
            run_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            owner_id VARCHAR({_STABLE_ID_LEN}) NOT NULL,
            operation_id VARCHAR({_MAX_OPERATION}) NOT NULL,
            fingerprint VARCHAR(64) NOT NULL,
            revision INTEGER NOT NULL,
            logical_tick BIGINT NOT NULL,
            memory_written_count INTEGER NOT NULL,
            belief_revision_count INTEGER NOT NULL,
            relationship_revision_count INTEGER NOT NULL,
            CONSTRAINT pk_subjective_operations
                PRIMARY KEY (run_id, owner_id, operation_id),
            CONSTRAINT fk_subj_ops_run
                FOREIGN KEY (run_id) REFERENCES simulation_runs (run_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_subj_ops_revision CHECK (revision >= 0),
            CONSTRAINT ck_subj_ops_tick CHECK (logical_tick >= 0),
            CONSTRAINT ck_subj_ops_fingerprint
                CHECK (char_length(fingerprint) = 64)
        )
        """
    )
    for table in _APPEND_ONLY_TABLES:
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
            "subjective_immutability_trigger",
            extra={"revision": revision, "table": table},
        )
    _LOG.info(
        "subjective_agent_models_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    for table in reversed(_APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_reject_mutation ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS reject_{table}_mutation()")
    op.execute("DROP TABLE IF EXISTS relationship_dimension_evidence CASCADE")
    op.execute("DROP TABLE IF EXISTS relationship_dimension_states CASCADE")
    op.execute("DROP TABLE IF EXISTS relationship_revisions CASCADE")
    op.execute("DROP TABLE IF EXISTS directed_relationships CASCADE")
    op.execute("DROP TABLE IF EXISTS semantic_belief_evidence CASCADE")
    op.execute("DROP TABLE IF EXISTS semantic_belief_revisions CASCADE")
    op.execute("DROP TABLE IF EXISTS semantic_beliefs CASCADE")
    op.execute("DROP TABLE IF EXISTS subjective_operations CASCADE")
    _LOG.info(
        "subjective_agent_models_migration_downgraded",
        extra={"revision": revision, "operation": "downgrade"},
    )
