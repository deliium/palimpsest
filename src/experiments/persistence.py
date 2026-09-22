"""Experiment-specific persistence DTOs and ports (framework-free).

Concrete SQLAlchemy adapters live in ``persistence`` and may import these
contracts. The ``experiments`` package never imports SQLAlchemy.

Neutral analysis evidence rows live here so persistence adapters stay
analysis-free and the outer composition service can map them into analysis
sources without importing persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memory.models import MemoryTrace
from simulation.evidence import EvidenceManifest
from world.identifiers import require_stable_id

EXPERIMENT_RECORD_SCHEMA_VERSION = "experiment-record-v1"


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
    """Async reader returning neutral analysis snapshots (no analysis imports)."""

    async def load(
        self,
        *,
        experiment_id: str,
        run_id: str,
        owner_id: str,
    ) -> PersistedAnalysisSnapshot: ...


class EvidenceManifestRepository(Protocol):
    """Port for durable evidence manifests (implemented by persistence later)."""

    async def get_manifest(self, run_id: str) -> EvidenceManifest | None: ...

    async def append_manifest(self, manifest: EvidenceManifest) -> None: ...
