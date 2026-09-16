"""SQLAlchemy 2 mappings for the append-only simulation event store.

Uses ``infrastructure.orm.Base`` / shared metadata. Importing this module
registers tables; it does not connect, migrate, or configure logging.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
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
    "SHA256_HEX_LEN",
    "ExperimentOrm",
    "ExperimentRunOrm",
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
    payload_hash: Mapped[str] = mapped_column(
        String(SHA256_HEX_LEN), nullable=False
    )
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
        Index("ix_snapshot_locations_entity", "entity_id"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


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
        CheckConstraint(
            "life_status IN ('alive', 'dead')", name="life_status_closed"
        ),
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
        Index("ix_snapshot_items_location", "run_id", "snapshot_id", "location_id"),
        Index("ix_snapshot_items_holder", "run_id", "snapshot_id", "holder_id"),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    location_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )
    holder_id: Mapped[str | None] = mapped_column(
        String(_STABLE_ID_LEN), nullable=True
    )


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
        CheckConstraint("quantity::text <> 'NaN'", name="quantity_not_nan"),
        CheckConstraint(
            "quantity::float8 != 'Infinity'::float8 AND "
            "quantity::float8 != '-Infinity'::float8",
            name="quantity_not_inf",
        ),
        CheckConstraint("char_length(name) > 0", name="name_nonempty"),
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
    location_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=False)
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
        CheckConstraint(
            "temperature::text <> 'NaN' AND "
            "temperature::float8 != 'Infinity'::float8 AND "
            "temperature::float8 != '-Infinity'::float8",
            name="temperature_finite",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    location_id: Mapped[str] = mapped_column(String(_STABLE_ID_LEN), nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric, nullable=False)
