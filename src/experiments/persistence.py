"""Experiment-specific persistence DTOs and ports (framework-free).

Concrete SQLAlchemy adapters live in ``persistence`` and may import these
contracts. The ``experiments`` package never imports SQLAlchemy.

Neutral analysis evidence rows live here so persistence adapters stay
analysis-free and the outer composition service can map them into analysis
sources without importing persistence.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from memory.models import MemoryTrace
from simulation.evidence import EvidenceManifest, OpaqueCanonicalEnvelope
from world.identifiers import require_exact_nonneg_int, require_stable_id

EXPERIMENT_RECORD_SCHEMA_VERSION = "experiment-record-v1"
TRUTH_SPEC_SCHEMA_VERSION = "claim-truth-v1"
METRIC_DOCUMENT_ENVELOPE_SCHEMA_VERSION = "metric-document-v1"


@dataclass(frozen=True, slots=True)
class ExperimentDefinitionRecord:
    """Immutable persisted experiment definition envelope."""

    experiment_id: str
    schema_version: str
    payload_hash: str
    definition_fingerprint: str

    def __post_init__(self) -> None:
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("schema_version", self.schema_version)
        require_stable_id("payload_hash", self.payload_hash)
        require_stable_id("definition_fingerprint", self.definition_fingerprint)


@dataclass(frozen=True, slots=True)
class ExperimentAssignmentRecord:
    """Immutable condition/seed/replicate assignment cell."""

    experiment_id: str
    condition_id: str
    seed_ordinal: int
    replicate_index: int
    run_id: str
    seed: int
    config_fingerprint: str

    def __post_init__(self) -> None:
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("condition_id", self.condition_id)
        require_stable_id("run_id", self.run_id)
        require_stable_id("config_fingerprint", self.config_fingerprint)
        if type(self.seed_ordinal) is not int or self.seed_ordinal < 0:
            raise ValueError("seed_ordinal must be non-negative int")
        if type(self.replicate_index) is not int or self.replicate_index < 0:
            raise ValueError("replicate_index must be non-negative int")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be non-negative int")


@dataclass(frozen=True, slots=True)
class ExperimentResultRecord:
    """Immutable final result for one assigned run."""

    run_id: str
    experiment_id: str
    condition_id: str
    payload_hash: str
    stop_reason: str
    ticks_committed: int

    def __post_init__(self) -> None:
        require_stable_id("run_id", self.run_id)
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("condition_id", self.condition_id)
        require_stable_id("payload_hash", self.payload_hash)
        require_stable_id("stop_reason", self.stop_reason)
        if type(self.ticks_committed) is not int or self.ticks_committed < 0:
            raise ValueError("ticks_committed must be non-negative int")


class ExperimentRecordRepository(Protocol):
    """Append-only experiment definition/assignment/result port."""

    async def append_definition(self, record: ExperimentDefinitionRecord) -> None: ...

    async def append_assignment(self, record: ExperimentAssignmentRecord) -> None: ...

    async def append_result(self, record: ExperimentResultRecord) -> None: ...

    async def get_definition(
        self, experiment_id: str
    ) -> ExperimentDefinitionRecord | None: ...

    async def list_assignments(
        self, experiment_id: str
    ) -> tuple[ExperimentAssignmentRecord, ...]: ...

    async def get_membership(
        self, *, experiment_id: str, run_id: str
    ) -> ExperimentMembership | None: ...

    async def get_membership_for_run(
        self, *, run_id: str
    ) -> ExperimentMembership | None: ...


@dataclass(frozen=True, slots=True)
class PersistedDerivationEdge:
    """Neutral derivation edge row (no analysis types)."""

    derived_memory_id: str
    source_memory_id: str
    ordinal: int
    reconstruction_id: str | None


@dataclass(frozen=True, slots=True)
class PersistedReconstructionRow:
    """Neutral reconstruction metadata row (no narrative payloads)."""

    reconstruction_id: str
    source_memory_ids: tuple[str, ...]
    created_tick: int
    generation: int
    policy_id: str
    policy_version: str
    used_provider: bool
    fallback_used: bool
    prompt_version: str | None
    schema_version: str | None
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class PersistedAnalysisSnapshot:
    """Detached subjective + objective evidence for one experiment membership.

    Framework-free. Persistence adapters produce these; composition maps them
    into analysis evidence sources. Events are opaque detached domain objects.
    """

    experiment_id: str
    run_id: str
    owner_id: str
    traces: tuple[MemoryTrace, ...]
    reconstructions: tuple[PersistedReconstructionRow, ...]
    derivation_edges: tuple[PersistedDerivationEdge, ...]
    events: tuple[object, ...]
    regional_context: PersistedRegionalContext | None = None
    objective_complete_through_boundary: int | None = None

    def __post_init__(self) -> None:
        if (
            self.regional_context is not None
            and type(self.regional_context) is not PersistedRegionalContext
        ):
            raise TypeError("regional_context must be PersistedRegionalContext or None")
        if self.objective_complete_through_boundary is not None:
            object.__setattr__(
                self,
                "objective_complete_through_boundary",
                require_exact_nonneg_int(
                    "objective_complete_through_boundary",
                    self.objective_complete_through_boundary,
                ),
            )

    def __repr__(self) -> str:
        return (
            f"PersistedAnalysisSnapshot(experiment_id={self.experiment_id!r}, "
            f"run_id={self.run_id!r}, owner_id={self.owner_id!r}, "
            f"trace_count={len(self.traces)}, "
            f"reconstruction_count={len(self.reconstructions)}, "
            f"edge_count={len(self.derivation_edges)}, "
            f"event_count={len(self.events)}, "
            f"has_regional_context={self.regional_context is not None}, "
            f"complete_boundary={self.objective_complete_through_boundary})"
        )


@dataclass(frozen=True, slots=True)
class PersistedRegionalLocation:
    """Detached location-to-region assignment from the bootstrap snapshot."""

    location_id: str
    region_id: str

    def __post_init__(self) -> None:
        require_stable_id("location_id", self.location_id)
        require_stable_id("region_id", self.region_id)


@dataclass(frozen=True, slots=True)
class PersistedRegionalInitialPlacement:
    """Detached bootstrap placement and optional lifecycle cohort facts."""

    body_id: str
    location_id: str
    alive: bool
    stage_id: str | None = None
    cohort_id: str | None = None

    def __post_init__(self) -> None:
        require_stable_id("body_id", self.body_id)
        require_stable_id("location_id", self.location_id)
        if type(self.alive) is not bool:
            raise TypeError("alive must be bool")
        for name in ("stage_id", "cohort_id"):
            value = getattr(self, name)
            if value is not None:
                require_stable_id(name, value)


@dataclass(frozen=True, slots=True)
class PersistedRegionalContext:
    """Neutral analysis-only region memberships and initial population state."""

    region_ids: tuple[str, ...]
    known_location_ids: tuple[str, ...]
    locations: tuple[PersistedRegionalLocation, ...]
    initial_placements: tuple[PersistedRegionalInitialPlacement, ...]
    owner_ids: tuple[str, ...]
    residence_min_ticks: int

    def __post_init__(self) -> None:
        for field_name in (
            "region_ids",
            "known_location_ids",
            "locations",
            "initial_placements",
            "owner_ids",
        ):
            value = getattr(self, field_name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise TypeError(f"{field_name} must be a tuple")
        regions = tuple(
            require_stable_id("region_id", item) for item in self.region_ids
        )
        if not regions or len(regions) != len(set(regions)):
            raise ValueError("invalid_regional_context_regions")
        object.__setattr__(self, "region_ids", tuple(sorted(regions)))
        known_locations = tuple(
            require_stable_id("location_id", item) for item in self.known_location_ids
        )
        if not known_locations or len(set(known_locations)) != len(known_locations):
            raise ValueError("invalid_regional_context_locations")
        object.__setattr__(self, "known_location_ids", tuple(sorted(known_locations)))
        if any(type(item) is not PersistedRegionalLocation for item in self.locations):
            raise TypeError("locations entries must be PersistedRegionalLocation")
        if any(
            type(item) is not PersistedRegionalInitialPlacement
            for item in self.initial_placements
        ):
            raise TypeError(
                "initial_placements entries must be PersistedRegionalInitialPlacement"
            )
        if len({item.location_id for item in self.locations}) != len(self.locations):
            raise ValueError("duplicate_regional_location")
        if any(item.location_id not in known_locations for item in self.locations):
            raise ValueError("regional_membership_location_unknown")
        if len({item.body_id for item in self.initial_placements}) != len(
            self.initial_placements
        ):
            raise ValueError("duplicate_regional_body")
        if any(item.region_id not in regions for item in self.locations):
            raise ValueError("unknown_regional_membership")
        object.__setattr__(
            self,
            "owner_ids",
            tuple(
                sorted({require_stable_id("owner_id", item) for item in self.owner_ids})
            ),
        )
        residence_min = require_exact_nonneg_int(
            "residence_min_ticks", self.residence_min_ticks
        )
        if residence_min < 1:
            raise ValueError("residence_min_ticks_must_be_positive")
        object.__setattr__(self, "residence_min_ticks", residence_min)


def regional_context_from_snapshot(snapshot: object) -> PersistedRegionalContext | None:
    """Detach bootstrap population evidence at the experiment contract boundary."""
    from simulation.persistence import WorldSnapshot
    from world.lifecycle import AgentLifecycleRecord
    from world.models import LifeStatus

    if type(snapshot) is not WorldSnapshot:
        raise TypeError("regional bootstrap must be WorldSnapshot")
    spec = snapshot.regions_migration
    if spec is None:
        return None
    lifecycle: dict[str, tuple[str | None, str | None]] = {}
    for row in snapshot.lifecycle_records:
        if type(row) is not AgentLifecycleRecord:
            raise TypeError("bootstrap lifecycle records must be AgentLifecycleRecord")
        lifecycle[row.body_id.value] = (row.stage.value, row.cohort_id)
    return PersistedRegionalContext(
        region_ids=tuple(row.region_id for row in spec.regions),
        known_location_ids=tuple(item.entity_id.value for item in snapshot.locations),
        locations=tuple(
            PersistedRegionalLocation(row.location_id.value, row.region_id)
            for row in spec.location_regions
        ),
        initial_placements=tuple(
            PersistedRegionalInitialPlacement(
                body_id=body.entity_id.value,
                location_id=body.location_id.value,
                alive=body.life_status is LifeStatus.ALIVE,
                stage_id=lifecycle.get(body.entity_id.value, (None, None))[0],
                cohort_id=lifecycle.get(body.entity_id.value, (None, None))[1],
            )
            for body in snapshot.bodies
        ),
        owner_ids=tuple(row.agent_id.value for row in snapshot.registrations),
        residence_min_ticks=spec.residence_min_ticks,
    )


class AnalysisEvidenceSnapshotReader(Protocol):
    """Async reader returning neutral analysis snapshots (no analysis imports).

    ``experiment_id`` may be omitted for run-scoped loads without experiment
    membership. When provided, adapters must verify canonical membership.
    """

    async def load(
        self,
        *,
        run_id: str,
        owner_id: str,
        experiment_id: str | None = None,
        manifest: EvidenceManifest | None = None,
    ) -> PersistedAnalysisSnapshot: ...


@dataclass(frozen=True, slots=True)
class ObjectiveEventPage:
    """Manifest-pinned keyset page of committed objective events."""

    run_id: str
    events: tuple[object, ...]
    complete_through_boundary: int
    next_tick: int | None = None
    next_sequence: int | None = None
    manifest_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self,
            "complete_through_boundary",
            require_exact_nonneg_int(
                "complete_through_boundary", self.complete_through_boundary
            ),
        )
        if type(self.events) is not tuple:
            raise TypeError("events must be a tuple")
        for name in ("next_tick", "next_sequence"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative int or None")
        if (self.next_tick is None) != (self.next_sequence is None):
            raise ValueError("next_tick and next_sequence must both be set or None")
        if self.manifest_hash is not None:
            object.__setattr__(
                self,
                "manifest_hash",
                require_stable_id("manifest_hash", self.manifest_hash),
            )

    @property
    def exhausted(self) -> bool:
        return self.next_tick is None

    def __repr__(self) -> str:
        return (
            f"ObjectiveEventPage(run_id={self.run_id!r}, "
            f"event_count={len(self.events)}, "
            f"boundary={self.complete_through_boundary}, "
            f"exhausted={self.exhausted})"
        )


SUBJECTIVE_EVIDENCE_LANES = (
    "direct_traces",
    "communicated_traces",
    "reconstructions",
    "derivation_edges",
)


@dataclass(frozen=True, slots=True)
class SubjectiveEvidencePage:
    """Owner-scoped, manifest-clamped keyset page of one subjective lane.

    A page carries rows from exactly one ordered lane so callers can stream
    traces, reconstructions and derivation edges without materializing a whole
    owner. ``next_tick``/``next_id`` are exclusive trace or reconstruction
    cursors; derivation edges use ``next_id``/``next_ordinal`` instead.
    """

    run_id: str
    owner_id: str
    lane: str
    traces: tuple[MemoryTrace, ...] = ()
    reconstructions: tuple[PersistedReconstructionRow, ...] = ()
    derivation_edges: tuple[PersistedDerivationEdge, ...] = ()
    next_tick: int | None = None
    next_id: str | None = None
    next_ordinal: int | None = None
    manifest_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self, "owner_id", require_stable_id("owner_id", self.owner_id)
        )
        if self.lane not in SUBJECTIVE_EVIDENCE_LANES:
            raise ValueError("invalid_subjective_lane")
        for name in ("traces", "reconstructions", "derivation_edges"):
            if type(getattr(self, name)) is not tuple:
                raise TypeError(f"{name} must be a tuple")
        populated = sum(
            bool(item)
            for item in (self.traces, self.reconstructions, self.derivation_edges)
        )
        if populated > 1:
            raise ValueError("subjective_page_mixed_lanes")
        if self.traces and self.lane not in ("direct_traces", "communicated_traces"):
            raise ValueError("subjective_page_lane_mismatch")
        if self.reconstructions and self.lane != "reconstructions":
            raise ValueError("subjective_page_lane_mismatch")
        if self.derivation_edges and self.lane != "derivation_edges":
            raise ValueError("subjective_page_lane_mismatch")
        if populated == 0 and self.next_id is not None:
            raise ValueError("subjective_page_empty_with_cursor")
        if self.next_id is None:
            if self.next_tick is not None or self.next_ordinal is not None:
                raise ValueError("subjective_page_cursor_incomplete")
        else:
            object.__setattr__(
                self, "next_id", require_stable_id("next_id", self.next_id)
            )
            if self.lane == "derivation_edges":
                if self.next_tick is not None:
                    raise ValueError("subjective_page_cursor_shape")
                if type(self.next_ordinal) is not int or self.next_ordinal < 0:
                    raise ValueError("subjective_page_cursor_shape")
            else:
                if self.next_tick is None:
                    raise ValueError("subjective_page_cursor_shape")
                object.__setattr__(
                    self,
                    "next_tick",
                    require_exact_nonneg_int("next_tick", self.next_tick),
                )
                if self.next_ordinal is not None:
                    raise ValueError("subjective_page_cursor_shape")
        if self.manifest_hash is not None:
            object.__setattr__(
                self,
                "manifest_hash",
                require_stable_id("manifest_hash", self.manifest_hash),
            )

    @property
    def exhausted(self) -> bool:
        return self.next_id is None

    def __repr__(self) -> str:
        return (
            f"SubjectiveEvidencePage(run_id={self.run_id!r}, "
            f"owner_id={self.owner_id!r}, lane={self.lane!r}, "
            f"trace_count={len(self.traces)}, "
            f"reconstruction_count={len(self.reconstructions)}, "
            f"edge_count={len(self.derivation_edges)}, "
            f"exhausted={self.exhausted})"
        )


class PagedObjectiveEvidenceReader(Protocol):
    """Bounded objective-event pages under one verified boundary."""

    async def load_objective_event_page(
        self,
        *,
        run_id: str,
        manifest: EvidenceManifest | None = None,
        after_tick: int | None = None,
        after_sequence: int | None = None,
        limit: int = 1_000,
    ) -> ObjectiveEventPage: ...


class PagedSubjectiveEvidenceReader(Protocol):
    """Bounded owner-scoped subjective lane pages with manifest clamping."""

    async def load_subjective_evidence_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        manifest: EvidenceManifest | None = None,
        lane: str = "direct_traces",
        after_tick: int | None = None,
        after_id: str | None = None,
        after_ordinal: int | None = None,
        limit: int = 1_000,
    ) -> SubjectiveEvidencePage: ...


class PagedAnalysisEvidenceReader(
    PagedObjectiveEvidenceReader, PagedSubjectiveEvidenceReader, Protocol
):
    """Optional paged reader over the same verified evidence as ``load``.

    Implementations must apply the same manifest high-water clamp and run/owner
    scope as the full loader. ``next_*`` cursors are exclusive and stable under
    concurrent appends beyond the pinned boundary.
    """


class EvidenceManifestRepository(Protocol):
    """Port for durable evidence manifests (implemented by persistence)."""

    async def get_manifest(
        self, run_id: str, *, manifest_hash: str | None = None
    ) -> EvidenceManifest | None: ...

    async def append_manifest(self, manifest: EvidenceManifest) -> None: ...

    async def list_manifests(self, *, run_id: str) -> tuple[EvidenceManifest, ...]: ...


class EvidenceAvailability(StrEnum):
    """Whether claim truth / metric evidence bytes are durable."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class TruthSpecRecord:
    """Opaque claim-level truth specification for one run.

    Persistence stores canonical bytes/hashes only — never imports analysis.
    """

    run_id: str
    claim_id: str
    availability: EvidenceAvailability
    envelope: OpaqueCanonicalEnvelope | None

    def __post_init__(self) -> None:
        require_stable_id("run_id", self.run_id)
        require_stable_id("claim_id", self.claim_id)
        if type(self.availability) is not EvidenceAvailability:
            raise TypeError("availability must be EvidenceAvailability")
        if self.availability is EvidenceAvailability.UNAVAILABLE:
            if self.envelope is not None:
                raise ValueError("unavailable_truth_must_omit_envelope")
        else:
            if self.envelope is None:
                raise ValueError("available_truth_requires_envelope")
            if type(self.envelope) is not OpaqueCanonicalEnvelope:
                raise TypeError("envelope must be OpaqueCanonicalEnvelope")

    def __repr__(self) -> str:
        hash_prefix = None if self.envelope is None else self.envelope.content_hash[:12]
        return (
            f"TruthSpecRecord(run_id={self.run_id!r}, claim_id={self.claim_id!r}, "
            f"availability={self.availability.value!r}, hash_prefix={hash_prefix!r})"
        )


class TruthSpecRepository(Protocol):
    """Append-only claim truth specs (opaque envelopes)."""

    async def append_truth_spec(self, record: TruthSpecRecord) -> None: ...

    async def get_truth_spec(
        self, *, run_id: str, claim_id: str
    ) -> TruthSpecRecord | None: ...

    async def list_truth_specs(self, *, run_id: str) -> tuple[TruthSpecRecord, ...]: ...


class MetricSetLifecycle(StrEnum):
    """Metric-set lifecycle distinct from objective run completion."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MetricSetRecord:
    """Mutable metric-set head linked to one evidence-manifest revision."""

    run_id: str
    metric_set_id: str
    lifecycle_state: MetricSetLifecycle
    evidence_manifest_hash: str
    lifecycle_version: int = 0

    def __post_init__(self) -> None:
        require_stable_id("run_id", self.run_id)
        require_stable_id("metric_set_id", self.metric_set_id)
        require_stable_id("evidence_manifest_hash", self.evidence_manifest_hash)
        if type(self.lifecycle_state) is not MetricSetLifecycle:
            raise TypeError("lifecycle_state must be MetricSetLifecycle")
        object.__setattr__(
            self,
            "lifecycle_version",
            require_exact_nonneg_int("lifecycle_version", self.lifecycle_version),
        )


@dataclass(frozen=True, slots=True)
class MetricDocumentRecord:
    """Immutable metric document linked to a metric set and evidence revision."""

    run_id: str
    metric_set_id: str
    metric_family: str
    evidence_manifest_hash: str
    envelope: OpaqueCanonicalEnvelope

    def __post_init__(self) -> None:
        require_stable_id("run_id", self.run_id)
        require_stable_id("metric_set_id", self.metric_set_id)
        require_stable_id("metric_family", self.metric_family)
        require_stable_id("evidence_manifest_hash", self.evidence_manifest_hash)
        if type(self.envelope) is not OpaqueCanonicalEnvelope:
            raise TypeError("envelope must be OpaqueCanonicalEnvelope")

    def __repr__(self) -> str:
        return (
            f"MetricDocumentRecord(run_id={self.run_id!r}, "
            f"metric_set_id={self.metric_set_id!r}, "
            f"metric_family={self.metric_family!r}, "
            f"hash_prefix={self.envelope.content_hash[:12]!r})"
        )


class MetricSetRepository(Protocol):
    """Metric-set lifecycle portal (optimistic version transitions)."""

    async def upsert_metric_set(self, record: MetricSetRecord) -> MetricSetRecord: ...

    async def get_metric_set(
        self, *, run_id: str, metric_set_id: str
    ) -> MetricSetRecord | None: ...

    async def transition_metric_set(
        self,
        *,
        run_id: str,
        metric_set_id: str,
        expected_version: int,
        to_state: MetricSetLifecycle,
    ) -> MetricSetRecord: ...


class MetricDocumentRepository(Protocol):
    """Append-only immutable metric documents."""

    async def append_metric_document(self, record: MetricDocumentRecord) -> None: ...

    async def get_metric_document(
        self, *, run_id: str, metric_set_id: str, metric_family: str
    ) -> MetricDocumentRecord | None: ...

    async def list_metric_documents(
        self, *, run_id: str, metric_set_id: str | None = None
    ) -> tuple[MetricDocumentRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class ExperimentMembership:
    """Canonical experiment/run membership (assignment preferred over legacy)."""

    experiment_id: str
    run_id: str
    source: str
    condition_id: str | None = None
    ordinal: int | None = None

    def __post_init__(self) -> None:
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("run_id", self.run_id)
        require_stable_id("source", self.source)
        if self.source not in {"assignment", "legacy_run"}:
            raise ValueError("source must be assignment or legacy_run")
        if self.condition_id is not None:
            require_stable_id("condition_id", self.condition_id)
        if self.ordinal is not None and (
            type(self.ordinal) is not int or self.ordinal < 0
        ):
            raise ValueError("ordinal must be non-negative int")


class ExperimentMembershipRepository(Protocol):
    """Canonical membership lookup across assignments and legacy experiment_runs."""

    async def get_membership(
        self, *, experiment_id: str, run_id: str
    ) -> ExperimentMembership | None: ...

    async def get_membership_for_run(
        self, *, run_id: str
    ) -> ExperimentMembership | None: ...


@dataclass(frozen=True, slots=True)
class EvidenceSpoolStatus:
    """Metadata-only append/seal status for one optional evidence spool."""

    active: bool
    failed: bool
    sealed: bool
    truncated: bool
    failure_code: str | None
    record_count: int
    byte_count: int
    first_boundary: int | None
    last_boundary: int | None

    def __post_init__(self) -> None:
        for name in ("active", "failed", "sealed", "truncated"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be bool")
        for name in ("record_count", "byte_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be non-negative int")
        for name in ("first_boundary", "last_boundary"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be non-negative int or None")
        if (self.first_boundary is None) != (self.last_boundary is None):
            raise ValueError("first/last boundary must both be set or None")
        if self.failure_code is not None:
            require_stable_id("failure_code", self.failure_code)
        if self.failed and self.failure_code is None:
            raise ValueError("failed spool requires a failure_code")


class EvidenceSpool(Protocol):
    """Byte-oriented append-only evidence storage behind a neutral port.

    Payload DTO encoding/validation belongs to the experiment or simulation
    owner. The spool stores verified bytes plus lane/boundary/identity metadata
    and never imports analysis.
    """

    def append(
        self,
        *,
        lane: str,
        boundary_tick: int,
        identity: str,
        payload: bytes,
    ) -> bool:
        """Append one record; return True when newly stored, False if identical."""

    def get(self, *, lane: str, identity: str) -> bytes | None: ...

    def read_boundary(self, *, lane: str, boundary_tick: int) -> tuple[bytes, ...]: ...

    def iter_lane(
        self,
        *,
        lane: str,
        after_boundary: int | None,
        limit: int,
    ) -> tuple[bytes, ...]: ...

    def seal(self) -> EvidenceSpoolStatus: ...

    def status(self) -> EvidenceSpoolStatus: ...

    def lane_status(self, lane: str) -> EvidenceSpoolStatus: ...


async def iter_objective_event_pages(
    reader: PagedObjectiveEvidenceReader,
    *,
    run_id: str,
    manifest: EvidenceManifest | None = None,
    limit: int = 1_000,
) -> AsyncIterator[object]:
    """Iterate verified objective events with a pinned boundary and cursor guard."""
    async for page in iter_objective_event_page_batches(
        reader, run_id=run_id, manifest=manifest, limit=limit
    ):
        for event in page.events:
            yield event


async def iter_objective_event_page_batches(
    reader: PagedObjectiveEvidenceReader,
    *,
    run_id: str,
    manifest: EvidenceManifest | None = None,
    limit: int = 1_000,
) -> AsyncIterator[ObjectiveEventPage]:
    """Iterate verified objective pages, pinning boundary and manifest scope."""
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive int")
    pinned_manifest = None if manifest is None else manifest.manifest_hash
    after_tick: int | None = None
    after_sequence: int | None = None
    pinned_boundary: int | None = None
    while True:
        page = await reader.load_objective_event_page(
            run_id=run_id,
            manifest=manifest,
            after_tick=after_tick,
            after_sequence=after_sequence,
            limit=limit,
        )
        if page.run_id != run_id:
            raise ValueError("page_run_mismatch")
        if (
            pinned_manifest is not None
            and page.manifest_hash is not None
            and page.manifest_hash != pinned_manifest
        ):
            raise ValueError("page_manifest_changed")
        if pinned_boundary is None:
            pinned_boundary = page.complete_through_boundary
        elif page.complete_through_boundary != pinned_boundary:
            raise ValueError("page_boundary_changed")
        yield page
        if page.exhausted:
            return
        next_tick = page.next_tick
        next_sequence = page.next_sequence
        if next_tick is None or next_sequence is None:
            raise ValueError("page_cursor_missing")
        if after_tick is not None and after_sequence is not None:
            if (next_tick, next_sequence) <= (after_tick, after_sequence):
                raise ValueError("page_cursor_nonadvancing")
        after_tick, after_sequence = next_tick, next_sequence


async def iter_subjective_evidence_pages(
    reader: PagedSubjectiveEvidenceReader,
    *,
    run_id: str,
    owner_id: str,
    manifest: EvidenceManifest | None = None,
    limit: int = 1_000,
) -> AsyncIterator[SubjectiveEvidencePage]:
    """Iterate all subjective lanes in fixed order with manifest pinning.

    Lanes are emitted as ``direct_traces``, ``communicated_traces``,
    ``reconstructions`` and ``derivation_edges``. Each lane streams keyset pages
    until exhausted; run/owner/lane scope and the pinned manifest hash are
    verified on every page.
    """
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive int")
    pinned_manifest = None if manifest is None else manifest.manifest_hash
    for lane in SUBJECTIVE_EVIDENCE_LANES:
        after_tick: int | None = None
        after_id: str | None = None
        after_ordinal: int | None = None
        while True:
            page = await reader.load_subjective_evidence_page(
                run_id=run_id,
                owner_id=owner_id,
                manifest=manifest,
                lane=lane,
                after_tick=after_tick,
                after_id=after_id,
                after_ordinal=after_ordinal,
                limit=limit,
            )
            if page.run_id != run_id or page.owner_id != owner_id:
                raise ValueError("page_scope_mismatch")
            if page.lane != lane:
                raise ValueError("page_lane_mismatch")
            if pinned_manifest is not None and page.manifest_hash != pinned_manifest:
                raise ValueError("page_manifest_changed")
            yield page
            if page.exhausted:
                break
            next_tick = page.next_tick
            next_id = page.next_id
            next_ordinal = page.next_ordinal
            if next_id is None:
                raise ValueError("page_cursor_missing")
            if lane == "derivation_edges":
                if next_ordinal is None or next_tick is not None:
                    raise ValueError("page_cursor_missing")
                if after_id is not None and after_ordinal is not None:
                    if (next_id, next_ordinal) <= (after_id, after_ordinal):
                        raise ValueError("page_cursor_nonadvancing")
            else:
                if next_tick is None or next_ordinal is not None:
                    raise ValueError("page_cursor_missing")
                if after_tick is not None and after_id is not None:
                    if (next_tick, next_id) <= (after_tick, after_id):
                        raise ValueError("page_cursor_nonadvancing")
            after_tick, after_id, after_ordinal = next_tick, next_id, next_ordinal
