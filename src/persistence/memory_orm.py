"""SQLAlchemy mappings for mutable owner-scoped episodic memory.

Subjective tables are deliberately excluded from ``AUTHORITATIVE_TABLES`` and
append-only history triggers. Importing this module registers tables on the
shared metadata; it does not connect, migrate, or configure logging.
"""

from __future__ import annotations

from typing import Final

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.orm import Base

_STABLE_ID_LEN: Final[int] = 128
_MAX_CONCEPT_CHARS: Final[int] = 256
_MAX_LABEL_CHARS: Final[int] = 256
_MAX_PREDICATE_CHARS: Final[int] = 128
_MAX_EMBEDDING_DIM: Final[int] = 4096
_MAX_POLICY_ID_CHARS: Final[int] = 64

SUBJECTIVE_MEMORY_TABLES: Final[tuple[str, ...]] = (
    "memory_traces",
    "memory_concepts",
    "memory_entity_mentions",
    "memory_relations",
    "memory_access_ops",
)

__all__ = [
    "SUBJECTIVE_MEMORY_TABLES",
    "MemoryAccessOpOrm",
    "MemoryConceptOrm",
    "MemoryEntityMentionOrm",
    "MemoryRelationOrm",
    "MemoryTraceOrm",
]


class MemoryTraceOrm(Base):
    __tablename__ = "memory_traces"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "owner_id", "memory_id"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_memory_traces_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("world_revision >= 0", name="world_revision_nonneg"),
        CheckConstraint(
            "emotional_salience >= 0.0 AND emotional_salience <= 1.0",
            name="salience_unit",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="confidence_unit",
        ),
        CheckConstraint(
            "emotional_salience::text <> 'NaN' AND "
            "emotional_salience::float8 != 'Infinity'::float8 AND "
            "emotional_salience::float8 != '-Infinity'::float8",
            name="salience_finite",
        ),
        CheckConstraint(
            "confidence::text <> 'NaN' AND "
            "confidence::float8 != 'Infinity'::float8 AND "
            "confidence::float8 != '-Infinity'::float8",
            name="confidence_finite",
        ),
        CheckConstraint(
            "source_kind IN ('direct_observation', 'communicated')",
            name="source_kind_closed",
        ),
        CheckConstraint("provenance_source_tick >= 0", name="prov_source_tick_nonneg"),
        CheckConstraint("created_tick >= 0", name="created_tick_nonneg"),
        CheckConstraint("source_tick >= 0", name="source_tick_nonneg"),
        CheckConstraint("last_access_tick >= 0", name="last_access_tick_nonneg"),
        CheckConstraint("access_count >= 0", name="access_count_nonneg"),
        CheckConstraint(
            "last_access_tick >= created_tick",
            name="last_access_after_created",
        ),
        CheckConstraint(
            "expires_at_tick IS NULL OR expires_at_tick >= created_tick",
            name="expires_after_created",
        ),
        CheckConstraint(
            "forgotten_at_tick IS NULL OR forgotten_at_tick >= created_tick",
            name="forgotten_after_created",
        ),
        CheckConstraint(
            "(source_kind = 'direct_observation' AND speaker_id IS NULL) OR "
            "(source_kind = 'communicated' AND speaker_id IS NOT NULL)",
            name="source_kind_speaker",
        ),
        CheckConstraint("generation >= 0", name="generation_nonneg"),
        CheckConstraint(
            "supersedes_memory_id IS NULL OR supersedes_memory_id <> memory_id",
            name="lineage_not_self",
        ),
        CheckConstraint(
            "(embedding IS NULL AND embedding_model IS NULL AND "
            "embedding_version IS NULL AND embedding_dimension IS NULL) OR "
            "(embedding IS NOT NULL AND embedding_model IS NOT NULL AND "
            "embedding_version IS NOT NULL AND embedding_dimension IS NOT NULL AND "
            f"embedding_dimension BETWEEN 1 AND {_MAX_EMBEDDING_DIM} AND "
            "embedding_dimension = vector_dims(embedding))",
            name="embedding_metadata",
        ),
        CheckConstraint(
            "embedding_model IS NULL OR ("
            f"char_length(embedding_model) BETWEEN 1 AND {_MAX_POLICY_ID_CHARS})",
            name="embedding_model_len",
        ),
        CheckConstraint(
            "embedding_version IS NULL OR ("
            f"char_length(embedding_version) BETWEEN 1 AND {_MAX_POLICY_ID_CHARS})",
            name="embedding_version_len",
        ),
        Index(
            "ix_memory_traces_scope_active_created",
            "run_id",
            "owner_id",
            "is_active",
            "created_tick",
        ),
        Index(
            "ix_memory_traces_scope_source_kind",
            "run_id",
            "owner_id",
            "source_kind",
        ),
        Index(
            "ix_memory_traces_scope_location",
            "run_id",
            "owner_id",
            "location_id",
        ),
        Index(
            "ix_memory_traces_context_tags",
            "context_tags",
            postgresql_using="gin",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    memory_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    world_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    emotional_salience: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_source_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    observed_source_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )
    speaker_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )
    created_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_access_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    access_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at_tick: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    forgotten_at_tick: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    location_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )
    context_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    supersedes_memory_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    embedding: Mapped[object | None] = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        Computed("forgotten_at_tick IS NULL", persisted=True),
        nullable=False,
    )


class MemoryConceptOrm(Base):
    __tablename__ = "memory_concepts"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "owner_id", "memory_id", "mention_id"),
        ForeignKeyConstraint(
            ["run_id", "owner_id", "memory_id"],
            [
                "memory_traces.run_id",
                "memory_traces.owner_id",
                "memory_traces.memory_id",
            ],
            name="fk_memory_concepts_trace",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "run_id",
            "owner_id",
            "memory_id",
            "ordinal",
            name="uq_memory_concepts_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_nonneg"),
        CheckConstraint(
            f"char_length(concept) BETWEEN 1 AND {_MAX_CONCEPT_CHARS}",
            name="concept_len",
        ),
        Index(
            "ix_memory_concepts_scope_concept",
            "run_id",
            "owner_id",
            "concept",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    memory_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    mention_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    concept: Mapped[str] = mapped_column(Text, nullable=False)


class MemoryEntityMentionOrm(Base):
    __tablename__ = "memory_entity_mentions"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "owner_id", "memory_id", "mention_id"),
        ForeignKeyConstraint(
            ["run_id", "owner_id", "memory_id"],
            [
                "memory_traces.run_id",
                "memory_traces.owner_id",
                "memory_traces.memory_id",
            ],
            name="fk_memory_entity_mentions_trace",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "run_id",
            "owner_id",
            "memory_id",
            "ordinal",
            name="uq_memory_entity_mentions_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_nonneg"),
        CheckConstraint(
            f"char_length(label) BETWEEN 1 AND {_MAX_LABEL_CHARS}",
            name="label_len",
        ),
        Index(
            "ix_memory_entity_mentions_scope_entity",
            "run_id",
            "owner_id",
            "entity_id",
        ),
        Index(
            "ix_memory_entity_mentions_scope_label",
            "run_id",
            "owner_id",
            "label",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    memory_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    mention_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN), nullable=True)


class MemoryRelationOrm(Base):
    __tablename__ = "memory_relations"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "owner_id", "memory_id", "relation_id"),
        ForeignKeyConstraint(
            ["run_id", "owner_id", "memory_id"],
            [
                "memory_traces.run_id",
                "memory_traces.owner_id",
                "memory_traces.memory_id",
            ],
            name="fk_memory_relations_trace",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "run_id",
            "owner_id",
            "memory_id",
            "ordinal",
            name="uq_memory_relations_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_nonneg"),
        CheckConstraint(
            f"char_length(predicate) BETWEEN 1 AND {_MAX_PREDICATE_CHARS}",
            name="predicate_len",
        ),
        CheckConstraint(
            "subject_kind IN ('concept', 'entity')",
            name="subject_kind_closed",
        ),
        CheckConstraint(
            "object_kind IN ('concept', 'entity')",
            name="object_kind_closed",
        ),
        Index(
            "ix_memory_relations_scope_predicate",
            "run_id",
            "owner_id",
            "predicate",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    memory_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    relation_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    predicate: Mapped[str] = mapped_column(Text, nullable=False)
    subject_kind: Mapped[str] = mapped_column(Text, nullable=False)
    subject_mention_id: Mapped[str] = mapped_column(
        String(_STABLE_ID_LEN), nullable=False
    )
    object_kind: Mapped[str] = mapped_column(Text, nullable=False)
    object_mention_id: Mapped[str] = mapped_column(
        String(_STABLE_ID_LEN), nullable=False
    )


class MemoryAccessOpOrm(Base):
    """Idempotency ledger for observational access receipts."""

    __tablename__ = "memory_access_ops"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "owner_id", "operation_id", "memory_id"),
        ForeignKeyConstraint(
            ["run_id", "owner_id", "memory_id"],
            [
                "memory_traces.run_id",
                "memory_traces.owner_id",
                "memory_traces.memory_id",
            ],
            name="fk_memory_access_ops_trace",
            ondelete="CASCADE",
        ),
        Index(
            "ix_memory_access_ops_scope_operation",
            "run_id",
            "owner_id",
            "operation_id",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    memory_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    access_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
