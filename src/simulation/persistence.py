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
from simulation.evidence import (
    ActionResolutionRecord,
    EvidenceManifest,
    GoalRevisionRecord,
)
from simulation.models import (
    DERIVATION_VERSION,
    RunId,
    SimulationRunConfig,
    require_seed,
)
from simulation.run_control import (
    ExecutionLease,
    RunControlRecord,
    RunLifecycleState,
    RunLifecycleTransition,
    StreamRecord,
    StreamRecordDraft,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V2,
    EVENT_SCHEMA_REPLAY_V3,
    EVENT_SCHEMA_REPLAY_V4,
    EVENT_SCHEMA_REPLAY_V5,
    WorldEvent,
    normalize_events,
)
from world.identifiers import (
    WorldId,
    WorldRevision,
    require_bounded_text,
    require_stable_id,
)
from world.models import AgentBody, Item, Location, Resource, Weather

# New-write versions for physical replay-v5 runs (structured communication).
# Taxonomy / accepted-set policy: see simulation.compatibility.COMPATIBILITY_MATRIX.
EVENT_SCHEMA_VERSION: Final[int] = EVENT_SCHEMA_REPLAY_V5
PROJECTOR_VERSION: Final[str] = "v2"
PERSISTENCE_CODEC_VERSION: Final[str] = "v2"

# Accepted restore/decode versions (legacy replay-v2/v3/v4 remain restorable).
ACCEPTED_EVENT_SCHEMA_VERSIONS: Final[frozenset[int]] = frozenset(
    {
        EVENT_SCHEMA_REPLAY_V2,
        EVENT_SCHEMA_REPLAY_V3,
        EVENT_SCHEMA_REPLAY_V4,
        EVENT_SCHEMA_REPLAY_V5,
    }
)
ACCEPTED_PROJECTOR_VERSIONS: Final[frozenset[str]] = frozenset({"v1", "v2"})
ACCEPTED_PERSISTENCE_CODEC_VERSIONS: Final[frozenset[str]] = frozenset({"v1", "v2"})

_SHA256_HEX_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_HASH_PREFIX_LEN: Final[int] = 8

__all__ = [
    "ACCEPTED_EVENT_SCHEMA_VERSIONS",
    "ACCEPTED_PERSISTENCE_CODEC_VERSIONS",
    "ACCEPTED_PROJECTOR_VERSIONS",
    "EVENT_SCHEMA_VERSION",
    "LEGACY_PENDING_FINALIZATION_CODEC_VERSION",
    "PENDING_FINALIZATION_CODEC_VERSION",
    "PERSISTENCE_CODEC_VERSION",
    "PROJECTOR_VERSION",
    "CommitHash",
    "ExperimentId",
    "ExperimentMetadata",
    "ExperimentRepository",
    "ExperimentRunAssignment",
    "FinalizedBoundaryBatch",
    "PayloadHash",
    "PendingFinalizationRecord",
    "PendingFinalizationRepository",
    "PendingFinalizationStatus",
    "ReplayCommitPage",
    "ReplayEventPage",
    "ReplayFallbackPolicy",
    "ReplayMode",
    "ReplayRequest",
    "ReplayResult",
    "ReplayStatus",
    "RunControlRepository",
    "RunCreateRequest",
    "RunManifest",
    "RunnerAttemptStateRecord",
    "RunnerAttemptStateRepository",
    "ScientificEvidenceRepository",
    "SimulationRunRepository",
    "SnapshotId",
    "SnapshotRepository",
    "StreamRepository",
    "TickAppendRequest",
    "TickCommit",
    "TickJournalRepository",
    "WorldEvent",
    "WorldSnapshot",
    "persistence_diagnostic_fields",
    "require_commit_hash",
    "require_payload_hash",
    "schema_projector_compatible",
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


def _require_accepted_schema_version(name: str, value: object) -> int:
    version = require_exact_nonneg_int(name, value)
    if version not in ACCEPTED_EVENT_SCHEMA_VERSIONS:
        raise ValueError(
            f"{name} must be an accepted event schema version "
            f"({sorted(ACCEPTED_EVENT_SCHEMA_VERSIONS)})"
        )
    return version


def _require_write_schema_version(name: str, value: object) -> int:
    version = require_exact_nonneg_int(name, value)
    if version != EVENT_SCHEMA_VERSION:
        raise ValueError(
            f"{name} must equal EVENT_SCHEMA_VERSION ({EVENT_SCHEMA_VERSION})"
        )
    return version


def _require_accepted_projector_version(name: str, value: object) -> str:
    version = _require_version_string(name, value)
    if version not in ACCEPTED_PROJECTOR_VERSIONS:
        raise ValueError(
            f"{name} must be an accepted projector version "
            f"({sorted(ACCEPTED_PROJECTOR_VERSIONS)})"
        )
    return version


def _require_write_projector_version(name: str, value: object) -> str:
    version = _require_version_string(name, value)
    if version != PROJECTOR_VERSION:
        raise ValueError(f"{name} must equal PROJECTOR_VERSION ({PROJECTOR_VERSION})")
    return version


def _require_accepted_persistence_codec_version(name: str, value: object) -> str:
    version = _require_version_string(name, value)
    if version not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS:
        raise ValueError(
            f"{name} must be an accepted persistence codec version "
            f"({sorted(ACCEPTED_PERSISTENCE_CODEC_VERSIONS)})"
        )
    return version


def _require_write_persistence_codec_version(name: str, value: object) -> str:
    version = _require_version_string(name, value)
    if version != PERSISTENCE_CODEC_VERSION:
        raise ValueError(
            f"{name} must equal PERSISTENCE_CODEC_VERSION ({PERSISTENCE_CODEC_VERSION})"
        )
    return version


def schema_projector_compatible(
    *, event_schema_version: int, projector_version: str
) -> bool:
    """True when schema and projector pair without mixed-version dispatch."""
    if event_schema_version == EVENT_SCHEMA_REPLAY_V2:
        return projector_version == "v1"
    if event_schema_version in {
        EVENT_SCHEMA_REPLAY_V3,
        EVENT_SCHEMA_REPLAY_V4,
        EVENT_SCHEMA_REPLAY_V5,
    }:
        return projector_version == "v2"
    return False


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
            _require_accepted_schema_version(
                "RunManifest.event_schema_version", self.event_schema_version
            ),
        )
        object.__setattr__(
            self,
            "projector_version",
            _require_accepted_projector_version(
                "RunManifest.projector_version", self.projector_version
            ),
        )
        object.__setattr__(
            self,
            "persistence_codec_version",
            _require_accepted_persistence_codec_version(
                "RunManifest.persistence_codec_version",
                self.persistence_codec_version,
            ),
        )
        if not schema_projector_compatible(
            event_schema_version=self.event_schema_version,
            projector_version=self.projector_version,
        ):
            raise ValueError(
                "RunManifest event schema and projector versions are incompatible"
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
            _require_accepted_schema_version(
                "WorldSnapshot.event_schema_version", self.event_schema_version
            ),
        )
        object.__setattr__(
            self,
            "projector_version",
            _require_accepted_projector_version(
                "WorldSnapshot.projector_version", self.projector_version
            ),
        )
        object.__setattr__(
            self,
            "persistence_codec_version",
            _require_accepted_persistence_codec_version(
                "WorldSnapshot.persistence_codec_version",
                self.persistence_codec_version,
            ),
        )
        if not schema_projector_compatible(
            event_schema_version=self.event_schema_version,
            projector_version=self.projector_version,
        ):
            raise ValueError(
                "WorldSnapshot event schema and projector versions are incompatible"
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
        if (
            self.predecessor_commit_hash is not None
            and type(self.predecessor_commit_hash) is not CommitHash
        ):
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
            _require_write_schema_version(
                "RunCreateRequest.event_schema_version", self.event_schema_version
            ),
        )
        object.__setattr__(
            self,
            "projector_version",
            _require_write_projector_version(
                "RunCreateRequest.projector_version", self.projector_version
            ),
        )
        object.__setattr__(
            self,
            "persistence_codec_version",
            _require_write_persistence_codec_version(
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
            raise ValueError("TickCommit.resulting_revision must be >= base_revision")
        if (
            self.predecessor_commit_hash is not None
            and type(self.predecessor_commit_hash) is not CommitHash
        ):
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
        if (
            self.expected_predecessor_commit_hash is not None
            and type(self.expected_predecessor_commit_hash) is not CommitHash
        ):
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
            # Checkpoint predecessor is this tick's commit hash (chain cursor
            # after the producing tick), not the tick write's expected
            # predecessor. The durable service/repository verifies equality
            # against the computed commit hash.
            if self.snapshot.predecessor_commit_hash is None:
                raise ValueError(
                    "TickAppendRequest.snapshot.predecessor_commit_hash must "
                    "equal this tick's commit hash"
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
    skill_policy: object | None = None
    skill_entity_ids: Sequence[object] | None = None
    skill_ledger: object | None = None
    skill_untargeted_request_ids: frozenset[str] | None = None
    teaching_policy: object | None = None
    teaching_entity_ids: Sequence[object] | None = None
    teaching_offers: object | None = None

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
        if (
            self.snapshot_next_tick is not None
            and type(self.snapshot_next_tick) is not Tick
        ):
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

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None: ...

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]: ...

    async def list_tick_commits(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
    ) -> tuple[TickCommit, ...]: ...


@dataclass(frozen=True, slots=True)
class ReplayEventPage:
    """Detached page of objective events for inspection without a live engine."""

    run_id: RunId
    from_tick: Tick
    to_tick: Tick | None
    limit: int
    offset: int
    events: tuple[WorldEvent, ...]
    next_offset: int | None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("ReplayEventPage.run_id must be RunId")
        if type(self.from_tick) is not Tick:
            raise TypeError("ReplayEventPage.from_tick must be Tick")
        if self.to_tick is not None and type(self.to_tick) is not Tick:
            raise TypeError("ReplayEventPage.to_tick must be Tick or None")
        object.__setattr__(
            self,
            "limit",
            require_exact_nonneg_int("ReplayEventPage.limit", self.limit),
        )
        object.__setattr__(
            self,
            "offset",
            require_exact_nonneg_int("ReplayEventPage.offset", self.offset),
        )
        if isinstance(self.events, (set, frozenset)):
            raise TypeError("events must be ordered")
        events = tuple(self.events)
        for item in events:
            if type(item) is not WorldEvent:
                raise TypeError("events entries must be WorldEvent")
        object.__setattr__(self, "events", events)
        if self.next_offset is not None:
            object.__setattr__(
                self,
                "next_offset",
                require_exact_nonneg_int(
                    "ReplayEventPage.next_offset", self.next_offset
                ),
            )


@dataclass(frozen=True, slots=True)
class ReplayCommitPage:
    """Detached page of tick commits for inspection without a live engine."""

    run_id: RunId
    from_tick: Tick
    to_tick: Tick | None
    commits: tuple[TickCommit, ...]
    next_from_tick: Tick | None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("ReplayCommitPage.run_id must be RunId")
        if type(self.from_tick) is not Tick:
            raise TypeError("ReplayCommitPage.from_tick must be Tick")
        if self.to_tick is not None and type(self.to_tick) is not Tick:
            raise TypeError("ReplayCommitPage.to_tick must be Tick or None")
        if isinstance(self.commits, (set, frozenset)):
            raise TypeError("commits must be ordered")
        commits = tuple(self.commits)
        for item in commits:
            if type(item) is not TickCommit:
                raise TypeError("commits entries must be TickCommit")
        object.__setattr__(self, "commits", commits)
        if self.next_from_tick is not None and type(self.next_from_tick) is not Tick:
            raise TypeError("next_from_tick must be Tick or None")


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


class PendingFinalizationStatus(StrEnum):
    """Outbox status for one pending subjective finalization."""

    PENDING = "pending"
    FINALIZED = "finalized"
    ABORTED = "aborted"


PENDING_FINALIZATION_CODEC_VERSION: Final[str] = "finalization-command-v1"
LEGACY_PENDING_FINALIZATION_CODEC_VERSION: Final[str] = "pending-finalization-v1"


@dataclass(frozen=True, slots=True)
class PendingFinalizationRecord:
    """Append-only pending finalization outbox row (not objective authority)."""

    run_id: RunId
    agent_id: str
    tick: int
    invocation_id: str
    integrity_hash: str
    codec_version: str
    payload: Mapping[str, object]
    status: PendingFinalizationStatus

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        require_stable_id("agent_id", self.agent_id)
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        require_stable_id("invocation_id", self.invocation_id)
        require_stable_id("integrity_hash", self.integrity_hash)
        require_stable_id("codec_version", self.codec_version)
        if type(self.status) is not PendingFinalizationStatus:
            raise TypeError("status must be PendingFinalizationStatus")
        if isinstance(self.payload, (str, bytes)) or not isinstance(
            self.payload, Mapping
        ):
            raise TypeError("payload must be a mapping")
        object.__setattr__(self, "payload", dict(self.payload))


@dataclass(frozen=True, slots=True)
class RunnerAttemptStateRecord:
    """Append-only runner attempt recovery state."""

    run_id: RunId
    attempt_id: str
    tick: int
    phase: str
    recovery_required: bool
    integrity_hash: str
    codec_version: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        require_stable_id("attempt_id", self.attempt_id)
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        require_stable_id("phase", self.phase)
        if type(self.recovery_required) is not bool:
            raise TypeError("recovery_required must be bool")
        require_stable_id("integrity_hash", self.integrity_hash)
        require_stable_id("codec_version", self.codec_version)
        if isinstance(self.payload, (str, bytes)) or not isinstance(
            self.payload, Mapping
        ):
            raise TypeError("payload must be a mapping")
        object.__setattr__(self, "payload", dict(self.payload))


class PendingFinalizationRepository(Protocol):
    """Append-only pending subjective finalization outbox."""

    async def append_pending(self, record: PendingFinalizationRecord) -> None: ...

    async def mark_finalized(
        self, *, run_id: RunId, agent_id: str, invocation_id: str
    ) -> None: ...

    async def mark_aborted(
        self, *, run_id: RunId, agent_id: str, invocation_id: str
    ) -> None: ...

    async def list_pending_for_tick(
        self, *, run_id: RunId, tick: int
    ) -> tuple[PendingFinalizationRecord, ...]: ...

    async def list_pending_for_run(
        self, *, run_id: RunId
    ) -> tuple[PendingFinalizationRecord, ...]: ...


class RunnerAttemptStateRepository(Protocol):
    """Append-only runner attempt recovery records."""

    async def append_attempt(self, record: RunnerAttemptStateRecord) -> None: ...

    async def list_recovery_required(
        self, *, run_id: RunId
    ) -> tuple[RunnerAttemptStateRecord, ...]: ...


class RunControlRepository(Protocol):
    """Durable run-control head: config V2, lifecycle, leases, progress."""

    async def upsert_configured(
        self,
        record: RunControlRecord,
    ) -> RunControlRecord: ...

    async def get(self, run_id: RunId) -> RunControlRecord | None: ...

    async def replace_configuration(
        self,
        record: RunControlRecord,
        *,
        expected_version: int,
    ) -> RunControlRecord: ...

    async def transition(
        self,
        *,
        run_id: RunId,
        expected_version: int,
        to_state: RunLifecycleState,
        reason_code: str,
        operation_id: str,
        ticks_committed: int | None = None,
        progress_cursor: int | None = None,
        terminal_reason_code: str | None = None,
    ) -> RunControlRecord: ...

    async def claim_lease(
        self,
        *,
        run_id: RunId,
        expected_version: int,
        lease: ExecutionLease,
        operation_id: str,
    ) -> RunControlRecord: ...

    async def heartbeat_lease(
        self,
        *,
        run_id: RunId,
        lease_id: str,
        heartbeat_at_unix_ms: int,
        expires_at_unix_ms: int,
        operation_id: str,
    ) -> RunControlRecord: ...

    async def release_lease(
        self,
        *,
        run_id: RunId,
        lease_id: str,
        operation_id: str,
    ) -> RunControlRecord: ...

    async def list_transitions(
        self, *, run_id: RunId
    ) -> tuple[RunLifecycleTransition, ...]: ...

    async def list_runs(
        self,
        *,
        after_run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[RunControlRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class FinalizedBoundaryBatch:
    """Atomic evidence + stream publication at a finalized tick boundary."""

    run_id: RunId
    tick: int
    resolutions: tuple[ActionResolutionRecord, ...] = ()
    goal_revisions: tuple[GoalRevisionRecord, ...] = ()
    stream_drafts: tuple[StreamRecordDraft, ...] = ()
    manifest: EvidenceManifest | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("tick", self.tick),
        )
        object.__setattr__(self, "resolutions", tuple(self.resolutions))
        object.__setattr__(self, "goal_revisions", tuple(self.goal_revisions))
        object.__setattr__(self, "stream_drafts", tuple(self.stream_drafts))
        for resolution in self.resolutions:
            if type(resolution) is not ActionResolutionRecord:
                raise TypeError("resolutions must be ActionResolutionRecord")
            if resolution.run_id != self.run_id.value:
                raise ValueError("resolution_run_mismatch")
        for goal in self.goal_revisions:
            if type(goal) is not GoalRevisionRecord:
                raise TypeError("goal_revisions must be GoalRevisionRecord")
            if goal.run_id != self.run_id.value:
                raise ValueError("goal_run_mismatch")
        for draft in self.stream_drafts:
            if type(draft) is not StreamRecordDraft:
                raise TypeError("stream_drafts must be StreamRecordDraft")
        if self.manifest is not None:
            if type(self.manifest) is not EvidenceManifest:
                raise TypeError("manifest must be EvidenceManifest")
            if self.manifest.run_id != self.run_id.value:
                raise ValueError("manifest_run_mismatch")


class ScientificEvidenceRepository(Protocol):
    """Append-only goal revisions, action resolutions, and evidence manifests."""

    async def append_goal_revision(self, record: GoalRevisionRecord) -> None: ...

    async def append_action_resolution(
        self, record: ActionResolutionRecord
    ) -> None: ...

    async def append_manifest(self, manifest: EvidenceManifest) -> None: ...

    async def get_manifest(
        self, *, run_id: str, manifest_hash: str | None = None
    ) -> EvidenceManifest | None: ...

    async def list_goal_revisions(
        self, *, run_id: str
    ) -> tuple[GoalRevisionRecord, ...]: ...

    async def list_action_resolutions(
        self, *, run_id: str, tick: int | None = None
    ) -> tuple[ActionResolutionRecord, ...]: ...

    async def publish_finalized_boundary(
        self, batch: FinalizedBoundaryBatch
    ) -> tuple[StreamRecord, ...]: ...


class StreamRepository(Protocol):
    """Unified durable stream/outbox with one monotonic cursor per run."""

    async def publish(
        self, *, run_id: RunId, drafts: Sequence[StreamRecordDraft]
    ) -> tuple[StreamRecord, ...]: ...

    async def read_after(
        self, *, run_id: RunId, after_cursor: int, limit: int
    ) -> tuple[StreamRecord, ...]: ...

    async def high_water(self, *, run_id: RunId) -> int: ...


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
        fields["record_count"] = require_exact_nonneg_int("record_count", record_count)
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
