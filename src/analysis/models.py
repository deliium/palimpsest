"""Immutable reconstruction-chain, metric-document, and memory-drift DTOs.

Domain values are log-free. Safe ``repr`` exposes IDs, counts, versions, and
status codes only — never narratives, event details, or memory payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from analysis.evidence import EvidenceStage, require_evidence_stage
from analysis.numerical import library_versions, quantize_float, require_finite
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "ACTION_RESOLUTION_RATES_FAMILY",
    "AGENT_VISIBLE_PROJECTOR_VERSION",
    "DRIFT_METRIC_VERSION",
    "EVENT_FACT_PROJECTOR_VERSION",
    "MEMORY_DYNAMICS_METRIC_VERSION",
    "METRIC_DOCUMENT_SCHEMA_VERSION",
    "SOCIAL_TRANSMISSION_METRIC_VERSION",
    "ActionResolutionRow",
    "AppliedActionRow",
    "BeliefClaimRow",
    "ChainNodeKind",
    "ComparisonStatus",
    "DriftDelta",
    "DriftStep",
    "EvidenceStage",
    "FactAvailability",
    "GoalTransitionRow",
    "MemoryDriftReport",
    "MemoryDynamicsAuditRow",
    "MemoryDynamicsReport",
    "MetricAvailability",
    "MetricCoverage",
    "MetricDocument",
    "MetricProvenance",
    "ObjectiveLinkStatus",
    "ReconstructionChain",
    "ReconstructionChainNode",
    "ReconstructionEvidence",
    "RelationshipEdgeRow",
    "ResourceHoldingRow",
    "SocialTransmissionReport",
    "StructuredFactSet",
    "SubjectiveDerivationEdge",
    "SurvivalAgentRow",
    "TransmissionDistortion",
    "TransmissionHopRecord",
    "TransmissionLineageEdge",
]

METRIC_DOCUMENT_SCHEMA_VERSION: Final[str] = "1"

DRIFT_METRIC_VERSION: Final[str] = "1"
EVENT_FACT_PROJECTOR_VERSION: Final[str] = "1"
AGENT_VISIBLE_PROJECTOR_VERSION: Final[str] = "1"

# Supporting Task-11 rates document family (not one of the fifteen catalog IDs).
ACTION_RESOLUTION_RATES_FAMILY: Final[str] = "action_resolution_rates"


class ChainNodeKind(StrEnum):
    """Ordered provenance roles along one reconstruction chain."""

    AGENT_VISIBLE_PROJECTION = "agent_visible_projection"
    OBJECTIVE_EVENT = "objective_event"
    ROOT_TRACE = "root_trace"
    RECONSTRUCTION = "reconstruction"
    DERIVED_TRACE = "derived_trace"
    AUTHORITATIVE_WORLD_GAP = "authoritative_world_gap"


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
    evidence_stage: EvidenceStage | None = None
    comparison_label: str = "primary"

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
        if self.evidence_stage is not None:
            object.__setattr__(
                self,
                "evidence_stage",
                require_evidence_stage("DriftStep.evidence_stage", self.evidence_stage),
            )
        object.__setattr__(
            self,
            "comparison_label",
            require_stable_id("DriftStep.comparison_label", self.comparison_label),
        )

    def __repr__(self) -> str:
        return (
            f"DriftStep(root={self.chain_root_memory_id!r}, "
            f"from={self.from_kind.value!r}, to={self.to_kind.value!r}, "
            f"label={self.comparison_label!r}, "
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
    authoritative_gap_steps: tuple[DriftStep, ...] = ()
    evidence_stage_counts: Mapping[str, int] | None = None

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
        if self.evidence_stage_counts is not None:
            cleaned: dict[str, int] = {}
            for key in sorted(self.evidence_stage_counts):
                value = self.evidence_stage_counts[key]
                if type(value) is not int or value < 0:
                    raise ValueError("MemoryDriftReport.evidence_stage_counts: invalid")
                cleaned[require_stable_id("evidence_stage_counts.key", key)] = value
            object.__setattr__(
                self, "evidence_stage_counts", MappingProxyType(cleaned)
            )

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
    """Ordered direct derivation edge for provenance traversal.

    Edges always carry run/owner scope so in-memory and durable stores can key
    and filter without post-hoc unscoped scans.
    """

    run_id: str
    owner_id: str
    derived_memory_id: str
    source_memory_id: str
    ordinal: int
    reconstruction_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("SubjectiveDerivationEdge.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("SubjectiveDerivationEdge.owner_id", self.owner_id),
        )
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
            f"SubjectiveDerivationEdge(run_id={self.run_id!r}, "
            f"owner_id={self.owner_id!r}, "
            f"derived_memory_id={self.derived_memory_id!r}, "
            f"source_memory_id={self.source_memory_id!r}, ordinal={self.ordinal}, "
            f"has_reconstruction={self.reconstruction_id is not None})"
        )


class MetricAvailability(StrEnum):
    """Whether a metric result is fully known, missing, unknown, or partial."""

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class MetricCoverage:
    """Observed-versus-expected coverage for one metric denominator."""

    observed: int
    expected: int
    ratio: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observed",
            require_exact_nonneg_int("MetricCoverage.observed", self.observed),
        )
        object.__setattr__(
            self,
            "expected",
            require_exact_nonneg_int("MetricCoverage.expected", self.expected),
        )
        if self.ratio is not None:
            object.__setattr__(
                self,
                "ratio",
                quantize_float(require_finite(float(self.ratio))),
            )

    def __repr__(self) -> str:
        return (
            f"MetricCoverage(observed={self.observed}, expected={self.expected}, "
            f"has_ratio={self.ratio is not None})"
        )


@dataclass(frozen=True, slots=True)
class MetricProvenance:
    """Stable provenance metadata without embedding evidence payloads."""

    source_kind: str
    source_ids: tuple[str, ...]
    notes_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_kind",
            require_stable_id("MetricProvenance.source_kind", self.source_kind),
        )
        ids = tuple(
            require_stable_id(f"MetricProvenance.source_ids[{index}]", item)
            for index, item in enumerate(self.source_ids)
        )
        object.__setattr__(self, "source_ids", ids)
        if self.notes_code is not None:
            object.__setattr__(
                self,
                "notes_code",
                require_stable_id("MetricProvenance.notes_code", self.notes_code),
            )

    def __repr__(self) -> str:
        return (
            f"MetricProvenance(source_kind={self.source_kind!r}, "
            f"source_id_count={len(self.source_ids)}, "
            f"notes_code={self.notes_code!r})"
        )


@dataclass(frozen=True, slots=True)
class MetricDocument:
    """Immutable, schema-versioned metric result with run scope and coverage.

    Family formulas, populations, and edge-case policy are defined in
    ``analysis.specifications`` (catalog ``metric-catalog-v1``). This document
    is the computed artifact, not the specification.
    """

    schema_version: str
    metric_family: str
    algorithm_version: str
    library_versions: Mapping[str, str]
    run_id: str
    input_revision: str
    evidence_stages: frozenset[EvidenceStage]
    population: str
    denominator: str
    coverage: MetricCoverage | None
    availability: MetricAvailability
    values: Mapping[str, object]
    provenance: MetricProvenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            require_stable_id("MetricDocument.schema_version", self.schema_version),
        )
        if self.schema_version != METRIC_DOCUMENT_SCHEMA_VERSION:
            raise ValueError("MetricDocument.schema_version: unsupported")
        object.__setattr__(
            self,
            "metric_family",
            require_stable_id("MetricDocument.metric_family", self.metric_family),
        )
        object.__setattr__(
            self,
            "algorithm_version",
            require_stable_id(
                "MetricDocument.algorithm_version", self.algorithm_version
            ),
        )
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("MetricDocument.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "input_revision",
            require_stable_id("MetricDocument.input_revision", self.input_revision),
        )
        object.__setattr__(
            self,
            "population",
            require_stable_id("MetricDocument.population", self.population),
        )
        object.__setattr__(
            self,
            "denominator",
            require_stable_id("MetricDocument.denominator", self.denominator),
        )
        if type(self.availability) is not MetricAvailability:
            raise TypeError("MetricDocument.availability: invalid_type")
        if type(self.provenance) is not MetricProvenance:
            raise TypeError("MetricDocument.provenance: invalid_type")
        if self.coverage is not None and type(self.coverage) is not MetricCoverage:
            raise TypeError("MetricDocument.coverage: invalid_type")
        if not isinstance(self.evidence_stages, frozenset) or not self.evidence_stages:
            raise ValueError("MetricDocument.evidence_stages: empty_or_invalid")
        stages = frozenset(
            require_evidence_stage("MetricDocument.evidence_stages", stage)
            for stage in self.evidence_stages
        )
        object.__setattr__(self, "evidence_stages", stages)

        if not isinstance(self.library_versions, Mapping) or not self.library_versions:
            raise ValueError("MetricDocument.library_versions: empty_or_invalid")
        required_libs = ("numpy", "pandas", "scipy", "networkx")
        versions: dict[str, str] = {}
        for lib_key in sorted(self.library_versions):
            if not isinstance(lib_key, str):
                raise TypeError("MetricDocument.library_versions: invalid_key")
            lib_value = self.library_versions[lib_key]
            if not isinstance(lib_value, str) or not lib_value:
                raise ValueError("MetricDocument.library_versions: invalid_value")
            versions[lib_key] = lib_value
        for name in required_libs:
            if name not in versions:
                raise ValueError(f"MetricDocument.library_versions: missing_{name}")
        object.__setattr__(self, "library_versions", MappingProxyType(versions))

        if not isinstance(self.values, Mapping):
            raise TypeError("MetricDocument.values: invalid_type")
        cleaned: dict[str, object] = {}
        for value_key in sorted(self.values):
            if not isinstance(value_key, str):
                raise TypeError("MetricDocument.values: invalid_key")
            raw_value: object = self.values[value_key]
            if raw_value is None:
                cleaned[value_key] = None
            elif isinstance(raw_value, bool):
                cleaned[value_key] = raw_value
            elif isinstance(raw_value, str):
                cleaned[value_key] = raw_value
            elif isinstance(raw_value, int) and not isinstance(raw_value, bool):
                cleaned[value_key] = raw_value
            elif isinstance(raw_value, float):
                cleaned[value_key] = quantize_float(require_finite(raw_value))
            else:
                raise TypeError("MetricDocument.values: invalid_value")
        object.__setattr__(self, "values", MappingProxyType(cleaned))

    @staticmethod
    def default_library_versions() -> Mapping[str, str]:
        """Installed scientific library versions for new documents."""
        return library_versions()

    def __repr__(self) -> str:
        return (
            f"MetricDocument(schema_version={self.schema_version!r}, "
            f"metric_family={self.metric_family!r}, run_id={self.run_id!r}, "
            f"availability={self.availability.value!r}, "
            f"stage_count={len(self.evidence_stages)}, "
            f"value_count={len(self.values)})"
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
    parent_communication_id: str | None = None
    concepts: frozenset[str] = frozenset()
    relations: frozenset[tuple[str, str, str]] = frozenset()
    adoption_stage: str | None = None

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
        if self.parent_communication_id is not None:
            object.__setattr__(
                self,
                "parent_communication_id",
                require_stable_id(
                    "TransmissionHopRecord.parent_communication_id",
                    self.parent_communication_id,
                ),
            )
        if self.adoption_stage is not None:
            object.__setattr__(
                self,
                "adoption_stage",
                require_stable_id(
                    "TransmissionHopRecord.adoption_stage", self.adoption_stage
                ),
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


@dataclass(frozen=True, slots=True)
class ResourceHoldingRow:
    """One agent's observed named resource measure (never labeled wealth)."""

    agent_id: str
    value: float | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "agent_id",
            require_stable_id("ResourceHoldingRow.agent_id", self.agent_id),
        )
        if self.value is not None:
            object.__setattr__(
                self,
                "value",
                quantize_float(require_finite(float(self.value))),
            )

    def __repr__(self) -> str:
        return (
            f"ResourceHoldingRow(agent_id={self.agent_id!r}, "
            f"observed={self.value is not None})"
        )


@dataclass(frozen=True, slots=True)
class AppliedActionRow:
    """Detached applied action token for objective/behavior metrics."""

    tick: int
    ordinal: int
    agent_id: str
    action_kind: str
    location_id: str | None = None
    target_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("AppliedActionRow.tick", self.tick),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("AppliedActionRow.ordinal", self.ordinal),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_stable_id("AppliedActionRow.agent_id", self.agent_id),
        )
        object.__setattr__(
            self,
            "action_kind",
            require_stable_id("AppliedActionRow.action_kind", self.action_kind),
        )
        if self.location_id is not None:
            object.__setattr__(
                self,
                "location_id",
                require_stable_id("AppliedActionRow.location_id", self.location_id),
            )
        if self.target_id is not None:
            object.__setattr__(
                self,
                "target_id",
                require_stable_id("AppliedActionRow.target_id", self.target_id),
            )

    def __repr__(self) -> str:
        return (
            f"AppliedActionRow(tick={self.tick}, ordinal={self.ordinal}, "
            f"agent_id={self.agent_id!r}, action_kind={self.action_kind!r})"
        )


@dataclass(frozen=True, slots=True)
class ActionResolutionRow:
    """Detached ActionResolution evidence row (status codes only)."""

    tick: int
    ordinal: int
    agent_id: str
    command_kind: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ActionResolutionRow.tick", self.tick),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("ActionResolutionRow.ordinal", self.ordinal),
        )
        object.__setattr__(
            self,
            "agent_id",
            require_stable_id("ActionResolutionRow.agent_id", self.agent_id),
        )
        object.__setattr__(
            self,
            "command_kind",
            require_stable_id("ActionResolutionRow.command_kind", self.command_kind),
        )
        object.__setattr__(
            self,
            "status",
            require_stable_id("ActionResolutionRow.status", self.status),
        )

    def __repr__(self) -> str:
        return (
            f"ActionResolutionRow(tick={self.tick}, ordinal={self.ordinal}, "
            f"agent_id={self.agent_id!r}, status={self.status!r})"
        )


@dataclass(frozen=True, slots=True)
class SurvivalAgentRow:
    """Registration plus optional objective death tick for survival metrics."""

    agent_id: str
    death_tick: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "agent_id",
            require_stable_id("SurvivalAgentRow.agent_id", self.agent_id),
        )
        if self.death_tick is not None:
            object.__setattr__(
                self,
                "death_tick",
                require_exact_nonneg_int(
                    "SurvivalAgentRow.death_tick", self.death_tick
                ),
            )

    def __repr__(self) -> str:
        return (
            f"SurvivalAgentRow(agent_id={self.agent_id!r}, "
            f"has_death={self.death_tick is not None})"
        )


@dataclass(frozen=True, slots=True)
class GoalTransitionRow:
    """Detached goal-transition receipt codes for goal-completion metrics."""

    goal_id: str
    owner_id: str
    tick: int
    reason_code: str
    to_status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "goal_id",
            require_stable_id("GoalTransitionRow.goal_id", self.goal_id),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("GoalTransitionRow.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("GoalTransitionRow.tick", self.tick),
        )
        object.__setattr__(
            self,
            "reason_code",
            require_stable_id("GoalTransitionRow.reason_code", self.reason_code),
        )
        object.__setattr__(
            self,
            "to_status",
            require_stable_id("GoalTransitionRow.to_status", self.to_status),
        )

    def __repr__(self) -> str:
        return (
            f"GoalTransitionRow(goal_id={self.goal_id!r}, "
            f"reason_code={self.reason_code!r}, tick={self.tick})"
        )


@dataclass(frozen=True, slots=True)
class BeliefClaimRow:
    """Detached belief-revision claim for accuracy / persistence metrics.

    ``claim_id`` must match a ``ClaimTruthSpec.claim_id`` to be evaluable.
    Objective truth never enters this row from cognition.
    """

    owner_id: str
    belief_id: str
    claim_id: str
    logical_tick: int
    activation_state: str
    confidence: float | None
    value_kind: str
    bool_value: bool | None = None
    categorical_value: str | None = None
    numeric_value: float | None = None
    evidence_stage: EvidenceStage = EvidenceStage.BELIEF_REVISION_TESTIMONY

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("BeliefClaimRow.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "belief_id",
            require_stable_id("BeliefClaimRow.belief_id", self.belief_id),
        )
        object.__setattr__(
            self,
            "claim_id",
            require_stable_id("BeliefClaimRow.claim_id", self.claim_id),
        )
        object.__setattr__(
            self,
            "logical_tick",
            require_exact_nonneg_int("BeliefClaimRow.logical_tick", self.logical_tick),
        )
        object.__setattr__(
            self,
            "activation_state",
            require_stable_id("BeliefClaimRow.activation_state", self.activation_state),
        )
        object.__setattr__(
            self,
            "value_kind",
            require_stable_id("BeliefClaimRow.value_kind", self.value_kind),
        )
        object.__setattr__(
            self,
            "evidence_stage",
            require_evidence_stage(
                "BeliefClaimRow.evidence_stage", self.evidence_stage
            ),
        )
        if self.confidence is not None:
            if type(self.confidence) is not float or (
                self.confidence != self.confidence
                or self.confidence in (float("inf"), float("-inf"))
            ):
                raise ValueError("BeliefClaimRow.confidence: non_finite")
        if self.categorical_value is not None:
            object.__setattr__(
                self,
                "categorical_value",
                require_stable_id(
                    "BeliefClaimRow.categorical_value", self.categorical_value
                ),
            )
        if self.numeric_value is not None:
            if type(self.numeric_value) is not float or (
                self.numeric_value != self.numeric_value
                or self.numeric_value in (float("inf"), float("-inf"))
            ):
                raise ValueError("BeliefClaimRow.numeric_value: non_finite")

    def __repr__(self) -> str:
        return (
            f"BeliefClaimRow(owner_id={self.owner_id!r}, belief_id={self.belief_id!r}, "
            f"claim_id={self.claim_id!r}, tick={self.logical_tick}, "
            f"activation={self.activation_state!r})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipEdgeRow:
    """One directed relationship revision snapshot for stability / network metrics."""

    source_id: str
    target_id: str
    logical_tick: int
    activation_state: str
    trust: float | None = None
    trust_confidence: float | None = None
    fear: float | None = None
    affection: float | None = None
    debt: float | None = None
    respect: float | None = None
    resentment: float | None = None
    familiarity: float | None = None
    dependency: float | None = None
    ordinal: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_id",
            require_stable_id("RelationshipEdgeRow.source_id", self.source_id),
        )
        object.__setattr__(
            self,
            "target_id",
            require_stable_id("RelationshipEdgeRow.target_id", self.target_id),
        )
        if self.source_id == self.target_id:
            raise ValueError("RelationshipEdgeRow: self_target")
        object.__setattr__(
            self,
            "logical_tick",
            require_exact_nonneg_int(
                "RelationshipEdgeRow.logical_tick", self.logical_tick
            ),
        )
        object.__setattr__(
            self,
            "activation_state",
            require_stable_id(
                "RelationshipEdgeRow.activation_state", self.activation_state
            ),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("RelationshipEdgeRow.ordinal", self.ordinal),
        )
        for name in (
            "trust",
            "fear",
            "affection",
            "debt",
            "respect",
            "resentment",
            "familiarity",
            "dependency",
            "trust_confidence",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            if type(value) is not float or (
                value != value or value in (float("inf"), float("-inf"))
            ):
                raise ValueError(f"RelationshipEdgeRow.{name}: non_finite")

    def __repr__(self) -> str:
        return (
            f"RelationshipEdgeRow(source_id={self.source_id!r}, "
            f"target_id={self.target_id!r}, tick={self.logical_tick}, "
            f"activation={self.activation_state!r})"
        )


@dataclass(frozen=True, slots=True)
class TransmissionLineageEdge:
    """Declared parent→child transmission link (never inferred from hop order)."""

    parent_communication_id: str | None
    child_communication_id: str
    transmission_root_id: str
    hop_count: int
    tick: int
    speaker_id: str
    listener_id: str | None
    cycle_rejected: bool = False
    unresolved: bool = False

    def __post_init__(self) -> None:
        if self.parent_communication_id is not None:
            object.__setattr__(
                self,
                "parent_communication_id",
                require_stable_id(
                    "TransmissionLineageEdge.parent_communication_id",
                    self.parent_communication_id,
                ),
            )
        object.__setattr__(
            self,
            "child_communication_id",
            require_stable_id(
                "TransmissionLineageEdge.child_communication_id",
                self.child_communication_id,
            ),
        )
        object.__setattr__(
            self,
            "transmission_root_id",
            require_stable_id(
                "TransmissionLineageEdge.transmission_root_id",
                self.transmission_root_id,
            ),
        )
        object.__setattr__(
            self,
            "hop_count",
            require_exact_nonneg_int(
                "TransmissionLineageEdge.hop_count", self.hop_count
            ),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("TransmissionLineageEdge.tick", self.tick),
        )
        object.__setattr__(
            self,
            "speaker_id",
            require_stable_id("TransmissionLineageEdge.speaker_id", self.speaker_id),
        )
        if self.listener_id is not None:
            object.__setattr__(
                self,
                "listener_id",
                require_stable_id(
                    "TransmissionLineageEdge.listener_id", self.listener_id
                ),
            )

    def __repr__(self) -> str:
        return (
            f"TransmissionLineageEdge(child={self.child_communication_id!r}, "
            f"root={self.transmission_root_id!r}, hop={self.hop_count}, "
            f"unresolved={self.unresolved}, cycle_rejected={self.cycle_rejected})"
        )


MEMORY_DYNAMICS_METRIC_VERSION: Final[str] = "memory_dynamics@1"


@dataclass(frozen=True, slots=True)
class MemoryDynamicsAuditRow:
    """Neutral in-run audit export (IDs/codes/counts only)."""

    reconstruction_id: str
    owner_id: str
    tick: int
    source_count: int
    competitor_count: int
    selected_count: int
    distortion_codes: tuple[str, ...]
    confidence_before: float
    confidence_after: float
    strength_delta_count: int
    source_memory_ids: tuple[str, ...] = ()
    competitor_ids: tuple[str, ...] = ()
    selected_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reconstruction_id",
            require_stable_id(
                "MemoryDynamicsAuditRow.reconstruction_id", self.reconstruction_id
            ),
        )
        object.__setattr__(
            self,
            "owner_id",
            require_stable_id("MemoryDynamicsAuditRow.owner_id", self.owner_id),
        )
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("MemoryDynamicsAuditRow.tick", self.tick),
        )
        for name in (
            "source_count",
            "competitor_count",
            "selected_count",
            "strength_delta_count",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"MemoryDynamicsAuditRow.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "confidence_before",
            quantize_float(require_finite(float(self.confidence_before))),
        )
        object.__setattr__(
            self,
            "confidence_after",
            quantize_float(require_finite(float(self.confidence_after))),
        )
        codes = tuple(self.distortion_codes)
        for code in codes:
            require_stable_id("MemoryDynamicsAuditRow.distortion_codes", code)
        object.__setattr__(self, "distortion_codes", codes)
        for field in ("source_memory_ids", "competitor_ids", "selected_ids"):
            ids = tuple(getattr(self, field))
            for item in ids:
                require_stable_id(f"MemoryDynamicsAuditRow.{field}", item)
            object.__setattr__(self, field, ids)

    def __repr__(self) -> str:
        return (
            f"MemoryDynamicsAuditRow(reconstruction_id={self.reconstruction_id!r}, "
            f"owner_id={self.owner_id!r}, tick={self.tick}, "
            f"source_count={self.source_count}, "
            f"competitor_count={self.competitor_count}, "
            f"selected_count={self.selected_count}, "
            f"distortion_code_count={len(self.distortion_codes)})"
        )


@dataclass(frozen=True, slots=True)
class MemoryDynamicsReport:
    """Experiment-scoped V2 memory-dynamics audit aggregate."""

    experiment_id: str
    run_id: str
    condition_id: str
    metric_version: str
    audits: tuple[MemoryDynamicsAuditRow, ...]
    memory_mode: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "experiment_id",
            require_stable_id("MemoryDynamicsReport.experiment_id", self.experiment_id),
        )
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("MemoryDynamicsReport.run_id", self.run_id),
        )
        object.__setattr__(
            self,
            "condition_id",
            require_stable_id("MemoryDynamicsReport.condition_id", self.condition_id),
        )
        object.__setattr__(
            self,
            "metric_version",
            require_stable_id(
                "MemoryDynamicsReport.metric_version", self.metric_version
            ),
        )
        object.__setattr__(
            self,
            "memory_mode",
            require_stable_id("MemoryDynamicsReport.memory_mode", self.memory_mode),
        )
        for row in self.audits:
            if type(row) is not MemoryDynamicsAuditRow:
                raise TypeError("MemoryDynamicsReport.audits: invalid_item")

    def __repr__(self) -> str:
        return (
            f"MemoryDynamicsReport(experiment_id={self.experiment_id!r}, "
            f"run_id={self.run_id!r}, condition_id={self.condition_id!r}, "
            f"audit_count={len(self.audits)}, memory_mode={self.memory_mode!r})"
        )

