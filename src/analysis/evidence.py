"""Closed evidence-stage taxonomy and run/owner-scoped evidence wrappers.

Immutable, log-free DTOs. Safe ``repr`` exposes IDs, stages, and counts only —
never payloads, claims, narratives, or metric values.

Does not import ``analysis.models`` at module load (MetricDocument imports this
module); model isinstance checks use deferred imports inside ``__post_init__``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from memory.models import MemoryTrace
from world.identifiers import require_stable_id

if TYPE_CHECKING:
    from analysis.models import ReconstructionEvidence, SubjectiveDerivationEdge

__all__ = [
    "EVIDENCE_STAGE_SCHEMA_VERSION",
    "EvidenceStage",
    "ScopedDerivationEdge",
    "ScopedEvidenceRef",
    "ScopedMemoryTrace",
    "ScopedReconstructionEvidence",
    "closed_evidence_stages",
    "require_evidence_stage",
]

EVIDENCE_STAGE_SCHEMA_VERSION: Final[str] = "1"


class EvidenceStage(StrEnum):
    """Closed set of scientific evidence stages for metric documents.

    Order is documentary only; membership is closed and fail-closed on unknown
    values. Stages must not be collapsed into a single narrative class.
    """

    OBJECTIVE_EVENT_STATE = "objective_event_state"
    AGENT_VISIBLE_PROJECTION = "agent_visible_projection"
    DIRECT_TRACE = "direct_trace"
    COMMUNICATED_TRACE = "communicated_trace"
    RECONSTRUCTION = "reconstruction"
    RECONSOLIDATED_TRACE = "reconsolidated_trace"
    BELIEF_REVISION_TESTIMONY = "belief_revision_testimony"
    RELATIONSHIP_REVISION = "relationship_revision"
    GOAL_TRANSITION = "goal_transition"
    ACTION_RESOLUTION = "action_resolution"


_CLOSED_STAGES: Final[frozenset[EvidenceStage]] = frozenset(EvidenceStage)


def closed_evidence_stages() -> frozenset[EvidenceStage]:
    """Return the closed membership set for validation and catalogs."""
    return _CLOSED_STAGES


def require_evidence_stage(label: str, value: object) -> EvidenceStage:
    """Validate a closed EvidenceStage; reject unknown members."""
    if type(value) is EvidenceStage:
        if value not in _CLOSED_STAGES:
            raise ValueError(f"{label}: unknown_evidence_stage")
        return value
    if isinstance(value, str):
        try:
            stage = EvidenceStage(value)
        except ValueError as exc:
            raise ValueError(f"{label}: unknown_evidence_stage") from exc
        if stage not in _CLOSED_STAGES:
            raise ValueError(f"{label}: unknown_evidence_stage")
        return stage
    raise TypeError(f"{label}: invalid_type")


@dataclass(frozen=True, slots=True)
class ScopedEvidenceRef:
    """Opaque, run-scoped pointer to one evidence item (no payload)."""

    run_id: str
    owner_id: str | None
    evidence_stage: EvidenceStage
    evidence_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("ScopedEvidenceRef.run_id", self.run_id),
        )
        if self.owner_id is not None:
            object.__setattr__(
                self,
                "owner_id",
                require_stable_id("ScopedEvidenceRef.owner_id", self.owner_id),
            )
        object.__setattr__(
            self,
            "evidence_stage",
            require_evidence_stage(
                "ScopedEvidenceRef.evidence_stage", self.evidence_stage
            ),
        )
        object.__setattr__(
            self,
            "evidence_id",
            require_stable_id("ScopedEvidenceRef.evidence_id", self.evidence_id),
        )

    def __repr__(self) -> str:
        return (
            f"ScopedEvidenceRef(run_id={self.run_id!r}, "
            f"owner_id={self.owner_id!r}, "
            f"evidence_stage={self.evidence_stage.value!r}, "
            f"evidence_id={self.evidence_id!r})"
        )


@dataclass(frozen=True, slots=True)
class ScopedMemoryTrace:
    """Memory trace stored under explicit run/owner scope and evidence stage."""

    run_id: str
    owner_id: str
    evidence_stage: EvidenceStage
    trace: MemoryTrace

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("ScopedMemoryTrace.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("ScopedMemoryTrace.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "evidence_stage",
            require_evidence_stage(
                "ScopedMemoryTrace.evidence_stage", self.evidence_stage
            ),
        )
        if type(self.trace) is not MemoryTrace:
            raise TypeError("ScopedMemoryTrace.trace: invalid_type")
        if self.trace.owner_id.value != self.owner_id:
            raise ValueError("ScopedMemoryTrace: owner_mismatch")
        if self.evidence_stage not in {
            EvidenceStage.DIRECT_TRACE,
            EvidenceStage.COMMUNICATED_TRACE,
            EvidenceStage.RECONSOLIDATED_TRACE,
        }:
            raise ValueError("ScopedMemoryTrace.evidence_stage: invalid_for_trace")

    def __repr__(self) -> str:
        return (
            f"ScopedMemoryTrace(run_id={self.run_id!r}, owner_id={self.owner_id!r}, "
            f"evidence_stage={self.evidence_stage.value!r}, "
            f"memory_id={self.trace.memory_id.value!r})"
        )


@dataclass(frozen=True, slots=True)
class ScopedReconstructionEvidence:
    """Reconstruction evidence already carrying run/owner, plus stage tag."""

    evidence_stage: EvidenceStage
    evidence: ReconstructionEvidence

    def __post_init__(self) -> None:
        from analysis.models import ReconstructionEvidence as ReconstructionEvidenceType

        object.__setattr__(
            self,
            "evidence_stage",
            require_evidence_stage(
                "ScopedReconstructionEvidence.evidence_stage", self.evidence_stage
            ),
        )
        if type(self.evidence) is not ReconstructionEvidenceType:
            raise TypeError("ScopedReconstructionEvidence.evidence: invalid_type")
        if self.evidence_stage is not EvidenceStage.RECONSTRUCTION:
            raise ValueError(
                "ScopedReconstructionEvidence.evidence_stage: must_be_reconstruction"
            )

    @property
    def run_id(self) -> str:
        return self.evidence.run_id

    @property
    def owner_id(self) -> str:
        return self.evidence.owner_id

    def __repr__(self) -> str:
        return (
            f"ScopedReconstructionEvidence("
            f"run_id={self.evidence.run_id!r}, "
            f"owner_id={self.evidence.owner_id!r}, "
            f"reconstruction_id={self.evidence.reconstruction_id!r})"
        )


@dataclass(frozen=True, slots=True)
class ScopedDerivationEdge:
    """Alias wrapper confirming a derivation edge carries run/owner scope."""

    edge: SubjectiveDerivationEdge

    def __post_init__(self) -> None:
        from analysis.models import SubjectiveDerivationEdge as EdgeType

        if type(self.edge) is not EdgeType:
            raise TypeError("ScopedDerivationEdge.edge: invalid_type")

    @property
    def run_id(self) -> str:
        return self.edge.run_id

    @property
    def owner_id(self) -> str:
        return self.edge.owner_id

    def __repr__(self) -> str:
        return (
            f"ScopedDerivationEdge(run_id={self.edge.run_id!r}, "
            f"owner_id={self.edge.owner_id!r}, "
            f"derived_memory_id={self.edge.derived_memory_id!r})"
        )
