"""Framework-free persistence DTOs and async repository protocols.

Ownership: ``simulation`` defines immutable run/snapshot/commit contracts and
repository ports. Adapters (SQLAlchemy) live outside this package. DTO and
protocol construction is log-free; use ``persistence_diagnostic_fields`` for
safe repository/orchestration diagnostics only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Protocol

from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick, require_exact_nonneg_int
from simulation.models import (
    DERIVATION_VERSION,
    RunId,
    SimulationRunConfig,
    require_seed,
)
from world.events import EVENT_SCHEMA_REPLAY_V1, WorldEvent, normalize_events
from world.identifiers import (
    WorldId,
    WorldRevision,
    require_bounded_text,
    require_stable_id,
)
from world.models import AgentBody, Item, Location, Resource, Weather

EVENT_SCHEMA_VERSION: Final[int] = EVENT_SCHEMA_REPLAY_V1
PROJECTOR_VERSION: Final[str] = "v1"
PERSISTENCE_CODEC_VERSION: Final[str] = "v1"

_SHA256_HEX_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_HASH_PREFIX_LEN: Final[int] = 8

__all__ = [
    "EVENT_SCHEMA_VERSION",
    "PERSISTENCE_CODEC_VERSION",
    "PROJECTOR_VERSION",
    "CommitHash",
    "ExperimentId",
    "ExperimentMetadata",
    "ExperimentRepository",
    "ExperimentRunAssignment",
    "PayloadHash",
    "ReplayFallbackPolicy",
    "ReplayMode",
    "ReplayRequest",
    "ReplayResult",
    "ReplayStatus",
    "RunCreateRequest",
    "RunManifest",
    "SimulationRunRepository",
    "SnapshotId",
    "SnapshotRepository",
    "TickAppendRequest",
    "TickCommit",
    "TickJournalRepository",
    "WorldSnapshot",
    "persistence_diagnostic_fields",
    "require_commit_hash",
    "require_payload_hash",
]


def require_commit_hash(name: str, value: object) -> str:
    """Accept only lowercase SHA-256 hex digests (64 characters)."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a str")
    if _SHA256_HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")
    return value


def require_payload_hash(name: str, value: object) -> str:
    """Accept only lowercase SHA-256 hex digests (64 characters)."""
    return require_commit_hash(name, value)


def _require_version_string(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _require_schema_version(name: str, value: object) -> int:
    version = require_exact_nonneg_int(name, value)
    if version != EVENT_SCHEMA_VERSION:
        raise ValueError(
            f"{name} must equal EVENT_SCHEMA_VERSION ({EVENT_SCHEMA_VERSION})"
        )
    return version


@dataclass(frozen=True, slots=True)
class ExperimentId:
    """Stable experiment identity."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("ExperimentId.value", self.value)


@dataclass(frozen=True, slots=True)
class SnapshotId:
    """Stable immutable checkpoint identity."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("SnapshotId.value", self.value)


@dataclass(frozen=True, slots=True)
class CommitHash:
    """Chained per-run commit digest (SHA-256 hex)."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", require_commit_hash("CommitHash.value", self.value)
        )


@dataclass(frozen=True, slots=True)
class PayloadHash:
    """Canonical payload digest (SHA-256 hex)."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", require_payload_hash("PayloadHash.value", self.value)
        )


@dataclass(frozen=True, slots=True)
class RunManifest:
    """Immutable identity and version envelope for one durable simulation run."""

    run_id: RunId
    world_id: WorldId
    seed: int
    config: SimulationRunConfig
    derivation_version: str
    event_schema_version: int
    projector_version: str
    persistence_codec_version: str

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("RunManifest.run_id must be RunId")
        if type(self.world_id) is not WorldId:
            raise TypeError("RunManifest.world_id must be WorldId")
        object.__setattr__(self, "seed", require_seed(self.seed))
        if type(self.config) is not SimulationRunConfig:
            raise TypeError("RunManifest.config must be SimulationRunConfig")
        if self.config.seed != self.seed:
            raise ValueError("RunManifest.seed must match config.seed")
        object.__setattr__(
            self,
            "derivation_version",
            _require_version_string(
                "RunManifest.derivation_version", self.derivation_version
            ),
        )
        object.__setattr__(
            self,
            "event_schema_version",
            _require_schema_version(
                "RunManifest.event_schema_version", self.event_schema_version
            ),
        )
        object.__setattr__(
            self,
            "projector_version",
            _require_version_string(
                "RunManifest.projector_version", self.projector_version
            ),
        )
        object.__setattr__(
            self,
            "persistence_codec_version",
            _require_version_string(
                "RunManifest.persistence_codec_version",
                self.persistence_codec_version,
            ),
        )


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    """Immutable objective checkpoint. Contains no live World or session token."""

    snapshot_id: SnapshotId
    run_id: RunId
    world_id: WorldId
    seed: int
    config: SimulationRunConfig
    registrations: Sequence[AgentRegistration]
    locations: Sequence[Location]
    bodies: Sequence[AgentBody]
    items: Sequence[Item]
    resources: Sequence[Resource]
    weather: Sequence[Weather]
    next_tick: Tick
    revision: WorldRevision
    event_schema_version: int
    projector_version: str
    persistence_codec_version: str
    derivation_version: str
    integrity_hash: PayloadHash
    predecessor_commit_hash: CommitHash | None

    def __post_init__(self) -> None:
        if type(self.snapshot_id) is not SnapshotId:
            raise TypeError("WorldSnapshot.snapshot_id must be SnapshotId")
        if type(self.run_id) is not RunId:
            raise TypeError("WorldSnapshot.run_id must be RunId")
        if type(self.world_id) is not WorldId:
            raise TypeError("WorldSnapshot.world_id must be WorldId")
        object.__setattr__(self, "seed", require_seed(self.seed))
        if type(self.config) is not SimulationRunConfig:
            raise TypeError("WorldSnapshot.config must be SimulationRunConfig")
        if self.config.seed != self.seed:
            raise ValueError("WorldSnapshot.seed must match config.seed")
        if type(self.next_tick) is not Tick:
            raise TypeError("WorldSnapshot.next_tick must be Tick")
        if type(self.revision) is not WorldRevision:
            raise TypeError("WorldSnapshot.revision must be WorldRevision")
        object.__setattr__(
            self,
            "event_schema_version",
            _require_schema_version(
                "WorldSnapshot.event_schema_version", self.event_schema_version
            ),
        )
        object.__setattr__(
            self,
            "projector_version",
            _require_version_string(
                "WorldSnapshot.projector_version", self.projector_version
            ),
        )
        object.__setattr__(
            self,
            "persistence_codec_version",
            _require_version_string(
                "WorldSnapshot.persistence_codec_version",
                self.persistence_codec_version,
            ),
        )
        object.__setattr__(
            self,
            "derivation_version",
            _require_version_string(
                "WorldSnapshot.derivation_version", self.derivation_version
            ),
        )
        if type(self.integrity_hash) is not PayloadHash:
            raise TypeError("WorldSnapshot.integrity_hash must be PayloadHash")
        if self.predecessor_commit_hash is not None and type(
            self.predecessor_commit_hash
        ) is not CommitHash:
            raise TypeError(
                "WorldSnapshot.predecessor_commit_hash must be CommitHash or None"
            )
        # Reuse bootstrap graph validation and ordered copying (inventory order
        # is preserved inside AgentBody).
        bootstrap = WorldBootstrap(
            world_id=self.world_id,
            revision=self.revision,
            locations=self.locations,
            items=self.items,
            resources=self.resources,
            bodies=self.bodies,
            weather=self.weather,
            registrations=self.registrations,
        )
        object.__setattr__(self, "locations", bootstrap.locations)
        object.__setattr__(self, "items", bootstrap.items)
        object.__setattr__(self, "resources", bootstrap.resources)
        object.__setattr__(self, "bodies", bootstrap.bodies)
        object.__setattr__(self, "weather", bootstrap.weather)
        object.__setattr__(self, "registrations", bootstrap.registrations)


@dataclass(frozen=True, slots=True)
class ExperimentMetadata:
    """Queryable experiment label. Values must not appear in diagnostic logs."""

    experiment_id: ExperimentId
    label: str

    def __post_init__(self) -> None:
        if type(self.experiment_id) is not ExperimentId:
            raise TypeError("ExperimentMetadata.experiment_id must be ExperimentId")
        object.__setattr__(
            self,
            "label",
            require_bounded_text(
                "ExperimentMetadata.label", self.label, max_length=256
            ),
        )


@dataclass(frozen=True, slots=True)
class ExperimentRunAssignment:
    """Immutable binding of one run into an experiment."""

    experiment_id: ExperimentId
    run_id: RunId
    ordinal: int = 0

    def __post_init__(self) -> None:
        if type(self.experiment_id) is not ExperimentId:
            raise TypeError(
                "ExperimentRunAssignment.experiment_id must be ExperimentId"
            )
        if type(self.run_id) is not RunId:
            raise TypeError("ExperimentRunAssignment.run_id must be RunId")
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("ExperimentRunAssignment.ordinal", self.ordinal),
        )


@dataclass(frozen=True, slots=True)
class RunCreateRequest:
    """Atomic create input: manifest fields, bootstrap checkpoint, assignment."""

    run_id: RunId
    world_id: WorldId
    seed: int
    config: SimulationRunConfig
    bootstrap: WorldSnapshot
    derivation_version: str = DERIVATION_VERSION
    event_schema_version: int = EVENT_SCHEMA_VERSION
    projector_version: str = PROJECTOR_VERSION
    persistence_codec_version: str = PERSISTENCE_CODEC_VERSION
    experiment_assignment: ExperimentRunAssignment | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("RunCreateRequest.run_id must be RunId")
        if type(self.world_id) is not WorldId:
            raise TypeError("RunCreateRequest.world_id must be WorldId")
        object.__setattr__(self, "seed", require_seed(self.seed))
        if type(self.config) is not SimulationRunConfig:
            raise TypeError("RunCreateRequest.config must be SimulationRunConfig")
        if self.config.seed != self.seed:
            raise ValueError("RunCreateRequest.seed must match config.seed")
        if type(self.bootstrap) is not WorldSnapshot:
            raise TypeError("RunCreateRequest.bootstrap must be WorldSnapshot")
        if self.bootstrap.run_id != self.run_id:
            raise ValueError("RunCreateRequest.bootstrap.run_id must match run_id")
        if self.bootstrap.world_id != self.world_id:
            raise ValueError("RunCreateRequest.bootstrap.world_id must match world_id")
        if self.bootstrap.seed != self.seed:
            raise ValueError("RunCreateRequest.bootstrap.seed must match seed")
        if self.bootstrap.config != self.config:
            raise ValueError("RunCreateRequest.bootstrap.config must match config")
        if self.bootstrap.next_tick != Tick(0):
            raise ValueError("RunCreateRequest.bootstrap.next_tick must be Tick(0)")
        if self.bootstrap.predecessor_commit_hash is not None:
            raise ValueError(
                "RunCreateRequest.bootstrap.predecessor_commit_hash must be None"
            )
        object.__setattr__(
            self,
            "derivation_version",
            _require_version_string(
                "RunCreateRequest.derivation_version", self.derivation_version
            ),
        )
        object.__setattr__(
            self,
            "event_schema_version",
            _require_schema_version(
                "RunCreateRequest.event_schema_version", self.event_schema_version
            ),
        )
        object.__setattr__(
            self,
            "projector_version",
            _require_version_string(
                "RunCreateRequest.projector_version", self.projector_version
            ),
        )
        object.__setattr__(
            self,
            "persistence_codec_version",
            _require_version_string(
                "RunCreateRequest.persistence_codec_version",
                self.persistence_codec_version,
            ),
        )
        if self.bootstrap.derivation_version != self.derivation_version:
            raise ValueError("bootstrap.derivation_version must match request")
        if self.bootstrap.event_schema_version != self.event_schema_version:
            raise ValueError("bootstrap.event_schema_version must match request")
        if self.bootstrap.projector_version != self.projector_version:
            raise ValueError("bootstrap.projector_version must match request")
        if self.bootstrap.persistence_codec_version != self.persistence_codec_version:
            raise ValueError("bootstrap.persistence_codec_version must match request")
        if self.experiment_assignment is not None:
            if type(self.experiment_assignment) is not ExperimentRunAssignment:
                raise TypeError(
                    "RunCreateRequest.experiment_assignment must be "
                    "ExperimentRunAssignment or None"
                )
            if self.experiment_assignment.run_id != self.run_id:
                raise ValueError(
                    "RunCreateRequest.experiment_assignment.run_id must match run_id"
                )


@dataclass(frozen=True, slots=True)
class TickCommit:
    """Cursor and integrity metadata for one atomically appended tick."""

    run_id: RunId
    tick: Tick
    resulting_tick: Tick
    base_revision: WorldRevision
    resulting_revision: WorldRevision
    predecessor_commit_hash: CommitHash | None
    commit_hash: CommitHash
    idempotency_key: str
    event_count: int
    payload_hash: PayloadHash
    snapshot_id: SnapshotId | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("TickCommit.run_id must be RunId")
        if type(self.tick) is not Tick:
            raise TypeError("TickCommit.tick must be Tick")
        if type(self.resulting_tick) is not Tick:
            raise TypeError("TickCommit.resulting_tick must be Tick")
        if self.resulting_tick.value != self.tick.value + 1:
            raise ValueError("TickCommit.resulting_tick must be exactly tick + 1")
        if type(self.base_revision) is not WorldRevision:
            raise TypeError("TickCommit.base_revision must be WorldRevision")
        if type(self.resulting_revision) is not WorldRevision:
            raise TypeError("TickCommit.resulting_revision must be WorldRevision")
        if self.resulting_revision.value < self.base_revision.value:
            raise ValueError(
                "TickCommit.resulting_revision must be >= base_revision"
            )
        if self.predecessor_commit_hash is not None and type(
            self.predecessor_commit_hash
        ) is not CommitHash:
            raise TypeError(
                "TickCommit.predecessor_commit_hash must be CommitHash or None"
            )
        if type(self.commit_hash) is not CommitHash:
            raise TypeError("TickCommit.commit_hash must be CommitHash")
        object.__setattr__(
            self,
            "idempotency_key",
            require_stable_id("TickCommit.idempotency_key", self.idempotency_key),
        )
        object.__setattr__(
            self,
            "event_count",
            require_exact_nonneg_int("TickCommit.event_count", self.event_count),
        )
        if type(self.payload_hash) is not PayloadHash:
            raise TypeError("TickCommit.payload_hash must be PayloadHash")
        if self.snapshot_id is not None and type(self.snapshot_id) is not SnapshotId:
            raise TypeError("TickCommit.snapshot_id must be SnapshotId or None")


@dataclass(frozen=True, slots=True)
class TickAppendRequest:
    """Atomic tick append input with optimistic predecessor checks."""

    run_id: RunId
    tick: Tick
    expected_base_revision: WorldRevision
    expected_predecessor_commit_hash: CommitHash | None
    idempotency_key: str
    events: Sequence[WorldEvent] = field(default_factory=tuple)
    snapshot: WorldSnapshot | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("TickAppendRequest.run_id must be RunId")
        if type(self.tick) is not Tick:
            raise TypeError("TickAppendRequest.tick must be Tick")
        if type(self.expected_base_revision) is not WorldRevision:
            raise TypeError(
                "TickAppendRequest.expected_base_revision must be WorldRevision"
            )
        if self.expected_predecessor_commit_hash is not None and type(
            self.expected_predecessor_commit_hash
        ) is not CommitHash:
            raise TypeError(
                "TickAppendRequest.expected_predecessor_commit_hash must be "
                "CommitHash or None"
            )
        object.__setattr__(
            self,
            "idempotency_key",
            require_stable_id(
                "TickAppendRequest.idempotency_key", self.idempotency_key
            ),
        )
        object.__setattr__(
            self, "events", _copy_events("TickAppendRequest.events", self.events)
        )
        for event in self.events:
            if event.run_id != self.run_id.value:
                raise ValueError(
                    "TickAppendRequest.events run_id must match request run_id"
                )
            if event.tick != self.tick.value:
                raise ValueError(
                    "TickAppendRequest.events tick must match request tick"
                )
        if self.snapshot is not None:
            if type(self.snapshot) is not WorldSnapshot:
                raise TypeError(
                    "TickAppendRequest.snapshot must be WorldSnapshot or None"
                )
            if self.snapshot.run_id != self.run_id:
                raise ValueError("TickAppendRequest.snapshot.run_id must match")
            if self.snapshot.next_tick.value != self.tick.value + 1:
                raise ValueError(
                    "TickAppendRequest.snapshot.next_tick must equal tick + 1"
                )
            if self.snapshot.predecessor_commit_hash != (
                self.expected_predecessor_commit_hash
            ):
                raise ValueError(
                    "TickAppendRequest.snapshot.predecessor_commit_hash must "
                    "match expected_predecessor_commit_hash"
                )


class ReplayFallbackPolicy(StrEnum):
    """Checkpoint selection policy for reconstruction."""

    LATEST_AT_OR_BEFORE = "latest_at_or_before"
    REQUIRE_EXACT = "require_exact"


class ReplayMode(StrEnum):
    """Whether a successful replay may continue appending to the same run."""

    CONTINUATION = "continuation"
    READONLY = "readonly"


class ReplayStatus(StrEnum):
    """Closed result status without embedding a live engine."""

    OK = "ok"
    SNAPSHOT_MISSING = "snapshot_missing"
    VERSION_INCOMPATIBLE = "version_incompatible"
    STREAM_DISCONTINUITY = "stream_discontinuity"
    TARGET_UNREACHABLE = "target_unreachable"


@dataclass(frozen=True, slots=True)
class ReplayRequest:
    """Public replay input. Engine materialization is owned by ReplayService."""

    run_id: RunId
    target_tick: Tick | None
    fallback_policy: ReplayFallbackPolicy = ReplayFallbackPolicy.LATEST_AT_OR_BEFORE

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("ReplayRequest.run_id must be RunId")
        if self.target_tick is not None and type(self.target_tick) is not Tick:
            raise TypeError("ReplayRequest.target_tick must be Tick or None")
        if type(self.fallback_policy) is not ReplayFallbackPolicy:
            raise TypeError(
                "ReplayRequest.fallback_policy must be ReplayFallbackPolicy"
            )


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Detached replay outcome metadata. No live WorldEngine is included."""

    run_id: RunId
    status: ReplayStatus
    mode: ReplayMode
    snapshot_id: SnapshotId | None
    snapshot_next_tick: Tick | None
    target_tick: Tick | None
    events_applied: int
    event_schema_version: int
    projector_version: str
    persistence_codec_version: str

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("ReplayResult.run_id must be RunId")
        if type(self.status) is not ReplayStatus:
            raise TypeError("ReplayResult.status must be ReplayStatus")
        if type(self.mode) is not ReplayMode:
            raise TypeError("ReplayResult.mode must be ReplayMode")
        if self.snapshot_id is not None and type(self.snapshot_id) is not SnapshotId:
            raise TypeError("ReplayResult.snapshot_id must be SnapshotId or None")
        if self.snapshot_next_tick is not None and type(
            self.snapshot_next_tick
        ) is not Tick:
            raise TypeError("ReplayResult.snapshot_next_tick must be Tick or None")
        if self.target_tick is not None and type(self.target_tick) is not Tick:
            raise TypeError("ReplayResult.target_tick must be Tick or None")
        object.__setattr__(
            self,
            "events_applied",
            require_exact_nonneg_int(
                "ReplayResult.events_applied", self.events_applied
            ),
        )
        object.__setattr__(
            self,
            "event_schema_version",
            require_exact_nonneg_int(
                "ReplayResult.event_schema_version", self.event_schema_version
            ),
        )
        object.__setattr__(
            self,
            "projector_version",
            _require_version_string(
                "ReplayResult.projector_version", self.projector_version
            ),
        )
        object.__setattr__(
            self,
            "persistence_codec_version",
            _require_version_string(
                "ReplayResult.persistence_codec_version",
                self.persistence_codec_version,
            ),
        )


class SimulationRunRepository(Protocol):
    """Create and load immutable run manifests."""

    async def create_run(self, request: RunCreateRequest) -> RunManifest: ...

    async def get_run(self, run_id: RunId) -> RunManifest | None: ...


class TickJournalRepository(Protocol):
    """Append-only tick commits and ordered event reads."""

    async def append_tick(self, request: TickAppendRequest) -> TickCommit: ...

    async def get_tick_commit(
        self, run_id: RunId, tick: Tick
    ) -> TickCommit | None: ...

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]: ...


class SnapshotRepository(Protocol):
    """Immutable checkpoint lookup."""

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None: ...

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None: ...


class ExperimentRepository(Protocol):
    """Experiment metadata and run assignment ports."""

    async def create_experiment(
        self, metadata: ExperimentMetadata
    ) -> ExperimentMetadata: ...

    async def assign_run(
        self, assignment: ExperimentRunAssignment
    ) -> ExperimentRunAssignment: ...

    async def get_experiment(
        self, experiment_id: ExperimentId
    ) -> ExperimentMetadata | None: ...


def persistence_diagnostic_fields(
    *,
    run_id: RunId | None = None,
    tick: Tick | None = None,
    revision: WorldRevision | None = None,
    record_count: int | None = None,
    version: str | int | None = None,
    commit_hash: CommitHash | PayloadHash | str | None = None,
) -> dict[str, str | int]:
    """Secret-safe fields for repository DEBUG/ERROR logs.

    Allowed: run ID, tick/revision cursor, record counts, version, hash prefix.
    Never include seeds, full configs, snapshots, event payloads, or experiment
    metadata values.
    """
    fields: dict[str, str | int] = {}
    if run_id is not None:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        fields["run_id"] = run_id.value
    if tick is not None:
        if type(tick) is not Tick:
            raise TypeError("tick must be Tick")
        fields["tick"] = tick.value
    if revision is not None:
        if type(revision) is not WorldRevision:
            raise TypeError("revision must be WorldRevision")
        fields["revision"] = revision.value
    if record_count is not None:
        fields["record_count"] = require_exact_nonneg_int(
            "record_count", record_count
        )
    if version is not None:
        if isinstance(version, bool) or not isinstance(version, (str, int)):
            raise TypeError("version must be str or int")
        if isinstance(version, str) and not version:
            raise ValueError("version must be non-empty")
        if isinstance(version, int) and version < 0:
            raise ValueError("version must be a non-negative integer")
        fields["version"] = version
    if commit_hash is not None:
        if type(commit_hash) is CommitHash:
            digest = commit_hash.value
        elif type(commit_hash) is PayloadHash:
            digest = commit_hash.value
        elif isinstance(commit_hash, str):
            digest = require_commit_hash("commit_hash", commit_hash)
        else:
            raise TypeError("commit_hash must be CommitHash, PayloadHash, or str")
        fields["hash_prefix"] = digest[:_HASH_PREFIX_LEN]
    return fields


def _copy_events(name: str, values: Sequence[WorldEvent]) -> tuple[WorldEvent, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    return normalize_events(values)
