"""SQLAlchemy 2 mappings for the append-only simulation event store.

Uses ``infrastructure.orm.Base`` / shared metadata. Importing this module
registers tables; it does not connect, migrate, or configure logging.

Subjective episodic-memory and reconstruction tables live in
``persistence.memory_orm`` and are intentionally excluded from
``AUTHORITATIVE_TABLES`` / objective replay.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.orm import Base

SHA256_HEX_LEN: Final[int] = 64
_STABLE_ID_LEN: Final[int] = 128

__all__ = [
    "AUTHORITATIVE_TABLES",
    "SCIENTIFIC_EVIDENCE_APPEND_ONLY_TABLES",
    "SCIENTIFIC_EVIDENCE_TABLES",
    "SHA256_HEX_LEN",
    "ActionResolutionOrm",
    "ClaimTruthSpecOrm",
    "EvidenceManifestOrm",
    "ExperimentAssignmentOrm",
    "ExperimentDefinitionOrm",
    "ExperimentOrm",
    "ExperimentResultOrm",
    "ExperimentRunOrm",
    "GoalRevisionOrm",
    "MetricDocumentOrm",
    "MetricSetOrm",
    "RunControlStateOrm",
    "RunLifecycleTransitionOrm",
    "RunStreamHeadOrm",
    "RunStreamRecordOrm",
    "RunnerAttemptStateOrm",
    "RunnerPendingFinalizationOrm",
    "SimulationRunOrm",
    "SnapshotBodyOrm",
    "SnapshotInventoryOrm",
    "SnapshotItemOrm",
    "SnapshotLocationOrm",
    "SnapshotRegistrationOrm",
    "SnapshotResourceOrm",
    "SnapshotWeatherOrm",
    "TickCommitOrm",
    "WorldEventOrm",
    "WorldSnapshotOrm",
]

AUTHORITATIVE_TABLES: Final[tuple[str, ...]] = (
    "experiments",
    "experiment_runs",
    "simulation_runs",
    "tick_commits",
    "world_events",
    "world_snapshots",
    "snapshot_locations",
    "snapshot_registrations",
    "snapshot_bodies",
    "snapshot_inventory",
    "snapshot_items",
    "snapshot_resources",
    "snapshot_weather",
)

SCIENTIFIC_EVIDENCE_TABLES: Final[tuple[str, ...]] = (
    "evidence_manifests",
    "goal_revisions",
    "action_resolutions",
    "claim_truth_specs",
    "metric_sets",
    "metric_documents",
    "run_stream_heads",
    "run_stream_records",
)

SCIENTIFIC_EVIDENCE_APPEND_ONLY_TABLES: Final[tuple[str, ...]] = (
    "goal_revisions",
    "action_resolutions",
    "claim_truth_specs",
    "evidence_manifests",
    "metric_documents",
    "run_stream_records",
)


class ExperimentOrm(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint("char_length(label) BETWEEN 1 AND 256", name="label_len"),
    )

    experiment_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class SimulationRunOrm(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint("seed >= 0", name="seed_nonneg"),
        CheckConstraint("config_seed >= 0", name="config_seed_nonneg"),
        CheckConstraint("seed = config_seed", name="seed_matches_config"),
        CheckConstraint("event_schema_version >= 0", name="event_schema_nonneg"),
        CheckConstraint(
            "char_length(bootstrap_snapshot_id) > 0", name="bootstrap_id_nonempty"
        ),
        ForeignKeyConstraint(
            ["run_id", "bootstrap_snapshot_id"],
            ["world_snapshots.run_id", "world_snapshots.snapshot_id"],
            name="fk_simulation_runs_bootstrap",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        Index("ix_simulation_runs_world_id", "world_id"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), primary_key=True)
    world_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    seed: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    config_seed: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    derivation_version: Mapped[str] = mapped_column(Text, nullable=False)
    event_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    projector_version: Mapped[str] = mapped_column(Text, nullable=False)
    persistence_codec_version: Mapped[str] = mapped_column(Text, nullable=False)
    bootstrap_snapshot_id: Mapped[str] = mapped_column(
        String(_STABLE_ID_LEN), nullable=False
    )
    physical_rules_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    physical_rules_fingerprint: Mapped[str | None] = mapped_column(
        String(SHA256_HEX_LEN), nullable=True
    )
    physical_rules_canonical: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )


class ExperimentRunOrm(Base):
    __tablename__ = "experiment_runs"
    __table_args__ = (
        PrimaryKeyConstraint("experiment_id", "run_id"),
        ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.experiment_id"],
            name="fk_experiment_runs_experiment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_experiment_runs_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_nonneg"),
        UniqueConstraint("experiment_id", "ordinal", name="uq_experiment_runs_ordinal"),
        Index("ix_experiment_runs_run_id", "run_id"),
    )

    experiment_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WorldSnapshotOrm(Base):
    __tablename__ = "world_snapshots"
    __table_args__ = (
        UniqueConstraint("run_id", "snapshot_id", name="uq_world_snapshots_run"),
        CheckConstraint("seed >= 0", name="seed_nonneg"),
        CheckConstraint("config_seed >= 0", name="config_seed_nonneg"),
        CheckConstraint("seed = config_seed", name="seed_matches_config"),
        CheckConstraint("next_tick >= 0", name="next_tick_nonneg"),
        CheckConstraint("revision >= 0", name="revision_nonneg"),
        CheckConstraint("event_schema_version >= 0", name="event_schema_nonneg"),
        CheckConstraint(
            f"char_length(integrity_hash) = {SHA256_HEX_LEN}",
            name="integrity_hash_len",
        ),
        CheckConstraint(
            "integrity_hash ~ '^[0-9a-f]{64}$'",
            name="integrity_hash_hex",
        ),
        CheckConstraint(
            "predecessor_commit_hash IS NULL OR ("
            f"char_length(predecessor_commit_hash) = {SHA256_HEX_LEN} AND "
            "predecessor_commit_hash ~ '^[0-9a-f]{64}$')",
            name="predecessor_hash_hex",
        ),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_world_snapshots_run",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        Index("ix_world_snapshots_run_next_tick", "run_id", "next_tick"),
        Index("ix_world_snapshots_run_revision", "run_id", "revision"),
    )

    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    world_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    seed: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    config_seed: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    next_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    projector_version: Mapped[str] = mapped_column(Text, nullable=False)
    persistence_codec_version: Mapped[str] = mapped_column(Text, nullable=False)
    derivation_version: Mapped[str] = mapped_column(Text, nullable=False)
    integrity_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    predecessor_commit_hash: Mapped[str | None] = mapped_column(
        String(SHA256_HEX_LEN), nullable=True
    )
    canonical_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class TickCommitOrm(Base):
    __tablename__ = "tick_commits"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "tick"),
        CheckConstraint("tick >= 0", name="tick_nonneg"),
        CheckConstraint("resulting_tick = tick + 1", name="resulting_tick_succ"),
        CheckConstraint("base_revision >= 0", name="base_revision_nonneg"),
        CheckConstraint("resulting_revision >= 0", name="resulting_revision_nonneg"),
        CheckConstraint(
            "resulting_revision >= base_revision", name="revision_monotonic"
        ),
        CheckConstraint(
            "resulting_revision - base_revision BETWEEN 0 AND 1",
            name="revision_delta",
        ),
        CheckConstraint("event_count >= 0", name="event_count_nonneg"),
        CheckConstraint(
            f"char_length(commit_hash) = {SHA256_HEX_LEN}", name="commit_hash_len"
        ),
        CheckConstraint("commit_hash ~ '^[0-9a-f]{64}$'", name="commit_hash_hex"),
        CheckConstraint(
            f"char_length(payload_hash) = {SHA256_HEX_LEN}", name="payload_hash_len"
        ),
        CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="payload_hash_hex"),
        CheckConstraint(
            "predecessor_commit_hash IS NULL OR ("
            f"char_length(predecessor_commit_hash) = {SHA256_HEX_LEN} AND "
            "predecessor_commit_hash ~ '^[0-9a-f]{64}$')",
            name="predecessor_hash_hex",
        ),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_tick_commits_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_id", "snapshot_id"],
            ["world_snapshots.run_id", "world_snapshots.snapshot_id"],
            name="fk_tick_commits_snapshot",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("run_id", "idempotency_key", name="uq_tick_commits_idem"),
        UniqueConstraint("run_id", "commit_hash", name="uq_tick_commits_hash"),
        Index("ix_tick_commits_run_revision", "run_id", "resulting_revision"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resulting_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    base_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resulting_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    predecessor_commit_hash: Mapped[str | None] = mapped_column(
        String(SHA256_HEX_LEN), nullable=True
    )
    commit_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )


class WorldEventOrm(Base):
    __tablename__ = "world_events"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "tick", "sequence"),
        UniqueConstraint("event_id", name="uq_world_events_event_id"),
        CheckConstraint("tick >= 0", name="tick_nonneg"),
        CheckConstraint("sequence >= 0", name="sequence_nonneg"),
        CheckConstraint("resulting_revision >= 0", name="resulting_revision_nonneg"),
        CheckConstraint("schema_version >= 0", name="schema_version_nonneg"),
        ForeignKeyConstraint(
            ["run_id", "tick"],
            ["tick_commits.run_id", "tick_commits.tick"],
            name="fk_world_events_tick",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_world_events_run_tick_revision",
            "run_id",
            "tick",
            "resulting_revision",
        ),
        Index("ix_world_events_actor_id", "actor_id"),
        Index("ix_world_events_target_id", "target_id"),
        Index("ix_world_events_event_type", "event_type"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    world_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    request_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    resulting_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN), nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    cause: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    occurrence: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)


class SnapshotLocationOrm(Base):
    __tablename__ = "snapshot_locations"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "snapshot_id", "entity_id"),
        ForeignKeyConstraint(
            ["run_id", "snapshot_id"],
            ["world_snapshots.run_id", "world_snapshots.snapshot_id"],
            name="fk_snapshot_locations_snapshot",
            ondelete="RESTRICT",
        ),
        CheckConstraint("char_length(name) > 0", name="name_nonempty"),
        CheckConstraint("body_capacity >= 1", name="body_capacity_positive"),
        CheckConstraint("item_capacity >= 0", name="item_capacity_nonneg"),
        CheckConstraint(
            "shelter_factor >= 0 AND shelter_factor <= 1", name="shelter_unit"
        ),
        CheckConstraint(
            "visibility_factor >= 0 AND visibility_factor <= 1",
            name="visibility_unit",
        ),
        Index("ix_snapshot_locations_entity", "entity_id"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    adjacent: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    body_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    item_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    base_temperature: Mapped[float] = mapped_column(Numeric, nullable=False)
    shelter_factor: Mapped[float] = mapped_column(Numeric, nullable=False)
    visibility_factor: Mapped[float] = mapped_column(Numeric, nullable=False)


class SnapshotRegistrationOrm(Base):
    __tablename__ = "snapshot_registrations"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "snapshot_id", "ordinal"),
        ForeignKeyConstraint(
            ["run_id", "snapshot_id"],
            ["world_snapshots.run_id", "world_snapshots.snapshot_id"],
            name="fk_snapshot_registrations_snapshot",
            ondelete="RESTRICT",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_nonneg"),
        UniqueConstraint(
            "run_id",
            "snapshot_id",
            "agent_id",
            name="uq_snapshot_registrations_agent",
        ),
        UniqueConstraint(
            "run_id",
            "snapshot_id",
            "entity_id",
            name="uq_snapshot_registrations_entity",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)


class SnapshotBodyOrm(Base):
    __tablename__ = "snapshot_bodies"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "snapshot_id", "entity_id"),
        ForeignKeyConstraint(
            ["run_id", "snapshot_id"],
            ["world_snapshots.run_id", "world_snapshots.snapshot_id"],
            name="fk_snapshot_bodies_snapshot",
            ondelete="RESTRICT",
        ),
        CheckConstraint("life_status IN ('alive', 'dead')", name="life_status_closed"),
        CheckConstraint("carry_capacity >= 1", name="carry_capacity_positive"),
        Index("ix_snapshot_bodies_location", "run_id", "snapshot_id", "location_id"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    location_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    health: Mapped[float] = mapped_column(Numeric, nullable=False)
    hunger: Mapped[float] = mapped_column(Numeric, nullable=False)
    thirst: Mapped[float] = mapped_column(Numeric, nullable=False)
    fatigue: Mapped[float] = mapped_column(Numeric, nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric, nullable=False)
    life_status: Mapped[str] = mapped_column(Text, nullable=False)
    carry_capacity: Mapped[int] = mapped_column(Integer, nullable=False)


class SnapshotInventoryOrm(Base):
    __tablename__ = "snapshot_inventory"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "snapshot_id", "body_id", "position"),
        ForeignKeyConstraint(
            ["run_id", "snapshot_id", "body_id"],
            [
                "snapshot_bodies.run_id",
                "snapshot_bodies.snapshot_id",
                "snapshot_bodies.entity_id",
            ],
            name="fk_snapshot_inventory_body",
            ondelete="RESTRICT",
        ),
        CheckConstraint("position >= 0", name="position_nonneg"),
        UniqueConstraint(
            "run_id",
            "snapshot_id",
            "item_id",
            name="uq_snapshot_inventory_item",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    body_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)


class SnapshotItemOrm(Base):
    __tablename__ = "snapshot_items"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "snapshot_id", "entity_id"),
        ForeignKeyConstraint(
            ["run_id", "snapshot_id"],
            ["world_snapshots.run_id", "world_snapshots.snapshot_id"],
            name="fk_snapshot_items_snapshot",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(location_id IS NULL) <> (holder_id IS NULL)",
            name="one_placement",
        ),
        CheckConstraint("char_length(name) > 0", name="name_nonempty"),
        CheckConstraint("char_length(kind) > 0", name="kind_nonempty"),
        CheckConstraint("load >= 1", name="load_positive"),
        Index("ix_snapshot_items_location", "run_id", "snapshot_id", "location_id"),
        Index("ix_snapshot_items_holder", "run_id", "snapshot_id", "holder_id"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    load: Mapped[int] = mapped_column(Integer, nullable=False)
    location_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )
    holder_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN), nullable=True)


class SnapshotResourceOrm(Base):
    __tablename__ = "snapshot_resources"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "snapshot_id", "entity_id"),
        ForeignKeyConstraint(
            ["run_id", "snapshot_id"],
            ["world_snapshots.run_id", "world_snapshots.snapshot_id"],
            name="fk_snapshot_resources_snapshot",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity >= 0", name="quantity_nonneg"),
        CheckConstraint("maximum_quantity >= 0", name="maximum_quantity_nonneg"),
        CheckConstraint("quantity <= maximum_quantity", name="quantity_within_maximum"),
        CheckConstraint("regeneration_per_tick >= 0", name="regeneration_nonneg"),
        CheckConstraint("quantity::text <> 'NaN'", name="quantity_not_nan"),
        CheckConstraint(
            "quantity::float8 != 'Infinity'::float8 AND "
            "quantity::float8 != '-Infinity'::float8",
            name="quantity_not_inf",
        ),
        CheckConstraint("char_length(name) > 0", name="name_nonempty"),
        CheckConstraint("char_length(kind) > 0", name="kind_nonempty"),
        CheckConstraint("char_length(unit) > 0", name="unit_nonempty"),
        Index(
            "ix_snapshot_resources_location",
            "run_id",
            "snapshot_id",
            "location_id",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    location_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=False)
    maximum_quantity: Mapped[float] = mapped_column(Numeric, nullable=False)
    regeneration_per_tick: Mapped[float] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)


class SnapshotWeatherOrm(Base):
    __tablename__ = "snapshot_weather"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "snapshot_id", "location_id"),
        ForeignKeyConstraint(
            ["run_id", "snapshot_id"],
            ["world_snapshots.run_id", "world_snapshots.snapshot_id"],
            name="fk_snapshot_weather_snapshot",
            ondelete="RESTRICT",
        ),
        CheckConstraint("char_length(condition) > 0", name="condition_nonempty"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    location_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)


class RunnerPendingFinalizationOrm(Base):
    """Append-only pending subjective finalization outbox (not authoritative)."""

    __tablename__ = "runner_pending_finalizations"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "agent_id", "invocation_id"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_runner_pending_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('pending', 'finalized', 'aborted')",
            name="ck_runner_pending_status",
        ),
        CheckConstraint(
            f"char_length(integrity_hash) = {SHA256_HEX_LEN}",
            name="ck_runner_pending_hash",
        ),
        UniqueConstraint("created_ordinal", name="uq_runner_pending_ordinal"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    invocation_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    integrity_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    codec_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class RunnerAttemptStateOrm(Base):
    """Append-only runner attempt recovery state (not authoritative)."""

    __tablename__ = "runner_attempt_states"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "attempt_id"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_runner_attempt_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"char_length(integrity_hash) = {SHA256_HEX_LEN}",
            name="ck_runner_attempt_hash",
        ),
        UniqueConstraint("created_ordinal", name="uq_runner_attempt_ordinal"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    recovery_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    integrity_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    codec_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class ExperimentDefinitionOrm(Base):
    __tablename__ = "experiment_definitions"
    __table_args__ = (
        CheckConstraint(
            f"char_length(payload_hash) = {SHA256_HEX_LEN}",
            name="ck_experiment_definitions_hash",
        ),
        CheckConstraint(
            f"char_length(definition_fingerprint) = {SHA256_HEX_LEN}",
            name="ck_experiment_definitions_fp",
        ),
        UniqueConstraint("created_ordinal", name="uq_experiment_definitions_ordinal"),
    )

    experiment_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    definition_fingerprint: Mapped[str] = mapped_column(
        String(SHA256_HEX_LEN), nullable=False
    )
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class ExperimentAssignmentOrm(Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (
        PrimaryKeyConstraint(
            "experiment_id", "condition_id", "seed_ordinal", "replicate_index"
        ),
        ForeignKeyConstraint(
            ["experiment_id"],
            ["experiment_definitions.experiment_id"],
            name="fk_experiment_assignments_definition",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_experiment_assignments_run",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("run_id", name="uq_experiment_assignments_run"),
        UniqueConstraint("created_ordinal", name="uq_experiment_assignments_ordinal"),
        CheckConstraint("seed >= 0", name="ck_experiment_assignments_seed"),
        CheckConstraint(
            "seed_ordinal >= 0 AND replicate_index >= 0",
            name="ck_experiment_assignments_ords",
        ),
    )

    experiment_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    condition_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    seed_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    replicate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(
        String(SHA256_HEX_LEN), nullable=False
    )
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class ExperimentResultOrm(Base):
    __tablename__ = "experiment_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id"],
            ["experiment_assignments.run_id"],
            name="fk_experiment_results_run",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("created_ordinal", name="uq_experiment_results_ordinal"),
        CheckConstraint("ticks_committed >= 0", name="ck_experiment_results_ticks"),
        CheckConstraint(
            f"char_length(payload_hash) = {SHA256_HEX_LEN}",
            name="ck_experiment_results_hash",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    condition_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    stop_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    ticks_committed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class RunControlStateOrm(Base):
    """Mutable durable run-control head (config, lifecycle, lease, progress)."""

    __tablename__ = "run_control_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_run_control_states_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "lifecycle_state IN ("
            "'configured','ready','paused','starting','running','stopping',"
            "'completed','failed','fenced','recovery-required','interrupted'"
            ")",
            name="ck_run_control_lifecycle_state",
        ),
        CheckConstraint(
            "config_availability IN ('available','unavailable')",
            name="ck_run_control_config_availability",
        ),
        CheckConstraint(
            "lifecycle_version >= 0",
            name="ck_run_control_lifecycle_version",
        ),
        CheckConstraint(
            "ticks_committed >= 0 AND progress_cursor >= 0",
            name="ck_run_control_progress_nonneg",
        ),
        CheckConstraint(
            "("
            "config_availability = 'unavailable' "
            "AND config_schema_version IS NULL "
            "AND config_fingerprint IS NULL "
            "AND config_payload IS NULL"
            ") OR ("
            "config_availability = 'available' "
            "AND config_schema_version IS NOT NULL "
            "AND config_fingerprint IS NOT NULL "
            "AND config_payload IS NOT NULL"
            ")",
            name="ck_run_control_config_envelope",
        ),
        CheckConstraint(
            f"("
            f"config_fingerprint IS NULL OR "
            f"char_length(config_fingerprint) = {SHA256_HEX_LEN}"
            f")",
            name="ck_run_control_config_fingerprint",
        ),
        Index("ix_run_control_states_lifecycle", "lifecycle_state"),
        Index("ix_run_control_states_lease", "lease_id"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), primary_key=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    config_availability: Mapped[str] = mapped_column(String(32), nullable=False)
    config_schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_fingerprint: Mapped[str | None] = mapped_column(
        String(SHA256_HEX_LEN), nullable=True
    )
    config_payload: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ticks_committed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    progress_cursor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    lease_id: Mapped[str | None] = mapped_column(String(_STABLE_ID_LEN), nullable=True)
    lease_owner_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )
    lease_claimed_at_unix_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    lease_heartbeat_at_unix_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    lease_expires_at_unix_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    terminal_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RunLifecycleTransitionOrm(Base):
    """Append-only optimistic lifecycle transition audit."""

    __tablename__ = "run_lifecycle_transitions"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "resulting_version"),
        ForeignKeyConstraint(
            ["run_id"],
            ["run_control_states.run_id"],
            name="fk_run_lifecycle_transitions_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "expected_version >= 0 AND resulting_version = expected_version + 1",
            name="ck_run_lifecycle_transition_versions",
        ),
        UniqueConstraint(
            "created_ordinal", name="uq_run_lifecycle_transitions_ordinal"
        ),
        Index("ix_run_lifecycle_transitions_operation", "operation_id"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resulting_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class EvidenceManifestOrm(Base):
    """Append-only evidence manifest / high-water revision."""

    __tablename__ = "evidence_manifests"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "manifest_hash"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_evidence_manifests_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"char_length(manifest_hash) = {SHA256_HEX_LEN}",
            name="ck_evidence_manifests_hash",
        ),
        UniqueConstraint("created_ordinal", name="uq_evidence_manifests_ordinal"),
        Index("ix_evidence_manifests_run", "run_id", "created_ordinal"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    objective_commit_hash: Mapped[str] = mapped_column(
        String(_STABLE_ID_LEN), nullable=False
    )
    high_water_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class GoalRevisionOrm(Base):
    """Append-only versioned goal transition."""

    __tablename__ = "goal_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "goal_id", "revision"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_goal_revisions_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 0 AND tick >= 0", name="ck_goal_revisions_nonneg"),
        CheckConstraint(
            f"char_length(content_hash) = {SHA256_HEX_LEN}",
            name="ck_goal_revisions_hash",
        ),
        UniqueConstraint("created_ordinal", name="uq_goal_revisions_ordinal"),
        Index("ix_goal_revisions_run_tick", "run_id", "tick", "created_ordinal"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    goal_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class ActionResolutionOrm(Base):
    """Append-only action resolution keyed by (run, tick, ordinal)."""

    __tablename__ = "action_resolutions"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "tick", "ordinal"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_action_resolutions_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "tick >= 0 AND ordinal >= 0", name="ck_action_resolutions_nonneg"
        ),
        CheckConstraint(
            f"char_length(content_hash) = {SHA256_HEX_LEN}",
            name="ck_action_resolutions_hash",
        ),
        UniqueConstraint("created_ordinal", name="uq_action_resolutions_ordinal"),
        Index("ix_action_resolutions_run", "run_id", "tick"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ordinal: Mapped[int] = mapped_column(BigInteger, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class ClaimTruthSpecOrm(Base):
    """Append-only claim-level truth specification (opaque payload)."""

    __tablename__ = "claim_truth_specs"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "claim_id"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_claim_truth_specs_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "availability IN ('available', 'unavailable')",
            name="ck_claim_truth_availability",
        ),
        CheckConstraint(
            "("
            "availability = 'unavailable' "
            "AND schema_version IS NULL "
            "AND content_hash IS NULL "
            "AND payload IS NULL"
            ") OR ("
            "availability = 'available' "
            "AND schema_version IS NOT NULL "
            "AND content_hash IS NOT NULL "
            "AND payload IS NOT NULL "
            f"AND char_length(content_hash) = {SHA256_HEX_LEN}"
            ")",
            name="ck_claim_truth_envelope",
        ),
        UniqueConstraint("created_ordinal", name="uq_claim_truth_specs_ordinal"),
        Index("ix_claim_truth_specs_run", "run_id", "created_ordinal"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    claim_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(SHA256_HEX_LEN), nullable=True
    )
    payload: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class MetricSetOrm(Base):
    """Mutable metric-set lifecycle head linked to an evidence revision."""

    __tablename__ = "metric_sets"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "metric_set_id"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_metric_sets_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_id", "evidence_manifest_hash"],
            ["evidence_manifests.run_id", "evidence_manifests.manifest_hash"],
            name="fk_metric_sets_manifest",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "lifecycle_state IN ("
            "'pending','running','complete','partial','failed'"
            ")",
            name="ck_metric_sets_lifecycle",
        ),
        CheckConstraint("lifecycle_version >= 0", name="ck_metric_sets_version"),
        CheckConstraint(
            f"char_length(evidence_manifest_hash) = {SHA256_HEX_LEN}",
            name="ck_metric_sets_hash",
        ),
        Index("ix_metric_sets_lifecycle", "lifecycle_state"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    metric_set_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_manifest_hash: Mapped[str] = mapped_column(
        String(SHA256_HEX_LEN), nullable=False
    )
    lifecycle_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )


class MetricDocumentOrm(Base):
    """Immutable metric document/result linked to metric set + evidence revision."""

    __tablename__ = "metric_documents"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "metric_set_id", "metric_family"),
        ForeignKeyConstraint(
            ["run_id", "metric_set_id"],
            ["metric_sets.run_id", "metric_sets.metric_set_id"],
            name="fk_metric_documents_set",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_id", "evidence_manifest_hash"],
            ["evidence_manifests.run_id", "evidence_manifests.manifest_hash"],
            name="fk_metric_documents_manifest",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"char_length(content_hash) = {SHA256_HEX_LEN}",
            name="ck_metric_documents_hash",
        ),
        CheckConstraint(
            f"char_length(evidence_manifest_hash) = {SHA256_HEX_LEN}",
            name="ck_metric_documents_manifest_hash",
        ),
        UniqueConstraint("created_ordinal", name="uq_metric_documents_ordinal"),
        Index(
            "ix_metric_documents_run_set",
            "run_id",
            "metric_set_id",
            "created_ordinal",
        ),
        Index("ix_metric_documents_content", "content_hash"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    metric_set_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    metric_family: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    evidence_manifest_hash: Mapped[str] = mapped_column(
        String(SHA256_HEX_LEN), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )


class RunStreamHeadOrm(Base):
    """Mutable per-run stream high-water cursor."""

    __tablename__ = "run_stream_heads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_run_stream_heads_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("high_water >= 0", name="ck_run_stream_heads_nonneg"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), primary_key=True)
    high_water: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class RunStreamRecordOrm(Base):
    """Append-only unified stream/outbox record with monotonic per-run cursor."""

    __tablename__ = "run_stream_records"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "cursor_value"),
        ForeignKeyConstraint(
            ["run_id"],
            ["simulation_runs.run_id"],
            name="fk_run_stream_records_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint("cursor_value >= 1", name="ck_run_stream_records_cursor"),
        CheckConstraint(
            "record_kind IN ("
            "'status','eventless_tick','event','metric',"
            "'result','recoverable_error','completion'"
            ")",
            name="ck_run_stream_records_kind",
        ),
        CheckConstraint(
            f"char_length(content_hash) = {SHA256_HEX_LEN}",
            name="ck_run_stream_records_hash",
        ),
        CheckConstraint(
            "related_tick IS NULL OR related_tick >= 0",
            name="ck_run_stream_records_tick",
        ),
        UniqueConstraint("created_ordinal", name="uq_run_stream_records_ordinal"),
        Index(
            "ix_run_stream_records_kind",
            "run_id",
            "record_kind",
            "cursor_value",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    cursor_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    record_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(SHA256_HEX_LEN), nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    related_tick: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_ordinal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, autoincrement=True
    )
