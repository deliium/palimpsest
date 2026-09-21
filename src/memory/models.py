"""Owner-bound memory and belief aggregates.

``MemoryTrace`` is a fragmentary episodic record: structured concepts, entity
mentions, relations, context, salience, confidence, and provenance. It is not a
chat transcript and does not require a natural-language sentence. Domain values
remain log-free; exceptions expose field names and stable reason codes only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from world.identifiers import (
    EntityId,
    EventId,
    WorldRevision,
    require_bounded_text,
    require_exact_nonneg_int,
    require_ordered_unique,
    require_stable_id,
)

__all__ = [
    "ACCESS_HISTORY_MODE_FAMILIARITY",
    "ACCESS_HISTORY_MODE_NOVELTY",
    "SCORE_QUANTUM",
    "AccessHistoryMode",
    "AgentId",
    "Belief",
    "BeliefId",
    "BeliefStore",
    "ConceptMention",
    "EntityId",
    "EntityMention",
    "EventId",
    "MemoryAccessReceipt",
    "MemoryApplyResult",
    "MemoryEmbedding",
    "MemoryForgetRequest",
    "MemoryForgetResult",
    "MemoryId",
    "MemoryLineage",
    "MemoryMutationBatch",
    "MemoryProvenance",
    "MemoryQueryContext",
    "MemoryQueryFilters",
    "MemoryRankedHit",
    "MemoryRelation",
    "MemoryRetentionPolicy",
    "MemoryRetrieveRequest",
    "MemoryRetrieveResult",
    "MemoryRunId",
    "MemoryScope",
    "MemoryScoreBreakdown",
    "MemoryScoreWeights",
    "MemoryScoringPolicy",
    "MemorySituationContext",
    "MemorySourceKind",
    "MemoryStore",
    "MemoryTrace",
    "MentionId",
    "OwnershipError",
    "RelationEndpoint",
    "RelationEndpointKind",
    "WorldRevision",
    "diagnostic_projection",
    "normalize_score_weights",
    "quantize_score",
]

_MAX_CONCEPT_CHARS: Final[int] = 256
_MAX_LABEL_CHARS: Final[int] = 256
_MAX_PREDICATE_CHARS: Final[int] = 128
_MAX_CONTEXT_TAG_CHARS: Final[int] = 128
_MAX_MENTIONS: Final[int] = 256
_MAX_RELATIONS: Final[int] = 256
_MAX_CONTEXT_TAGS: Final[int] = 64


class OwnershipError(PermissionError):
    """Raised when a write targets a different owner than the aggregate."""


class MemorySourceKind(StrEnum):
    """Whether a trace came from direct perception or a communicated claim."""

    DIRECT_OBSERVATION = "direct_observation"
    COMMUNICATED = "communicated"


class RelationEndpointKind(StrEnum):
    """Trace-local endpoint kind for a normalized relation."""

    CONCEPT = "concept"
    ENTITY = "entity"


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite float in [0.0, 1.0]")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be a finite float in [0.0, 1.0]")
    return 0.0 if number == 0.0 else number


def _require_ordered_models[T](
    name: str, values: Sequence[object], *, model_type: type[T], max_items: int
) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name}: not_ordered_sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name}: not_ordered_sequence")
    items = tuple(values)
    if len(items) > max_items:
        raise ValueError(f"{name}: exceeds_max_length")
    for item in items:
        if type(item) is not model_type:
            raise TypeError(f"{name}: invalid_item_type")
    return items  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class MemoryId:
    value: str

    def __post_init__(self) -> None:
        require_stable_id("MemoryId.value", self.value)


@dataclass(frozen=True, slots=True)
class BeliefId:
    value: str

    def __post_init__(self) -> None:
        require_stable_id("BeliefId.value", self.value)


@dataclass(frozen=True, slots=True)
class MentionId:
    """Stable identifier unique within one ``MemoryTrace``."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("MentionId.value", self.value)


@dataclass(frozen=True, slots=True)
class ConceptMention:
    """One structured concept fragment; not a required sentence."""

    mention_id: MentionId
    concept: str

    def __post_init__(self) -> None:
        if type(self.mention_id) is not MentionId:
            raise TypeError("ConceptMention.mention_id: invalid_type")
        object.__setattr__(
            self,
            "concept",
            require_bounded_text(
                "ConceptMention.concept",
                self.concept,
                max_length=_MAX_CONCEPT_CHARS,
            ),
        )

    def __repr__(self) -> str:
        return f"ConceptMention(mention_id={self.mention_id.value!r})"


@dataclass(frozen=True, slots=True)
class EntityMention:
    """Perceived entity mention with optional opaque grounding."""

    mention_id: MentionId
    label: str
    entity_id: EntityId | None = None

    def __post_init__(self) -> None:
        if type(self.mention_id) is not MentionId:
            raise TypeError("EntityMention.mention_id: invalid_type")
        object.__setattr__(
            self,
            "label",
            require_bounded_text(
                "EntityMention.label",
                self.label,
                max_length=_MAX_LABEL_CHARS,
            ),
        )
        if self.entity_id is not None and type(self.entity_id) is not EntityId:
            raise TypeError("EntityMention.entity_id: invalid_type")

    def __repr__(self) -> str:
        grounded = self.entity_id is not None
        return (
            f"EntityMention(mention_id={self.mention_id.value!r}, grounded={grounded})"
        )


@dataclass(frozen=True, slots=True)
class RelationEndpoint:
    """Typed endpoint referencing a concept or entity mention in the same trace."""

    kind: RelationEndpointKind
    mention_id: MentionId

    def __post_init__(self) -> None:
        if type(self.kind) is not RelationEndpointKind:
            raise TypeError("RelationEndpoint.kind: invalid_type")
        if type(self.mention_id) is not MentionId:
            raise TypeError("RelationEndpoint.mention_id: invalid_type")

    def __repr__(self) -> str:
        return (
            f"RelationEndpoint(kind={self.kind.value!r}, "
            f"mention_id={self.mention_id.value!r})"
        )


@dataclass(frozen=True, slots=True)
class MemoryRelation:
    """Normalized relation between two mention endpoints."""

    relation_id: MentionId
    predicate: str
    subject: RelationEndpoint
    object: RelationEndpoint

    def __post_init__(self) -> None:
        if type(self.relation_id) is not MentionId:
            raise TypeError("MemoryRelation.relation_id: invalid_type")
        object.__setattr__(
            self,
            "predicate",
            require_bounded_text(
                "MemoryRelation.predicate",
                self.predicate,
                max_length=_MAX_PREDICATE_CHARS,
            ),
        )
        if type(self.subject) is not RelationEndpoint:
            raise TypeError("MemoryRelation.subject: invalid_type")
        if type(self.object) is not RelationEndpoint:
            raise TypeError("MemoryRelation.object: invalid_type")

    def __repr__(self) -> str:
        return f"MemoryRelation(relation_id={self.relation_id.value!r})"


@dataclass(frozen=True, slots=True)
class MemorySituationContext:
    """Situational context retained with a trace (no narrative payload)."""

    location_id: EntityId | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.location_id is not None and type(self.location_id) is not EntityId:
            raise TypeError("MemorySituationContext.location_id: invalid_type")
        if isinstance(self.tags, (set, frozenset, Mapping)):
            raise TypeError("MemorySituationContext.tags: not_ordered_sequence")
        if isinstance(self.tags, (str, bytes, bytearray)) or not isinstance(
            self.tags, Sequence
        ):
            raise TypeError("MemorySituationContext.tags: not_ordered_sequence")
        raw_tags = tuple(self.tags)
        if len(raw_tags) > _MAX_CONTEXT_TAGS:
            raise ValueError("MemorySituationContext.tags: exceeds_max_length")
        seen: set[str] = set()
        tags: list[str] = []
        for tag in raw_tags:
            text = require_bounded_text(
                "MemorySituationContext.tags",
                tag,
                max_length=_MAX_CONTEXT_TAG_CHARS,
            )
            if text in seen:
                raise ValueError("MemorySituationContext.tags: duplicate")
            seen.add(text)
            tags.append(text)
        object.__setattr__(self, "tags", tuple(tags))

    def __repr__(self) -> str:
        return (
            f"MemorySituationContext(has_location={self.location_id is not None}, "
            f"tag_count={len(self.tags)})"
        )


@dataclass(frozen=True, slots=True)
class MemoryProvenance:
    """Direct observation versus communicated claim, with opaque correlation.

    ``observed_source_id`` is correlation metadata copied from a redacted
    observation only. It never grants dereference of objective events or state.
    """

    kind: MemorySourceKind
    source_tick: int
    observed_source_id: EventId | None = None
    speaker_id: EntityId | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not MemorySourceKind:
            raise TypeError("MemoryProvenance.kind: invalid_type")
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int("MemoryProvenance.source_tick", self.source_tick),
        )
        if (
            self.observed_source_id is not None
            and type(self.observed_source_id) is not EventId
        ):
            raise TypeError("MemoryProvenance.observed_source_id: invalid_type")
        if self.speaker_id is not None and type(self.speaker_id) is not EntityId:
            raise TypeError("MemoryProvenance.speaker_id: invalid_type")
        if self.kind is MemorySourceKind.DIRECT_OBSERVATION:
            if self.speaker_id is not None:
                raise ValueError("MemoryProvenance.speaker_id: forbidden_for_direct")
        elif self.kind is MemorySourceKind.COMMUNICATED:
            if self.speaker_id is None:
                raise ValueError(
                    "MemoryProvenance.speaker_id: required_for_communicated"
                )
        else:  # pragma: no cover - closed enum
            raise ValueError("MemoryProvenance.kind: unsupported")

    def __repr__(self) -> str:
        return (
            f"MemoryProvenance(kind={self.kind.value!r}, "
            f"source_tick={self.source_tick}, "
            f"has_source={self.observed_source_id is not None}, "
            f"has_speaker={self.speaker_id is not None})"
        )


@dataclass(frozen=True, slots=True)
class MemoryLineage:
    """Reserved reconsolidation lineage; V1 does not apply reconstruction policy."""

    supersedes_memory_id: MemoryId | None = None
    generation: int = 0

    def __post_init__(self) -> None:
        if (
            self.supersedes_memory_id is not None
            and type(self.supersedes_memory_id) is not MemoryId
        ):
            raise TypeError("MemoryLineage.supersedes_memory_id: invalid_type")
        object.__setattr__(
            self,
            "generation",
            require_exact_nonneg_int("MemoryLineage.generation", self.generation),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryLineage(has_supersedes={self.supersedes_memory_id is not None}, "
            f"generation={self.generation})"
        )


@dataclass(frozen=True, slots=True)
class MemoryTrace:
    """Immutable fragmentary episodic memory owned by one agent.

    Rejects arbitrary payload maps and objective authority containers. Nested
    mentions use ordered tuples and unique trace-local IDs so serialization and
    relation endpoints stay deterministic.
    """

    memory_id: MemoryId
    owner_id: AgentId
    world_revision: WorldRevision
    concepts: tuple[ConceptMention, ...]
    entities: tuple[EntityMention, ...]
    relations: tuple[MemoryRelation, ...]
    context: MemorySituationContext
    emotional_salience: float
    confidence: float
    provenance: MemoryProvenance
    created_tick: int
    source_tick: int
    last_access_tick: int
    access_count: int
    expires_at_tick: int | None = None
    forgotten_at_tick: int | None = None
    lineage: MemoryLineage = MemoryLineage()
    embedding: MemoryEmbedding | None = None

    def __post_init__(self) -> None:
        if type(self.memory_id) is not MemoryId:
            raise TypeError("MemoryTrace.memory_id: invalid_type")
        if type(self.owner_id) is not AgentId:
            raise TypeError("MemoryTrace.owner_id: invalid_type")
        if type(self.world_revision) is not WorldRevision:
            raise TypeError("MemoryTrace.world_revision: invalid_type")

        concepts = _require_ordered_models(
            "MemoryTrace.concepts",
            self.concepts,
            model_type=ConceptMention,
            max_items=_MAX_MENTIONS,
        )
        entities = _require_ordered_models(
            "MemoryTrace.entities",
            self.entities,
            model_type=EntityMention,
            max_items=_MAX_MENTIONS,
        )
        relations = _require_ordered_models(
            "MemoryTrace.relations",
            self.relations,
            model_type=MemoryRelation,
            max_items=_MAX_RELATIONS,
        )
        object.__setattr__(self, "concepts", concepts)
        object.__setattr__(self, "entities", entities)
        object.__setattr__(self, "relations", relations)

        if type(self.context) is not MemorySituationContext:
            raise TypeError("MemoryTrace.context: invalid_type")
        if type(self.provenance) is not MemoryProvenance:
            raise TypeError("MemoryTrace.provenance: invalid_type")
        if type(self.lineage) is not MemoryLineage:
            raise TypeError("MemoryTrace.lineage: invalid_type")
        if self.embedding is not None and type(self.embedding) is not MemoryEmbedding:
            raise TypeError("MemoryTrace.embedding: invalid_type")

        object.__setattr__(
            self,
            "emotional_salience",
            _unit_interval("MemoryTrace.emotional_salience", self.emotional_salience),
        )
        object.__setattr__(
            self,
            "confidence",
            _unit_interval("MemoryTrace.confidence", self.confidence),
        )

        created = require_exact_nonneg_int(
            "MemoryTrace.created_tick", self.created_tick
        )
        source = require_exact_nonneg_int("MemoryTrace.source_tick", self.source_tick)
        last_access = require_exact_nonneg_int(
            "MemoryTrace.last_access_tick", self.last_access_tick
        )
        access_count = require_exact_nonneg_int(
            "MemoryTrace.access_count", self.access_count
        )
        object.__setattr__(self, "created_tick", created)
        object.__setattr__(self, "source_tick", source)
        object.__setattr__(self, "last_access_tick", last_access)
        object.__setattr__(self, "access_count", access_count)

        if last_access < created:
            raise ValueError("MemoryTrace.last_access_tick: before_created")

        if self.expires_at_tick is not None:
            expires = require_exact_nonneg_int(
                "MemoryTrace.expires_at_tick", self.expires_at_tick
            )
            if expires < created:
                raise ValueError("MemoryTrace.expires_at_tick: before_created")
            object.__setattr__(self, "expires_at_tick", expires)

        if self.forgotten_at_tick is not None:
            forgotten = require_exact_nonneg_int(
                "MemoryTrace.forgotten_at_tick", self.forgotten_at_tick
            )
            if forgotten < created:
                raise ValueError("MemoryTrace.forgotten_at_tick: before_created")
            object.__setattr__(self, "forgotten_at_tick", forgotten)

        concept_ids = {item.mention_id.value: item for item in concepts}
        entity_ids = {item.mention_id.value: item for item in entities}
        if len(concept_ids) != len(concepts):
            raise ValueError("MemoryTrace.concepts: duplicate_mention_id")
        if len(entity_ids) != len(entities):
            raise ValueError("MemoryTrace.entities: duplicate_mention_id")
        overlap = set(concept_ids) & set(entity_ids)
        if overlap:
            raise ValueError("MemoryTrace.mentions: overlapping_mention_id")

        relation_ids: set[str] = set()
        for relation in relations:
            rid = relation.relation_id.value
            if rid in relation_ids:
                raise ValueError("MemoryTrace.relations: duplicate_relation_id")
            relation_ids.add(rid)
            if rid in concept_ids or rid in entity_ids:
                raise ValueError("MemoryTrace.relations: relation_id_collides_mention")
            _validate_endpoint(
                "MemoryTrace.relations.subject",
                relation.subject,
                concept_ids=concept_ids,
                entity_ids=entity_ids,
            )
            _validate_endpoint(
                "MemoryTrace.relations.object",
                relation.object,
                concept_ids=concept_ids,
                entity_ids=entity_ids,
            )

        if (
            self.lineage.supersedes_memory_id is not None
            and self.lineage.supersedes_memory_id == self.memory_id
        ):
            raise ValueError("MemoryLineage.supersedes_memory_id: self_reference")

    def __repr__(self) -> str:
        return (
            f"MemoryTrace(memory_id={self.memory_id.value!r}, "
            f"owner_id={self.owner_id.value!r}, "
            f"concept_count={len(self.concepts)}, "
            f"entity_count={len(self.entities)}, "
            f"relation_count={len(self.relations)}, "
            f"confidence={self.confidence}, "
            f"salience={self.emotional_salience}, "
            f"access_count={self.access_count}, "
            f"forgotten={self.forgotten_at_tick is not None})"
        )


def _validate_endpoint(
    name: str,
    endpoint: RelationEndpoint,
    *,
    concept_ids: Mapping[str, ConceptMention],
    entity_ids: Mapping[str, EntityMention],
) -> None:
    mid = endpoint.mention_id.value
    if endpoint.kind is RelationEndpointKind.CONCEPT:
        if mid not in concept_ids:
            raise ValueError(f"{name}: unknown_concept_mention")
    elif endpoint.kind is RelationEndpointKind.ENTITY:
        if mid not in entity_ids:
            raise ValueError(f"{name}: unknown_entity_mention")
    else:  # pragma: no cover - closed enum
        raise ValueError(f"{name}: unsupported_endpoint_kind")


@dataclass(frozen=True, slots=True)
class Belief:
    """Immutable belief snapshot with confidence and evidence links."""

    belief_id: BeliefId
    owner_id: AgentId
    proposition: str
    confidence: float
    evidence_memory_ids: tuple[MemoryId, ...]

    def __post_init__(self) -> None:
        if type(self.belief_id) is not BeliefId:
            raise TypeError("Belief.belief_id must be BeliefId")
        if type(self.owner_id) is not AgentId:
            raise TypeError("Belief.owner_id must be AgentId")
        require_bounded_text("Belief.proposition", self.proposition)
        object.__setattr__(
            self, "confidence", _unit_interval("Belief.confidence", self.confidence)
        )
        evidence = require_ordered_unique(
            "Belief.evidence_memory_ids",
            self.evidence_memory_ids,
            item_type=MemoryId,
        )
        object.__setattr__(self, "evidence_memory_ids", evidence)


class MemoryStore:
    """Mutable memory aggregate bound to a single owner."""

    __slots__ = ("_owner_id", "_records")

    def __init__(self, owner_id: AgentId) -> None:
        self._owner_id = owner_id
        self._records: dict[MemoryId, MemoryTrace] = {}

    @property
    def owner_id(self) -> AgentId:
        return self._owner_id

    def snapshot(self) -> tuple[MemoryTrace, ...]:
        return tuple(self._records.values())

    def write(self, record: MemoryTrace) -> None:
        if type(record) is not MemoryTrace:
            raise TypeError("MemoryStore.write requires MemoryTrace")
        if record.owner_id != self._owner_id:
            raise OwnershipError(
                f"memory write owner {record.owner_id.value!r} does not match "
                f"store owner {self._owner_id.value!r}"
            )
        # Frozen traces are already detached; store by identity key only.
        self._records[record.memory_id] = record


class BeliefStore:
    """Mutable belief aggregate bound to a single owner."""

    __slots__ = ("_beliefs", "_owner_id")

    def __init__(self, owner_id: AgentId) -> None:
        self._owner_id = owner_id
        self._beliefs: dict[BeliefId, Belief] = {}

    @property
    def owner_id(self) -> AgentId:
        return self._owner_id

    def snapshot(self) -> tuple[Belief, ...]:
        return tuple(self._beliefs.values())

    def write(self, belief: Belief) -> None:
        if type(belief) is not Belief:
            raise TypeError("BeliefStore.write requires Belief")
        if belief.owner_id != self._owner_id:
            raise OwnershipError(
                f"belief write owner {belief.owner_id.value!r} does not match "
                f"store owner {self._owner_id.value!r}"
            )
        self._beliefs[belief.belief_id] = Belief(
            belief_id=belief.belief_id,
            owner_id=belief.owner_id,
            proposition=belief.proposition,
            confidence=belief.confidence,
            evidence_memory_ids=belief.evidence_memory_ids,
        )


# ---------------------------------------------------------------------------
# Owner-scoped retrieval, scoring, access, and forgetting contracts
# ---------------------------------------------------------------------------

SCORE_QUANTUM: Final[float] = 1e-6
_MAX_POLICY_ID_CHARS: Final[int] = 64
_MAX_EMBEDDING_DIM: Final[int] = 4096
_MAX_QUERY_LIMIT: Final[int] = 256
_MAX_BATCH_ITEMS: Final[int] = 256
_MAX_OPERATION_ID_CHARS: Final[int] = 128


class AccessHistoryMode(StrEnum):
    """How access counts contribute to scoring (policy-owned, not hidden)."""

    FAMILIARITY = "familiarity"
    NOVELTY = "novelty"


# Stable aliases for documentation and diagnostics allowlists.
ACCESS_HISTORY_MODE_FAMILIARITY: Final[str] = AccessHistoryMode.FAMILIARITY.value
ACCESS_HISTORY_MODE_NOVELTY: Final[str] = AccessHistoryMode.NOVELTY.value


@dataclass(frozen=True, slots=True)
class MemoryRunId:
    """Opaque simulation-run identity for memory scoping (not a domain seed)."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("MemoryRunId.value", self.value)


@dataclass(frozen=True, slots=True)
class MemoryScope:
    """Fixed run+owner binding for a normal ``MemoryService`` instance."""

    run_id: MemoryRunId
    owner_id: AgentId

    def __post_init__(self) -> None:
        if type(self.run_id) is not MemoryRunId:
            raise TypeError("MemoryScope.run_id: invalid_type")
        if type(self.owner_id) is not AgentId:
            raise TypeError("MemoryScope.owner_id: invalid_type")

    def __repr__(self) -> str:
        return (
            f"MemoryScope(run_id={self.run_id.value!r}, "
            f"owner_id={self.owner_id.value!r})"
        )


@dataclass(frozen=True, slots=True)
class MemoryEmbedding:
    """Optional fixed-dimension embedding with model/version metadata."""

    vector: tuple[float, ...]
    model: str
    version: str

    def __post_init__(self) -> None:
        if isinstance(self.vector, (set, frozenset, Mapping)):
            raise TypeError("MemoryEmbedding.vector: not_ordered_sequence")
        if isinstance(self.vector, (str, bytes, bytearray)) or not isinstance(
            self.vector, Sequence
        ):
            raise TypeError("MemoryEmbedding.vector: not_ordered_sequence")
        raw = tuple(self.vector)
        if not raw:
            raise ValueError("MemoryEmbedding.vector: empty")
        if len(raw) > _MAX_EMBEDDING_DIM:
            raise ValueError("MemoryEmbedding.vector: exceeds_max_dimension")
        floats: list[float] = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise TypeError("MemoryEmbedding.vector: invalid_component_type")
            number = float(item)
            if not math.isfinite(number):
                raise ValueError("MemoryEmbedding.vector: non_finite")
            floats.append(0.0 if number == 0.0 else number)
        object.__setattr__(self, "vector", tuple(floats))
        object.__setattr__(
            self,
            "model",
            require_bounded_text(
                "MemoryEmbedding.model", self.model, max_length=_MAX_POLICY_ID_CHARS
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "MemoryEmbedding.version",
                self.version,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )

    @property
    def dimension(self) -> int:
        return len(self.vector)

    def __repr__(self) -> str:
        return (
            f"MemoryEmbedding(dimension={self.dimension}, "
            f"model={self.model!r}, version={self.version!r})"
        )


@dataclass(frozen=True, slots=True)
class MemoryScoreWeights:
    """Non-negative weights for the six V1 score components."""

    semantic_relevance: float = 0.0
    recency: float = 0.0
    emotional_salience: float = 0.0
    current_context_overlap: float = 0.0
    social_relevance: float = 0.0
    access_history: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "semantic_relevance",
            "recency",
            "emotional_salience",
            "current_context_overlap",
            "social_relevance",
            "access_history",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"MemoryScoreWeights.{name}: not_nonneg_finite")
            number = float(value)
            if not math.isfinite(number) or number < 0.0:
                raise ValueError(f"MemoryScoreWeights.{name}: not_nonneg_finite")
            object.__setattr__(self, name, 0.0 if number == 0.0 else number)

    def enabled_components(self) -> tuple[str, ...]:
        names = (
            "semantic_relevance",
            "recency",
            "emotional_salience",
            "current_context_overlap",
            "social_relevance",
            "access_history",
        )
        return tuple(name for name in names if getattr(self, name) > 0.0)

    def __repr__(self) -> str:
        return f"MemoryScoreWeights(enabled={list(self.enabled_components())})"


def normalize_score_weights(weights: MemoryScoreWeights) -> MemoryScoreWeights:
    """Normalize active (strictly positive) weights to sum to 1.0."""
    if type(weights) is not MemoryScoreWeights:
        raise TypeError("normalize_score_weights: invalid_type")
    active = weights.enabled_components()
    if not active:
        raise ValueError("MemoryScoreWeights: no_active_weights")
    total = sum(getattr(weights, name) for name in active)
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError("MemoryScoreWeights: invalid_weight_sum")
    kwargs = {
        name: 0.0
        for name in (
            "semantic_relevance",
            "recency",
            "emotional_salience",
            "current_context_overlap",
            "social_relevance",
            "access_history",
        )
    }
    for name in active:
        kwargs[name] = getattr(weights, name) / total
    return MemoryScoreWeights(**kwargs)


def quantize_score(value: float) -> float:
    """Quantize a finite score at ``SCORE_QUANTUM`` (documented V1 boundary)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("quantize_score: not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("quantize_score: not_finite")
    steps = round(number / SCORE_QUANTUM)
    quantized = steps * SCORE_QUANTUM
    return 0.0 if quantized == 0.0 else quantized


@dataclass(frozen=True, slots=True)
class MemoryScoringPolicy:
    """Versioned immutable retrieval scoring policy."""

    policy_id: str
    version: str
    weights: MemoryScoreWeights
    access_history_mode: AccessHistoryMode = AccessHistoryMode.FAMILIARITY
    embedding_dimension: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "MemoryScoringPolicy.policy_id",
                self.policy_id,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "MemoryScoringPolicy.version",
                self.version,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        if type(self.weights) is not MemoryScoreWeights:
            raise TypeError("MemoryScoringPolicy.weights: invalid_type")
        if not self.weights.enabled_components():
            raise ValueError("MemoryScoringPolicy.weights: no_active_weights")
        if type(self.access_history_mode) is not AccessHistoryMode:
            raise TypeError("MemoryScoringPolicy.access_history_mode: invalid_type")
        if self.embedding_dimension is not None:
            dim = require_exact_nonneg_int(
                "MemoryScoringPolicy.embedding_dimension", self.embedding_dimension
            )
            if dim < 1 or dim > _MAX_EMBEDDING_DIM:
                raise ValueError(
                    "MemoryScoringPolicy.embedding_dimension: out_of_range"
                )
            object.__setattr__(self, "embedding_dimension", dim)
            if self.weights.semantic_relevance <= 0.0:
                raise ValueError(
                    "MemoryScoringPolicy.embedding_dimension: semantic_disabled"
                )
        elif self.weights.semantic_relevance > 0.0:
            raise ValueError(
                "MemoryScoringPolicy.semantic_relevance: embedding_dimension_required"
            )
        object.__setattr__(self, "weights", normalize_score_weights(self.weights))

    def __repr__(self) -> str:
        return (
            f"MemoryScoringPolicy(policy_id={self.policy_id!r}, "
            f"version={self.version!r}, "
            f"enabled={list(self.weights.enabled_components())})"
        )


@dataclass(frozen=True, slots=True)
class MemoryScoreBreakdown:
    """Per-component scores before weight aggregation (each in ``[0, 1]``)."""

    semantic_relevance: float = 0.0
    recency: float = 0.0
    emotional_salience: float = 0.0
    current_context_overlap: float = 0.0
    social_relevance: float = 0.0
    access_history: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "semantic_relevance",
            "recency",
            "emotional_salience",
            "current_context_overlap",
            "social_relevance",
            "access_history",
        ):
            object.__setattr__(
                self,
                name,
                _unit_interval(f"MemoryScoreBreakdown.{name}", getattr(self, name)),
            )

    def __repr__(self) -> str:
        return "MemoryScoreBreakdown(...)"


@dataclass(frozen=True, slots=True)
class MemoryRetentionPolicy:
    """Versioned retention decay used by soft-forget maintenance."""

    policy_id: str
    version: str
    half_life_ticks: int
    forget_threshold: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "MemoryRetentionPolicy.policy_id",
                self.policy_id,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "MemoryRetentionPolicy.version",
                self.version,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        half_life = require_exact_nonneg_int(
            "MemoryRetentionPolicy.half_life_ticks", self.half_life_ticks
        )
        if half_life < 1:
            raise ValueError("MemoryRetentionPolicy.half_life_ticks: must_be_positive")
        object.__setattr__(self, "half_life_ticks", half_life)
        object.__setattr__(
            self,
            "forget_threshold",
            _unit_interval(
                "MemoryRetentionPolicy.forget_threshold", self.forget_threshold
            ),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryRetentionPolicy(policy_id={self.policy_id!r}, "
            f"version={self.version!r}, half_life_ticks={self.half_life_ticks})"
        )


@dataclass(frozen=True, slots=True)
class MemoryQueryFilters:
    """Structured candidate filters applied before semantic scoring/limit."""

    created_tick_min: int | None = None
    created_tick_max: int | None = None
    source_tick_min: int | None = None
    source_tick_max: int | None = None
    location_id: EntityId | None = None
    provenance_kind: MemorySourceKind | None = None
    concepts: tuple[str, ...] = ()
    entity_ids: tuple[EntityId, ...] = ()
    relation_predicates: tuple[str, ...] = ()
    min_confidence: float | None = None
    min_salience: float | None = None
    context_tags: tuple[str, ...] = ()
    require_active: bool = True

    def __post_init__(self) -> None:
        for name in (
            "created_tick_min",
            "created_tick_max",
            "source_tick_min",
            "source_tick_max",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    require_exact_nonneg_int(f"MemoryQueryFilters.{name}", value),
                )
        if (
            self.created_tick_min is not None
            and self.created_tick_max is not None
            and self.created_tick_min > self.created_tick_max
        ):
            raise ValueError("MemoryQueryFilters.created_tick: inverted_range")
        if (
            self.source_tick_min is not None
            and self.source_tick_max is not None
            and self.source_tick_min > self.source_tick_max
        ):
            raise ValueError("MemoryQueryFilters.source_tick: inverted_range")
        if self.location_id is not None and type(self.location_id) is not EntityId:
            raise TypeError("MemoryQueryFilters.location_id: invalid_type")
        if (
            self.provenance_kind is not None
            and type(self.provenance_kind) is not MemorySourceKind
        ):
            raise TypeError("MemoryQueryFilters.provenance_kind: invalid_type")
        object.__setattr__(
            self,
            "concepts",
            _require_ordered_unique_text(
                "MemoryQueryFilters.concepts",
                self.concepts,
                max_length=_MAX_CONCEPT_CHARS,
                max_items=_MAX_MENTIONS,
            ),
        )
        object.__setattr__(
            self,
            "entity_ids",
            require_ordered_unique(
                "MemoryQueryFilters.entity_ids",
                self.entity_ids,
                item_type=EntityId,
            ),
        )
        if len(self.entity_ids) > _MAX_MENTIONS:
            raise ValueError("MemoryQueryFilters.entity_ids: exceeds_max_length")
        object.__setattr__(
            self,
            "relation_predicates",
            _require_ordered_unique_text(
                "MemoryQueryFilters.relation_predicates",
                self.relation_predicates,
                max_length=_MAX_PREDICATE_CHARS,
                max_items=_MAX_RELATIONS,
            ),
        )
        object.__setattr__(
            self,
            "context_tags",
            _require_ordered_unique_text(
                "MemoryQueryFilters.context_tags",
                self.context_tags,
                max_length=_MAX_CONTEXT_TAG_CHARS,
                max_items=_MAX_CONTEXT_TAGS,
            ),
        )
        if self.min_confidence is not None:
            object.__setattr__(
                self,
                "min_confidence",
                _unit_interval(
                    "MemoryQueryFilters.min_confidence",
                    self.min_confidence,
                ),
            )
        if self.min_salience is not None:
            object.__setattr__(
                self,
                "min_salience",
                _unit_interval("MemoryQueryFilters.min_salience", self.min_salience),
            )
        if type(self.require_active) is not bool:
            raise TypeError("MemoryQueryFilters.require_active: invalid_type")

    def __repr__(self) -> str:
        return (
            f"MemoryQueryFilters(require_active={self.require_active}, "
            f"concept_count={len(self.concepts)}, "
            f"entity_count={len(self.entity_ids)}, "
            f"predicate_count={len(self.relation_predicates)})"
        )


def _require_ordered_unique_text(
    name: str,
    values: Sequence[object],
    *,
    max_length: int,
    max_items: int,
) -> tuple[str, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name}: not_ordered_sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name}: not_ordered_sequence")
    items = tuple(values)
    if len(items) > max_items:
        raise ValueError(f"{name}: exceeds_max_length")
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = require_bounded_text(name, item, max_length=max_length)
        if text in seen:
            raise ValueError(f"{name}: duplicate")
        seen.add(text)
        out.append(text)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class MemoryQueryContext:
    """Owner-safe current-context and social ranking signals.

    These are query inputs, not imports of world authority or the ``social``
    package. They never grant cross-agent memory access.
    """

    location_id: EntityId | None = None
    tags: tuple[str, ...] = ()
    related_entity_ids: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        if self.location_id is not None and type(self.location_id) is not EntityId:
            raise TypeError("MemoryQueryContext.location_id: invalid_type")
        object.__setattr__(
            self,
            "tags",
            _require_ordered_unique_text(
                "MemoryQueryContext.tags",
                self.tags,
                max_length=_MAX_CONTEXT_TAG_CHARS,
                max_items=_MAX_CONTEXT_TAGS,
            ),
        )
        object.__setattr__(
            self,
            "related_entity_ids",
            require_ordered_unique(
                "MemoryQueryContext.related_entity_ids",
                self.related_entity_ids,
                item_type=EntityId,
            ),
        )
        if len(self.related_entity_ids) > _MAX_MENTIONS:
            raise ValueError(
                "MemoryQueryContext.related_entity_ids: exceeds_max_length"
            )

    def __repr__(self) -> str:
        return (
            f"MemoryQueryContext(has_location={self.location_id is not None}, "
            f"tag_count={len(self.tags)}, "
            f"related_count={len(self.related_entity_ids)})"
        )


@dataclass(frozen=True, slots=True)
class MemoryRetrieveRequest:
    """Scoped retrieve input; scope itself is bound on the service instance."""

    current_tick: int
    limit: int
    scoring_policy: MemoryScoringPolicy
    filters: MemoryQueryFilters = MemoryQueryFilters()
    context: MemoryQueryContext = MemoryQueryContext()
    query_embedding: MemoryEmbedding | None = None
    operation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "current_tick",
            require_exact_nonneg_int(
                "MemoryRetrieveRequest.current_tick", self.current_tick
            ),
        )
        limit = require_exact_nonneg_int("MemoryRetrieveRequest.limit", self.limit)
        if limit < 1 or limit > _MAX_QUERY_LIMIT:
            raise ValueError("MemoryRetrieveRequest.limit: out_of_range")
        object.__setattr__(self, "limit", limit)
        if type(self.scoring_policy) is not MemoryScoringPolicy:
            raise TypeError("MemoryRetrieveRequest.scoring_policy: invalid_type")
        if type(self.filters) is not MemoryQueryFilters:
            raise TypeError("MemoryRetrieveRequest.filters: invalid_type")
        if type(self.context) is not MemoryQueryContext:
            raise TypeError("MemoryRetrieveRequest.context: invalid_type")
        if self.query_embedding is not None:
            if type(self.query_embedding) is not MemoryEmbedding:
                raise TypeError("MemoryRetrieveRequest.query_embedding: invalid_type")
            expected = self.scoring_policy.embedding_dimension
            if expected is None:
                raise ValueError(
                    "MemoryRetrieveRequest.query_embedding: semantic_disabled"
                )
            if self.query_embedding.dimension != expected:
                raise ValueError(
                    "MemoryRetrieveRequest.query_embedding: dimension_mismatch"
                )
        elif self.scoring_policy.weights.semantic_relevance > 0.0:
            raise ValueError(
                "MemoryRetrieveRequest.query_embedding: required_for_semantic"
            )
        if self.operation_id is not None:
            object.__setattr__(
                self,
                "operation_id",
                require_bounded_text(
                    "MemoryRetrieveRequest.operation_id",
                    self.operation_id,
                    max_length=_MAX_OPERATION_ID_CHARS,
                ),
            )

    def __repr__(self) -> str:
        return (
            f"MemoryRetrieveRequest(current_tick={self.current_tick}, "
            f"limit={self.limit}, "
            f"policy_version={self.scoring_policy.version!r}, "
            f"semantic={self.query_embedding is not None})"
        )


@dataclass(frozen=True, slots=True)
class MemoryAccessReceipt:
    """Idempotent pending access update produced by observational retrieve."""

    memory_id: MemoryId
    access_tick: int
    operation_id: str

    def __post_init__(self) -> None:
        if type(self.memory_id) is not MemoryId:
            raise TypeError("MemoryAccessReceipt.memory_id: invalid_type")
        object.__setattr__(
            self,
            "access_tick",
            require_exact_nonneg_int(
                "MemoryAccessReceipt.access_tick", self.access_tick
            ),
        )
        object.__setattr__(
            self,
            "operation_id",
            require_bounded_text(
                "MemoryAccessReceipt.operation_id",
                self.operation_id,
                max_length=_MAX_OPERATION_ID_CHARS,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryAccessReceipt(memory_id={self.memory_id.value!r}, "
            f"access_tick={self.access_tick})"
        )


@dataclass(frozen=True, slots=True)
class MemoryRankedHit:
    """One ranked retrieved snapshot with score metadata for later policies."""

    rank: int
    trace: MemoryTrace
    score: float
    breakdown: MemoryScoreBreakdown
    matched_concept_mention_ids: tuple[MentionId, ...]
    matched_entity_mention_ids: tuple[MentionId, ...]
    scoring_policy_id: str
    scoring_policy_version: str
    retrieval_tick: int

    def __post_init__(self) -> None:
        rank = require_exact_nonneg_int("MemoryRankedHit.rank", self.rank)
        if rank < 1:
            raise ValueError("MemoryRankedHit.rank: must_be_positive")
        object.__setattr__(self, "rank", rank)
        if type(self.trace) is not MemoryTrace:
            raise TypeError("MemoryRankedHit.trace: invalid_type")
        object.__setattr__(
            self, "score", _unit_interval("MemoryRankedHit.score", self.score)
        )
        if type(self.breakdown) is not MemoryScoreBreakdown:
            raise TypeError("MemoryRankedHit.breakdown: invalid_type")
        object.__setattr__(
            self,
            "matched_concept_mention_ids",
            require_ordered_unique(
                "MemoryRankedHit.matched_concept_mention_ids",
                self.matched_concept_mention_ids,
                item_type=MentionId,
            ),
        )
        object.__setattr__(
            self,
            "matched_entity_mention_ids",
            require_ordered_unique(
                "MemoryRankedHit.matched_entity_mention_ids",
                self.matched_entity_mention_ids,
                item_type=MentionId,
            ),
        )
        object.__setattr__(
            self,
            "scoring_policy_id",
            require_bounded_text(
                "MemoryRankedHit.scoring_policy_id",
                self.scoring_policy_id,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "scoring_policy_version",
            require_bounded_text(
                "MemoryRankedHit.scoring_policy_version",
                self.scoring_policy_version,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "retrieval_tick",
            require_exact_nonneg_int(
                "MemoryRankedHit.retrieval_tick", self.retrieval_tick
            ),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryRankedHit(rank={self.rank}, "
            f"memory_id={self.trace.memory_id.value!r}, "
            f"score={self.score}, "
            f"policy_version={self.scoring_policy_version!r})"
        )


@dataclass(frozen=True, slots=True)
class MemoryRetrieveResult:
    """Observational retrieve output: ranked hits plus pending access receipts."""

    hits: tuple[MemoryRankedHit, ...]
    pending_accesses: tuple[MemoryAccessReceipt, ...]
    candidate_count: int
    retrieval_tick: int
    scoring_policy_version: str

    def __post_init__(self) -> None:
        hits = _require_ordered_models(
            "MemoryRetrieveResult.hits",
            self.hits,
            model_type=MemoryRankedHit,
            max_items=_MAX_QUERY_LIMIT,
        )
        object.__setattr__(self, "hits", hits)
        for index, hit in enumerate(hits, start=1):
            if hit.rank != index:
                raise ValueError("MemoryRetrieveResult.hits: rank_not_dense")
        accesses = _require_ordered_models(
            "MemoryRetrieveResult.pending_accesses",
            self.pending_accesses,
            model_type=MemoryAccessReceipt,
            max_items=_MAX_QUERY_LIMIT,
        )
        object.__setattr__(self, "pending_accesses", accesses)
        object.__setattr__(
            self,
            "candidate_count",
            require_exact_nonneg_int(
                "MemoryRetrieveResult.candidate_count", self.candidate_count
            ),
        )
        object.__setattr__(
            self,
            "retrieval_tick",
            require_exact_nonneg_int(
                "MemoryRetrieveResult.retrieval_tick", self.retrieval_tick
            ),
        )
        object.__setattr__(
            self,
            "scoring_policy_version",
            require_bounded_text(
                "MemoryRetrieveResult.scoring_policy_version",
                self.scoring_policy_version,
                max_length=_MAX_POLICY_ID_CHARS,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryRetrieveResult(hit_count={len(self.hits)}, "
            f"pending_access_count={len(self.pending_accesses)}, "
            f"candidate_count={self.candidate_count}, "
            f"retrieval_tick={self.retrieval_tick})"
        )


@dataclass(frozen=True, slots=True)
class MemoryMutationBatch:
    """Atomic batch of create and access updates applied after cognition."""

    writes: tuple[MemoryTrace, ...] = ()
    accesses: tuple[MemoryAccessReceipt, ...] = ()
    operation_id: str | None = None

    def __post_init__(self) -> None:
        writes = _require_ordered_models(
            "MemoryMutationBatch.writes",
            self.writes,
            model_type=MemoryTrace,
            max_items=_MAX_BATCH_ITEMS,
        )
        object.__setattr__(self, "writes", writes)
        write_ids = [item.memory_id.value for item in writes]
        if len(set(write_ids)) != len(write_ids):
            raise ValueError("MemoryMutationBatch.writes: duplicate_memory_id")
        accesses = _require_ordered_models(
            "MemoryMutationBatch.accesses",
            self.accesses,
            model_type=MemoryAccessReceipt,
            max_items=_MAX_BATCH_ITEMS,
        )
        object.__setattr__(self, "accesses", accesses)
        if self.operation_id is not None:
            object.__setattr__(
                self,
                "operation_id",
                require_bounded_text(
                    "MemoryMutationBatch.operation_id",
                    self.operation_id,
                    max_length=_MAX_OPERATION_ID_CHARS,
                ),
            )

    def __repr__(self) -> str:
        return (
            f"MemoryMutationBatch(write_count={len(self.writes)}, "
            f"access_count={len(self.accesses)})"
        )


@dataclass(frozen=True, slots=True)
class MemoryApplyResult:
    """Outcome of an atomic apply batch (metadata only for diagnostics)."""

    written_count: int
    access_applied_count: int
    access_idempotent_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "written_count",
            require_exact_nonneg_int(
                "MemoryApplyResult.written_count", self.written_count
            ),
        )
        object.__setattr__(
            self,
            "access_applied_count",
            require_exact_nonneg_int(
                "MemoryApplyResult.access_applied_count", self.access_applied_count
            ),
        )
        object.__setattr__(
            self,
            "access_idempotent_count",
            require_exact_nonneg_int(
                "MemoryApplyResult.access_idempotent_count",
                self.access_idempotent_count,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryApplyResult(written_count={self.written_count}, "
            f"access_applied_count={self.access_applied_count}, "
            f"access_idempotent_count={self.access_idempotent_count})"
        )


@dataclass(frozen=True, slots=True)
class MemoryForgetRequest:
    """Owner-scoped soft-forget maintenance at an explicit logical tick."""

    current_tick: int
    retention_policy: MemoryRetentionPolicy
    operation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "current_tick",
            require_exact_nonneg_int(
                "MemoryForgetRequest.current_tick", self.current_tick
            ),
        )
        if type(self.retention_policy) is not MemoryRetentionPolicy:
            raise TypeError("MemoryForgetRequest.retention_policy: invalid_type")
        if self.operation_id is not None:
            object.__setattr__(
                self,
                "operation_id",
                require_bounded_text(
                    "MemoryForgetRequest.operation_id",
                    self.operation_id,
                    max_length=_MAX_OPERATION_ID_CHARS,
                ),
            )

    def __repr__(self) -> str:
        return (
            f"MemoryForgetRequest(current_tick={self.current_tick}, "
            f"policy_version={self.retention_policy.version!r})"
        )


@dataclass(frozen=True, slots=True)
class MemoryForgetResult:
    """Soft-forget maintenance counts (no hard deletes)."""

    forgotten_count: int
    examined_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "forgotten_count",
            require_exact_nonneg_int(
                "MemoryForgetResult.forgotten_count", self.forgotten_count
            ),
        )
        object.__setattr__(
            self,
            "examined_count",
            require_exact_nonneg_int(
                "MemoryForgetResult.examined_count", self.examined_count
            ),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryForgetResult(forgotten_count={self.forgotten_count}, "
            f"examined_count={self.examined_count})"
        )


_SAFE_DIAGNOSTIC_KEYS: Final[frozenset[str]] = frozenset(
    {
        "operation",
        "run_id",
        "owner_id",
        "tick",
        "policy_id",
        "policy_version",
        "enabled_components",
        "candidate_count",
        "result_count",
        "write_count",
        "access_count",
        "forgotten_count",
        "examined_count",
        "duration_ms",
        "reason_code",
        "status",
    }
)


def diagnostic_projection(metadata: Mapping[str, object]) -> dict[str, object]:
    """Return a metadata-only diagnostic dict; reject unknown or payload keys."""
    if not isinstance(metadata, Mapping):
        raise TypeError("diagnostic_projection: invalid_type")
    out: dict[str, object] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or key not in _SAFE_DIAGNOSTIC_KEYS:
            raise ValueError("diagnostic_projection: disallowed_key")
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("diagnostic_projection: non_finite")
            out[key] = value
            continue
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            items = tuple(value)
            for item in items:
                if not isinstance(item, str):
                    raise ValueError("diagnostic_projection: invalid_sequence_item")
            out[key] = list(items)
            continue
        raise ValueError("diagnostic_projection: invalid_value_type")
    return out
