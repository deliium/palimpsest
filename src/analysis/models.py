"""Immutable reconstruction-chain and memory-drift analysis DTOs.

Domain values are log-free. Safe ``repr`` exposes IDs, counts, versions, and
status codes only — never narratives, event details, or memory payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "DRIFT_METRIC_VERSION",
    "EVENT_FACT_PROJECTOR_VERSION",
    "SOCIAL_TRANSMISSION_METRIC_VERSION",
    "ChainNodeKind",
    "ComparisonStatus",
    "DriftDelta",
    "DriftStep",
    "FactAvailability",
    "MemoryDriftReport",
    "ObjectiveLinkStatus",
    "ReconstructionChain",
    "ReconstructionChainNode",
    "ReconstructionEvidence",
    "SocialTransmissionReport",
    "StructuredFactSet",
    "SubjectiveDerivationEdge",
    "TransmissionDistortion",
    "TransmissionHopRecord",
]

DRIFT_METRIC_VERSION: Final[str] = "1"
EVENT_FACT_PROJECTOR_VERSION: Final[str] = "1"


class ChainNodeKind(StrEnum):
    """Ordered provenance roles along one reconstruction chain."""

    OBJECTIVE_EVENT = "objective_event"
    ROOT_TRACE = "root_trace"
    RECONSTRUCTION = "reconstruction"
    DERIVED_TRACE = "derived_trace"


class ObjectiveLinkStatus(StrEnum):
    """Correlation of a root trace to an immutable objective event."""

    LINKED = "linked"
    UNLINKED = "unlinked"
    ABSENT = "absent"
    NOT_APPLICABLE = "not_applicable"


class FactAvailability(StrEnum):
    """Whether a fact set is known, explicitly empty, or unavailable."""

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class ComparisonStatus(StrEnum):
    """How to interpret a drift delta given availability of either side."""

    COMPLETE = "complete"
    BEFORE_UNKNOWN = "before_unknown"
    AFTER_UNKNOWN = "after_unknown"
    BOTH_UNKNOWN = "both_unknown"


@dataclass(frozen=True, slots=True)
class StructuredFactSet:
    """Comparable structured projection of one chain node."""

    concepts: frozenset[str]
    entity_ids: frozenset[str]
    entity_labels: frozenset[str]
    relations: frozenset[tuple[str, str, str]]
    context_tags: frozenset[str]
    location_id: str | None
    confidence: float | None
    salience: float | None
    narrative_fingerprint: str | None
    availability: FactAvailability
    projector_version: str

    def __post_init__(self) -> None:
        if type(self.availability) is not FactAvailability:
            raise TypeError("StructuredFactSet.availability: invalid_type")
        object.__setattr__(
            self,
            "projector_version",
            require_stable_id(
                "StructuredFactSet.projector_version", self.projector_version
            ),
        )
        if self.location_id is not None:
            object.__setattr__(
                self,
                "location_id",
                require_stable_id("StructuredFactSet.location_id", self.location_id),
            )
        if self.confidence is not None and (
            type(self.confidence) is not float
            or self.confidence != self.confidence
            or self.confidence in (float("inf"), float("-inf"))
        ):
            raise ValueError("StructuredFactSet.confidence: non_finite")
        if self.salience is not None and (
            type(self.salience) is not float
            or self.salience != self.salience
            or self.salience in (float("inf"), float("-inf"))
        ):
            raise ValueError("StructuredFactSet.salience: non_finite")

    def __repr__(self) -> str:
        return (
            f"StructuredFactSet(availability={self.availability.value!r}, "
            f"concept_count={len(self.concepts)}, "
            f"entity_id_count={len(self.entity_ids)}, "
            f"relation_count={len(self.relations)}, "
            f"tag_count={len(self.context_tags)}, "
            f"has_location={self.location_id is not None}, "
            f"projector_version={self.projector_version!r})"
        )


@dataclass(frozen=True, slots=True)
class DriftDelta:
    """Per-step or cumulative structured drift between two fact sets."""

    retained_concepts: frozenset[str]
    lost_concepts: frozenset[str]
    added_concepts: frozenset[str]
    retained_entity_ids: frozenset[str]
    lost_entity_ids: frozenset[str]
    added_entity_ids: frozenset[str]
    retained_relations: frozenset[tuple[str, str, str]]
    lost_relations: frozenset[tuple[str, str, str]]
    added_relations: frozenset[tuple[str, str, str]]
    retained_context_tags: frozenset[str]
    lost_context_tags: frozenset[str]
    added_context_tags: frozenset[str]
    location_changed: bool
    confidence_delta: float | None
    salience_delta: float | None
    provenance_continuous: bool
    canonical_equal: bool
    unsupported_concepts: frozenset[str]
    contradicted_entity_ids: frozenset[str]
    comparison_status: ComparisonStatus

    def __post_init__(self) -> None:
        if type(self.comparison_status) is not ComparisonStatus:
            raise TypeError("DriftDelta.comparison_status: invalid_type")
        if type(self.location_changed) is not bool:
            raise TypeError("DriftDelta.location_changed: invalid_type")
        if type(self.provenance_continuous) is not bool:
            raise TypeError("DriftDelta.provenance_continuous: invalid_type")
        if type(self.canonical_equal) is not bool:
            raise TypeError("DriftDelta.canonical_equal: invalid_type")

    def __repr__(self) -> str:
        return (
            f"DriftDelta(status={self.comparison_status.value!r}, "
            f"retained_concepts={len(self.retained_concepts)}, "
            f"lost_concepts={len(self.lost_concepts)}, "
            f"added_concepts={len(self.added_concepts)}, "
            f"canonical_equal={self.canonical_equal}, "
            f"provenance_continuous={self.provenance_continuous})"
        )


@dataclass(frozen=True, slots=True)
class ReconstructionChainNode:
    """One node in an auditable reconstruction provenance chain."""

    kind: ChainNodeKind
    node_id: str
    generation: int
    facts: StructuredFactSet
    observed_source_id: str | None
    objective_link: ObjectiveLinkStatus

    def __post_init__(self) -> None:
        if type(self.kind) is not ChainNodeKind:
            raise TypeError("ReconstructionChainNode.kind: invalid_type")
        object.__setattr__(
            self,
            "node_id",
            require_stable_id("ReconstructionChainNode.node_id", self.node_id),
        )
        object.__setattr__(
            self,
            "generation",
            require_exact_nonneg_int(
                "ReconstructionChainNode.generation", self.generation
            ),
        )
        if type(self.facts) is not StructuredFactSet:
            raise TypeError("ReconstructionChainNode.facts: invalid_type")
        if self.observed_source_id is not None:
            object.__setattr__(
                self,
                "observed_source_id",
                require_stable_id(
                    "ReconstructionChainNode.observed_source_id",
                    self.observed_source_id,
                ),
            )
        if type(self.objective_link) is not ObjectiveLinkStatus:
            raise TypeError("ReconstructionChainNode.objective_link: invalid_type")

    def __repr__(self) -> str:
        return (
            f"ReconstructionChainNode(kind={self.kind.value!r}, "
            f"node_id={self.node_id!r}, generation={self.generation}, "
            f"objective_link={self.objective_link.value!r})"
        )


@dataclass(frozen=True, slots=True)
class ReconstructionChain:
    """Ordered provenance from optional objective source through derived story."""

    root_memory_id: str
    observed_source_id: str | None
    objective_link: ObjectiveLinkStatus
    nodes: tuple[ReconstructionChainNode, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "root_memory_id",
            require_stable_id(
                "ReconstructionChain.root_memory_id", self.root_memory_id
            ),
        )
        if self.observed_source_id is not None:
            object.__setattr__(
                self,
                "observed_source_id",
                require_stable_id(
                    "ReconstructionChain.observed_source_id",
                    self.observed_source_id,
                ),
            )
        if type(self.objective_link) is not ObjectiveLinkStatus:
            raise TypeError("ReconstructionChain.objective_link: invalid_type")
        if not isinstance(self.nodes, tuple):
            raise TypeError("ReconstructionChain.nodes: invalid_type")
        for node in self.nodes:
            if type(node) is not ReconstructionChainNode:
                raise TypeError("ReconstructionChain.nodes: invalid_item")

    def __repr__(self) -> str:
        return (
            f"ReconstructionChain(root_memory_id={self.root_memory_id!r}, "
            f"objective_link={self.objective_link.value!r}, "
            f"node_count={len(self.nodes)})"
        )


@dataclass(frozen=True, slots=True)
class DriftStep:
    """One consecutive comparison along a reconstruction chain."""

    chain_root_memory_id: str
    from_kind: ChainNodeKind
    to_kind: ChainNodeKind
    from_id: str
    to_id: str
    delta: DriftDelta

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "chain_root_memory_id",
            require_stable_id(
                "DriftStep.chain_root_memory_id", self.chain_root_memory_id
            ),
        )
        if type(self.from_kind) is not ChainNodeKind:
            raise TypeError("DriftStep.from_kind: invalid_type")
        if type(self.to_kind) is not ChainNodeKind:
            raise TypeError("DriftStep.to_kind: invalid_type")
        object.__setattr__(
            self, "from_id", require_stable_id("DriftStep.from_id", self.from_id)
        )
        object.__setattr__(
            self, "to_id", require_stable_id("DriftStep.to_id", self.to_id)
        )
        if type(self.delta) is not DriftDelta:
            raise TypeError("DriftStep.delta: invalid_type")

    def __repr__(self) -> str:
        return (
            f"DriftStep(root={self.chain_root_memory_id!r}, "
            f"from={self.from_kind.value!r}, to={self.to_kind.value!r}, "
            f"canonical_equal={self.delta.canonical_equal})"
        )


@dataclass(frozen=True, slots=True)
class MemoryDriftReport:
    """Experiment-scoped drift report over one run/owner."""

    experiment_id: str
    run_id: str
    owner_id: str
    projector_version: str
    metric_version: str
    chains: tuple[ReconstructionChain, ...]
    steps: tuple[DriftStep, ...]
    cumulative: tuple[DriftDelta, ...]
    linked_count: int
    unlinked_count: int
    absent_source_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "experiment_id",
            require_stable_id("MemoryDriftReport.experiment_id", self.experiment_id),
        )
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("MemoryDriftReport.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("MemoryDriftReport.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "projector_version",
            require_stable_id(
                "MemoryDriftReport.projector_version", self.projector_version
            ),
        )
        object.__setattr__(
            self,
            "metric_version",
            require_stable_id("MemoryDriftReport.metric_version", self.metric_version),
        )
        object.__setattr__(
            self,
            "linked_count",
            require_exact_nonneg_int(
                "MemoryDriftReport.linked_count", self.linked_count
            ),
        )
        object.__setattr__(
            self,
            "unlinked_count",
            require_exact_nonneg_int(
                "MemoryDriftReport.unlinked_count", self.unlinked_count
            ),
        )
        object.__setattr__(
            self,
            "absent_source_count",
            require_exact_nonneg_int(
                "MemoryDriftReport.absent_source_count", self.absent_source_count
            ),
        )
        if len(self.cumulative) != len(self.chains):
            raise ValueError("MemoryDriftReport.cumulative: length_mismatch")

    def __repr__(self) -> str:
        return (
            f"MemoryDriftReport(experiment_id={self.experiment_id!r}, "
            f"run_id={self.run_id!r}, owner_id={self.owner_id!r}, "
            f"chain_count={len(self.chains)}, step_count={len(self.steps)}, "
            f"linked_count={self.linked_count}, "
            f"unlinked_count={self.unlinked_count})"
        )


@dataclass(frozen=True, slots=True)
class SubjectiveDerivationEdge:
    """Ordered direct derivation edge for provenance traversal."""

    derived_memory_id: str
    source_memory_id: str
    ordinal: int
    reconstruction_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "derived_memory_id",
            require_stable_id(
                "SubjectiveDerivationEdge.derived_memory_id", self.derived_memory_id
            ),
        )
        object.__setattr__(
            self,
            "source_memory_id",
            require_stable_id(
                "SubjectiveDerivationEdge.source_memory_id", self.source_memory_id
            ),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("SubjectiveDerivationEdge.ordinal", self.ordinal),
        )
        if self.reconstruction_id is not None:
            object.__setattr__(
                self,
                "reconstruction_id",
                require_stable_id(
                    "SubjectiveDerivationEdge.reconstruction_id",
                    self.reconstruction_id,
                ),
            )
        if self.derived_memory_id == self.source_memory_id:
            raise ValueError("SubjectiveDerivationEdge: self_reference")

    def __repr__(self) -> str:
        return (
            f"SubjectiveDerivationEdge(derived_memory_id={self.derived_memory_id!r}, "
            f"source_memory_id={self.source_memory_id!r}, ordinal={self.ordinal}, "
            f"has_reconstruction={self.reconstruction_id is not None})"
        )


@dataclass(frozen=True, slots=True)
class ReconstructionEvidence:
    """Subjective reconstruction evidence for analysis (no WorldEvent fields)."""

    reconstruction_id: str
    run_id: str
    owner_id: str
    source_memory_ids: tuple[str, ...]
    concepts: tuple[str, ...]
    entity_ids: tuple[str, ...]
    entity_labels: tuple[str, ...]
    relations: tuple[tuple[str, str, str], ...]
    context_tags: tuple[str, ...]
    location_id: str | None
    confidence: float
    emotional_salience: float
    generation: int
    created_tick: int
    policy_id: str
    policy_version: str
    narrative_fingerprint: str | None
    content_available: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reconstruction_id",
            require_stable_id(
                "ReconstructionEvidence.reconstruction_id", self.reconstruction_id
            ),
        )
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("ReconstructionEvidence.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("ReconstructionEvidence.owner_id", self.owner_id),
        )
        if not self.source_memory_ids:
            raise ValueError("ReconstructionEvidence.source_memory_ids: empty")
        object.__setattr__(
            self,
            "generation",
            require_exact_nonneg_int(
                "ReconstructionEvidence.generation", self.generation
            ),
        )
        if self.generation < 1:
            raise ValueError("ReconstructionEvidence.generation: must_be_positive")
        object.__setattr__(
            self,
            "created_tick",
            require_exact_nonneg_int(
                "ReconstructionEvidence.created_tick", self.created_tick
            ),
        )
        if type(self.content_available) is not bool:
            raise TypeError("ReconstructionEvidence.content_available: invalid_type")

    def __repr__(self) -> str:
        return (
            f"ReconstructionEvidence(reconstruction_id={self.reconstruction_id!r}, "
            f"run_id={self.run_id!r}, owner_id={self.owner_id!r}, "
            f"source_count={len(self.source_memory_ids)}, "
            f"generation={self.generation}, "
            f"content_available={self.content_available})"
        )


SOCIAL_TRANSMISSION_METRIC_VERSION: Final[str] = "1"


@dataclass(frozen=True, slots=True)
class TransmissionHopRecord:
    """One hop in a transmission chain (metadata only)."""

    communication_id: str
    event_id: str | None
    speaker_id: str
    listener_id: str | None
    action_kind: str
    hop_count: int
    tick: int
    sender_confidence: float | None
    receiver_confidence: float | None
    transmission_root_id: str
    concept_count: int
    relation_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "communication_id",
            require_stable_id(
                "TransmissionHopRecord.communication_id", self.communication_id
            ),
        )
        object.__setattr__(
            self,
            "hop_count",
            require_exact_nonneg_int("TransmissionHopRecord.hop_count", self.hop_count),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("TransmissionHopRecord.tick", self.tick),
        )

    def __repr__(self) -> str:
        return (
            f"TransmissionHopRecord(communication_id={self.communication_id!r}, "
            f"hop_count={self.hop_count}, action_kind={self.action_kind!r}, "
            f"tick={self.tick})"
        )


@dataclass(frozen=True, slots=True)
class TransmissionDistortion:
    """Per-hop structured additions/losses/changes without payload text."""

    from_communication_id: str
    to_communication_id: str
    concepts_added: int
    concepts_removed: int
    relations_added: int
    relations_removed: int
    cumulative_change: int

    def __repr__(self) -> str:
        return (
            f"TransmissionDistortion("
            f"from={self.from_communication_id!r}, to={self.to_communication_id!r}, "
            f"cumulative_change={self.cumulative_change})"
        )


@dataclass(frozen=True, slots=True)
class SocialTransmissionReport:
    """Read-only transmission graph metrics for one experiment run."""

    experiment_id: str
    run_id: str
    metric_version: str
    transmission_root_id: str
    hops: tuple[TransmissionHopRecord, ...]
    distortions: tuple[TransmissionDistortion, ...]
    unique_agent_count: int
    branch_count: int
    fan_out_count: int
    max_hop_count: int
    unresolved_link_count: int
    event_count: int
    trace_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "experiment_id",
            require_stable_id(
                "SocialTransmissionReport.experiment_id", self.experiment_id
            ),
        )
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("SocialTransmissionReport.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "transmission_root_id",
            require_stable_id(
                "SocialTransmissionReport.transmission_root_id",
                self.transmission_root_id,
            ),
        )
        object.__setattr__(
            self,
            "unique_agent_count",
            require_exact_nonneg_int(
                "SocialTransmissionReport.unique_agent_count", self.unique_agent_count
            ),
        )
        object.__setattr__(
            self,
            "max_hop_count",
            require_exact_nonneg_int(
                "SocialTransmissionReport.max_hop_count", self.max_hop_count
            ),
        )

    def __repr__(self) -> str:
        return (
            f"SocialTransmissionReport(experiment_id={self.experiment_id!r}, "
            f"run_id={self.run_id!r}, root={self.transmission_root_id!r}, "
            f"hop_count={len(self.hops)}, max_hop={self.max_hop_count}, "
            f"unique_agents={self.unique_agent_count}, "
            f"unresolved={self.unresolved_link_count}, "
            f"metric_version={self.metric_version!r})"
        )
