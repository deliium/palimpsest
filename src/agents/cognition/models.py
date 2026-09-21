"""Immutable cognitive stage artifacts and scientific boundary records.

These values capture inspectable claims and choices for analysis. They do not
store hidden rationale, chain-of-thought, prompts, raw provider responses,
credentials, or endpoints. Pydantic/`LLMResult` validation is never treated as
command or world authority here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId, GoalId
from memory.beliefs import (
    BeliefActivationState,
    BeliefValueKind,
    ClaimSubjectKind,
    SemanticBelief,
    SemanticClaim,
    canonical_claim_identity,
)
from memory.models import (
    Belief,
    BeliefId,
    MemoryAccessReceipt,
    MemoryId,
    MemoryRankedHit,
    MemoryTrace,
    ReconsolidationIntent,
    ReconstructedMemory,
)
from world.actions import AgentCommand, require_agent_command
from world.identifiers import (
    EntityId,
    WorldRevision,
    require_bounded_text,
    require_exact_nonneg_int,
    require_ordered_unique,
    require_stable_id,
)
from world.models import LifeStatus
from world.observations import Observation

__all__ = [
    "BOUNDARY_SCHEMA_VERSION",
    "DEFAULT_SELF_MODEL_POLICY",
    "ActionPlan",
    "CognitionFailureReason",
    "CognitiveLoopInput",
    "CognitiveLoopResult",
    "ComponentBoundaryRecord",
    "ComponentKind",
    "ComponentStatus",
    "DecisionMetadata",
    "ImaginedFuture",
    "IntentionCode",
    "InternalAgentState",
    "InterpretedPerception",
    "MemoryUpdateIntent",
    "MemoryUpdateKind",
    "MotivationCode",
    "MotivationEvaluation",
    "MotivationScore",
    "PerceptionClaimCode",
    "PossibleFutures",
    "RetrievedMemoryContext",
    "SelectedIntention",
    "SelfBeliefState",
    "SelfModel",
    "SelfModelProjectionPolicy",
    "SelfRelevantBelief",
    "SituationClaimCode",
    "SituationModel",
    "SubjectiveSnapshot",
    "diagnostic_projection",
    "project_legacy_self_belief_state",
    "project_self_model",
    "require_confidence",
]

BOUNDARY_SCHEMA_VERSION: Final[int] = 1

_MAX_COMPONENT_VERSION_CHARS: Final[int] = 64
_MAX_SELECTION_CODES: Final[int] = 64
_MAX_FUTURES: Final[int] = 32
_MAX_MOTIVES: Final[int] = 32
_MAX_MEMORY_REFS: Final[int] = 256
_MAX_CLAIM_CODES: Final[int] = 64


class ComponentKind(StrEnum):
    """Closed set of cognitive pipeline component identities."""

    PERCEPTION = "perception"
    MEMORY_RETRIEVAL = "memory_retrieval"
    SITUATION = "situation"
    SELF_STATE = "self_state"
    FUTURES = "futures"
    MOTIVATION = "motivation"
    INTENTION = "intention"
    PLANNING = "planning"
    MEMORY_UPDATE = "memory_update"


class ComponentStatus(StrEnum):
    """Closed component completion statuses."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CognitionFailureReason(StrEnum):
    """Stable failure codes suitable for WARN/ERROR logs."""

    INVALID_INPUT = "invalid_input"
    INVALID_OUTPUT = "invalid_output"
    TYPE_MISMATCH = "type_mismatch"
    OWNERSHIP = "ownership"
    COMPONENT_FAILED = "component_failed"
    CANCELLED = "cancelled"
    COMMAND_REJECTED = "command_rejected"


class PerceptionClaimCode(StrEnum):
    """Closed perception interpretation claims (not free-form narrative)."""

    SELF_PRESENT = "self_present"
    SELF_ALIVE = "self_alive"
    SELF_DEAD = "self_dead"
    HAS_LOCATION = "has_location"
    HAS_EXITS = "has_exits"
    HAS_VISIBLE_BODIES = "has_visible_bodies"
    HAS_ITEMS = "has_items"
    HAS_RESOURCES = "has_resources"
    HAS_OCCURRENCES = "has_occurrences"
    HAS_COMMUNICATIONS = "has_communications"


class SituationClaimCode(StrEnum):
    """Closed situation-model claim codes."""

    IDLE = "idle"
    LOCAL_SCENE = "local_scene"
    SOCIAL_SIGNAL = "social_signal"
    RESOURCE_PRESENT = "resource_present"
    THREAT_SIGNAL = "threat_signal"
    TERMINAL_SELF = "terminal_self"


class MotivationCode(StrEnum):
    """Closed motivation labels for V1 scoring."""

    SURVIVE = "survive"
    REST = "rest"
    EXPLORE = "explore"
    SOCIALIZE = "socialize"
    WAIT = "wait"


class IntentionCode(StrEnum):
    """Closed intention labels selected from motivations."""

    WAIT = "wait"
    MOVE = "move"
    SEARCH = "search"
    REST = "rest"
    COMMUNICATE = "communicate"
    SURVIVE = "survive"


class MemoryUpdateKind(StrEnum):
    """Closed subjective update intent kinds (memory, belief, relationship)."""

    WRITE_MEMORY = "write_memory"
    WRITE_BELIEF = "write_belief"
    REVISE_SEMANTIC_BELIEF = "revise_semantic_belief"
    REVISE_RELATIONSHIP = "revise_relationship"


def require_confidence(name: str, value: object) -> float:
    """Accept a finite confidence in ``[0.0, 1.0]``; reject booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite float in [0.0, 1.0]")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be a finite float in [0.0, 1.0]")
    return 0.0 if number == 0.0 else number


def _require_component_version(value: object) -> str:
    text = require_bounded_text(
        "component_version", value, max_length=_MAX_COMPONENT_VERSION_CHARS
    )
    if "/" in text or "\\" in text or ".." in text:
        raise ValueError("component_version must be a single safe path segment")
    return text


def _require_ordered_enum[E: StrEnum](
    name: str, values: Sequence[object], *, enum_type: type[E]
) -> tuple[E, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    items = tuple(values)
    if len(items) > _MAX_CLAIM_CODES:
        raise ValueError(f"{name} exceeds maximum length {_MAX_CLAIM_CODES}")
    seen: set[E] = set()
    out: list[E] = []
    for item in items:
        if type(item) is not enum_type:
            raise TypeError(f"{name} entries must be {enum_type.__name__}")
        if item in seen:
            raise ValueError(f"{name} must not contain duplicates")
        seen.add(item)
        out.append(item)
    return tuple(out)


def _require_count_map(name: str, value: Mapping[str, object]) -> Mapping[str, int]:
    if type(value) is not dict and not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    out: dict[str, int] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{name} keys must be str")
        require_stable_id(f"{name}.key", key)
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError(f"{name}[{key!r}] must be a non-negative int")
        if raw < 0:
            raise ValueError(f"{name}[{key!r}] must be a non-negative int")
        out[key] = raw
    return dict(out)


@dataclass(frozen=True, slots=True)
class DecisionMetadata:
    """Inspectable choice codes and counts — not chain-of-thought."""

    selection_codes: tuple[str, ...] = ()
    candidate_count: int = 0
    tie_break_applied: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.selection_codes, (set, frozenset, Mapping)):
            raise TypeError("DecisionMetadata.selection_codes must be ordered")
        if isinstance(self.selection_codes, (str, bytes)) or not isinstance(
            self.selection_codes, Sequence
        ):
            raise TypeError("DecisionMetadata.selection_codes must be ordered")
        codes = tuple(self.selection_codes)
        if len(codes) > _MAX_SELECTION_CODES:
            raise ValueError("DecisionMetadata.selection_codes exceeds maximum length")
        normalized: list[str] = []
        seen: set[str] = set()
        for code in codes:
            text = require_stable_id("DecisionMetadata.selection_codes", code)
            if text in seen:
                raise ValueError("DecisionMetadata.selection_codes must be unique")
            seen.add(text)
            normalized.append(text)
        object.__setattr__(self, "selection_codes", tuple(normalized))
        object.__setattr__(
            self,
            "candidate_count",
            require_exact_nonneg_int(
                "DecisionMetadata.candidate_count", self.candidate_count
            ),
        )
        if type(self.tie_break_applied) is not bool:
            raise TypeError("DecisionMetadata.tie_break_applied must be bool")

    def __repr__(self) -> str:
        return (
            f"DecisionMetadata(selection_code_count={len(self.selection_codes)}, "
            f"candidate_count={self.candidate_count}, "
            f"tie_break_applied={self.tie_break_applied})"
        )


@dataclass(frozen=True, slots=True)
class InternalAgentState:
    """Immutable per-invocation snapshot of agent-owned internal state."""

    owner_id: AgentId
    invocation_count: int = 0
    last_intention: IntentionCode | None = None
    last_command_kind: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("InternalAgentState.owner_id must be AgentId")
        object.__setattr__(
            self,
            "invocation_count",
            require_exact_nonneg_int(
                "InternalAgentState.invocation_count", self.invocation_count
            ),
        )
        if (
            self.last_intention is not None
            and type(self.last_intention) is not IntentionCode
        ):
            raise TypeError(
                "InternalAgentState.last_intention must be IntentionCode or None"
            )
        if self.last_command_kind is not None:
            object.__setattr__(
                self,
                "last_command_kind",
                require_stable_id(
                    "InternalAgentState.last_command_kind", self.last_command_kind
                ),
            )

    def __repr__(self) -> str:
        return (
            f"InternalAgentState(owner_id={self.owner_id.value!r}, "
            f"invocation_count={self.invocation_count})"
        )


@dataclass(frozen=True, slots=True)
class SubjectiveSnapshot:
    """One frozen owner-scoped subjective view for a cognition invocation."""

    owner_id: AgentId
    revision: int
    memories: tuple[MemoryTrace, ...]
    legacy_beliefs: tuple[Belief, ...]
    semantic_beliefs: tuple[SemanticBelief, ...]
    relationships: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("SubjectiveSnapshot.owner_id must be AgentId")
        object.__setattr__(
            self,
            "revision",
            require_exact_nonneg_int("SubjectiveSnapshot.revision", self.revision),
        )
        if isinstance(self.memories, (set, frozenset, Mapping)):
            raise TypeError("SubjectiveSnapshot.memories must be ordered")
        if isinstance(self.memories, (str, bytes)) or not isinstance(
            self.memories, Sequence
        ):
            raise TypeError("SubjectiveSnapshot.memories must be ordered")
        memories = tuple(self.memories)
        seen_memory: set[str] = set()
        for memory in memories:
            if type(memory) is not MemoryTrace:
                raise TypeError(
                    "SubjectiveSnapshot.memories entries must be MemoryTrace"
                )
            if memory.owner_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.memories: ownership")
            if memory.memory_id.value in seen_memory:
                raise ValueError("SubjectiveSnapshot.memories: duplicate")
            seen_memory.add(memory.memory_id.value)
        object.__setattr__(self, "memories", memories)
        if isinstance(self.legacy_beliefs, (set, frozenset, Mapping)):
            raise TypeError("SubjectiveSnapshot.legacy_beliefs must be ordered")
        if isinstance(self.legacy_beliefs, (str, bytes)) or not isinstance(
            self.legacy_beliefs, Sequence
        ):
            raise TypeError("SubjectiveSnapshot.legacy_beliefs must be ordered")
        legacy = tuple(self.legacy_beliefs)
        seen_legacy: set[str] = set()
        for legacy_belief in legacy:
            if type(legacy_belief) is not Belief:
                raise TypeError(
                    "SubjectiveSnapshot.legacy_beliefs entries must be Belief"
                )
            if legacy_belief.owner_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.legacy_beliefs: ownership")
            if legacy_belief.belief_id.value in seen_legacy:
                raise ValueError("SubjectiveSnapshot.legacy_beliefs: duplicate")
            seen_legacy.add(legacy_belief.belief_id.value)
        object.__setattr__(self, "legacy_beliefs", legacy)
        if isinstance(self.semantic_beliefs, (set, frozenset, Mapping)):
            raise TypeError("SubjectiveSnapshot.semantic_beliefs must be ordered")
        if isinstance(self.semantic_beliefs, (str, bytes)) or not isinstance(
            self.semantic_beliefs, Sequence
        ):
            raise TypeError("SubjectiveSnapshot.semantic_beliefs must be ordered")
        semantic = tuple(self.semantic_beliefs)
        for semantic_belief in semantic:
            if type(semantic_belief) is not SemanticBelief:
                raise TypeError(
                    "SubjectiveSnapshot.semantic_beliefs entries must be SemanticBelief"
                )
            if semantic_belief.owner_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.semantic_beliefs: ownership")
        object.__setattr__(self, "semantic_beliefs", semantic)
        if isinstance(self.relationships, (set, frozenset, Mapping)):
            raise TypeError("SubjectiveSnapshot.relationships must be ordered")
        if isinstance(self.relationships, (str, bytes)) or not isinstance(
            self.relationships, Sequence
        ):
            raise TypeError("SubjectiveSnapshot.relationships must be ordered")
        relationships = tuple(self.relationships)
        from social.relationships import DirectedRelationshipProfile

        for profile in relationships:
            if type(profile) is not DirectedRelationshipProfile:
                raise TypeError(
                    "SubjectiveSnapshot.relationships entries must be "
                    "DirectedRelationshipProfile"
                )
            if profile.source_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.relationships: ownership")
        object.__setattr__(self, "relationships", relationships)

    def __repr__(self) -> str:
        return (
            f"SubjectiveSnapshot(owner_id={self.owner_id.value!r}, "
            f"revision={self.revision}, "
            f"memory_count={len(self.memories)}, "
            f"legacy_belief_count={len(self.legacy_beliefs)}, "
            f"semantic_belief_count={len(self.semantic_beliefs)}, "
            f"relationship_count={len(self.relationships)})"
        )


@dataclass(frozen=True, slots=True)
class CognitiveLoopInput:
    """Sole loop input: one owned observation plus immutable internal state.

    Must not embed ``WorldState``, ``ObservationBatch``, ``TickToken``,
    ``ActionSubmission``, repositories, or mutation writers.
    """

    agent_id: AgentId
    observation: Observation
    internal_state: InternalAgentState
    snapshot: SubjectiveSnapshot | None = None

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("CognitiveLoopInput.agent_id must be AgentId")
        if type(self.observation) is not Observation:
            raise TypeError("CognitiveLoopInput.observation must be Observation")
        if type(self.internal_state) is not InternalAgentState:
            raise TypeError(
                "CognitiveLoopInput.internal_state must be InternalAgentState"
            )
        if self.internal_state.owner_id != self.agent_id:
            raise ValueError("InternalAgentState.owner_id must match agent_id")
        if self.snapshot is not None:
            if type(self.snapshot) is not SubjectiveSnapshot:
                raise TypeError(
                    "CognitiveLoopInput.snapshot must be SubjectiveSnapshot"
                )
            if self.snapshot.owner_id != self.agent_id:
                raise ValueError("SubjectiveSnapshot.owner_id must match agent_id")

    def __repr__(self) -> str:
        snap_rev = None if self.snapshot is None else self.snapshot.revision
        return (
            f"CognitiveLoopInput(agent_id={self.agent_id.value!r}, "
            f"tick={self.observation.tick}, "
            f"revision={self.observation.revision.value}, "
            f"snapshot_revision={snap_rev})"
        )


@dataclass(frozen=True, slots=True)
class InterpretedPerception:
    """Structured perception claims derived from one observation."""

    owner_id: AgentId
    observer_id: EntityId
    tick: int
    revision: WorldRevision
    life_status: LifeStatus | None
    location_id: EntityId | None
    claim_codes: tuple[PerceptionClaimCode, ...]
    counts: Mapping[str, int]
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("InterpretedPerception.owner_id must be AgentId")
        if type(self.observer_id) is not EntityId:
            raise TypeError("InterpretedPerception.observer_id must be EntityId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("InterpretedPerception.tick", self.tick),
        )
        if type(self.revision) is not WorldRevision:
            raise TypeError("InterpretedPerception.revision must be WorldRevision")
        if self.life_status is not None and type(self.life_status) is not LifeStatus:
            raise TypeError(
                "InterpretedPerception.life_status must be LifeStatus or None"
            )
        if self.location_id is not None and type(self.location_id) is not EntityId:
            raise TypeError(
                "InterpretedPerception.location_id must be EntityId or None"
            )
        object.__setattr__(
            self,
            "claim_codes",
            _require_ordered_enum(
                "InterpretedPerception.claim_codes",
                self.claim_codes,
                enum_type=PerceptionClaimCode,
            ),
        )
        object.__setattr__(
            self,
            "counts",
            _require_count_map("InterpretedPerception.counts", self.counts),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("InterpretedPerception.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError(
                "InterpretedPerception.decision_metadata must be DecisionMetadata"
            )

    def __repr__(self) -> str:
        return (
            f"InterpretedPerception(owner_id={self.owner_id.value!r}, "
            f"tick={self.tick}, claim_count={len(self.claim_codes)}, "
            f"confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class RetrievedMemoryContext:
    """Owner-scoped reconstructive recall with scientific source metadata.

    ``reconstructions`` are the remembered episodes for downstream cognition.
    Ranked hits and pending access receipts remain scientific evidence only and
    must never be treated as the remembered episode itself. Operational logs
    must never serialize reconstruction or hit payloads.
    """

    owner_id: AgentId
    memory_ids: tuple[MemoryId, ...]
    belief_ids: tuple[BeliefId, ...]
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()
    ranked_hits: tuple[MemoryRankedHit, ...] = ()
    pending_accesses: tuple[MemoryAccessReceipt, ...] = ()
    candidate_count: int = 0
    retrieval_tick: int | None = None
    scoring_policy_version: str | None = None
    reconstructions: tuple[ReconstructedMemory, ...] = ()
    reconsolidation: ReconsolidationIntent | None = None
    reconstruction_policy_version: str | None = None
    semantic_beliefs: tuple[SemanticBelief, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("RetrievedMemoryContext.owner_id must be AgentId")
        memories = require_ordered_unique(
            "RetrievedMemoryContext.memory_ids",
            self.memory_ids,
            item_type=MemoryId,
        )
        if len(memories) > _MAX_MEMORY_REFS:
            raise ValueError("RetrievedMemoryContext.memory_ids exceeds maximum length")
        object.__setattr__(self, "memory_ids", memories)
        beliefs = require_ordered_unique(
            "RetrievedMemoryContext.belief_ids",
            self.belief_ids,
            item_type=BeliefId,
        )
        if len(beliefs) > _MAX_MEMORY_REFS:
            raise ValueError("RetrievedMemoryContext.belief_ids exceeds maximum length")
        object.__setattr__(self, "belief_ids", beliefs)
        object.__setattr__(
            self,
            "confidence",
            require_confidence("RetrievedMemoryContext.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError(
                "RetrievedMemoryContext.decision_metadata must be DecisionMetadata"
            )
        if isinstance(self.ranked_hits, (set, frozenset, Mapping)):
            raise TypeError("RetrievedMemoryContext.ranked_hits must be ordered")
        if isinstance(self.ranked_hits, (str, bytes)) or not isinstance(
            self.ranked_hits, Sequence
        ):
            raise TypeError("RetrievedMemoryContext.ranked_hits must be ordered")
        hits = tuple(self.ranked_hits)
        if len(hits) > _MAX_MEMORY_REFS:
            raise ValueError(
                "RetrievedMemoryContext.ranked_hits exceeds maximum length"
            )
        hit_ids: list[MemoryId] = []
        for hit in hits:
            if type(hit) is not MemoryRankedHit:
                raise TypeError(
                    "RetrievedMemoryContext.ranked_hits entries must be MemoryRankedHit"
                )
            if hit.trace.owner_id != self.owner_id:
                raise ValueError("RetrievedMemoryContext ranked hit owner mismatch")
            hit_ids.append(hit.trace.memory_id)
        object.__setattr__(self, "ranked_hits", hits)
        if memories and hit_ids and tuple(hit_ids) != memories:
            # When both are populated they must agree in order.
            raise ValueError("RetrievedMemoryContext memory_ids/ranked_hits mismatch")
        if isinstance(self.pending_accesses, (set, frozenset, Mapping)):
            raise TypeError("RetrievedMemoryContext.pending_accesses must be ordered")
        if isinstance(self.pending_accesses, (str, bytes)) or not isinstance(
            self.pending_accesses, Sequence
        ):
            raise TypeError("RetrievedMemoryContext.pending_accesses must be ordered")
        accesses = tuple(self.pending_accesses)
        if len(accesses) > _MAX_MEMORY_REFS:
            raise ValueError(
                "RetrievedMemoryContext.pending_accesses exceeds maximum length"
            )
        for receipt in accesses:
            if type(receipt) is not MemoryAccessReceipt:
                raise TypeError(
                    "RetrievedMemoryContext.pending_accesses entries must be "
                    "MemoryAccessReceipt"
                )
        object.__setattr__(self, "pending_accesses", accesses)
        object.__setattr__(
            self,
            "candidate_count",
            require_exact_nonneg_int(
                "RetrievedMemoryContext.candidate_count", self.candidate_count
            ),
        )
        if self.retrieval_tick is not None:
            object.__setattr__(
                self,
                "retrieval_tick",
                require_exact_nonneg_int(
                    "RetrievedMemoryContext.retrieval_tick", self.retrieval_tick
                ),
            )
        if self.scoring_policy_version is not None:
            object.__setattr__(
                self,
                "scoring_policy_version",
                require_bounded_text(
                    "RetrievedMemoryContext.scoring_policy_version",
                    self.scoring_policy_version,
                    max_length=_MAX_COMPONENT_VERSION_CHARS,
                ),
            )
        if isinstance(self.reconstructions, (set, frozenset, Mapping)):
            raise TypeError("RetrievedMemoryContext.reconstructions must be ordered")
        if isinstance(self.reconstructions, (str, bytes)) or not isinstance(
            self.reconstructions, Sequence
        ):
            raise TypeError("RetrievedMemoryContext.reconstructions must be ordered")
        reconstructions = tuple(self.reconstructions)
        if len(reconstructions) > _MAX_MEMORY_REFS:
            raise ValueError(
                "RetrievedMemoryContext.reconstructions exceeds maximum length"
            )
        for item in reconstructions:
            if type(item) is not ReconstructedMemory:
                raise TypeError(
                    "RetrievedMemoryContext.reconstructions entries must be "
                    "ReconstructedMemory"
                )
            if item.owner_id != self.owner_id:
                raise ValueError("RetrievedMemoryContext reconstruction owner mismatch")
        object.__setattr__(self, "reconstructions", reconstructions)
        if self.reconsolidation is not None:
            if type(self.reconsolidation) is not ReconsolidationIntent:
                raise TypeError(
                    "RetrievedMemoryContext.reconsolidation must be "
                    "ReconsolidationIntent"
                )
            if self.reconsolidation.record.owner_id != self.owner_id:
                raise ValueError(
                    "RetrievedMemoryContext reconsolidation owner mismatch"
                )
        if self.reconstruction_policy_version is not None:
            object.__setattr__(
                self,
                "reconstruction_policy_version",
                require_bounded_text(
                    "RetrievedMemoryContext.reconstruction_policy_version",
                    self.reconstruction_policy_version,
                    max_length=_MAX_COMPONENT_VERSION_CHARS,
                ),
            )
        if isinstance(self.semantic_beliefs, (set, frozenset, Mapping)):
            raise TypeError("RetrievedMemoryContext.semantic_beliefs must be ordered")
        if isinstance(self.semantic_beliefs, (str, bytes)) or not isinstance(
            self.semantic_beliefs, Sequence
        ):
            raise TypeError("RetrievedMemoryContext.semantic_beliefs must be ordered")
        semantic = tuple(self.semantic_beliefs)
        if len(semantic) > _MAX_MEMORY_REFS:
            raise ValueError(
                "RetrievedMemoryContext.semantic_beliefs exceeds maximum length"
            )
        seen_belief_ids: set[str] = set()
        for belief_item in semantic:
            if type(belief_item) is not SemanticBelief:
                raise TypeError(
                    "RetrievedMemoryContext.semantic_beliefs entries must be "
                    "SemanticBelief"
                )
            if belief_item.owner_id != self.owner_id:
                raise ValueError(
                    "RetrievedMemoryContext semantic belief owner mismatch"
                )
            if belief_item.belief_id.value in seen_belief_ids:
                raise ValueError(
                    "RetrievedMemoryContext.semantic_beliefs: duplicate_belief_id"
                )
            seen_belief_ids.add(belief_item.belief_id.value)
        object.__setattr__(self, "semantic_beliefs", semantic)

    def __repr__(self) -> str:
        return (
            f"RetrievedMemoryContext(owner_id={self.owner_id.value!r}, "
            f"memory_count={len(self.memory_ids)}, "
            f"belief_count={len(self.belief_ids)}, "
            f"semantic_belief_count={len(self.semantic_beliefs)}, "
            f"hit_count={len(self.ranked_hits)}, "
            f"reconstruction_count={len(self.reconstructions)}, "
            f"pending_access_count={len(self.pending_accesses)}, "
            f"has_reconsolidation={self.reconsolidation is not None}, "
            f"candidate_count={self.candidate_count}, "
            f"confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class SituationModel:
    """Situation claims assembled from perception and memory references."""

    owner_id: AgentId
    tick: int
    claim_codes: tuple[SituationClaimCode, ...]
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("SituationModel.owner_id must be AgentId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("SituationModel.tick", self.tick),
        )
        object.__setattr__(
            self,
            "claim_codes",
            _require_ordered_enum(
                "SituationModel.claim_codes",
                self.claim_codes,
                enum_type=SituationClaimCode,
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("SituationModel.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError("SituationModel.decision_metadata must be DecisionMetadata")

    def __repr__(self) -> str:
        return (
            f"SituationModel(owner_id={self.owner_id.value!r}, tick={self.tick}, "
            f"claim_count={len(self.claim_codes)}, confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class SelfBeliefState:
    """Legacy projected self/belief identifiers for the owning agent.

    Prefer :class:`SelfModel` for emergent self-understanding. This type remains
    for schema compatibility and lossy projection helpers.
    """

    owner_id: AgentId
    life_status: LifeStatus | None
    belief_ids: tuple[BeliefId, ...]
    goal_ids: tuple[GoalId, ...]
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("SelfBeliefState.owner_id must be AgentId")
        if self.life_status is not None and type(self.life_status) is not LifeStatus:
            raise TypeError("SelfBeliefState.life_status must be LifeStatus or None")
        object.__setattr__(
            self,
            "belief_ids",
            require_ordered_unique(
                "SelfBeliefState.belief_ids", self.belief_ids, item_type=BeliefId
            ),
        )
        object.__setattr__(
            self,
            "goal_ids",
            require_ordered_unique(
                "SelfBeliefState.goal_ids", self.goal_ids, item_type=GoalId
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("SelfBeliefState.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError(
                "SelfBeliefState.decision_metadata must be DecisionMetadata"
            )

    def __repr__(self) -> str:
        return (
            f"SelfBeliefState(owner_id={self.owner_id.value!r}, "
            f"belief_count={len(self.belief_ids)}, "
            f"goal_count={len(self.goal_ids)}, confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class SelfModelProjectionPolicy:
    """Versioned policy for selecting self-relevant semantic beliefs."""

    policy_id: str
    version: str
    min_confidence: float = 0.2
    require_active: bool = True
    max_beliefs: int = 32

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "SelfModelProjectionPolicy.policy_id",
                self.policy_id,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "SelfModelProjectionPolicy.version",
                self.version,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "min_confidence",
            require_confidence(
                "SelfModelProjectionPolicy.min_confidence", self.min_confidence
            ),
        )
        if type(self.require_active) is not bool:
            raise TypeError("SelfModelProjectionPolicy.require_active: invalid_type")
        object.__setattr__(
            self,
            "max_beliefs",
            require_exact_nonneg_int(
                "SelfModelProjectionPolicy.max_beliefs", self.max_beliefs
            ),
        )
        if self.max_beliefs < 1 or self.max_beliefs > _MAX_MEMORY_REFS:
            raise ValueError("SelfModelProjectionPolicy.max_beliefs: out_of_bounds")

    def __repr__(self) -> str:
        return (
            f"SelfModelProjectionPolicy(policy_id={self.policy_id!r}, "
            f"version={self.version!r}, max_beliefs={self.max_beliefs})"
        )


DEFAULT_SELF_MODEL_POLICY: Final[SelfModelProjectionPolicy] = SelfModelProjectionPolicy(
    policy_id="self-model-projection", version="1"
)


@dataclass(frozen=True, slots=True)
class SelfRelevantBelief:
    """One ordered self-relevant belief selected into a ``SelfModel``."""

    belief_id: BeliefId
    claim: SemanticClaim
    confidence: float

    def __post_init__(self) -> None:
        if type(self.belief_id) is not BeliefId:
            raise TypeError("SelfRelevantBelief.belief_id: invalid_type")
        if type(self.claim) is not SemanticClaim:
            raise TypeError("SelfRelevantBelief.claim: invalid_type")
        object.__setattr__(
            self,
            "confidence",
            require_confidence("SelfRelevantBelief.confidence", self.confidence),
        )

    def __repr__(self) -> str:
        return (
            f"SelfRelevantBelief(belief_id={self.belief_id.value!r}, "
            f"confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class SelfModel:
    """Emergent self-model projected from owner-scoped semantic beliefs."""

    owner_id: AgentId
    policy_id: str
    policy_version: str
    life_status: LifeStatus | None
    beliefs: tuple[SelfRelevantBelief, ...]
    goal_ids: tuple[GoalId, ...]
    confidence: float
    candidate_count: int
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("SelfModel.owner_id must be AgentId")
        if self.life_status is not None and type(self.life_status) is not LifeStatus:
            raise TypeError("SelfModel.life_status must be LifeStatus or None")
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "SelfModel.policy_id",
                self.policy_id,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_bounded_text(
                "SelfModel.policy_version",
                self.policy_version,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        if isinstance(self.beliefs, (set, frozenset, Mapping)):
            raise TypeError("SelfModel.beliefs must be ordered")
        if isinstance(self.beliefs, (str, bytes)) or not isinstance(
            self.beliefs, Sequence
        ):
            raise TypeError("SelfModel.beliefs must be ordered")
        beliefs = tuple(self.beliefs)
        if len(beliefs) > _MAX_MEMORY_REFS:
            raise ValueError("SelfModel.beliefs exceeds maximum length")
        seen: set[str] = set()
        for item in beliefs:
            if type(item) is not SelfRelevantBelief:
                raise TypeError("SelfModel.beliefs entries must be SelfRelevantBelief")
            if item.belief_id.value in seen:
                raise ValueError("SelfModel.beliefs: duplicate_belief_id")
            seen.add(item.belief_id.value)
        object.__setattr__(self, "beliefs", beliefs)
        object.__setattr__(
            self,
            "goal_ids",
            require_ordered_unique(
                "SelfModel.goal_ids", self.goal_ids, item_type=GoalId
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("SelfModel.confidence", self.confidence),
        )
        object.__setattr__(
            self,
            "candidate_count",
            require_exact_nonneg_int("SelfModel.candidate_count", self.candidate_count),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError("SelfModel.decision_metadata must be DecisionMetadata")

    @property
    def belief_ids(self) -> tuple[BeliefId, ...]:
        return tuple(item.belief_id for item in self.beliefs)

    def __repr__(self) -> str:
        return (
            f"SelfModel(owner_id={self.owner_id.value!r}, "
            f"policy_version={self.policy_version!r}, "
            f"belief_count={len(self.beliefs)}, "
            f"candidate_count={self.candidate_count}, "
            f"goal_count={len(self.goal_ids)}, confidence={self.confidence})"
        )


def _claim_references_owner(claim: SemanticClaim, owner_id: AgentId) -> bool:
    subject = claim.subject
    if (
        subject.kind is ClaimSubjectKind.AGENT
        and subject.agent_id is not None
        and subject.agent_id == owner_id
    ):
        return True
    value = claim.value
    if (
        value.kind is BeliefValueKind.AGENT
        and value.agent_id is not None
        and value.agent_id == owner_id
    ):
        return True
    return False


def project_self_model(
    *,
    owner_id: AgentId,
    life_status: LifeStatus | None,
    beliefs: Sequence[SemanticBelief],
    goal_ids: Sequence[GoalId] = (),
    policy: SelfModelProjectionPolicy | None = None,
) -> SelfModel:
    """Deterministically project an emergent ``SelfModel`` from semantic beliefs."""
    if type(owner_id) is not AgentId:
        raise TypeError("project_self_model: invalid_owner")
    if policy is None:
        policy = DEFAULT_SELF_MODEL_POLICY
    elif type(policy) is not SelfModelProjectionPolicy:
        raise TypeError("project_self_model: invalid_policy")
    if life_status is not None and type(life_status) is not LifeStatus:
        raise TypeError("project_self_model: invalid_life_status")

    candidates: list[SemanticBelief] = []
    for belief in beliefs:
        if type(belief) is not SemanticBelief:
            raise TypeError("project_self_model: invalid_belief")
        if belief.owner_id != owner_id:
            continue
        if policy.require_active and belief.activation_state is not (
            BeliefActivationState.ACTIVE
        ):
            continue
        if belief.confidence.confidence < policy.min_confidence:
            continue
        if not _claim_references_owner(belief.claim, owner_id):
            continue
        candidates.append(belief)

    candidates.sort(
        key=lambda item: (
            -item.confidence.confidence,
            item.belief_id.value,
            canonical_claim_identity(item.claim),
        )
    )
    selected = candidates[: policy.max_beliefs]
    selected_refs = tuple(
        SelfRelevantBelief(
            belief_id=item.belief_id,
            claim=item.claim,
            confidence=item.confidence.confidence,
        )
        for item in selected
    )
    if selected_refs:
        aggregate = sum(item.confidence for item in selected_refs) / len(selected_refs)
    else:
        aggregate = 1.0 if not candidates else 0.0
    # Quantize via require_confidence bounds.
    aggregate = float(require_confidence("SelfModel.confidence", aggregate))
    return SelfModel(
        owner_id=owner_id,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        life_status=life_status,
        beliefs=selected_refs,
        goal_ids=tuple(goal_ids),
        confidence=aggregate,
        candidate_count=len(candidates),
        decision_metadata=DecisionMetadata(
            candidate_count=len(candidates),
            selection_codes=tuple(item.belief_id.value for item in selected_refs),
        ),
    )


def project_legacy_self_belief_state(model: SelfModel) -> SelfBeliefState:
    """Lossy projection onto legacy ``SelfBeliefState`` (IDs only)."""
    if type(model) is not SelfModel:
        raise TypeError("project_legacy_self_belief_state: invalid_type")
    return SelfBeliefState(
        owner_id=model.owner_id,
        life_status=model.life_status,
        belief_ids=model.belief_ids,
        goal_ids=model.goal_ids,
        confidence=model.confidence,
        decision_metadata=model.decision_metadata,
    )


@dataclass(frozen=True, slots=True)
class ImaginedFuture:
    """One bounded imagined future identified by closed claim codes."""

    future_id: str
    claim_codes: tuple[SituationClaimCode, ...]
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "future_id",
            require_stable_id("ImaginedFuture.future_id", self.future_id),
        )
        object.__setattr__(
            self,
            "claim_codes",
            _require_ordered_enum(
                "ImaginedFuture.claim_codes",
                self.claim_codes,
                enum_type=SituationClaimCode,
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("ImaginedFuture.confidence", self.confidence),
        )

    def __repr__(self) -> str:
        return (
            f"ImaginedFuture(future_id={self.future_id!r}, "
            f"claim_count={len(self.claim_codes)}, confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class PossibleFutures:
    """Bounded set of imagined futures for motivation scoring."""

    owner_id: AgentId
    futures: tuple[ImaginedFuture, ...]
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("PossibleFutures.owner_id must be AgentId")
        if isinstance(self.futures, (set, frozenset, Mapping)):
            raise TypeError("PossibleFutures.futures must be an ordered sequence")
        if isinstance(self.futures, (str, bytes)) or not isinstance(
            self.futures, Sequence
        ):
            raise TypeError("PossibleFutures.futures must be an ordered sequence")
        futures = tuple(self.futures)
        if len(futures) > _MAX_FUTURES:
            raise ValueError("PossibleFutures.futures exceeds maximum length")
        seen: set[str] = set()
        for future in futures:
            if type(future) is not ImaginedFuture:
                raise TypeError(
                    "PossibleFutures.futures entries must be ImaginedFuture"
                )
            if future.future_id in seen:
                raise ValueError("PossibleFutures.futures must have unique future_id")
            seen.add(future.future_id)
        object.__setattr__(self, "futures", futures)
        object.__setattr__(
            self,
            "confidence",
            require_confidence("PossibleFutures.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError(
                "PossibleFutures.decision_metadata must be DecisionMetadata"
            )

    def __repr__(self) -> str:
        return (
            f"PossibleFutures(owner_id={self.owner_id.value!r}, "
            f"future_count={len(self.futures)}, confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class MotivationScore:
    """One closed motive with a validated confidence-like score."""

    motive: MotivationCode
    score: float

    def __post_init__(self) -> None:
        if type(self.motive) is not MotivationCode:
            raise TypeError("MotivationScore.motive must be MotivationCode")
        object.__setattr__(
            self, "score", require_confidence("MotivationScore.score", self.score)
        )

    def __repr__(self) -> str:
        return f"MotivationScore(motive={self.motive.value!r}, score={self.score})"


@dataclass(frozen=True, slots=True)
class MotivationEvaluation:
    """Ordered motive scores for intention selection."""

    owner_id: AgentId
    scores: tuple[MotivationScore, ...]
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("MotivationEvaluation.owner_id must be AgentId")
        if isinstance(self.scores, (set, frozenset, Mapping)):
            raise TypeError("MotivationEvaluation.scores must be an ordered sequence")
        if isinstance(self.scores, (str, bytes)) or not isinstance(
            self.scores, Sequence
        ):
            raise TypeError("MotivationEvaluation.scores must be an ordered sequence")
        scores = tuple(self.scores)
        if len(scores) > _MAX_MOTIVES:
            raise ValueError("MotivationEvaluation.scores exceeds maximum length")
        seen: set[MotivationCode] = set()
        for score in scores:
            if type(score) is not MotivationScore:
                raise TypeError(
                    "MotivationEvaluation.scores entries must be MotivationScore"
                )
            if score.motive in seen:
                raise ValueError("MotivationEvaluation.scores must be unique by motive")
            seen.add(score.motive)
        object.__setattr__(self, "scores", scores)
        object.__setattr__(
            self,
            "confidence",
            require_confidence("MotivationEvaluation.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError(
                "MotivationEvaluation.decision_metadata must be DecisionMetadata"
            )

    def __repr__(self) -> str:
        return (
            f"MotivationEvaluation(owner_id={self.owner_id.value!r}, "
            f"score_count={len(self.scores)}, confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class SelectedIntention:
    """Single selected intention from motivation evaluation."""

    owner_id: AgentId
    intention: IntentionCode
    source_motive: MotivationCode | None
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("SelectedIntention.owner_id must be AgentId")
        if type(self.intention) is not IntentionCode:
            raise TypeError("SelectedIntention.intention must be IntentionCode")
        if (
            self.source_motive is not None
            and type(self.source_motive) is not MotivationCode
        ):
            raise TypeError(
                "SelectedIntention.source_motive must be MotivationCode or None"
            )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("SelectedIntention.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError(
                "SelectedIntention.decision_metadata must be DecisionMetadata"
            )

    def __repr__(self) -> str:
        return (
            f"SelectedIntention(owner_id={self.owner_id.value!r}, "
            f"intention={self.intention.value!r}, confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class ActionPlan:
    """Planner output carrying exactly one closed ``AgentCommand``."""

    owner_id: AgentId
    command: AgentCommand
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("ActionPlan.owner_id must be AgentId")
        object.__setattr__(self, "command", require_agent_command(self.command))
        object.__setattr__(
            self,
            "confidence",
            require_confidence("ActionPlan.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError("ActionPlan.decision_metadata must be DecisionMetadata")

    def __repr__(self) -> str:
        return (
            f"ActionPlan(owner_id={self.owner_id.value!r}, "
            f"command_type={type(self.command).__name__}, "
            f"confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class MemoryUpdateIntent:
    """Post-cognition subjective write intent (not an applied mutation)."""

    owner_id: AgentId
    kind: MemoryUpdateKind
    memory: MemoryTrace | None = None
    belief: Belief | None = None
    belief_revision: object | None = None
    relationship_revision: object | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("MemoryUpdateIntent.owner_id must be AgentId")
        if type(self.kind) is not MemoryUpdateKind:
            raise TypeError("MemoryUpdateIntent.kind must be MemoryUpdateKind")
        if self.kind is MemoryUpdateKind.WRITE_MEMORY:
            if type(self.memory) is not MemoryTrace:
                raise TypeError("WRITE_MEMORY requires MemoryTrace")
            if (
                self.belief is not None
                or self.belief_revision is not None
                or self.relationship_revision is not None
            ):
                raise ValueError("WRITE_MEMORY must not carry other payloads")
            if self.memory.owner_id != self.owner_id:
                raise ValueError("MemoryTrace.owner_id must match intent owner_id")
        elif self.kind is MemoryUpdateKind.WRITE_BELIEF:
            if type(self.belief) is not Belief:
                raise TypeError("WRITE_BELIEF requires Belief")
            if (
                self.memory is not None
                or self.belief_revision is not None
                or self.relationship_revision is not None
            ):
                raise ValueError("WRITE_BELIEF must not carry other payloads")
            if self.belief.owner_id != self.owner_id:
                raise ValueError("Belief.owner_id must match intent owner_id")
        elif self.kind is MemoryUpdateKind.REVISE_SEMANTIC_BELIEF:
            from memory.beliefs import BeliefRevisionRequest

            if type(self.belief_revision) is not BeliefRevisionRequest:
                raise TypeError("REVISE_SEMANTIC_BELIEF requires BeliefRevisionRequest")
            if (
                self.memory is not None
                or self.belief is not None
                or self.relationship_revision is not None
            ):
                raise ValueError("REVISE_SEMANTIC_BELIEF must not carry other payloads")
            if self.belief_revision.owner_id != self.owner_id:
                raise ValueError(
                    "BeliefRevisionRequest.owner_id must match intent owner_id"
                )
        elif self.kind is MemoryUpdateKind.REVISE_RELATIONSHIP:
            from social.relationships import RelationshipRevisionRequest

            if type(self.relationship_revision) is not RelationshipRevisionRequest:
                raise TypeError(
                    "REVISE_RELATIONSHIP requires RelationshipRevisionRequest"
                )
            if (
                self.memory is not None
                or self.belief is not None
                or self.belief_revision is not None
            ):
                raise ValueError("REVISE_RELATIONSHIP must not carry other payloads")
            if self.relationship_revision.source_id != self.owner_id:
                raise ValueError(
                    "RelationshipRevisionRequest.source_id must match intent owner_id"
                )
        else:  # pragma: no cover - closed enum
            raise ValueError("unsupported MemoryUpdateKind")

    def __repr__(self) -> str:
        return (
            f"MemoryUpdateIntent(owner_id={self.owner_id.value!r}, "
            f"kind={self.kind.value!r})"
        )


_STAGE_OUTPUT_TYPES: Final[frozenset[type]] = frozenset(
    {
        InterpretedPerception,
        RetrievedMemoryContext,
        SituationModel,
        SelfBeliefState,
        SelfModel,
        PossibleFutures,
        MotivationEvaluation,
        SelectedIntention,
        ActionPlan,
    }
)


@dataclass(frozen=True, slots=True)
class ComponentBoundaryRecord:
    """Versioned scientific boundary record for one component invocation.

    Typed input/output artifacts are retained for analysis callers. Operational
    logs must use :func:`diagnostic_projection` only — never serialize artifact
    payloads, prompts, provider responses, or private rationale.
    """

    invocation_id: str
    component_kind: ComponentKind
    component_version: str
    ordinal: int
    status: ComponentStatus
    confidence: float
    input_artifact: object
    output_artifact: object | None
    decision_metadata: DecisionMetadata
    failure_reason: CognitionFailureReason | None = None
    schema_version: int = BOUNDARY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "invocation_id",
            require_stable_id(
                "ComponentBoundaryRecord.invocation_id", self.invocation_id
            ),
        )
        if type(self.component_kind) is not ComponentKind:
            raise TypeError(
                "ComponentBoundaryRecord.component_kind must be ComponentKind"
            )
        object.__setattr__(
            self,
            "component_version",
            _require_component_version(self.component_version),
        )
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("ComponentBoundaryRecord.ordinal", self.ordinal),
        )
        if type(self.status) is not ComponentStatus:
            raise TypeError("ComponentBoundaryRecord.status must be ComponentStatus")
        object.__setattr__(
            self,
            "confidence",
            require_confidence("ComponentBoundaryRecord.confidence", self.confidence),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError(
                "ComponentBoundaryRecord.decision_metadata must be DecisionMetadata"
            )
        if self.failure_reason is not None and type(self.failure_reason) is not (
            CognitionFailureReason
        ):
            raise TypeError(
                "ComponentBoundaryRecord.failure_reason must be "
                "CognitionFailureReason or None"
            )
        object.__setattr__(
            self,
            "schema_version",
            require_exact_nonneg_int(
                "ComponentBoundaryRecord.schema_version", self.schema_version
            ),
        )
        if self.schema_version != BOUNDARY_SCHEMA_VERSION:
            raise ValueError(
                f"ComponentBoundaryRecord.schema_version must be "
                f"{BOUNDARY_SCHEMA_VERSION}"
            )
        _validate_boundary_artifacts(self)
        # Strip forbidden attribute names if a subclass sneaks them in later.
        for forbidden in (
            "rationale",
            "chain_of_thought",
            "prompt",
            "raw_response",
            "credentials",
            "endpoint",
        ):
            if hasattr(self, forbidden):
                raise TypeError(
                    f"ComponentBoundaryRecord must not expose {forbidden!r}"
                )

    def __repr__(self) -> str:
        return (
            f"ComponentBoundaryRecord(invocation_id={self.invocation_id!r}, "
            f"component_kind={self.component_kind.value!r}, "
            f"ordinal={self.ordinal}, status={self.status.value!r}, "
            f"confidence={self.confidence})"
        )


def _validate_boundary_artifacts(record: ComponentBoundaryRecord) -> None:
    input_type = type(record.input_artifact)
    output = record.output_artifact
    if record.component_kind is ComponentKind.PERCEPTION:
        if input_type is not Observation and input_type is not CognitiveLoopInput:
            raise TypeError(
                "perception input_artifact must be Observation or CognitiveLoopInput"
            )
    elif record.component_kind is ComponentKind.MEMORY_UPDATE:
        if input_type is not CognitiveLoopResult and input_type is not ActionPlan:
            raise TypeError(
                "memory_update input_artifact must be CognitiveLoopResult or ActionPlan"
            )
    elif input_type not in _STAGE_OUTPUT_TYPES and input_type is not CognitiveLoopInput:
        # Allow prior-stage outputs or loop input as typed inputs.
        if input_type is not Observation:
            raise TypeError(
                f"unsupported input_artifact type {input_type.__name__} "
                f"for {record.component_kind.value}"
            )

    if record.status is ComponentStatus.COMPLETED:
        if output is None:
            raise ValueError("completed boundary requires output_artifact")
        if record.component_kind is ComponentKind.MEMORY_UPDATE:
            if type(output) is not tuple:
                raise TypeError(
                    "memory_update output_artifact must be tuple of MemoryUpdateIntent"
                )
            for item in output:
                if type(item) is not MemoryUpdateIntent:
                    raise TypeError(
                        "memory_update output entries must be MemoryUpdateIntent"
                    )
        elif type(output) not in _STAGE_OUTPUT_TYPES:
            raise TypeError(f"unsupported output_artifact type {type(output).__name__}")
        if record.failure_reason is not None:
            raise ValueError("completed boundary must not carry failure_reason")
    else:
        if output is not None:
            raise ValueError("non-completed boundary must not carry output_artifact")
        if record.status is ComponentStatus.FAILED and record.failure_reason is None:
            raise ValueError("failed boundary requires failure_reason")
        if (
            record.status is ComponentStatus.CANCELLED
            and record.failure_reason is not None
            and record.failure_reason is not CognitionFailureReason.CANCELLED
        ):
            raise ValueError("cancelled boundary failure_reason must be CANCELLED")


@dataclass(frozen=True, slots=True)
class CognitiveLoopResult:
    """Successful loop result: one closed command plus scientific receipts.

    ``final_confidence`` is the planner-supplied confidence only. It is not an
    aggregate statistical estimate across stages.
    """

    invocation_id: str
    agent_id: AgentId
    command: AgentCommand
    boundary_records: tuple[ComponentBoundaryRecord, ...]
    memory_update_intents: tuple[MemoryUpdateIntent, ...]
    final_confidence: float
    internal_state: InternalAgentState
    pending_accesses: tuple[MemoryAccessReceipt, ...] = ()
    pending_reconsolidation: ReconsolidationIntent | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "invocation_id",
            require_stable_id("CognitiveLoopResult.invocation_id", self.invocation_id),
        )
        if type(self.agent_id) is not AgentId:
            raise TypeError("CognitiveLoopResult.agent_id must be AgentId")
        object.__setattr__(self, "command", require_agent_command(self.command))
        if isinstance(self.boundary_records, (set, frozenset, Mapping)):
            raise TypeError("CognitiveLoopResult.boundary_records must be ordered")
        if isinstance(self.boundary_records, (str, bytes)) or not isinstance(
            self.boundary_records, Sequence
        ):
            raise TypeError("CognitiveLoopResult.boundary_records must be ordered")
        records = tuple(self.boundary_records)
        for record in records:
            if type(record) is not ComponentBoundaryRecord:
                raise TypeError(
                    "CognitiveLoopResult.boundary_records entries must be "
                    "ComponentBoundaryRecord"
                )
            if record.invocation_id != self.invocation_id:
                raise ValueError("boundary record invocation_id mismatch")
        object.__setattr__(self, "boundary_records", records)
        if isinstance(self.memory_update_intents, (set, frozenset, Mapping)):
            raise TypeError("CognitiveLoopResult.memory_update_intents must be ordered")
        if isinstance(self.memory_update_intents, (str, bytes)) or not isinstance(
            self.memory_update_intents, Sequence
        ):
            raise TypeError("CognitiveLoopResult.memory_update_intents must be ordered")
        intents = tuple(self.memory_update_intents)
        for intent in intents:
            if type(intent) is not MemoryUpdateIntent:
                raise TypeError(
                    "CognitiveLoopResult.memory_update_intents entries must be "
                    "MemoryUpdateIntent"
                )
            if intent.owner_id != self.agent_id:
                raise ValueError("memory update intent owner must match agent_id")
        object.__setattr__(self, "memory_update_intents", intents)
        if isinstance(self.pending_accesses, (set, frozenset, Mapping)):
            raise TypeError("CognitiveLoopResult.pending_accesses must be ordered")
        if isinstance(self.pending_accesses, (str, bytes)) or not isinstance(
            self.pending_accesses, Sequence
        ):
            raise TypeError("CognitiveLoopResult.pending_accesses must be ordered")
        accesses = tuple(self.pending_accesses)
        for receipt in accesses:
            if type(receipt) is not MemoryAccessReceipt:
                raise TypeError(
                    "CognitiveLoopResult.pending_accesses entries must be "
                    "MemoryAccessReceipt"
                )
        object.__setattr__(self, "pending_accesses", accesses)
        if self.pending_reconsolidation is not None:
            if type(self.pending_reconsolidation) is not ReconsolidationIntent:
                raise TypeError(
                    "CognitiveLoopResult.pending_reconsolidation must be "
                    "ReconsolidationIntent"
                )
            if self.pending_reconsolidation.record.owner_id != self.agent_id:
                raise ValueError("pending_reconsolidation owner must match agent_id")
        object.__setattr__(
            self,
            "final_confidence",
            require_confidence(
                "CognitiveLoopResult.final_confidence", self.final_confidence
            ),
        )
        if type(self.internal_state) is not InternalAgentState:
            raise TypeError(
                "CognitiveLoopResult.internal_state must be InternalAgentState"
            )
        if self.internal_state.owner_id != self.agent_id:
            raise ValueError("internal_state.owner_id must match agent_id")

    def __repr__(self) -> str:
        return (
            f"CognitiveLoopResult(invocation_id={self.invocation_id!r}, "
            f"agent_id={self.agent_id.value!r}, "
            f"command_type={type(self.command).__name__}, "
            f"boundary_count={len(self.boundary_records)}, "
            f"memory_update_count={len(self.memory_update_intents)}, "
            f"pending_access_count={len(self.pending_accesses)}, "
            f"final_confidence={self.final_confidence})"
        )


def diagnostic_projection(
    value: ComponentBoundaryRecord | CognitiveLoopResult | CognitiveLoopInput,
) -> Mapping[str, object]:
    """Return a metadata-only projection safe for trusted runtime logging."""
    if type(value) is ComponentBoundaryRecord:
        fields: dict[str, object] = {
            "schema_version": value.schema_version,
            "invocation_id": value.invocation_id,
            "component_kind": value.component_kind.value,
            "component_version": value.component_version,
            "ordinal": value.ordinal,
            "status": value.status.value,
            "confidence": value.confidence,
            "input_type": type(value.input_artifact).__name__,
            "output_type": (
                None
                if value.output_artifact is None
                else type(value.output_artifact).__name__
            ),
            "selection_code_count": len(value.decision_metadata.selection_codes),
            "candidate_count": value.decision_metadata.candidate_count,
            "tie_break_applied": value.decision_metadata.tie_break_applied,
        }
        if value.failure_reason is not None:
            fields["failure_reason"] = value.failure_reason.value
        return fields
    if type(value) is CognitiveLoopResult:
        return {
            "invocation_id": value.invocation_id,
            "agent_id": value.agent_id.value,
            "command_type": type(value.command).__name__,
            "boundary_count": len(value.boundary_records),
            "memory_update_count": len(value.memory_update_intents),
            "pending_access_count": len(value.pending_accesses),
            "final_confidence": value.final_confidence,
            "invocation_count": value.internal_state.invocation_count,
        }
    if type(value) is CognitiveLoopInput:
        return {
            "agent_id": value.agent_id.value,
            "tick": value.observation.tick,
            "revision": value.observation.revision.value,
            "invocation_count": value.internal_state.invocation_count,
        }
    raise TypeError("diagnostic_projection requires a supported cognition model")
