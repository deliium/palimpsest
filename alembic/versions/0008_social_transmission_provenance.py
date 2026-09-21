"""Social transmission provenance on memory traces and belief evidence.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-22

Adds owner-scoped transmission metadata columns for communicated memory
traces and applied testimony-factor columns on semantic belief evidence.
Does not alter authoritative event history or AUTHORITATIVE_TABLES.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG = logging.getLogger("alembic.social_transmission_provenance")

_STABLE_ID_LEN = 128
_MAX_POLICY = 64


def upgrade() -> None:
    _LOG.info(
        "social_transmission_migration_start",
        extra={"revision": revision, "operation": "upgrade"},
    )
    op.execute(
        f"""
        ALTER TABLE memory_traces
            ADD COLUMN transmission_communication_id VARCHAR({_STABLE_ID_LEN}) NULL,
            ADD COLUMN transmission_action_kind VARCHAR(8) NULL,
            ADD COLUMN transmission_hop_count INTEGER NULL,
            ADD COLUMN transmission_sender_confidence DOUBLE PRECISION NULL,
            ADD COLUMN transmission_receiver_confidence DOUBLE PRECISION NULL,
            ADD COLUMN transmission_content_fingerprint VARCHAR({_STABLE_ID_LEN}) NULL,
            ADD COLUMN transmission_parent_communication_id
                VARCHAR({_STABLE_ID_LEN}) NULL,
            ADD COLUMN transmission_source_agent_chain TEXT[] NULL,
            ADD COLUMN transmission_root_id VARCHAR({_STABLE_ID_LEN}) NULL,
            ADD COLUMN transmission_policy_version VARCHAR({_MAX_POLICY}) NULL
        """
    )
    op.execute(
        """
        ALTER TABLE memory_traces
            ADD CONSTRAINT ck_memory_traces_transmission_shape
            CHECK (
                (
                    source_kind = 'direct_observation'
                    AND transmission_communication_id IS NULL
                    AND transmission_action_kind IS NULL
                    AND transmission_hop_count IS NULL
                    AND transmission_sender_confidence IS NULL
                    AND transmission_receiver_confidence IS NULL
                    AND transmission_content_fingerprint IS NULL
                    AND transmission_parent_communication_id IS NULL
                    AND transmission_source_agent_chain IS NULL
                    AND transmission_root_id IS NULL
                    AND transmission_policy_version IS NULL
                )
                OR (
                    source_kind = 'communicated'
                    AND transmission_communication_id IS NOT NULL
                    AND transmission_action_kind IN ('talk', 'ask', 'tell')
                    AND transmission_hop_count IS NOT NULL
                    AND transmission_hop_count >= 0
                    AND transmission_sender_confidence IS NOT NULL
                    AND transmission_sender_confidence >= 0.0
                    AND transmission_sender_confidence <= 1.0
                    AND transmission_receiver_confidence IS NOT NULL
                    AND transmission_receiver_confidence >= 0.0
                    AND transmission_receiver_confidence <= 1.0
                    AND transmission_content_fingerprint IS NOT NULL
                    AND transmission_source_agent_chain IS NOT NULL
                    AND cardinality(transmission_source_agent_chain) >= 1
                    AND transmission_hop_count =
                        cardinality(transmission_source_agent_chain) - 1
                    AND transmission_root_id IS NOT NULL
                    AND transmission_policy_version IS NOT NULL
                )
            )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_memory_traces_scope_transmission_root
            ON memory_traces (run_id, owner_id, transmission_root_id)
            WHERE transmission_root_id IS NOT NULL
        """
    )
    op.execute(
        f"""
        ALTER TABLE semantic_belief_evidence
            ADD COLUMN testimony_decision VARCHAR(16) NULL,
            ADD COLUMN testimony_hop_count INTEGER NULL,
            ADD COLUMN testimony_trust DOUBLE PRECISION NULL,
            ADD COLUMN testimony_trust_confidence DOUBLE PRECISION NULL,
            ADD COLUMN testimony_sender_confidence DOUBLE PRECISION NULL,
            ADD COLUMN testimony_receiver_confidence DOUBLE PRECISION NULL,
            ADD COLUMN testimony_context_relevance DOUBLE PRECISION NULL,
            ADD COLUMN testimony_hop_attenuation DOUBLE PRECISION NULL,
            ADD COLUMN testimony_base_contribution DOUBLE PRECISION NULL,
            ADD COLUMN testimony_adjusted_contribution DOUBLE PRECISION NULL,
            ADD COLUMN testimony_confidence_delta DOUBLE PRECISION NULL,
            ADD COLUMN testimony_policy_version VARCHAR({_MAX_POLICY}) NULL
        """
    )
    op.execute(
        """
        ALTER TABLE semantic_belief_evidence
            ADD CONSTRAINT ck_sem_belief_ev_testimony_shape
            CHECK (
                (
                    testimony_decision IS NULL
                    AND testimony_hop_count IS NULL
                    AND testimony_trust IS NULL
                    AND testimony_trust_confidence IS NULL
                    AND testimony_sender_confidence IS NULL
                    AND testimony_receiver_confidence IS NULL
                    AND testimony_context_relevance IS NULL
                    AND testimony_hop_attenuation IS NULL
                    AND testimony_base_contribution IS NULL
                    AND testimony_adjusted_contribution IS NULL
                    AND testimony_confidence_delta IS NULL
                    AND testimony_policy_version IS NULL
                )
                OR (
                    testimony_decision IN (
                        'accept', 'discount', 'contradict', 'defer'
                    )
                    AND testimony_hop_count IS NOT NULL
                    AND testimony_hop_count >= 0
                    AND testimony_trust IS NOT NULL
                    AND testimony_trust >= 0.0 AND testimony_trust <= 1.0
                    AND testimony_trust_confidence IS NOT NULL
                    AND testimony_trust_confidence >= 0.0
                    AND testimony_trust_confidence <= 1.0
                    AND testimony_sender_confidence IS NOT NULL
                    AND testimony_sender_confidence >= 0.0
                    AND testimony_sender_confidence <= 1.0
                    AND testimony_receiver_confidence IS NOT NULL
                    AND testimony_receiver_confidence >= 0.0
                    AND testimony_receiver_confidence <= 1.0
                    AND testimony_context_relevance IS NOT NULL
                    AND testimony_context_relevance >= 0.0
                    AND testimony_context_relevance <= 1.0
                    AND testimony_hop_attenuation IS NOT NULL
                    AND testimony_hop_attenuation >= 0.0
                    AND testimony_hop_attenuation <= 1.0
                    AND testimony_base_contribution IS NOT NULL
                    AND testimony_base_contribution >= 0.0
                    AND testimony_base_contribution <= 1.0
                    AND testimony_adjusted_contribution IS NOT NULL
                    AND testimony_adjusted_contribution >= 0.0
                    AND testimony_adjusted_contribution <= 1.0
                    AND testimony_confidence_delta IS NOT NULL
                    AND testimony_confidence_delta >= -1.0
                    AND testimony_confidence_delta <= 1.0
                    AND testimony_policy_version IS NOT NULL
                )
            )
        """
    )
    _LOG.info(
        "social_transmission_migration_complete",
        extra={"revision": revision, "operation": "upgrade"},
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE semantic_belief_evidence "
        "DROP CONSTRAINT IF EXISTS ck_sem_belief_ev_testimony_shape"
    )
    op.execute(
        """
        ALTER TABLE semantic_belief_evidence
            DROP COLUMN IF EXISTS testimony_decision,
            DROP COLUMN IF EXISTS testimony_hop_count,
            DROP COLUMN IF EXISTS testimony_trust,
            DROP COLUMN IF EXISTS testimony_trust_confidence,
            DROP COLUMN IF EXISTS testimony_sender_confidence,
            DROP COLUMN IF EXISTS testimony_receiver_confidence,
            DROP COLUMN IF EXISTS testimony_context_relevance,
            DROP COLUMN IF EXISTS testimony_hop_attenuation,
            DROP COLUMN IF EXISTS testimony_base_contribution,
            DROP COLUMN IF EXISTS testimony_adjusted_contribution,
            DROP COLUMN IF EXISTS testimony_confidence_delta,
            DROP COLUMN IF EXISTS testimony_policy_version
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_memory_traces_scope_transmission_root")
    op.execute(
        "ALTER TABLE memory_traces "
        "DROP CONSTRAINT IF EXISTS ck_memory_traces_transmission_shape"
    )
    op.execute(
        """
        ALTER TABLE memory_traces
            DROP COLUMN IF EXISTS transmission_communication_id,
            DROP COLUMN IF EXISTS transmission_action_kind,
            DROP COLUMN IF EXISTS transmission_hop_count,
            DROP COLUMN IF EXISTS transmission_sender_confidence,
            DROP COLUMN IF EXISTS transmission_receiver_confidence,
            DROP COLUMN IF EXISTS transmission_content_fingerprint,
            DROP COLUMN IF EXISTS transmission_parent_communication_id,
            DROP COLUMN IF EXISTS transmission_source_agent_chain,
            DROP COLUMN IF EXISTS transmission_root_id,
            DROP COLUMN IF EXISTS transmission_policy_version
        """
    )
    _LOG.info(
        "social_transmission_migration_downgraded",
        extra={"revision": revision, "operation": "downgrade"},
    )
