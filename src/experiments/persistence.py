"""Experiment-specific persistence DTOs and ports (framework-free).

Concrete SQLAlchemy adapters live in ``persistence`` and may import these
contracts. The ``experiments`` package never imports SQLAlchemy.

Neutral analysis evidence rows live here so persistence adapters stay
analysis-free and the outer composition service can map them into analysis
sources without importing persistence.
"""

from __future__ import annotations

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

    def __repr__(self) -> str:
        return (
            f"PersistedAnalysisSnapshot(experiment_id={self.experiment_id!r}, "
            f"run_id={self.run_id!r}, owner_id={self.owner_id!r}, "
            f"trace_count={len(self.traces)}, "
            f"reconstruction_count={len(self.reconstructions)}, "
            f"edge_count={len(self.derivation_edges)}, "
            f"event_count={len(self.events)})"
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


class EvidenceManifestRepository(Protocol):
    """Port for durable evidence manifests (implemented by persistence)."""

    async def get_manifest(
        self, run_id: str, *, manifest_hash: str | None = None
    ) -> EvidenceManifest | None: ...

    async def append_manifest(self, manifest: EvidenceManifest) -> None: ...

    async def list_manifests(
        self, *, run_id: str
    ) -> tuple[EvidenceManifest, ...]: ...


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
        hash_prefix = (
            None if self.envelope is None else self.envelope.content_hash[:12]
        )
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

    async def list_truth_specs(
        self, *, run_id: str
    ) -> tuple[TruthSpecRecord, ...]: ...


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
