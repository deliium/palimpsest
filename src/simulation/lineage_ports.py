"""Bounded historical-lineage source, publication and capture ports.

Adapters enforce every read and byte allowance before touching storage. The
neutral query core never infers source cost from port-call count, and HTTP
callers cannot select a producer budget.

Framework-free. No persistence, API, analysis, experiments or ORM imports.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Final, Protocol

from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageNativeKind,
    require_lineage_key,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageDirection,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageQuery,
    LineageScope,
    LineageSnapshotRef,
    MentorshipLineageRecord,
    require_lineage_cursor,
)
from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CAPTURE_MAX_ARTIFACT_BYTES",
    "CAPTURE_MAX_EDGES",
    "CAPTURE_MAX_NODES",
    "CAPTURE_MAX_NORMALIZED_BYTES",
    "CAPTURE_MAX_PUBLICATION_RESERVATIONS",
    "DEFAULT_SOURCE_PAGE_READS",
    "DEFAULT_SOURCE_PAGE_SIZE",
    "MAX_RESPONSE_BYTES",
    "MAX_SOURCE_BYTES",
    "MAX_SOURCE_PAGE_READS",
    "MAX_SOURCE_PAGE_SIZE",
    "PRODUCER_MAX_SOURCE_BYTES",
    "PRODUCER_MAX_SOURCE_READS",
    "AgentLifecycleFact",
    "KinshipSourceEdge",
    "LineageBoundaryFrame",
    "LineageBoundarySink",
    "LineageNeighborPage",
    "LineageNeighborRow",
    "LineageNodeCatalogueCursor",
    "LineageNodeCataloguePage",
    "LineagePublication",
    "LineagePublicationPort",
    "LineageReadBudget",
    "LineageReadPort",
    "LineageReadReservation",
    "LineageReadSession",
    "LineageSnapshotCatalogueCursor",
    "LineageSnapshotCataloguePage",
    "LineageSourceProjection",
    "LineageTraversalCursor",
    "MentorshipBondSource",
    "NarrativeVariantSource",
    "OfficeConceptSource",
    "OfficeOccupantClaimSource",
    "OfficeSuccessionSource",
    "OwnerLineageSource",
    "PracticalKnowledgeSource",
    "RecordSourceArtifact",
    "RecordSourceEvent",
    "event_precedes_boundary",
    "lineage_query_fingerprint",
]

DEFAULT_SOURCE_PAGE_SIZE: Final[int] = 128
MAX_SOURCE_PAGE_SIZE: Final[int] = 256
DEFAULT_SOURCE_PAGE_READS: Final[int] = 128
MAX_SOURCE_PAGE_READS: Final[int] = 128
MAX_SOURCE_BYTES: Final[int] = 8 * 1024 * 1024
MAX_RESPONSE_BYTES: Final[int] = 1 * 1024 * 1024

PRODUCER_MAX_SOURCE_READS: Final[int] = 65_536
PRODUCER_MAX_SOURCE_BYTES: Final[int] = 256 * 1024 * 1024

CAPTURE_MAX_NODES: Final[int] = 20_000
CAPTURE_MAX_EDGES: Final[int] = 40_000
CAPTURE_MAX_NORMALIZED_BYTES: Final[int] = 64 * 1024 * 1024
CAPTURE_MAX_PUBLICATION_RESERVATIONS: Final[int] = 1_000
CAPTURE_MAX_ARTIFACT_BYTES: Final[int] = 256 * 1024 * 1024


def event_precedes_boundary(*, boundary_tick: int, event_tick: int) -> bool:
    """Whether an event admitted into a finalized boundary is included.

    Boundary ``B`` is finalized state after exactly ``B`` ticks. Initial state is
    ``B=0`` and admitted events carry ticks strictly below ``B``.
    """
    boundary = require_exact_nonneg_int("boundary_tick", boundary_tick)
    event = require_exact_nonneg_int("event_tick", event_tick)
    return event < boundary


@dataclass(frozen=True, slots=True)
class LineageReadReservation:
    """One reserved physical read plus its declared maximum byte count."""

    source_bytes: int
    sequence: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_bytes",
            require_exact_nonneg_int(
                "LineageReadReservation.source_bytes", self.source_bytes
            ),
        )
        object.__setattr__(
            self,
            "sequence",
            require_exact_nonneg_int("LineageReadReservation.sequence", self.sequence),
        )

    def require_actual_bytes(self, actual_bytes: int) -> int:
        """Reject a decoded/read size that exceeds the reservation."""
        actual = require_exact_nonneg_int(
            "LineageReadReservation.actual_bytes", actual_bytes
        )
        if actual > self.source_bytes:
            raise LineageError("snapshot_corrupt")
        return actual


class LineageReadBudget:
    """Request-local physical-read and source-byte allowance with counters."""

    __slots__ = (
        "_bytes_remaining",
        "_exhausted_reason",
        "_max_physical_reads",
        "_max_source_bytes",
        "_physical_reads_charged",
        "_reads_remaining",
        "_source_bytes_charged",
    )

    def __init__(
        self,
        *,
        max_physical_reads: int = DEFAULT_SOURCE_PAGE_READS,
        max_source_bytes: int = MAX_SOURCE_BYTES,
    ) -> None:
        reads = require_exact_nonneg_int("max_physical_reads", max_physical_reads)
        source_bytes = require_exact_nonneg_int("max_source_bytes", max_source_bytes)
        if reads < 1 or source_bytes < 1:
            raise LineageError("invalid_lineage_budget")
        self._max_physical_reads = reads
        self._max_source_bytes = source_bytes
        self._reads_remaining = reads
        self._bytes_remaining = source_bytes
        self._physical_reads_charged = 0
        self._source_bytes_charged = 0
        self._exhausted_reason: str | None = None

    @classmethod
    def for_query(cls) -> LineageReadBudget:
        return cls(
            max_physical_reads=MAX_SOURCE_PAGE_READS,
            max_source_bytes=MAX_SOURCE_BYTES,
        )

    @classmethod
    def for_capture(cls) -> LineageReadBudget:
        """Trusted producer budget; never selectable through an HTTP query."""
        return cls(
            max_physical_reads=PRODUCER_MAX_SOURCE_READS,
            max_source_bytes=PRODUCER_MAX_SOURCE_BYTES,
        )

    @property
    def max_physical_reads(self) -> int:
        return self._max_physical_reads

    @property
    def max_source_bytes(self) -> int:
        return self._max_source_bytes

    @property
    def physical_reads_remaining(self) -> int:
        return self._reads_remaining

    @property
    def source_bytes_remaining(self) -> int:
        return self._bytes_remaining

    @property
    def physical_reads_charged(self) -> int:
        return self._physical_reads_charged

    @property
    def source_bytes_charged(self) -> int:
        return self._source_bytes_charged

    @property
    def exhausted_reason(self) -> str | None:
        """Which allowance stopped the last reservation, if any."""
        return self._exhausted_reason

    def reserve(self, source_bytes: int) -> LineageReadReservation:
        """Charge one read and its declared bytes before any I/O."""
        size = require_exact_nonneg_int("source_bytes", source_bytes)
        if self._reads_remaining < 1 or self._bytes_remaining < size:
            self._exhausted_reason = (
                "source_read_limit"
                if self._reads_remaining < 1
                else "source_byte_limit"
            )
            raise LineageError("lineage_source_budget")
        self._reads_remaining -= 1
        self._bytes_remaining -= size
        self._physical_reads_charged += 1
        self._source_bytes_charged += size
        return LineageReadReservation(
            source_bytes=size,
            sequence=self._physical_reads_charged,
        )

    def record_cache_hit(self) -> None:
        """Cache hits do not consume a new physical read or source bytes."""
        return None


_ARTIFACT_KINDS: Final[frozenset[str]] = frozenset(
    {"mark", "sign", "note", "map", "record", "memorial"}
)
_RECORD_INTEGRITIES: Final[frozenset[str]] = frozenset(
    {"intact", "damaged", "partially_lost", "destroyed"}
)
_LIFE_STATUSES: Final[frozenset[str]] = frozenset({"alive", "dead"})
_RECORD_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "artifact_created",
        "artifact_modified",
        "artifact_moved",
        "artifact_destroyed",
        "artifact_copied",
        "artifact_annotated",
        "artifact_damaged",
        "artifact_partially_lost",
    }
)


def _require_closed_code(name: str, value: object, allowed: frozenset[str]) -> str:
    code = require_stable_id(name, value)
    if code not in allowed:
        raise ValueError(f"{name} is not a supported code")
    return code


@dataclass(frozen=True, slots=True)
class KinshipSourceEdge:
    """Detached objective parent->child fact with its native edge identity."""

    parent_id: str
    child_id: str
    established_tick: int
    edge_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "parent_id",
            require_stable_id("KinshipSourceEdge.parent_id", self.parent_id),
        )
        object.__setattr__(
            self,
            "child_id",
            require_stable_id("KinshipSourceEdge.child_id", self.child_id),
        )
        object.__setattr__(
            self,
            "established_tick",
            require_exact_nonneg_int(
                "KinshipSourceEdge.established_tick", self.established_tick
            ),
        )
        object.__setattr__(
            self,
            "edge_id",
            require_stable_id("KinshipSourceEdge.edge_id", self.edge_id),
        )


@dataclass(frozen=True, slots=True)
class AgentLifecycleFact:
    """Detached objective life-status fact for one registered agent at a boundary."""

    agent_id: str
    body_id: str
    entry_tick: int
    life_status: str
    observed_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "agent_id",
            require_stable_id("AgentLifecycleFact.agent_id", self.agent_id),
        )
        object.__setattr__(
            self,
            "body_id",
            require_stable_id("AgentLifecycleFact.body_id", self.body_id),
        )
        object.__setattr__(
            self,
            "entry_tick",
            require_exact_nonneg_int("AgentLifecycleFact.entry_tick", self.entry_tick),
        )
        object.__setattr__(
            self,
            "life_status",
            _require_closed_code(
                "AgentLifecycleFact.life_status", self.life_status, _LIFE_STATUSES
            ),
        )
        object.__setattr__(
            self,
            "observed_tick",
            require_exact_nonneg_int(
                "AgentLifecycleFact.observed_tick", self.observed_tick
            ),
        )


@dataclass(frozen=True, slots=True)
class RecordSourceArtifact:
    """Safe physical record metadata without marks, titles or text."""

    artifact_id: str
    kind: str
    author_id: str
    created_tick: int
    content_revision: int
    integrity: str
    annotation_revisions: int
    lost_mark_count: int
    copy_generation: int
    observed_tick: int
    parent_artifact_id: str | None = None
    source_artifact_id: str | None = None
    custodian_repository_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "author_id"):
            object.__setattr__(
                self,
                name,
                require_stable_id(f"RecordSourceArtifact.{name}", getattr(self, name)),
            )
        object.__setattr__(
            self,
            "kind",
            _require_closed_code(
                "RecordSourceArtifact.kind", self.kind, _ARTIFACT_KINDS
            ),
        )
        object.__setattr__(
            self,
            "integrity",
            _require_closed_code(
                "RecordSourceArtifact.integrity", self.integrity, _RECORD_INTEGRITIES
            ),
        )
        for name in (
            "created_tick",
            "content_revision",
            "annotation_revisions",
            "lost_mark_count",
            "copy_generation",
            "observed_tick",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"RecordSourceArtifact.{name}", getattr(self, name)
                ),
            )
        for name in (
            "parent_artifact_id",
            "source_artifact_id",
            "custodian_repository_id",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    require_stable_id(f"RecordSourceArtifact.{name}", value),
                )


@dataclass(frozen=True, slots=True)
class RecordSourceEvent:
    """Ordered detached physical record event metadata (no content)."""

    artifact_id: str
    tick: int
    sequence: int
    event_kind: str
    success: bool = True
    parent_artifact_id: str | None = None
    source_artifact_id: str | None = None
    integrity: str | None = None
    lost_mark_count_delta: int = 0
    annotation_revisions: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_id",
            require_stable_id("RecordSourceEvent.artifact_id", self.artifact_id),
        )
        for name in (
            "tick",
            "sequence",
            "lost_mark_count_delta",
            "annotation_revisions",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"RecordSourceEvent.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "event_kind",
            _require_closed_code(
                "RecordSourceEvent.event_kind", self.event_kind, _RECORD_EVENT_KINDS
            ),
        )
        if type(self.success) is not bool:
            raise ValueError("RecordSourceEvent.success must be a bool")
        for name in ("parent_artifact_id", "source_artifact_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    require_stable_id(f"RecordSourceEvent.{name}", value),
                )
        if self.integrity is not None:
            object.__setattr__(
                self,
                "integrity",
                _require_closed_code(
                    "RecordSourceEvent.integrity", self.integrity, _RECORD_INTEGRITIES
                ),
            )


@dataclass(frozen=True, slots=True)
class LineageSourceProjection:
    """Normalized node/edge batch plus source coverage for one family boundary."""

    nodes: tuple[LineageNode, ...]
    edges: tuple[LineageEdge, ...]
    coverage: LineageCoverage

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        for node in nodes:
            if type(node) is not LineageNode:
                raise ValueError("LineageSourceProjection.nodes must be LineageNode")
        edges = tuple(self.edges)
        for edge in edges:
            if type(edge) is not LineageEdge:
                raise ValueError("LineageSourceProjection.edges must be LineageEdge")
        if type(self.coverage) is not LineageCoverage:
            raise ValueError("LineageSourceProjection.coverage must be LineageCoverage")
        node_keys = {node.key for node in nodes}
        if len(node_keys) != len(nodes):
            raise ValueError("duplicate_lineage_identity")
        for edge in edges:
            if edge.source_key not in node_keys or edge.target_key not in node_keys:
                raise ValueError("lineage edge endpoint descriptor is missing")
        if len({edge.edge_key for edge in edges}) != len(edges):
            raise ValueError("duplicate_lineage_edge")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)


_MENTORSHIP_ROLES: Final[frozenset[str]] = frozenset({"mentor", "apprentice"})
_NARRATIVE_SOURCE_LOSS_STATES: Final[frozenset[str]] = frozenset(
    {"intact", "partial", "lost", "unknown"}
)


@dataclass(frozen=True, slots=True)
class MentorshipBondSource:
    """One owner-local belief about a directed mentorship bond."""

    partner_id: str
    role: str
    content_kinds: tuple[str, ...]
    strength: float
    formed_tick: int
    last_teaching_tick: int
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "partner_id",
            require_stable_id("MentorshipBondSource.partner_id", self.partner_id),
        )
        object.__setattr__(
            self,
            "role",
            _require_closed_code(
                "MentorshipBondSource.role", self.role, _MENTORSHIP_ROLES
            ),
        )
        object.__setattr__(
            self,
            "content_kinds",
            tuple(
                require_stable_id("MentorshipBondSource.content_kind", item)
                for item in self.content_kinds
            ),
        )
        object.__setattr__(
            self,
            "strength",
            float(self.strength),
        )
        for name in ("formed_tick", "last_teaching_tick"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"MentorshipBondSource.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "policy_version",
            require_stable_id(
                "MentorshipBondSource.policy_version", self.policy_version
            ),
        )


@dataclass(frozen=True, slots=True)
class PracticalKnowledgeSource:
    """One owner-local practical-knowledge entry (no content text)."""

    entry_id: str
    kind: str
    content_key: str
    origin: str
    parent_entry_ids: tuple[str, ...]
    lineage_root_id: str
    hop_index: int
    mutated: bool
    evidence_refs: tuple[str, ...]
    acquired_tick: int
    active: bool
    capability_anchor: str | None = None
    source_agent_id: str | None = None
    teacher_agent_id: str | None = None
    policy_version: str = "practical-knowledge-v1"

    def __post_init__(self) -> None:
        for name in ("entry_id", "kind", "content_key", "origin", "lineage_root_id"):
            object.__setattr__(
                self,
                name,
                require_stable_id(
                    f"PracticalKnowledgeSource.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "parent_entry_ids",
            tuple(
                require_stable_id("PracticalKnowledgeSource.parent_id", item)
                for item in self.parent_entry_ids
            ),
        )
        for name in ("hop_index", "acquired_tick"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"PracticalKnowledgeSource.{name}", getattr(self, name)
                ),
            )
        for name in ("mutated", "active"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"PracticalKnowledgeSource.{name} must be a bool")
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(
                require_stable_id("PracticalKnowledgeSource.evidence_ref", item)
                for item in self.evidence_refs
            ),
        )
        for name in ("capability_anchor", "source_agent_id", "teacher_agent_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    require_stable_id(f"PracticalKnowledgeSource.{name}", value),
                )
        object.__setattr__(
            self,
            "policy_version",
            require_stable_id(
                "PracticalKnowledgeSource.policy_version", self.policy_version
            ),
        )


@dataclass(frozen=True, slots=True)
class NarrativeVariantSource:
    """One owner-local narrative variant with lineage/status metadata only."""

    variant_id: str
    origin: str
    status: str
    strength: float
    first_tick: int | None
    last_tick: int | None
    repetition_count: int
    mutation_generation: int
    parent_variant_ids: tuple[str, ...] = ()
    merged_into_id: str | None = None
    competing_variant_ids: tuple[str, ...] = ()
    source_event_id: str | None = None
    source_memory_id: str | None = None
    reconstruction_id: str | None = None
    transmission_root_id: str | None = None
    source_loss_state: str = "unknown"
    source_loss_reason: str | None = None
    source_loss_tick: int | None = None
    known_witness_count: int = 0
    dead_witness_count: int = 0
    record_backed: bool = False

    def __post_init__(self) -> None:
        for name in ("variant_id", "origin", "status"):
            object.__setattr__(
                self,
                name,
                require_stable_id(
                    f"NarrativeVariantSource.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(self, "strength", float(self.strength))
        for name in ("first_tick", "last_tick", "source_loss_tick"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    require_exact_nonneg_int(f"NarrativeVariantSource.{name}", value),
                )
        for name in (
            "repetition_count",
            "mutation_generation",
            "known_witness_count",
            "dead_witness_count",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"NarrativeVariantSource.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "parent_variant_ids",
            tuple(
                require_stable_id("NarrativeVariantSource.parent_id", item)
                for item in self.parent_variant_ids
            ),
        )
        object.__setattr__(
            self,
            "competing_variant_ids",
            tuple(
                require_stable_id("NarrativeVariantSource.competing_id", item)
                for item in self.competing_variant_ids
            ),
        )
        for name in (
            "merged_into_id",
            "source_event_id",
            "source_memory_id",
            "reconstruction_id",
            "transmission_root_id",
            "source_loss_reason",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    require_stable_id(f"NarrativeVariantSource.{name}", value),
                )
        object.__setattr__(
            self,
            "source_loss_state",
            _require_closed_code(
                "NarrativeVariantSource.source_loss_state",
                self.source_loss_state,
                _NARRATIVE_SOURCE_LOSS_STATES,
            ),
        )
        if type(self.record_backed) is not bool:
            raise ValueError("NarrativeVariantSource.record_backed must be a bool")


@dataclass(frozen=True, slots=True)
class OfficeOccupantClaimSource:
    """One owner-local occupant claim (never a global occupant)."""

    claim_id: str
    occupant_id: str
    status: str
    support_strength: float
    opposition_strength: float
    first_tick: int
    last_tick: int
    attributed_supporters: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("claim_id", "occupant_id", "status"):
            object.__setattr__(
                self,
                name,
                require_stable_id(
                    f"OfficeOccupantClaimSource.{name}", getattr(self, name)
                ),
            )
        for name in ("support_strength", "opposition_strength"):
            object.__setattr__(self, name, float(getattr(self, name)))
        for name in ("first_tick", "last_tick"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"OfficeOccupantClaimSource.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "attributed_supporters",
            tuple(
                require_stable_id("OfficeOccupantClaimSource.supporter", item)
                for item in self.attributed_supporters
            ),
        )


@dataclass(frozen=True, slots=True)
class OfficeSuccessionSource:
    """One owner-local office transition record."""

    succession_id: str
    kind: str
    tick: int
    prior_occupant_id: str | None = None
    proposed_occupant_id: str | None = None
    predecessor_office_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("succession_id", "kind"):
            object.__setattr__(
                self,
                name,
                require_stable_id(
                    f"OfficeSuccessionSource.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("OfficeSuccessionSource.tick", self.tick),
        )
        for name in (
            "prior_occupant_id",
            "proposed_occupant_id",
            "predecessor_office_id",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    require_stable_id(f"OfficeSuccessionSource.{name}", value),
                )


@dataclass(frozen=True, slots=True)
class OfficeConceptSource:
    """One owner-local office identity with claims and transitions."""

    office_id: str
    status: str
    function: str
    first_tick: int
    last_tick: int
    predecessor_office_id: str | None = None
    claims: tuple[OfficeOccupantClaimSource, ...] = ()
    succession: tuple[OfficeSuccessionSource, ...] = ()
    pruned_claim_count: int = 0
    pruned_succession_count: int = 0

    def __post_init__(self) -> None:
        for name in ("office_id", "status", "function"):
            object.__setattr__(
                self,
                name,
                require_stable_id(f"OfficeConceptSource.{name}", getattr(self, name)),
            )
        for name in ("first_tick", "last_tick"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"OfficeConceptSource.{name}", getattr(self, name)
                ),
            )
        if self.predecessor_office_id is not None:
            object.__setattr__(
                self,
                "predecessor_office_id",
                require_stable_id(
                    "OfficeConceptSource.predecessor_office_id",
                    self.predecessor_office_id,
                ),
            )
        claims = tuple(self.claims)
        for claim in claims:
            if type(claim) is not OfficeOccupantClaimSource:
                raise ValueError(
                    "OfficeConceptSource.claims must be OfficeOccupantClaimSource"
                )
        succession = tuple(self.succession)
        for item in succession:
            if type(item) is not OfficeSuccessionSource:
                raise ValueError(
                    "OfficeConceptSource.succession must be OfficeSuccessionSource"
                )
        object.__setattr__(self, "claims", claims)
        object.__setattr__(self, "succession", succession)
        for name in ("pruned_claim_count", "pruned_succession_count"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"OfficeConceptSource.{name}", getattr(self, name)
                ),
            )


@dataclass(frozen=True, slots=True)
class OwnerLineageSource:
    """Detached normalized evidence for exactly one run, owner and boundary."""

    run_id: RunId
    owner_id: str
    boundary_tick: int
    mentorship_bonds: tuple[MentorshipBondSource, ...] = ()
    mentorship_records: tuple[MentorshipLineageRecord, ...] = ()
    practical_knowledge: tuple[PracticalKnowledgeSource, ...] = ()
    narratives: tuple[NarrativeVariantSource, ...] = ()
    offices: tuple[OfficeConceptSource, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise ValueError("OwnerLineageSource.run_id must be RunId")
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("OwnerLineageSource.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int(
                "OwnerLineageSource.boundary_tick", self.boundary_tick
            ),
        )
        for name, expected in (
            ("mentorship_bonds", MentorshipBondSource),
            ("mentorship_records", MentorshipLineageRecord),
            ("practical_knowledge", PracticalKnowledgeSource),
            ("narratives", NarrativeVariantSource),
            ("offices", OfficeConceptSource),
        ):
            values = tuple(getattr(self, name))
            for item in values:
                if type(item) is not expected:
                    raise ValueError(f"OwnerLineageSource.{name} has an invalid item")
            object.__setattr__(self, name, values)
        for record in self.mentorship_records:
            if record.owner_id != self.owner_id:
                raise ValueError("OwnerLineageSource mentorship owner mismatch")
        object.__setattr__(
            self,
            "notices",
            tuple(
                require_stable_id("OwnerLineageSource.notice", item)
                for item in self.notices
            ),
        )


@dataclass(frozen=True, slots=True)
class LineageNeighborRow:
    """One admitted edge plus the descriptor of the discovered endpoint."""

    edge: LineageEdge
    node: LineageNode

    def __post_init__(self) -> None:
        if type(self.edge) is not LineageEdge:
            raise ValueError("LineageNeighborRow.edge must be LineageEdge")
        if type(self.node) is not LineageNode:
            raise ValueError("LineageNeighborRow.node must be LineageNode")


@dataclass(frozen=True, slots=True)
class LineageNeighborPage:
    """Bounded native adjacency page."""

    rows: tuple[LineageNeighborRow, ...]
    declared_count: int
    continuation: str | None = None

    def __post_init__(self) -> None:
        rows = tuple(self.rows)
        for row in rows:
            if type(row) is not LineageNeighborRow:
                raise ValueError("LineageNeighborPage.rows must be LineageNeighborRow")
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self,
            "declared_count",
            require_exact_nonneg_int(
                "LineageNeighborPage.declared_count", self.declared_count
            ),
        )
        if self.continuation is not None:
            object.__setattr__(
                self, "continuation", require_lineage_cursor(self.continuation)
            )


@dataclass(frozen=True, slots=True)
class LineageNodeCataloguePage:
    """Bounded node catalogue/lookup page."""

    rows: tuple[LineageNode, ...]
    declared_count: int
    continuation: str | None = None
    coverage: LineageCoverage | None = None

    def __post_init__(self) -> None:
        rows = tuple(self.rows)
        for row in rows:
            if type(row) is not LineageNode:
                raise ValueError("LineageNodeCataloguePage.rows must be LineageNode")
        object.__setattr__(self, "rows", rows)
        if self.coverage is not None and type(self.coverage) is not LineageCoverage:
            raise ValueError(
                "LineageNodeCataloguePage.coverage must be LineageCoverage"
            )
        object.__setattr__(
            self,
            "declared_count",
            require_exact_nonneg_int(
                "LineageNodeCataloguePage.declared_count", self.declared_count
            ),
        )
        if self.continuation is not None:
            object.__setattr__(
                self, "continuation", require_lineage_cursor(self.continuation)
            )


@dataclass(frozen=True, slots=True)
class LineageSnapshotCataloguePage:
    """Bounded snapshot-catalogue page."""

    rows: tuple[LineageSnapshotRef, ...]
    declared_count: int
    continuation: str | None = None

    def __post_init__(self) -> None:
        rows = tuple(self.rows)
        for row in rows:
            if type(row) is not LineageSnapshotRef:
                raise ValueError(
                    "LineageSnapshotCataloguePage.rows must be LineageSnapshotRef"
                )
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self,
            "declared_count",
            require_exact_nonneg_int(
                "LineageSnapshotCataloguePage.declared_count", self.declared_count
            ),
        )
        if self.continuation is not None:
            object.__setattr__(
                self, "continuation", require_lineage_cursor(self.continuation)
            )


class LineageReadSession(Protocol):
    """One pinned immutable source session sharing a single read budget."""

    @property
    def run_commit_ref(self) -> str:
        """Immutable run-catalogue commit pinned by this session."""

    async def resolve_snapshot(
        self, scope: LineageScope, boundary_tick: int | None = None
    ) -> LineageSnapshotRef:
        """Resolve latest once or require an exact captured boundary."""

    async def get_node(
        self, snapshot: LineageSnapshotRef, key: str
    ) -> LineageNode | None:
        """Exact qualified-key node lookup."""

    async def neighbors(
        self,
        snapshot: LineageSnapshotRef,
        key: str,
        direction: LineageDirection,
        after: str | None,
        limit: int,
    ) -> LineageNeighborPage:
        """Bounded native adjacency read in one direction."""

    async def node_page(
        self, snapshot: LineageSnapshotRef, after: str | None, limit: int
    ) -> LineageNodeCataloguePage:
        """Bounded node-catalogue page."""

    async def lookup_nodes(
        self,
        snapshot: LineageSnapshotRef,
        native_kind: LineageNativeKind,
        native_id: str,
        after: str | None,
        limit: int,
    ) -> LineageNodeCataloguePage:
        """Bounded exact native-kind/ID index lookup."""

    async def snapshot_page(
        self, scope: LineageScope, after: str | None, limit: int
    ) -> LineageSnapshotCataloguePage:
        """Bounded snapshot-catalogue page for one scope."""

    async def coverage(self, snapshot: LineageSnapshotRef) -> LineageCoverage:
        """Coverage envelope declared by one pinned publication."""



class LineageReadPort(Protocol):
    """Reader capability. Queries accept only this port."""

    def open_read(
        self,
        *,
        run_id: RunId,
        budget: LineageReadBudget,
        commit_ref: str | None = None,
    ) -> AbstractAsyncContextManager[LineageReadSession]:
        """Open one session pinning a committed immutable catalogue generation."""


@dataclass(frozen=True, slots=True)
class LineageBoundaryFrame:
    """Detached finalized evidence for one family/class/owner boundary."""

    run_id: RunId
    scope: LineageScope
    boundary_tick: int
    observed_boundary: int
    nodes: tuple[LineageNode, ...]
    edges: tuple[LineageEdge, ...]
    coverage: LineageCoverage
    mentorship_records: tuple[MentorshipLineageRecord, ...] = ()
    source_revision: str = "native-v1"

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise ValueError("LineageBoundaryFrame.run_id must be RunId")
        if type(self.scope) is not LineageScope:
            raise ValueError("LineageBoundaryFrame.scope must be LineageScope")
        if self.scope.run_id != self.run_id:
            raise ValueError("LineageBoundaryFrame run mismatch")
        if type(self.coverage) is not LineageCoverage:
            raise ValueError("LineageBoundaryFrame.coverage must be LineageCoverage")
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int(
                "LineageBoundaryFrame.boundary_tick", self.boundary_tick
            ),
        )
        object.__setattr__(
            self,
            "observed_boundary",
            require_exact_nonneg_int(
                "LineageBoundaryFrame.observed_boundary", self.observed_boundary
            ),
        )
        nodes = tuple(self.nodes)
        for node in nodes:
            if type(node) is not LineageNode:
                raise ValueError("LineageBoundaryFrame.nodes must be LineageNode")
            if node.ref.run_id != self.run_id:
                raise ValueError("LineageBoundaryFrame node run mismatch")
            if node.ref.family is not self.scope.family:
                raise ValueError("LineageBoundaryFrame node family mismatch")
            if node.ref.evidence_class is not self.scope.evidence_class:
                raise ValueError("LineageBoundaryFrame node class mismatch")
            if (
                self.scope.evidence_class is LineageEvidenceClass.SUBJECTIVE
                and node.ref.identity_owner != self.scope.owner_id
            ):
                raise ValueError("LineageBoundaryFrame node owner mismatch")
        if len(nodes) > CAPTURE_MAX_NODES:
            raise LineageError("invalid_lineage_budget")
        edges = tuple(self.edges)
        for edge in edges:
            if type(edge) is not LineageEdge:
                raise ValueError("LineageBoundaryFrame.edges must be LineageEdge")
        if len(edges) > CAPTURE_MAX_EDGES:
            raise LineageError("invalid_lineage_budget")
        records = tuple(self.mentorship_records)
        for record in records:
            if type(record) is not MentorshipLineageRecord:
                raise ValueError(
                    "LineageBoundaryFrame.mentorship_records must be "
                    "MentorshipLineageRecord"
                )
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "mentorship_records", records)
        object.__setattr__(
            self,
            "source_revision",
            require_stable_id(
                "LineageBoundaryFrame.source_revision", self.source_revision
            ),
        )


@dataclass(frozen=True, slots=True)
class LineagePublication:
    """Immutable snapshot publication payload for the writer capability."""

    snapshot: LineageSnapshotRef
    frame: LineageBoundaryFrame

    def __post_init__(self) -> None:
        if type(self.snapshot) is not LineageSnapshotRef:
            raise ValueError("LineagePublication.snapshot must be LineageSnapshotRef")
        if type(self.frame) is not LineageBoundaryFrame:
            raise ValueError("LineagePublication.frame must be LineageBoundaryFrame")
        if self.snapshot.boundary_tick != self.frame.boundary_tick:
            raise ValueError("LineagePublication boundary mismatch")


class LineagePublicationPort(Protocol):
    """Writer-only capability, separate from the reader capability."""

    async def publish(self, publication: LineagePublication) -> LineageSnapshotRef:
        """Atomically publish a snapshot and its discovery indexes."""


class LineageBoundarySink(Protocol):
    """Capture capability used by the trusted experiment composition."""

    async def capture(self, frame: LineageBoundaryFrame) -> LineageSnapshotRef | None:
        """Capture one finalized boundary; return None when capture stops."""


@dataclass(frozen=True, slots=True)
class LineageTraversalCursor:
    """Continuation pinned to one snapshot, root and effective query."""

    snapshot_id: str
    snapshot_digest: str
    root_key: str
    query_fingerprint: str
    record_offset: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "snapshot_id",
            require_stable_id("LineageTraversalCursor.snapshot_id", self.snapshot_id),
        )
        object.__setattr__(
            self,
            "snapshot_digest",
            require_lineage_key(
                "LineageTraversalCursor.snapshot_digest", self.snapshot_digest
            ),
        )
        object.__setattr__(
            self,
            "root_key",
            require_lineage_key("LineageTraversalCursor.root_key", self.root_key),
        )
        object.__setattr__(
            self,
            "query_fingerprint",
            require_lineage_key(
                "LineageTraversalCursor.query_fingerprint", self.query_fingerprint
            ),
        )
        object.__setattr__(
            self,
            "record_offset",
            require_exact_nonneg_int(
                "LineageTraversalCursor.record_offset", self.record_offset
            ),
        )


@dataclass(frozen=True, slots=True)
class LineageNodeCatalogueCursor:
    """Continuation pinned to one snapshot and node filter (no root)."""

    snapshot_id: str
    snapshot_digest: str
    filter_fingerprint: str
    last_node_key: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "snapshot_id",
            require_stable_id(
                "LineageNodeCatalogueCursor.snapshot_id", self.snapshot_id
            ),
        )
        object.__setattr__(
            self,
            "snapshot_digest",
            require_lineage_key(
                "LineageNodeCatalogueCursor.snapshot_digest", self.snapshot_digest
            ),
        )
        object.__setattr__(
            self,
            "filter_fingerprint",
            require_lineage_key(
                "LineageNodeCatalogueCursor.filter_fingerprint",
                self.filter_fingerprint,
            ),
        )
        object.__setattr__(
            self,
            "last_node_key",
            require_lineage_key(
                "LineageNodeCatalogueCursor.last_node_key", self.last_node_key
            ),
        )


@dataclass(frozen=True, slots=True)
class LineageSnapshotCatalogueCursor:
    """Continuation pinned to a committed run/scope catalogue generation."""

    run_commit_ref: str
    scope_fingerprint: str
    catalogue_generation: str
    last_boundary_key: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_commit_ref",
            require_stable_id(
                "LineageSnapshotCatalogueCursor.run_commit_ref", self.run_commit_ref
            ),
        )
        object.__setattr__(
            self,
            "scope_fingerprint",
            require_lineage_key(
                "LineageSnapshotCatalogueCursor.scope_fingerprint",
                self.scope_fingerprint,
            ),
        )
        object.__setattr__(
            self,
            "catalogue_generation",
            require_stable_id(
                "LineageSnapshotCatalogueCursor.catalogue_generation",
                self.catalogue_generation,
            ),
        )
        object.__setattr__(
            self,
            "last_boundary_key",
            require_stable_id(
                "LineageSnapshotCatalogueCursor.last_boundary_key",
                self.last_boundary_key,
            ),
        )


def lineage_query_fingerprint(query: LineageQuery) -> str:
    """Stable fingerprint of the effective graph query."""
    if type(query) is not LineageQuery:
        raise TypeError("query must be LineageQuery")
    payload = {
        "direction": query.direction.value,
        "family": query.scope.family.value,
        "evidence_class": query.scope.evidence_class.value,
        "living_only": query.living_only,
        "max_depth": query.max_depth,
        "max_edges": query.max_edges,
        "max_nodes": query.max_nodes,
        "owner_id": query.scope.owner_id,
        "page_size": query.page_size,
        "root_key": query.root.key if query.root is not None else None,
        "run_id": query.scope.run_id.value,
        "snapshot_digest": (
            query.snapshot.digest if query.snapshot is not None else None
        ),
        "snapshot_id": (
            query.snapshot.publication_id if query.snapshot is not None else None
        ),
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
