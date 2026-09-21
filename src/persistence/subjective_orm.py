"""SQLAlchemy mappings for subjective beliefs and directed relationships.

Subjective tables are excluded from ``AUTHORITATIVE_TABLES`` and objective replay.
Importing this module registers tables on the shared metadata.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.orm import Base

_STABLE_ID_LEN: Final[int] = 128
_MAX_POLICY: Final[int] = 64
_MAX_PREDICATE: Final[int] = 128
_MAX_CONCEPT: Final[int] = 256
_MAX_TEXT: Final[int] = 512
_MAX_OPERATION: Final[int] = 128

SUBJECTIVE_AGENT_TABLES: Final[tuple[str, ...]] = (
    "semantic_beliefs",
    "semantic_belief_revisions",
    "semantic_belief_evidence",
    "directed_relationships",
    "relationship_revisions",
    "relationship_dimension_states",
    "relationship_dimension_evidence",
    "subjective_operations",
)

__all__ = [
    "SUBJECTIVE_AGENT_TABLES",
    "DirectedRelationshipOrm",
    "RelationshipDimensionEvidenceOrm",
    "RelationshipDimensionStateOrm",
    "RelationshipRevisionOrm",
    "SemanticBeliefEvidenceOrm",
    "SemanticBeliefOrm",
    "SemanticBeliefRevisionOrm",
    "SubjectiveOperationOrm",
]


class SemanticBeliefOrm(Base):
    """Mutable semantic-belief head for one owner scope."""

    __tablename__ = "semantic_beliefs"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "owner_id", "belief_id"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_semantic_beliefs_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision_ordinal >= 0", name="ck_sem_belief_ordinal_nonneg"),
        CheckConstraint("created_tick >= 0", name="ck_sem_belief_created_nonneg"),
        CheckConstraint(
            "updated_tick >= created_tick", name="ck_sem_belief_tick_order"
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_sem_belief_conf"
        ),
        CheckConstraint(
            "support_mass >= 0.0 AND support_mass <= 1.0",
            name="ck_sem_belief_support",
        ),
        CheckConstraint(
            "contradiction_mass >= 0.0 AND contradiction_mass <= 1.0",
            name="ck_sem_belief_contradict",
        ),
        CheckConstraint(
            "activation_state IN ('candidate', 'active', 'retired')",
            name="ck_sem_belief_activation",
        ),
        CheckConstraint(
            "subject_kind IN ('agent', 'entity', 'concept')",
            name="ck_sem_belief_subject_kind",
        ),
        CheckConstraint(
            "value_kind IN ('bool', 'number', 'text', 'agent', 'entity')",
            name="ck_sem_belief_value_kind",
        ),
        CheckConstraint(
            "evidence_support_count >= 0 AND evidence_contradiction_count >= 0",
            name="ck_sem_belief_evidence_counts",
        ),
        Index("ix_semantic_beliefs_scope_tick", "run_id", "owner_id", "updated_tick"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    belief_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    subject_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_agent_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN))
    subject_entity_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN))
    subject_concept: Mapped[str | None] = mapped_column(String(_MAX_CONCEPT))
    predicate: Mapped[str] = mapped_column(String(_MAX_PREDICATE), nullable=False)
    value_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    value_number: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(_MAX_TEXT))
    value_agent_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN))
    value_entity_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    support_mass: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction_mass: Mapped[float] = mapped_column(Float, nullable=False)
    activation_state: Mapped[str] = mapped_column(String(16), nullable=False)
    current_revision_id: Mapped[str] = mapped_column(
        String(_STABLE_ID_LEN), nullable=False
    )
    revision_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)
    evidence_support_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_contradiction_count: Mapped[int] = mapped_column(Integer, nullable=False)


class SemanticBeliefRevisionOrm(Base):
    """Append-only semantic belief revision."""

    __tablename__ = "semantic_belief_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "owner_id", "belief_id", "revision_id"),
        ForeignKeyConstraint(
            ["run_id", "owner_id", "belief_id"],
            [
                "semantic_beliefs.run_id",
                "semantic_beliefs.owner_id",
                "semantic_beliefs.belief_id",
            ],
            name="fk_sem_belief_rev_belief",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "run_id",
            "owner_id",
            "belief_id",
            "ordinal",
            name="uq_sem_belief_rev_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ck_sem_belief_rev_ordinal"),
        CheckConstraint("logical_tick >= 0", name="ck_sem_belief_rev_tick"),
        CheckConstraint(
            "activation_state IN ('candidate', 'active', 'retired')",
            name="ck_sem_belief_rev_activation",
        ),
        Index(
            "ix_sem_belief_rev_scope",
            "run_id",
            "owner_id",
            "belief_id",
            "ordinal",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    belief_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    logical_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    activation_state: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    support_mass: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction_mass: Mapped[float] = mapped_column(Float, nullable=False)
    previous_revision_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN))
    policy_id: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)
    claim_canonical: Mapped[str] = mapped_column(Text, nullable=False)


class SemanticBeliefEvidenceOrm(Base):
    """Append-only evidence row referencing an owned memory trace."""

    __tablename__ = "semantic_belief_evidence"
    __table_args__ = (
        PrimaryKeyConstraint(
            "run_id", "owner_id", "belief_id", "revision_id", "ordinal"
        ),
        ForeignKeyConstraint(
            ["run_id", "owner_id", "belief_id", "revision_id"],
            [
                "semantic_belief_revisions.run_id",
                "semantic_belief_revisions.owner_id",
                "semantic_belief_revisions.belief_id",
                "semantic_belief_revisions.revision_id",
            ],
            name="fk_sem_belief_ev_rev",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_id", "owner_id", "memory_id"],
            [
                "memory_traces.run_id",
                "memory_traces.owner_id",
                "memory_traces.memory_id",
            ],
            name="fk_sem_belief_ev_memory",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "run_id",
            "owner_id",
            "belief_id",
            "revision_id",
            "memory_id",
            name="uq_sem_belief_ev_memory",
        ),
        CheckConstraint("ordinal >= 0", name="ck_sem_belief_ev_ordinal"),
        CheckConstraint(
            "stance IN ('supporting', 'contradicting')",
            name="ck_sem_belief_ev_stance",
        ),
        CheckConstraint(
            "contribution >= 0.0 AND contribution <= 1.0",
            name="ck_sem_belief_ev_contribution",
        ),
        CheckConstraint(
            "testimony_decision IS NULL OR testimony_decision IN "
            "('accept', 'discount', 'contradict', 'defer')",
            name="ck_sem_belief_ev_testimony_decision",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    belief_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    lineage_root_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    stance: Mapped[str] = mapped_column(String(16), nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    testimony_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    testimony_hop_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    testimony_trust: Mapped[float | None] = mapped_column(Float, nullable=True)
    testimony_trust_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    testimony_sender_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    testimony_receiver_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    testimony_context_relevance: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    testimony_hop_attenuation: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    testimony_base_contribution: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    testimony_adjusted_contribution: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    testimony_confidence_delta: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    testimony_policy_version: Mapped[str | None] = mapped_column(
        String(_MAX_POLICY), nullable=True
    )


class DirectedRelationshipOrm(Base):
    """Mutable directed relationship profile head."""

    __tablename__ = "directed_relationships"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "source_id", "relationship_id"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_directed_rel_run",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "run_id",
            "source_id",
            "target_id",
            name="uq_directed_rel_pair",
        ),
        CheckConstraint("source_id <> target_id", name="ck_directed_rel_not_self"),
        CheckConstraint("revision_ordinal >= 0", name="ck_directed_rel_ordinal"),
        CheckConstraint("created_tick >= 0", name="ck_directed_rel_created"),
        CheckConstraint(
            "updated_tick >= created_tick", name="ck_directed_rel_tick_order"
        ),
        CheckConstraint(
            "activation_state IN ('candidate', 'active', 'retired')",
            name="ck_directed_rel_activation",
        ),
        Index(
            "ix_directed_rel_source_tick",
            "run_id",
            "source_id",
            "updated_tick",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    source_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    relationship_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    target_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    activation_state: Mapped[str] = mapped_column(String(16), nullable=False)
    current_revision_id: Mapped[str] = mapped_column(
        String(_STABLE_ID_LEN), nullable=False
    )
    revision_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)


class RelationshipRevisionOrm(Base):
    """Append-only relationship revision."""

    __tablename__ = "relationship_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "source_id", "relationship_id", "revision_id"),
        ForeignKeyConstraint(
            ["run_id", "source_id", "relationship_id"],
            [
                "directed_relationships.run_id",
                "directed_relationships.source_id",
                "directed_relationships.relationship_id",
            ],
            name="fk_rel_rev_profile",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "run_id",
            "source_id",
            "relationship_id",
            "ordinal",
            name="uq_rel_rev_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ck_rel_rev_ordinal"),
        CheckConstraint("logical_tick >= 0", name="ck_rel_rev_tick"),
        CheckConstraint(
            "activation_state IN ('candidate', 'active', 'retired')",
            name="ck_rel_rev_activation",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    source_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    relationship_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    target_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    logical_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    activation_state: Mapped[str] = mapped_column(String(16), nullable=False)
    previous_revision_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN))
    policy_id: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)


class RelationshipDimensionStateOrm(Base):
    """Append-only per-revision dimension snapshot."""

    __tablename__ = "relationship_dimension_states"
    __table_args__ = (
        PrimaryKeyConstraint(
            "run_id", "source_id", "relationship_id", "revision_id", "dimension"
        ),
        ForeignKeyConstraint(
            ["run_id", "source_id", "relationship_id", "revision_id"],
            [
                "relationship_revisions.run_id",
                "relationship_revisions.source_id",
                "relationship_revisions.relationship_id",
                "relationship_revisions.revision_id",
            ],
            name="fk_rel_dim_rev",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "dimension IN ("
            "'trust','fear','affection','debt','respect',"
            "'resentment','familiarity','dependency')",
            name="ck_rel_dim_closed",
        ),
        CheckConstraint("value >= -1.0 AND value <= 1.0", name="ck_rel_dim_value"),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_rel_dim_conf"
        ),
        CheckConstraint("logical_tick >= 0", name="ck_rel_dim_tick"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    source_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    relationship_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    support_mass: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction_mass: Mapped[float] = mapped_column(Float, nullable=False)
    logical_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(_MAX_POLICY), nullable=False)


class RelationshipDimensionEvidenceOrm(Base):
    """Append-only opaque episodic evidence for one dimension revision."""

    __tablename__ = "relationship_dimension_evidence"
    __table_args__ = (
        PrimaryKeyConstraint(
            "run_id",
            "source_id",
            "relationship_id",
            "revision_id",
            "dimension",
            "ordinal",
        ),
        ForeignKeyConstraint(
            [
                "run_id",
                "source_id",
                "relationship_id",
                "revision_id",
                "dimension",
            ],
            [
                "relationship_dimension_states.run_id",
                "relationship_dimension_states.source_id",
                "relationship_dimension_states.relationship_id",
                "relationship_dimension_states.revision_id",
                "relationship_dimension_states.dimension",
            ],
            name="fk_rel_dim_ev_state",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "run_id",
            "source_id",
            "relationship_id",
            "revision_id",
            "dimension",
            "memory_ref",
            name="uq_rel_dim_ev_memory",
        ),
        CheckConstraint("ordinal >= 0", name="ck_rel_dim_ev_ordinal"),
        CheckConstraint(
            "contribution >= 0.0 AND contribution <= 1.0",
            name="ck_rel_dim_ev_contribution",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    source_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    relationship_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_ref: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    lineage_root_ref: Mapped[str] = mapped_column(
        String(_STABLE_ID_LEN), nullable=False
    )
    contribution: Mapped[float] = mapped_column(Float, nullable=False)


class SubjectiveOperationOrm(Base):
    """Idempotent owner-scoped subjective commit receipt."""

    __tablename__ = "subjective_operations"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "owner_id", "operation_id"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_subj_ops_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 0", name="ck_subj_ops_revision"),
        CheckConstraint("logical_tick >= 0", name="ck_subj_ops_tick"),
        CheckConstraint(
            "char_length(fingerprint) = 64", name="ck_subj_ops_fingerprint"
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(_MAX_OPERATION), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    logical_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    memory_written_count: Mapped[int] = mapped_column(Integer, nullable=False)
    belief_revision_count: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship_revision_count: Mapped[int] = mapped_column(Integer, nullable=False)
