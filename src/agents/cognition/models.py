"""Immutable cognitive stage artifacts and scientific boundary records.

These values capture inspectable claims and choices for analysis. They do not
store hidden rationale, chain-of-thought, prompts, raw provider responses,
credentials, or endpoints. Pydantic/`LLMResult` validation is never treated as
command or world authority here.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.cognition.identity import (
    IDENTITY_POLICY_ID,
    IDENTITY_POLICY_VERSION,
    IdentityBeliefView,
    IdentityDissonanceNotice,
    IdentityPolicy,
    IdentityRevisionPoint,
    IdentityRevisionSummary,
    IdentityState,
    aggregate_identity_confidence,
    derive_identity_rate,
    derive_identity_stability,
    parse_identity_predicate,
)
from agents.models import (
    AgentId,
    DriveKind,
    DriveProfile,
    Goal,
    GoalHorizon,
    GoalId,
    GoalStatus,
    default_drive_profile,
    validate_goal_hierarchy,
)
from memory.beliefs import (
    BeliefActivationState,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubjectKind,
    SemanticBelief,
    SemanticBeliefHistory,
    SemanticClaim,
    canonical_claim_identity,
)
from memory.models import (
    Belief,
    BeliefId,
    ConceptMention,
    EntityMention,
    MemoryAccessReceipt,
    MemoryId,
    MemoryRankedHit,
    MemoryRelation,
    MemorySituationContext,
    MemoryTrace,
    ReconsolidationIntent,
    ReconstructedMemory,
    quantize_score,
)
from social.models import CommunicationEnvelope
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

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.models")

__all__ = [
    "BOUNDARY_SCHEMA_VERSION",
    "DEFAULT_EMOTION_KINDS",
    "DEFAULT_EMOTION_POLICY_VERSION",
    "DEFAULT_SELF_MODEL_POLICY",
    "ActionDirection",
    "ActionPlan",
    "AgentEmotionalState",
    "CognitionFailureReason",
    "CognitiveLoopInput",
    "CognitiveLoopProposal",
    "CognitiveLoopResult",
    "ComponentBoundaryRecord",
    "ComponentKind",
    "ComponentStatus",
    "CounterpartBinding",
    "DecisionMetadata",
    "DriveEffect",
    "EmotionDriverCode",
    "EmotionIntensity",
    "EmotionKind",
    "EmotionRegulationPolicy",
    "EmotionalStateEvaluation",
    "EpisodeFacts",
    "FutureAppraisal",
    "FutureSourceRef",
    "GoalBoard",
    "GoalEffect",
    "GoalTransitionIntent",
    "GoalTransitionIntentReason",
    "ImaginedFuture",
    "IntentionCode",
    "InternalAgentState",
    "InterpretedPerception",
    "MemoryUpdateIntent",
    "MemoryUpdateKind",
    "MortalityOpportunityForeclosure",
    "MotivationCode",
    "MotivationEvaluation",
    "MotivationScore",
    "OptionSpaceChange",
    "OwnerSafeSocialIdentity",
    "PerceivedNeedPressures",
    "PerceptionClaimCode",
    "PossibleFutures",
    "ReferenceEpisode",
    "RetrievedMemoryContext",
    "SelectedIntention",
    "SelfBeliefState",
    "SelfModel",
    "SelfModelProjectionPolicy",
    "SelfRelevantBelief",
    "SituationClaimCode",
    "SituationModel",
    "SocialEffect",
    "SubjectiveRisk",
    "SubjectiveRiskKind",
    "SubjectiveSnapshot",
    "SubjectiveUncertainty",
    "UncertaintyBand",
    "action_direction_for_intention",
    "default_emotion_regulation_policy",
    "diagnostic_projection",
    "empty_emotional_state",
    "episode_facts",
    "intensity_band",
    "intention_for_action_direction",
    "project_identity_state",
    "project_legacy_self_belief_state",
    "project_self_model",
    "require_confidence",
    "require_signed_unit",
]

BOUNDARY_SCHEMA_VERSION: Final[int] = 1

_MAX_COMPONENT_VERSION_CHARS: Final[int] = 64
_MAX_SELECTION_CODES: Final[int] = 64
_MAX_FUTURES: Final[int] = 32
_MAX_MOTIVES: Final[int] = 32
_MAX_MEMORY_REFS: Final[int] = 256
_MAX_CLAIM_CODES: Final[int] = 64
_MAX_EFFECTS: Final[int] = 32
_MAX_RISKS: Final[int] = 16
_MAX_SOURCE_REFS: Final[int] = 64
_MAX_APPRAISALS: Final[int] = 32
_MAX_GOAL_BOARD_GOALS: Final[int] = 64
_MAX_GOAL_FOCI: Final[int] = 8
_MAX_GOAL_TRANSITION_INTENTS: Final[int] = 64
_EFFECT_QUANTUM: Final[float] = 1e-6
_MORTALITY_WEIGHT_GOAL: Final[float] = 0.30
_MORTALITY_WEIGHT_ATTACHMENT: Final[float] = 0.20
_MORTALITY_WEIGHT_SAFETY: Final[float] = 0.20
_MORTALITY_WEIGHT_AUTONOMY: Final[float] = 0.15
_MORTALITY_WEIGHT_OPTIONS: Final[float] = 0.15


class ComponentKind(StrEnum):
    """Closed set of cognitive pipeline component identities."""

    PERCEPTION = "perception"
    MEMORY_RETRIEVAL = "memory_retrieval"
    SITUATION = "situation"
    SELF_STATE = "self_state"
    GOAL_MANAGEMENT = "goal_management"
    EMOTIONAL_STATE = "emotional_state"
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


class EmotionKind(StrEnum):
    """Closed short-term emotion catalog (not free-form affect labels).

    Distinct from ``RelationshipDimension.FEAR`` — emotion fear is transient
    owner affect; relationship fear is an asymmetric directed assessment.
    """

    FEAR = "fear"
    ANGER = "anger"
    SADNESS = "sadness"
    RELIEF = "relief"
    ATTACHMENT = "attachment"
    ANXIETY = "anxiety"
    CONFIDENCE = "confidence"


DEFAULT_EMOTION_KINDS: Final[tuple[EmotionKind, ...]] = (
    EmotionKind.FEAR,
    EmotionKind.ANGER,
    EmotionKind.SADNESS,
    EmotionKind.RELIEF,
    EmotionKind.ATTACHMENT,
    EmotionKind.ANXIETY,
    EmotionKind.CONFIDENCE,
)

DEFAULT_EMOTION_POLICY_VERSION: Final[str] = "emotion.v1"


class EmotionDriverCode(StrEnum):
    """Closed driver reason codes for emotional-state transitions."""

    OBSERVATION = "observation"
    MEMORY_SALIENCE = "memory_salience"
    THREAT = "threat"
    GOAL_PROGRESS = "goal_progress"
    GOAL_FAILURE = "goal_failure"
    SOCIAL_INTERACTION = "social_interaction"
    RELATIONSHIP = "relationship"
    PHYSICAL_CONDITION = "physical_condition"
    DECAY = "decay"
    REGULATION = "regulation"
    PASSTHROUGH = "passthrough"


class MotivationCode(StrEnum):
    """Closed motivation labels for V1 scoring."""

    SURVIVE = "survive"
    REST = "rest"
    EXPLORE = "explore"
    SOCIALIZE = "socialize"
    WAIT = "wait"


class IntentionCode(StrEnum):
    """Closed intention labels selected from motivations or directions."""

    WAIT = "wait"
    MOVE = "move"
    SEARCH = "search"
    REST = "rest"
    COMMUNICATE = "communicate"
    SURVIVE = "survive"
    DRINK = "drink"
    EAT = "eat"
    SLEEP = "sleep"
    FLEE = "flee"
    HELP = "help"
    ATTACK = "attack"


class ActionDirection(StrEnum):
    """Closed actionable directions compatible with world command kinds."""

    WAIT = "wait"
    MOVE = "move"
    SEARCH = "search"
    DRINK = "drink"
    EAT = "eat"
    SLEEP = "sleep"
    FLEE = "flee"
    COMMUNICATE = "communicate"
    HELP = "help"
    ATTACK = "attack"


class SubjectiveRiskKind(StrEnum):
    """Closed subjective risk categories for imagined futures."""

    PHYSICAL_HARM = "physical_harm"
    RESOURCE_LOSS = "resource_loss"
    SOCIAL_COST = "social_cost"
    AUTONOMY_LOSS = "autonomy_loss"
    GOAL_FORECLOSURE = "goal_foreclosure"
    UNKNOWN = "unknown"


class UncertaintyBand(StrEnum):
    """Closed uncertainty magnitude bands."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


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


def require_signed_unit(name: str, value: object) -> float:
    """Accept a finite signed unit value in ``[-1.0, 1.0]``; reject booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_signed_unit")
    number = float(value)
    if not math.isfinite(number) or number < -1.0 or number > 1.0:
        raise ValueError(f"{name}: not_signed_unit")
    return 0.0 if number == 0.0 else number


def _quantize_unit(value: float) -> float:
    steps = round(value / _EFFECT_QUANTUM)
    quantized = steps * _EFFECT_QUANTUM
    if quantized < 0.0:
        quantized = 0.0
    elif quantized > 1.0:
        quantized = 1.0
    return 0.0 if quantized == 0.0 else quantized


def _require_positive_int(name: str, value: object) -> int:
    number = require_exact_nonneg_int(name, value)
    if number < 1:
        raise ValueError(f"{name}: must_be_positive")
    return number


def _require_ordered_model_tuple[T](
    name: str,
    values: Sequence[object],
    *,
    model_type: type[T],
    max_items: int,
) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name}: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name}: not_ordered")
    items = tuple(values)
    if len(items) > max_items:
        raise ValueError(f"{name}: exceeds_max_length")
    for item in items:
        if type(item) is not model_type:
            raise TypeError(f"{name}: invalid_entry_type")
    return items  # type: ignore[return-value]


def _require_stable_id_tuple(
    name: str, values: Sequence[object], *, max_items: int
) -> tuple[str, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name}: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name}: not_ordered")
    items = tuple(values)
    if len(items) > max_items:
        raise ValueError(f"{name}: exceeds_max_length")
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = require_stable_id(name, item)
        if text in seen:
            raise ValueError(f"{name}: duplicate")
        seen.add(text)
        out.append(text)
    return tuple(out)


_DIRECTION_FOR_INTENTION: Final[Mapping[IntentionCode, ActionDirection]] = {
    IntentionCode.WAIT: ActionDirection.WAIT,
    IntentionCode.MOVE: ActionDirection.MOVE,
    IntentionCode.SEARCH: ActionDirection.SEARCH,
    IntentionCode.REST: ActionDirection.SLEEP,
    IntentionCode.COMMUNICATE: ActionDirection.COMMUNICATE,
    IntentionCode.SURVIVE: ActionDirection.FLEE,
    IntentionCode.DRINK: ActionDirection.DRINK,
    IntentionCode.EAT: ActionDirection.EAT,
    IntentionCode.SLEEP: ActionDirection.SLEEP,
    IntentionCode.FLEE: ActionDirection.FLEE,
    IntentionCode.HELP: ActionDirection.HELP,
    IntentionCode.ATTACK: ActionDirection.ATTACK,
}

_INTENTION_FOR_DIRECTION: Final[Mapping[ActionDirection, IntentionCode]] = {
    ActionDirection.WAIT: IntentionCode.WAIT,
    ActionDirection.MOVE: IntentionCode.MOVE,
    ActionDirection.SEARCH: IntentionCode.SEARCH,
    ActionDirection.DRINK: IntentionCode.DRINK,
    ActionDirection.EAT: IntentionCode.EAT,
    ActionDirection.SLEEP: IntentionCode.SLEEP,
    ActionDirection.FLEE: IntentionCode.FLEE,
    ActionDirection.COMMUNICATE: IntentionCode.COMMUNICATE,
    ActionDirection.HELP: IntentionCode.HELP,
    ActionDirection.ATTACK: IntentionCode.ATTACK,
}


def action_direction_for_intention(intention: IntentionCode) -> ActionDirection:
    """Map a closed intention code onto a command-compatible action direction."""
    if type(intention) is not IntentionCode:
        raise TypeError("action_direction_for_intention: invalid_type")
    return _DIRECTION_FOR_INTENTION[intention]


def intention_for_action_direction(direction: ActionDirection) -> IntentionCode:
    """Map a closed action direction onto an intention code."""
    if type(direction) is not ActionDirection:
        raise TypeError("intention_for_action_direction: invalid_type")
    return _INTENTION_FOR_DIRECTION[direction]


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
class CounterpartBinding:
    """Owner-safe AgentId/EntityId pair for one visible or communicative counterpart."""

    agent_id: AgentId
    entity_id: EntityId

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("CounterpartBinding.agent_id: invalid_type")
        if type(self.entity_id) is not EntityId:
            raise TypeError("CounterpartBinding.entity_id: invalid_type")

    def __repr__(self) -> str:
        return (
            f"CounterpartBinding(agent_id={self.agent_id.value!r}, "
            f"entity_id={self.entity_id.value!r})"
        )


@dataclass(frozen=True, slots=True)
class OwnerSafeSocialIdentity:
    """Minimal identity projection for applying directed relationships.

    Contains only the owner binding plus counterparts derived from visible or
    communicative entities. Never embeds the full registration map.
    """

    owner_id: AgentId
    owner_entity_id: EntityId
    counterparts: tuple[CounterpartBinding, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("OwnerSafeSocialIdentity.owner_id: invalid_type")
        if type(self.owner_entity_id) is not EntityId:
            raise TypeError("OwnerSafeSocialIdentity.owner_entity_id: invalid_type")
        if isinstance(self.counterparts, (set, frozenset, Mapping)):
            raise TypeError("OwnerSafeSocialIdentity.counterparts: not_ordered")
        if isinstance(self.counterparts, (str, bytes)) or not isinstance(
            self.counterparts, Sequence
        ):
            raise TypeError("OwnerSafeSocialIdentity.counterparts: not_ordered")
        counterparts = tuple(self.counterparts)
        seen_agents: set[str] = set()
        seen_entities: set[str] = set()
        previous_entity: str | None = None
        for binding in counterparts:
            if type(binding) is not CounterpartBinding:
                raise TypeError(
                    "OwnerSafeSocialIdentity.counterparts: invalid_entry_type"
                )
            if binding.agent_id == self.owner_id:
                raise ValueError("OwnerSafeSocialIdentity.counterparts: owner_listed")
            if binding.entity_id == self.owner_entity_id:
                raise ValueError("OwnerSafeSocialIdentity.counterparts: owner_entity")
            if binding.agent_id.value in seen_agents:
                raise ValueError(
                    "OwnerSafeSocialIdentity.counterparts: duplicate_agent"
                )
            if binding.entity_id.value in seen_entities:
                raise ValueError(
                    "OwnerSafeSocialIdentity.counterparts: duplicate_entity"
                )
            if (
                previous_entity is not None
                and binding.entity_id.value < previous_entity
            ):
                raise ValueError("OwnerSafeSocialIdentity.counterparts: unordered")
            previous_entity = binding.entity_id.value
            seen_agents.add(binding.agent_id.value)
            seen_entities.add(binding.entity_id.value)
        object.__setattr__(self, "counterparts", counterparts)

    def __repr__(self) -> str:
        return (
            f"OwnerSafeSocialIdentity(owner_id={self.owner_id.value!r}, "
            f"owner_entity_id={self.owner_entity_id.value!r}, "
            f"counterpart_count={len(self.counterparts)})"
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
    goals: tuple[Goal, ...] = ()
    drives: DriveProfile | None = None
    inbox: tuple[CommunicationEnvelope, ...] = ()
    social_identity: OwnerSafeSocialIdentity | None = None
    emotional_state: AgentEmotionalState | None = None

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
        if isinstance(self.goals, (set, frozenset, Mapping)):
            raise TypeError("SubjectiveSnapshot.goals: not_ordered")
        if isinstance(self.goals, (str, bytes)) or not isinstance(self.goals, Sequence):
            raise TypeError("SubjectiveSnapshot.goals: not_ordered")
        goals = tuple(self.goals)
        seen_goals: set[str] = set()
        for goal in goals:
            if type(goal) is not Goal:
                raise TypeError("SubjectiveSnapshot.goals: invalid_entry_type")
            if goal.owner_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.goals: ownership")
            if goal.goal_id.value in seen_goals:
                raise ValueError("SubjectiveSnapshot.goals: duplicate")
            seen_goals.add(goal.goal_id.value)
        object.__setattr__(self, "goals", goals)
        if self.drives is None:
            object.__setattr__(self, "drives", default_drive_profile(self.owner_id))
        else:
            if type(self.drives) is not DriveProfile:
                raise TypeError("SubjectiveSnapshot.drives: invalid_type")
            if self.drives.owner_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.drives: ownership")
        if isinstance(self.inbox, (set, frozenset, Mapping)):
            raise TypeError("SubjectiveSnapshot.inbox: not_ordered")
        if isinstance(self.inbox, (str, bytes)) or not isinstance(self.inbox, Sequence):
            raise TypeError("SubjectiveSnapshot.inbox: not_ordered")
        inbox = tuple(self.inbox)
        for envelope in inbox:
            if type(envelope) is not CommunicationEnvelope:
                raise TypeError("SubjectiveSnapshot.inbox: invalid_entry_type")
            if envelope.recipient_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.inbox: ownership")
        object.__setattr__(self, "inbox", inbox)
        if self.social_identity is not None:
            if type(self.social_identity) is not OwnerSafeSocialIdentity:
                raise TypeError("SubjectiveSnapshot.social_identity: invalid_type")
            if self.social_identity.owner_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.social_identity: ownership")
        if self.emotional_state is not None:
            if type(self.emotional_state) is not AgentEmotionalState:
                raise TypeError("SubjectiveSnapshot.emotional_state: invalid_type")
            if self.emotional_state.owner_id != self.owner_id:
                raise ValueError("SubjectiveSnapshot.emotional_state: ownership")

    def __repr__(self) -> str:
        drive_count = 0 if self.drives is None else len(self.drives.dispositions)
        counterpart_count = (
            0
            if self.social_identity is None
            else len(self.social_identity.counterparts)
        )
        emotion_kinds = (
            0
            if self.emotional_state is None
            else len(self.emotional_state.intensities)
        )
        return (
            f"SubjectiveSnapshot(owner_id={self.owner_id.value!r}, "
            f"revision={self.revision}, "
            f"memory_count={len(self.memories)}, "
            f"legacy_belief_count={len(self.legacy_beliefs)}, "
            f"semantic_belief_count={len(self.semantic_beliefs)}, "
            f"relationship_count={len(self.relationships)}, "
            f"goal_count={len(self.goals)}, "
            f"drive_count={drive_count}, "
            f"inbox_count={len(self.inbox)}, "
            f"counterpart_count={counterpart_count}, "
            f"emotion_kind_count={emotion_kinds})"
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
class EpisodeFacts:
    """Shared read-only episode facts for communication and imagination.

    Reconstruction-only generation/provider/lineage fields are intentionally
    absent so reference and reconstructed episodes can share one consumer path.
    """

    owner_id: AgentId
    concepts: tuple[ConceptMention, ...]
    entities: tuple[EntityMention, ...]
    relations: tuple[MemoryRelation, ...]
    confidence: float
    emotional_salience: float
    source_memory_ids: tuple[MemoryId, ...]
    narrative: str
    episode_kind: str
    episode_id: str


@dataclass(frozen=True, slots=True)
class ReferenceEpisode:
    """Lossless owner-scoped projection of a stored trace for exact memory.

    Distinct from ``ReconstructedMemory``: no reconstruction lineage, provider
    flags, generation, or fabricated reconstruction identity.
    """

    episode_id: str
    owner_id: AgentId
    source_memory_id: MemoryId
    narrative: str
    concepts: tuple[ConceptMention, ...]
    entities: tuple[EntityMention, ...]
    relations: tuple[MemoryRelation, ...]
    context: MemorySituationContext
    confidence: float
    emotional_salience: float
    created_tick: int
    source_tick: int
    policy_id: str
    policy_version: str

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("ReferenceEpisode.owner_id must be AgentId")
        if type(self.source_memory_id) is not MemoryId:
            raise TypeError("ReferenceEpisode.source_memory_id must be MemoryId")
        if type(self.context) is not MemorySituationContext:
            raise TypeError("ReferenceEpisode.context must be MemorySituationContext")
        object.__setattr__(
            self,
            "episode_id",
            require_bounded_text(
                "ReferenceEpisode.episode_id", self.episode_id, max_length=128
            ),
        )
        object.__setattr__(
            self,
            "narrative",
            require_bounded_text(
                "ReferenceEpisode.narrative", self.narrative, max_length=4096
            ),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("ReferenceEpisode.confidence", self.confidence),
        )
        object.__setattr__(
            self,
            "emotional_salience",
            require_confidence(
                "ReferenceEpisode.emotional_salience", self.emotional_salience
            ),
        )
        object.__setattr__(
            self,
            "created_tick",
            require_exact_nonneg_int(
                "ReferenceEpisode.created_tick", self.created_tick
            ),
        )
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int("ReferenceEpisode.source_tick", self.source_tick),
        )
        object.__setattr__(
            self,
            "policy_id",
            require_bounded_text(
                "ReferenceEpisode.policy_id", self.policy_id, max_length=64
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_bounded_text(
                "ReferenceEpisode.policy_version",
                self.policy_version,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        object.__setattr__(self, "concepts", tuple(self.concepts))
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "relations", tuple(self.relations))

    @classmethod
    def from_trace(
        cls,
        trace: MemoryTrace,
        *,
        policy_id: str,
        policy_version: str,
    ) -> ReferenceEpisode:
        """Project a stored trace into a reference episode without reconstruction."""
        if type(trace) is not MemoryTrace:
            raise TypeError("from_trace requires MemoryTrace")
        narrative = (
            f"reference:{trace.memory_id.value}:t{trace.source_tick}:"
            f"c{len(trace.concepts)}:e{len(trace.entities)}:r{len(trace.relations)}"
        )
        return cls(
            episode_id=f"ref-{trace.memory_id.value}",
            owner_id=trace.owner_id,
            source_memory_id=trace.memory_id,
            narrative=narrative,
            concepts=trace.concepts,
            entities=trace.entities,
            relations=trace.relations,
            context=trace.context,
            confidence=trace.confidence,
            emotional_salience=trace.emotional_salience,
            created_tick=trace.created_tick,
            source_tick=trace.source_tick,
            policy_id=policy_id,
            policy_version=policy_version,
        )


def episode_facts(context: RetrievedMemoryContext) -> tuple[EpisodeFacts, ...]:
    """Return shared episode facts from reference or reconstructed channels."""
    if type(context) is not RetrievedMemoryContext:
        raise TypeError("episode_facts requires RetrievedMemoryContext")
    facts: list[EpisodeFacts] = []
    for item in context.reference_episodes:
        facts.append(
            EpisodeFacts(
                owner_id=item.owner_id,
                concepts=item.concepts,
                entities=item.entities,
                relations=item.relations,
                confidence=item.confidence,
                emotional_salience=item.emotional_salience,
                source_memory_ids=(item.source_memory_id,),
                narrative=item.narrative,
                episode_kind="reference",
                episode_id=item.episode_id,
            )
        )
    for item in context.reconstructions:
        facts.append(
            EpisodeFacts(
                owner_id=item.owner_id,
                concepts=item.concepts,
                entities=item.entities,
                relations=item.relations,
                confidence=item.confidence,
                emotional_salience=item.emotional_salience,
                source_memory_ids=item.source_memory_ids,
                narrative=item.narrative,
                episode_kind="reconstructed",
                episode_id=item.reconstruction_id.value,
            )
        )
    return tuple(facts)


@dataclass(frozen=True, slots=True)
class RetrievedMemoryContext:
    """Owner-scoped recall with reconstructive and/or exact-reference episodes.

    ``reconstructions`` and ``reference_episodes`` are the remembered episode
    channels for downstream cognition. Ranked hits and pending access receipts
    remain scientific evidence only. Reconstruction-only fields are unavailable
    on reference episodes; consumers must use ``episode_facts``.
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
    reference_episodes: tuple[ReferenceEpisode, ...] = ()
    reconsolidation: ReconsolidationIntent | None = None
    reconstruction_policy_version: str | None = None
    semantic_beliefs: tuple[SemanticBelief, ...] = ()
    pending_semanticization: BeliefRevisionRequest | None = None

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
        if isinstance(self.reference_episodes, (set, frozenset, Mapping)):
            raise TypeError("RetrievedMemoryContext.reference_episodes must be ordered")
        if isinstance(self.reference_episodes, (str, bytes)) or not isinstance(
            self.reference_episodes, Sequence
        ):
            raise TypeError("RetrievedMemoryContext.reference_episodes must be ordered")
        references = tuple(self.reference_episodes)
        if len(references) > _MAX_MEMORY_REFS:
            raise ValueError(
                "RetrievedMemoryContext.reference_episodes exceeds maximum length"
            )
        for item in references:
            if type(item) is not ReferenceEpisode:
                raise TypeError(
                    "RetrievedMemoryContext.reference_episodes entries must be "
                    "ReferenceEpisode"
                )
            if item.owner_id != self.owner_id:
                raise ValueError(
                    "RetrievedMemoryContext reference episode owner mismatch"
                )
        if reconstructions and references:
            raise ValueError(
                "RetrievedMemoryContext cannot mix reconstructions and "
                "reference_episodes"
            )
        object.__setattr__(self, "reference_episodes", references)
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
        if self.pending_semanticization is not None:
            if type(self.pending_semanticization) is not BeliefRevisionRequest:
                raise TypeError(
                    "RetrievedMemoryContext.pending_semanticization must be "
                    "BeliefRevisionRequest"
                )
            if self.pending_semanticization.owner_id != self.owner_id:
                raise ValueError(
                    "RetrievedMemoryContext pending_semanticization owner mismatch"
                )

    def __repr__(self) -> str:
        return (
            f"RetrievedMemoryContext(owner_id={self.owner_id.value!r}, "
            f"memory_count={len(self.memory_ids)}, "
            f"belief_count={len(self.belief_ids)}, "
            f"semantic_belief_count={len(self.semantic_beliefs)}, "
            f"hit_count={len(self.ranked_hits)}, "
            f"reconstruction_count={len(self.reconstructions)}, "
            f"reference_episode_count={len(self.reference_episodes)}, "
            f"pending_access_count={len(self.pending_accesses)}, "
            f"has_reconsolidation={self.reconsolidation is not None}, "
            f"has_semanticization={self.pending_semanticization is not None}, "
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
    identity: IdentityState | None = None

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
        if self.identity is not None:
            if type(self.identity) is not IdentityState:
                raise TypeError("SelfModel.identity: invalid_type")
            if self.identity.owner_id != self.owner_id:
                raise ValueError("SelfModel.identity: owner_mismatch")

    @property
    def belief_ids(self) -> tuple[BeliefId, ...]:
        return tuple(item.belief_id for item in self.beliefs)

    def __repr__(self) -> str:
        return (
            f"SelfModel(owner_id={self.owner_id.value!r}, "
            f"policy_version={self.policy_version!r}, "
            f"belief_count={len(self.beliefs)}, "
            f"candidate_count={self.candidate_count}, "
            f"goal_count={len(self.goal_ids)}, confidence={self.confidence}, "
            f"identity_count="
            f"{0 if self.identity is None else len(self.identity.views)})"
        )


class GoalTransitionIntentReason(StrEnum):
    """Closed subjective goal-transition reasons (not WorldEngine receipts)."""

    FAILED = "failed"
    SUSPENDED = "suspended"
    RESUMED = "resumed"
    ABANDONED = "abandoned"
    DECOMPOSED = "decomposed"
    REVISED = "revised"
    ADOPTED = "adopted"
    PROGRESS_UPDATED = "progress_updated"
    FOCUS_SELECTED = "focus_selected"


@dataclass(frozen=True, slots=True)
class GoalTransitionIntent:
    """Owner-scoped intent to mutate live goals after cognition finalize."""

    goal_id: GoalId
    owner_id: AgentId
    from_status: GoalStatus
    to_status: GoalStatus
    reason_code: GoalTransitionIntentReason
    tick: int
    resulting_goal: Goal | None = None

    def __post_init__(self) -> None:
        if type(self.goal_id) is not GoalId:
            raise TypeError("GoalTransitionIntent.goal_id: invalid_type")
        if type(self.owner_id) is not AgentId:
            raise TypeError("GoalTransitionIntent.owner_id: invalid_type")
        if type(self.from_status) is not GoalStatus:
            raise TypeError("GoalTransitionIntent.from_status: invalid_type")
        if type(self.to_status) is not GoalStatus:
            raise TypeError("GoalTransitionIntent.to_status: invalid_type")
        if type(self.reason_code) is not GoalTransitionIntentReason:
            raise TypeError("GoalTransitionIntent.reason_code: invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("GoalTransitionIntent.tick", self.tick),
        )
        if self.resulting_goal is not None:
            if type(self.resulting_goal) is not Goal:
                raise TypeError("GoalTransitionIntent.resulting_goal: invalid_type")
            if self.resulting_goal.owner_id != self.owner_id:
                raise ValueError("GoalTransitionIntent.resulting_goal: owner_mismatch")
            if self.resulting_goal.goal_id != self.goal_id:
                raise ValueError(
                    "GoalTransitionIntent.resulting_goal: goal_id_mismatch"
                )
            if self.resulting_goal.status is not self.to_status:
                raise ValueError(
                    "GoalTransitionIntent.resulting_goal: status_mismatch"
                )

    def __repr__(self) -> str:
        return (
            f"GoalTransitionIntent(goal_id={self.goal_id.value!r}, "
            f"owner_id={self.owner_id.value!r}, "
            f"from_status={self.from_status.value!r}, "
            f"to_status={self.to_status.value!r}, "
            f"reason_code={self.reason_code.value!r}, tick={self.tick})"
        )


@dataclass(frozen=True, slots=True)
class GoalBoard:
    """Frozen hierarchical goal board emitted by ``GOAL_MANAGEMENT``."""

    owner_id: AgentId
    tick: int
    goals: tuple[Goal, ...]
    foci_ids: tuple[GoalId, ...]
    transition_intents: tuple[GoalTransitionIntent, ...]
    confidence: float
    policy_version: str
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("GoalBoard.owner_id: invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("GoalBoard.tick", self.tick),
        )
        if isinstance(self.goals, (set, frozenset, Mapping)):
            raise TypeError("GoalBoard.goals: not_ordered")
        if isinstance(self.goals, (str, bytes)) or not isinstance(self.goals, Sequence):
            raise TypeError("GoalBoard.goals: not_ordered")
        goals = tuple(self.goals)
        if len(goals) > _MAX_GOAL_BOARD_GOALS:
            raise ValueError("GoalBoard.goals: too_many")
        seen: set[GoalId] = set()
        for goal in goals:
            if type(goal) is not Goal:
                raise TypeError("GoalBoard.goals: invalid_entry_type")
            if goal.owner_id != self.owner_id:
                raise ValueError("GoalBoard.goals: owner_mismatch")
            if goal.goal_id in seen:
                raise ValueError("GoalBoard.goals: duplicate_goal_id")
            seen.add(goal.goal_id)
        validate_goal_hierarchy(goals)
        object.__setattr__(self, "goals", goals)
        if isinstance(self.foci_ids, (set, frozenset, Mapping)):
            raise TypeError("GoalBoard.foci_ids: not_ordered")
        if isinstance(self.foci_ids, (str, bytes)) or not isinstance(
            self.foci_ids, Sequence
        ):
            raise TypeError("GoalBoard.foci_ids: not_ordered")
        foci = tuple(self.foci_ids)
        if len(foci) > _MAX_GOAL_FOCI:
            raise ValueError("GoalBoard.foci_ids: too_many")
        foci_seen: set[GoalId] = set()
        by_id = {goal.goal_id: goal for goal in goals}
        for focus_id in foci:
            if type(focus_id) is not GoalId:
                raise TypeError("GoalBoard.foci_ids: invalid_entry_type")
            if focus_id in foci_seen:
                raise ValueError("GoalBoard.foci_ids: duplicate_goal_id")
            foci_seen.add(focus_id)
            focus = by_id.get(focus_id)
            if focus is None:
                raise ValueError("GoalBoard.foci_ids: missing_goal")
            if focus.horizon is not GoalHorizon.CURRENT_INTENTION:
                raise ValueError("GoalBoard.foci_ids: not_current_intention")
            if focus.status is not GoalStatus.ACTIVE:
                raise ValueError("GoalBoard.foci_ids: not_active")
        object.__setattr__(self, "foci_ids", foci)
        if isinstance(self.transition_intents, (set, frozenset, Mapping)):
            raise TypeError("GoalBoard.transition_intents: not_ordered")
        if isinstance(self.transition_intents, (str, bytes)) or not isinstance(
            self.transition_intents, Sequence
        ):
            raise TypeError("GoalBoard.transition_intents: not_ordered")
        intents = tuple(self.transition_intents)
        if len(intents) > _MAX_GOAL_TRANSITION_INTENTS:
            raise ValueError("GoalBoard.transition_intents: too_many")
        for intent in intents:
            if type(intent) is not GoalTransitionIntent:
                raise TypeError("GoalBoard.transition_intents: invalid_entry_type")
            if intent.owner_id != self.owner_id:
                raise ValueError("GoalBoard.transition_intents: owner_mismatch")
            if intent.tick != self.tick:
                raise ValueError("GoalBoard.transition_intents: tick_mismatch")
        object.__setattr__(self, "transition_intents", intents)
        object.__setattr__(
            self,
            "confidence",
            require_confidence("GoalBoard.confidence", self.confidence),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_bounded_text(
                "GoalBoard.policy_version",
                self.policy_version,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError("GoalBoard.decision_metadata: invalid_type")

    def __repr__(self) -> str:
        return (
            f"GoalBoard(owner_id={self.owner_id.value!r}, tick={self.tick}, "
            f"goal_count={len(self.goals)}, foci_count={len(self.foci_ids)}, "
            f"transition_count={len(self.transition_intents)}, "
            f"policy_version={self.policy_version!r})"
        )


def intensity_band(value: float) -> UncertaintyBand:
    """Map a unit-interval intensity to a closed band (no narrative)."""
    intensity = require_confidence("intensity_band", value)
    if intensity < 0.34:
        return UncertaintyBand.LOW
    if intensity < 0.67:
        return UncertaintyBand.MEDIUM
    return UncertaintyBand.HIGH


@dataclass(frozen=True, slots=True)
class EmotionIntensity:
    """One quantized unit-interval intensity for a closed emotion kind."""

    kind: EmotionKind
    intensity: float

    def __post_init__(self) -> None:
        if type(self.kind) is not EmotionKind:
            raise TypeError("EmotionIntensity.kind: invalid_type")
        object.__setattr__(
            self,
            "intensity",
            quantize_score(
                require_confidence("EmotionIntensity.intensity", self.intensity)
            ),
        )

    def __repr__(self) -> str:
        return (
            f"EmotionIntensity(kind={self.kind.value!r}, "
            f"band={intensity_band(self.intensity).value!r})"
        )


@dataclass(frozen=True, slots=True)
class EmotionRegulationPolicy:
    """Versioned per-kind decay, gain, and clamp policy for emotional state."""

    policy_version: str
    enabled_kinds: tuple[EmotionKind, ...]
    decay_rates: Mapping[EmotionKind, float]
    gain_caps: Mapping[EmotionKind, float]
    floors: Mapping[EmotionKind, float]
    ceilings: Mapping[EmotionKind, float]
    baselines: Mapping[EmotionKind, float]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            require_bounded_text(
                "EmotionRegulationPolicy.policy_version",
                self.policy_version,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        if isinstance(self.enabled_kinds, (set, frozenset, Mapping)):
            raise TypeError("EmotionRegulationPolicy.enabled_kinds: not_ordered")
        if isinstance(self.enabled_kinds, (str, bytes)) or not isinstance(
            self.enabled_kinds, Sequence
        ):
            raise TypeError("EmotionRegulationPolicy.enabled_kinds: not_ordered")
        enabled = tuple(self.enabled_kinds)
        if not enabled:
            raise ValueError("EmotionRegulationPolicy.enabled_kinds: empty")
        seen: set[EmotionKind] = set()
        for kind in enabled:
            if type(kind) is not EmotionKind:
                raise TypeError(
                    "EmotionRegulationPolicy.enabled_kinds: invalid_entry_type"
                )
            if kind not in DEFAULT_EMOTION_KINDS:
                raise ValueError(
                    "EmotionRegulationPolicy.enabled_kinds: unknown_kind"
                )
            if kind in seen:
                raise ValueError(
                    "EmotionRegulationPolicy.enabled_kinds: duplicate_kind"
                )
            seen.add(kind)
        # Keep catalog order for determinism.
        ordered = tuple(kind for kind in DEFAULT_EMOTION_KINDS if kind in seen)
        object.__setattr__(self, "enabled_kinds", ordered)

        def _map(
            name: str,
            raw: Mapping[EmotionKind, float],
            *,
            allow_zero: bool = True,
        ) -> dict[EmotionKind, float]:
            if type(raw) is not dict and not isinstance(raw, Mapping):
                raise TypeError(f"{name}: invalid_type")
            if isinstance(raw, (set, frozenset)):
                raise TypeError(f"{name}: invalid_type")
            out: dict[EmotionKind, float] = {}
            for kind in ordered:
                if kind not in raw:
                    raise ValueError(f"{name}: incomplete_set")
                value = require_confidence(f"{name}[{kind.value}]", raw[kind])
                if not allow_zero and value <= 0.0:
                    raise ValueError(f"{name}: non_positive")
                out[kind] = quantize_score(value)
            for key in raw:
                if type(key) is not EmotionKind:
                    raise TypeError(f"{name}: invalid_key_type")
                if key not in seen:
                    raise ValueError(f"{name}: disabled_kind")
            return out

        decay = _map("EmotionRegulationPolicy.decay_rates", self.decay_rates)
        gains = _map("EmotionRegulationPolicy.gain_caps", self.gain_caps)
        floors = _map("EmotionRegulationPolicy.floors", self.floors)
        ceilings = _map("EmotionRegulationPolicy.ceilings", self.ceilings)
        baselines = _map("EmotionRegulationPolicy.baselines", self.baselines)
        for kind in ordered:
            if floors[kind] > ceilings[kind]:
                raise ValueError("EmotionRegulationPolicy: floor_above_ceiling")
            if baselines[kind] < floors[kind] or baselines[kind] > ceilings[kind]:
                raise ValueError("EmotionRegulationPolicy: baseline_out_of_bounds")
            if gains[kind] > ceilings[kind]:
                raise ValueError("EmotionRegulationPolicy: gain_above_ceiling")
        object.__setattr__(self, "decay_rates", dict(decay))
        object.__setattr__(self, "gain_caps", dict(gains))
        object.__setattr__(self, "floors", dict(floors))
        object.__setattr__(self, "ceilings", dict(ceilings))
        object.__setattr__(self, "baselines", dict(baselines))

    def __repr__(self) -> str:
        return (
            f"EmotionRegulationPolicy(policy_version={self.policy_version!r}, "
            f"enabled_kind_count={len(self.enabled_kinds)})"
        )


def default_emotion_regulation_policy(
    *,
    enabled_kinds: Sequence[EmotionKind] | None = None,
) -> EmotionRegulationPolicy:
    """Return the default ``emotion.v1`` regulation policy."""
    kinds = (
        tuple(DEFAULT_EMOTION_KINDS)
        if enabled_kinds is None
        else tuple(enabled_kinds)
    )
    decay = {kind: 0.15 for kind in kinds}
    gains = {kind: 0.85 for kind in kinds}
    floors = {kind: 0.0 for kind in kinds}
    ceilings = {kind: 1.0 for kind in kinds}
    baselines = {kind: 0.0 for kind in kinds}
    return EmotionRegulationPolicy(
        policy_version=DEFAULT_EMOTION_POLICY_VERSION,
        enabled_kinds=kinds,
        decay_rates=decay,
        gain_caps=gains,
        floors=floors,
        ceilings=ceilings,
        baselines=baselines,
    )


@dataclass(frozen=True, slots=True)
class AgentEmotionalState:
    """Owner-scoped transient emotion vector (subjective; not world state)."""

    owner_id: AgentId
    tick: int
    intensities: tuple[EmotionIntensity, ...]
    last_update_tick: int
    policy_version: str

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("AgentEmotionalState.owner_id: invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("AgentEmotionalState.tick", self.tick),
        )
        object.__setattr__(
            self,
            "last_update_tick",
            require_exact_nonneg_int(
                "AgentEmotionalState.last_update_tick", self.last_update_tick
            ),
        )
        if self.last_update_tick > self.tick:
            raise ValueError("AgentEmotionalState.last_update_tick: ahead_of_tick")
        object.__setattr__(
            self,
            "policy_version",
            require_bounded_text(
                "AgentEmotionalState.policy_version",
                self.policy_version,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        if isinstance(self.intensities, (set, frozenset, Mapping)):
            raise TypeError("AgentEmotionalState.intensities: not_ordered")
        if isinstance(self.intensities, (str, bytes)) or not isinstance(
            self.intensities, Sequence
        ):
            raise TypeError("AgentEmotionalState.intensities: not_ordered")
        items = tuple(self.intensities)
        if len(items) > len(DEFAULT_EMOTION_KINDS):
            raise ValueError("AgentEmotionalState.intensities: too_many")
        seen: set[EmotionKind] = set()
        for entry in items:
            if type(entry) is not EmotionIntensity:
                raise TypeError("AgentEmotionalState.intensities: invalid_entry_type")
            if entry.kind not in DEFAULT_EMOTION_KINDS:
                raise ValueError("AgentEmotionalState.intensities: unknown_kind")
            if entry.kind in seen:
                raise ValueError("AgentEmotionalState.intensities: duplicate_kind")
            seen.add(entry.kind)
        # Stable catalog order among present kinds.
        by_kind = {entry.kind: entry for entry in items}
        ordered = tuple(
            by_kind[kind] for kind in DEFAULT_EMOTION_KINDS if kind in by_kind
        )
        object.__setattr__(self, "intensities", ordered)

    def intensity_map(self) -> dict[EmotionKind, float]:
        """Return a kind→quantized intensity mapping (copy)."""
        return {entry.kind: entry.intensity for entry in self.intensities}

    def get(self, kind: EmotionKind) -> float:
        """Return intensity for ``kind``, or ``0.0`` when absent/disabled."""
        if type(kind) is not EmotionKind:
            raise TypeError("AgentEmotionalState.get: invalid_kind")
        for entry in self.intensities:
            if entry.kind is kind:
                return entry.intensity
        return 0.0

    def max_intensity(self) -> float:
        """Return the maximum quantized intensity, or ``0.0`` when empty."""
        if not self.intensities:
            return 0.0
        return max(entry.intensity for entry in self.intensities)

    def is_neutral(self) -> bool:
        """True when every present intensity is zero (or vector empty)."""
        return all(entry.intensity == 0.0 for entry in self.intensities)

    def __repr__(self) -> str:
        max_band = intensity_band(self.max_intensity()).value
        return (
            f"AgentEmotionalState(owner_id={self.owner_id.value!r}, "
            f"tick={self.tick}, kind_count={len(self.intensities)}, "
            f"max_intensity_band={max_band!r}, "
            f"last_update_tick={self.last_update_tick}, "
            f"policy_version={self.policy_version!r})"
        )


def empty_emotional_state(
    owner_id: AgentId,
    *,
    tick: int = 0,
    policy_version: str = DEFAULT_EMOTION_POLICY_VERSION,
    enabled_kinds: Sequence[EmotionKind] | None = None,
) -> AgentEmotionalState:
    """Build a zero-intensity emotional state for ``owner_id``."""
    if type(owner_id) is not AgentId:
        raise TypeError("empty_emotional_state: invalid_owner_type")
    kinds = (
        tuple(DEFAULT_EMOTION_KINDS)
        if enabled_kinds is None
        else tuple(enabled_kinds)
    )
    ordered = tuple(kind for kind in DEFAULT_EMOTION_KINDS if kind in set(kinds))
    intensities = tuple(
        EmotionIntensity(kind=kind, intensity=0.0) for kind in ordered
    )
    return AgentEmotionalState(
        owner_id=owner_id,
        tick=tick,
        intensities=intensities,
        last_update_tick=tick,
        policy_version=policy_version,
    )


@dataclass(frozen=True, slots=True)
class EmotionalStateEvaluation:
    """Frozen stage output from ``EMOTIONAL_STATE`` appraisal."""

    owner_id: AgentId
    tick: int
    state: AgentEmotionalState
    driver_codes: tuple[EmotionDriverCode, ...]
    confidence: float
    policy_version: str
    decision_metadata: DecisionMetadata = DecisionMetadata()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("EmotionalStateEvaluation.owner_id: invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("EmotionalStateEvaluation.tick", self.tick),
        )
        if type(self.state) is not AgentEmotionalState:
            raise TypeError("EmotionalStateEvaluation.state: invalid_type")
        if self.state.owner_id != self.owner_id:
            raise ValueError("EmotionalStateEvaluation.state: owner_mismatch")
        if self.state.tick != self.tick:
            raise ValueError("EmotionalStateEvaluation.state: tick_mismatch")
        if isinstance(self.driver_codes, (set, frozenset, Mapping)):
            raise TypeError("EmotionalStateEvaluation.driver_codes: not_ordered")
        if isinstance(self.driver_codes, (str, bytes)) or not isinstance(
            self.driver_codes, Sequence
        ):
            raise TypeError("EmotionalStateEvaluation.driver_codes: not_ordered")
        codes = tuple(self.driver_codes)
        if len(codes) > _MAX_SELECTION_CODES:
            raise ValueError("EmotionalStateEvaluation.driver_codes: too_many")
        seen: set[EmotionDriverCode] = set()
        for code in codes:
            if type(code) is not EmotionDriverCode:
                raise TypeError(
                    "EmotionalStateEvaluation.driver_codes: invalid_entry_type"
                )
            if code in seen:
                raise ValueError(
                    "EmotionalStateEvaluation.driver_codes: duplicate_code"
                )
            seen.add(code)
        object.__setattr__(self, "driver_codes", codes)
        object.__setattr__(
            self,
            "confidence",
            require_confidence(
                "EmotionalStateEvaluation.confidence", self.confidence
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_bounded_text(
                "EmotionalStateEvaluation.policy_version",
                self.policy_version,
                max_length=_MAX_COMPONENT_VERSION_CHARS,
            ),
        )
        if type(self.decision_metadata) is not DecisionMetadata:
            raise TypeError(
                "EmotionalStateEvaluation.decision_metadata: invalid_type"
            )

    def __repr__(self) -> str:
        return (
            f"EmotionalStateEvaluation(owner_id={self.owner_id.value!r}, "
            f"tick={self.tick}, kind_count={len(self.state.intensities)}, "
            f"driver_count={len(self.driver_codes)}, "
            f"max_intensity_band="
            f"{intensity_band(self.state.max_intensity()).value!r}, "
            f"policy_version={self.policy_version!r})"
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
        identity=None,
    )


def _chain_memory_ids(
    history: SemanticBeliefHistory,
) -> tuple[tuple[MemoryId, ...], tuple[MemoryId, ...]]:
    latest: dict[str, tuple[str, MemoryId]] = {}
    order: list[str] = []
    for revision in history.revisions:
        grouped = (
            ("supporting", revision.evidence.supporting),
            ("contradicting", revision.evidence.contradicting),
        )
        for stance, items in grouped:
            for item in items:
                key = item.memory_id.value
                if key not in latest:
                    order.append(key)
                latest[key] = (stance, item.memory_id)
    supporting = tuple(
        latest[key][1] for key in order if latest[key][0] == "supporting"
    )
    contradicting = tuple(
        latest[key][1] for key in order if latest[key][0] == "contradicting"
    )
    return supporting, contradicting


def _reason_code(exc: ValueError) -> str:
    text = str(exc)
    if ": " in text:
        return text.rsplit(": ", 1)[-1]
    return "invalid"


def _history_revision_inputs(
    history: SemanticBeliefHistory,
) -> tuple[tuple[IdentityRevisionPoint, ...], tuple[IdentityRevisionSummary, ...]]:
    points: list[IdentityRevisionPoint] = []
    summaries: list[IdentityRevisionSummary] = []
    previous_contradictions = 0
    for revision in history.revisions:
        contradiction_count = len(revision.evidence.contradicting)
        contradicted = contradiction_count > previous_contradictions
        previous_contradictions = contradiction_count
        points.append(
            IdentityRevisionPoint(
                ordinal=revision.ordinal,
                tick=revision.logical_tick,
                confidence=revision.confidence.confidence,
                contradicted=contradicted,
            )
        )
        summaries.append(
            IdentityRevisionSummary(
                ordinal=revision.ordinal,
                tick=revision.logical_tick,
                activation=revision.activation_state,
            )
        )
    return tuple(points), tuple(summaries)


def project_identity_state(
    *,
    owner_id: AgentId,
    histories: Sequence[SemanticBeliefHistory],
    policy: IdentityPolicy | None = None,
    dissonance_notices: Sequence[IdentityDissonanceNotice] = (),
) -> IdentityState:
    """Project identity views. Unknown predicate segments fail closed."""
    if type(owner_id) is not AgentId:
        raise TypeError("project_identity_state: invalid_owner")
    active = policy if policy is not None else IdentityPolicy()
    if type(active) is not IdentityPolicy:
        raise TypeError("project_identity_state: invalid_policy")
    if isinstance(histories, (set, frozenset, Mapping)):
        raise TypeError("project_identity_state.histories: not_ordered")
    if isinstance(histories, (str, bytes)) or not isinstance(histories, Sequence):
        raise TypeError("project_identity_state.histories: not_ordered")
    views: list[IdentityBeliefView] = []
    seen: set[str] = set()
    for history in histories:
        if type(history) is not SemanticBeliefHistory:
            raise TypeError("project_identity_state: invalid_history")
        belief = history.belief
        if belief.owner_id != owner_id:
            _LOG.error(
                "identity_projection_rejected",
                extra={
                    "reason_code": "owner_mismatch",
                    "owner_id": owner_id.value,
                },
            )
            raise ValueError("project_identity_state: owner_mismatch")
        predicate = belief.claim.predicate
        if predicate.split(".", 1)[0] != "identity":
            continue
        try:
            aspect, provenance, token = parse_identity_predicate(predicate)
        except ValueError as exc:
            code = _reason_code(exc)
            _LOG.error(
                "identity_projection_rejected",
                extra={"reason_code": code, "owner_id": owner_id.value},
            )
            raise
        if (
            belief.claim.value.kind is not BeliefValueKind.BOOL
            or belief.claim.value.bool_value is not True
        ):
            continue
        if belief.activation_state is BeliefActivationState.RETIRED:
            continue
        if belief.activation_state not in (
            BeliefActivationState.CANDIDATE,
            BeliefActivationState.ACTIVE,
        ):
            continue
        if belief.confidence.confidence < active.min_confidence:
            continue
        if belief.belief_id.value in seen:
            raise ValueError("project_identity_state: duplicate_belief_id")
        seen.add(belief.belief_id.value)
        points, summaries = _history_revision_inputs(history)
        support_ids, contradict_ids = _chain_memory_ids(history)
        views.append(
            IdentityBeliefView(
                belief_id=belief.belief_id,
                aspect=aspect,
                provenance=provenance,
                evidence_token=token,
                claim=belief.claim,
                confidence=belief.confidence.confidence,
                derived_rate=derive_identity_rate(
                    support_count=belief.evidence_support_count,
                    contradiction_count=belief.evidence_contradiction_count,
                ),
                supporting_memory_ids=support_ids,
                contradicting_memory_ids=contradict_ids,
                derived_stability=derive_identity_stability(points, policy=active),
                activation=belief.activation_state,
                revisions=summaries,
            )
        )
    views.sort(
        key=lambda item: (
            item.aspect.value,
            item.provenance.value,
            -item.confidence,
            item.belief_id.value,
        )
    )
    selected = tuple(views[: active.max_beliefs])
    return IdentityState(
        owner_id=owner_id,
        policy_id=IDENTITY_POLICY_ID,
        policy_version=IDENTITY_POLICY_VERSION,
        views=selected,
        aggregate_confidence=aggregate_identity_confidence(selected),
        dissonance_notices=tuple(dissonance_notices),
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
class PerceivedNeedPressures:
    """Physiology-derived need pressures in unit interval form."""

    hunger: float
    thirst: float
    fatigue: float
    health: float
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "hunger",
            require_confidence("PerceivedNeedPressures.hunger", self.hunger),
        )
        object.__setattr__(
            self,
            "thirst",
            require_confidence("PerceivedNeedPressures.thirst", self.thirst),
        )
        object.__setattr__(
            self,
            "fatigue",
            require_confidence("PerceivedNeedPressures.fatigue", self.fatigue),
        )
        object.__setattr__(
            self,
            "health",
            require_confidence("PerceivedNeedPressures.health", self.health),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("PerceivedNeedPressures.confidence", self.confidence),
        )

    def __repr__(self) -> str:
        return f"PerceivedNeedPressures(confidence={self.confidence})"


@dataclass(frozen=True, slots=True)
class DriveEffect:
    """Expected signed effect on one independent drive."""

    kind: DriveKind
    delta: float
    confidence: float

    def __post_init__(self) -> None:
        if type(self.kind) is not DriveKind:
            raise TypeError("DriveEffect.kind: invalid_type")
        object.__setattr__(
            self, "delta", require_signed_unit("DriveEffect.delta", self.delta)
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("DriveEffect.confidence", self.confidence),
        )

    def __repr__(self) -> str:
        return f"DriveEffect(kind={self.kind.value!r})"


@dataclass(frozen=True, slots=True)
class GoalEffect:
    """Expected signed progress effect on one active goal."""

    goal_id: GoalId
    progress_delta: float
    confidence: float

    def __post_init__(self) -> None:
        if type(self.goal_id) is not GoalId:
            raise TypeError("GoalEffect.goal_id: invalid_type")
        object.__setattr__(
            self,
            "progress_delta",
            require_signed_unit("GoalEffect.progress_delta", self.progress_delta),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("GoalEffect.confidence", self.confidence),
        )

    def __repr__(self) -> str:
        return f"GoalEffect(goal_id={self.goal_id.value!r})"


@dataclass(frozen=True, slots=True)
class SocialEffect:
    """Expected signed affinity effect toward one counterpart (or anonymous)."""

    counterpart_id: AgentId | None
    affinity_delta: float
    confidence: float

    def __post_init__(self) -> None:
        if self.counterpart_id is not None and type(self.counterpart_id) is not AgentId:
            raise TypeError("SocialEffect.counterpart_id: invalid_type")
        object.__setattr__(
            self,
            "affinity_delta",
            require_signed_unit("SocialEffect.affinity_delta", self.affinity_delta),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("SocialEffect.confidence", self.confidence),
        )

    def __repr__(self) -> str:
        counterpart = None if self.counterpart_id is None else self.counterpart_id.value
        return f"SocialEffect(counterpart_id={counterpart!r})"


@dataclass(frozen=True, slots=True)
class SubjectiveRisk:
    """Typed subjective risk estimate for one imagined future."""

    kind: SubjectiveRiskKind
    severity: float
    likelihood: float
    confidence: float

    def __post_init__(self) -> None:
        if type(self.kind) is not SubjectiveRiskKind:
            raise TypeError("SubjectiveRisk.kind: invalid_type")
        object.__setattr__(
            self,
            "severity",
            require_confidence("SubjectiveRisk.severity", self.severity),
        )
        object.__setattr__(
            self,
            "likelihood",
            require_confidence("SubjectiveRisk.likelihood", self.likelihood),
        )
        object.__setattr__(
            self,
            "confidence",
            require_confidence("SubjectiveRisk.confidence", self.confidence),
        )

    def __repr__(self) -> str:
        return f"SubjectiveRisk(kind={self.kind.value!r})"


@dataclass(frozen=True, slots=True)
class SubjectiveUncertainty:
    """Epistemic/aleatory uncertainty with a closed magnitude band."""

    epistemic: float = 0.0
    aleatory: float = 0.0
    band: UncertaintyBand = UncertaintyBand.LOW

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "epistemic",
            require_confidence("SubjectiveUncertainty.epistemic", self.epistemic),
        )
        object.__setattr__(
            self,
            "aleatory",
            require_confidence("SubjectiveUncertainty.aleatory", self.aleatory),
        )
        if type(self.band) is not UncertaintyBand:
            raise TypeError("SubjectiveUncertainty.band: invalid_type")

    def __repr__(self) -> str:
        return f"SubjectiveUncertainty(band={self.band.value!r})"


@dataclass(frozen=True, slots=True)
class OptionSpaceChange:
    """Expected change in perceived future option space."""

    retained_options_ratio: float = 1.0
    foreclosed_ratio: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "retained_options_ratio",
            require_confidence(
                "OptionSpaceChange.retained_options_ratio", self.retained_options_ratio
            ),
        )
        object.__setattr__(
            self,
            "foreclosed_ratio",
            require_confidence(
                "OptionSpaceChange.foreclosed_ratio", self.foreclosed_ratio
            ),
        )

    def __repr__(self) -> str:
        return (
            f"OptionSpaceChange(retained_options_ratio={self.retained_options_ratio}, "
            f"foreclosed_ratio={self.foreclosed_ratio})"
        )


@dataclass(frozen=True, slots=True)
class MortalityOpportunityForeclosure:
    """Anticipatory fear of death as opportunity foreclosure (no death_penalty).

    ``composite`` is derived deterministically as a quantized weighted sum of the
    component unit values, scaled by ``death_probability``:

    ``composite = quantize(death_probability * (
        0.30 * outstanding_goal_value
        + 0.20 * attachment_loss
        + 0.20 * safety_activation
        + 0.15 * autonomy_loss
        + 0.15 * option_space.foreclosed_ratio
    ))``

    Component weights sum to ``1.0``. Callers may pass any ``composite``; it is
    always overwritten with the derived value.
    """

    death_probability: float
    outstanding_goal_value: float
    attachment_loss: float
    safety_activation: float
    autonomy_loss: float
    option_space: OptionSpaceChange
    composite: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "death_probability",
            require_confidence(
                "MortalityOpportunityForeclosure.death_probability",
                self.death_probability,
            ),
        )
        object.__setattr__(
            self,
            "outstanding_goal_value",
            require_confidence(
                "MortalityOpportunityForeclosure.outstanding_goal_value",
                self.outstanding_goal_value,
            ),
        )
        object.__setattr__(
            self,
            "attachment_loss",
            require_confidence(
                "MortalityOpportunityForeclosure.attachment_loss",
                self.attachment_loss,
            ),
        )
        object.__setattr__(
            self,
            "safety_activation",
            require_confidence(
                "MortalityOpportunityForeclosure.safety_activation",
                self.safety_activation,
            ),
        )
        object.__setattr__(
            self,
            "autonomy_loss",
            require_confidence(
                "MortalityOpportunityForeclosure.autonomy_loss",
                self.autonomy_loss,
            ),
        )
        if type(self.option_space) is not OptionSpaceChange:
            raise TypeError(
                "MortalityOpportunityForeclosure.option_space: invalid_type"
            )
        weighted = (
            _MORTALITY_WEIGHT_GOAL * self.outstanding_goal_value
            + _MORTALITY_WEIGHT_ATTACHMENT * self.attachment_loss
            + _MORTALITY_WEIGHT_SAFETY * self.safety_activation
            + _MORTALITY_WEIGHT_AUTONOMY * self.autonomy_loss
            + _MORTALITY_WEIGHT_OPTIONS * self.option_space.foreclosed_ratio
        )
        object.__setattr__(
            self,
            "composite",
            _quantize_unit(self.death_probability * weighted),
        )

    def __repr__(self) -> str:
        return (
            f"MortalityOpportunityForeclosure("
            f"death_probability={self.death_probability}, "
            f"composite={self.composite})"
        )


@dataclass(frozen=True, slots=True)
class FutureSourceRef:
    """Ordered unique subjective provenance IDs (no payloads)."""

    belief_ids: tuple[str, ...] = ()
    memory_ids: tuple[str, ...] = ()
    relationship_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "belief_ids",
            _require_stable_id_tuple(
                "FutureSourceRef.belief_ids",
                self.belief_ids,
                max_items=_MAX_SOURCE_REFS,
            ),
        )
        object.__setattr__(
            self,
            "memory_ids",
            _require_stable_id_tuple(
                "FutureSourceRef.memory_ids",
                self.memory_ids,
                max_items=_MAX_SOURCE_REFS,
            ),
        )
        object.__setattr__(
            self,
            "relationship_ids",
            _require_stable_id_tuple(
                "FutureSourceRef.relationship_ids",
                self.relationship_ids,
                max_items=_MAX_SOURCE_REFS,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"FutureSourceRef(belief_count={len(self.belief_ids)}, "
            f"memory_count={len(self.memory_ids)}, "
            f"relationship_count={len(self.relationship_ids)})"
        )


def _require_drive_effects(
    name: str, values: Sequence[object]
) -> tuple[DriveEffect, ...]:
    effects = _require_ordered_model_tuple(
        name, values, model_type=DriveEffect, max_items=_MAX_EFFECTS
    )
    seen: set[DriveKind] = set()
    for effect in effects:
        if effect.kind in seen:
            raise ValueError(f"{name}: duplicate_kind")
        seen.add(effect.kind)
    return effects


def _require_goal_effects(
    name: str, values: Sequence[object]
) -> tuple[GoalEffect, ...]:
    effects = _require_ordered_model_tuple(
        name, values, model_type=GoalEffect, max_items=_MAX_EFFECTS
    )
    seen: set[str] = set()
    for effect in effects:
        if effect.goal_id.value in seen:
            raise ValueError(f"{name}: duplicate_goal_id")
        seen.add(effect.goal_id.value)
    return effects


def _require_social_effects(
    name: str, values: Sequence[object]
) -> tuple[SocialEffect, ...]:
    effects = _require_ordered_model_tuple(
        name, values, model_type=SocialEffect, max_items=_MAX_EFFECTS
    )
    seen: set[str | None] = set()
    for effect in effects:
        key = None if effect.counterpart_id is None else effect.counterpart_id.value
        if key in seen:
            raise ValueError(f"{name}: duplicate_counterpart")
        seen.add(key)
    return effects


def _require_risks(name: str, values: Sequence[object]) -> tuple[SubjectiveRisk, ...]:
    risks = _require_ordered_model_tuple(
        name, values, model_type=SubjectiveRisk, max_items=_MAX_RISKS
    )
    seen: set[SubjectiveRiskKind] = set()
    for risk in risks:
        if risk.kind in seen:
            raise ValueError(f"{name}: duplicate_kind")
        seen.add(risk.kind)
    return risks


@dataclass(frozen=True, slots=True)
class ImaginedFuture:
    """One bounded imagined future with independent effect and risk vectors.

    Legacy construction ``ImaginedFuture(future_id, claim_codes, confidence)``
    remains valid: new fields default to safe empty/neutral values.
    """

    future_id: str
    claim_codes: tuple[SituationClaimCode, ...]
    confidence: float
    direction: ActionDirection = ActionDirection.WAIT
    target_entity_id: str | None = None
    target_agent_id: AgentId | None = None
    horizon_ticks: int = 1
    drive_effects: tuple[DriveEffect, ...] = ()
    goal_effects: tuple[GoalEffect, ...] = ()
    social_effects: tuple[SocialEffect, ...] = ()
    risks: tuple[SubjectiveRisk, ...] = ()
    uncertainty: SubjectiveUncertainty = SubjectiveUncertainty()
    mortality: MortalityOpportunityForeclosure | None = None
    subjective_probability: float | None = None
    source_refs: FutureSourceRef = FutureSourceRef()

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
        if type(self.direction) is not ActionDirection:
            raise TypeError("ImaginedFuture.direction: invalid_type")
        if self.target_entity_id is not None:
            object.__setattr__(
                self,
                "target_entity_id",
                require_stable_id(
                    "ImaginedFuture.target_entity_id", self.target_entity_id
                ),
            )
        if self.target_agent_id is not None and type(self.target_agent_id) is not (
            AgentId
        ):
            raise TypeError("ImaginedFuture.target_agent_id: invalid_type")
        object.__setattr__(
            self,
            "horizon_ticks",
            _require_positive_int("ImaginedFuture.horizon_ticks", self.horizon_ticks),
        )
        object.__setattr__(
            self,
            "drive_effects",
            _require_drive_effects("ImaginedFuture.drive_effects", self.drive_effects),
        )
        object.__setattr__(
            self,
            "goal_effects",
            _require_goal_effects("ImaginedFuture.goal_effects", self.goal_effects),
        )
        object.__setattr__(
            self,
            "social_effects",
            _require_social_effects(
                "ImaginedFuture.social_effects", self.social_effects
            ),
        )
        object.__setattr__(
            self,
            "risks",
            _require_risks("ImaginedFuture.risks", self.risks),
        )
        if type(self.uncertainty) is not SubjectiveUncertainty:
            raise TypeError("ImaginedFuture.uncertainty: invalid_type")
        if self.mortality is not None and type(self.mortality) is not (
            MortalityOpportunityForeclosure
        ):
            raise TypeError("ImaginedFuture.mortality: invalid_type")
        if self.subjective_probability is None:
            object.__setattr__(self, "subjective_probability", self.confidence)
        else:
            object.__setattr__(
                self,
                "subjective_probability",
                require_confidence(
                    "ImaginedFuture.subjective_probability",
                    self.subjective_probability,
                ),
            )
        if type(self.source_refs) is not FutureSourceRef:
            raise TypeError("ImaginedFuture.source_refs: invalid_type")

    def __repr__(self) -> str:
        return (
            f"ImaginedFuture(future_id={self.future_id!r}, "
            f"direction={self.direction.value!r}, "
            f"claim_count={len(self.claim_codes)}, "
            f"drive_effect_count={len(self.drive_effects)}, "
            f"goal_effect_count={len(self.goal_effects)}, "
            f"social_effect_count={len(self.social_effects)}, "
            f"risk_count={len(self.risks)}, "
            f"horizon_ticks={self.horizon_ticks}, "
            f"confidence={self.confidence})"
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
class FutureAppraisal:
    """Per-future appraisal retaining independent effect and risk vectors."""

    future_id: str
    drive_effects: tuple[DriveEffect, ...] = ()
    goal_effects: tuple[GoalEffect, ...] = ()
    risks: tuple[SubjectiveRisk, ...] = ()
    mortality: MortalityOpportunityForeclosure | None = None
    uncertainty: SubjectiveUncertainty = SubjectiveUncertainty()
    support_drive_count: int = 0
    support_goal_count: int = 0
    support_social_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "future_id",
            require_stable_id("FutureAppraisal.future_id", self.future_id),
        )
        object.__setattr__(
            self,
            "drive_effects",
            _require_drive_effects("FutureAppraisal.drive_effects", self.drive_effects),
        )
        object.__setattr__(
            self,
            "goal_effects",
            _require_goal_effects("FutureAppraisal.goal_effects", self.goal_effects),
        )
        object.__setattr__(
            self,
            "risks",
            _require_risks("FutureAppraisal.risks", self.risks),
        )
        if self.mortality is not None and type(self.mortality) is not (
            MortalityOpportunityForeclosure
        ):
            raise TypeError("FutureAppraisal.mortality: invalid_type")
        if type(self.uncertainty) is not SubjectiveUncertainty:
            raise TypeError("FutureAppraisal.uncertainty: invalid_type")
        object.__setattr__(
            self,
            "support_drive_count",
            require_exact_nonneg_int(
                "FutureAppraisal.support_drive_count", self.support_drive_count
            ),
        )
        object.__setattr__(
            self,
            "support_goal_count",
            require_exact_nonneg_int(
                "FutureAppraisal.support_goal_count", self.support_goal_count
            ),
        )
        object.__setattr__(
            self,
            "support_social_count",
            require_exact_nonneg_int(
                "FutureAppraisal.support_social_count", self.support_social_count
            ),
        )

    def __repr__(self) -> str:
        return (
            f"FutureAppraisal(future_id={self.future_id!r}, "
            f"drive_effect_count={len(self.drive_effects)}, "
            f"goal_effect_count={len(self.goal_effects)}, "
            f"risk_count={len(self.risks)}, "
            f"support_drive_count={self.support_drive_count}, "
            f"support_goal_count={self.support_goal_count}, "
            f"support_social_count={self.support_social_count})"
        )


@dataclass(frozen=True, slots=True)
class MotivationEvaluation:
    """Ordered motive scores plus independent future appraisals."""

    owner_id: AgentId
    scores: tuple[MotivationScore, ...]
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()
    appraisals: tuple[FutureAppraisal, ...] = ()
    active_drive_kinds: tuple[DriveKind, ...] = ()
    active_goal_ids: tuple[GoalId, ...] = ()

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
        appraisals = _require_ordered_model_tuple(
            "MotivationEvaluation.appraisals",
            self.appraisals,
            model_type=FutureAppraisal,
            max_items=_MAX_APPRAISALS,
        )
        seen_futures: set[str] = set()
        for appraisal in appraisals:
            if appraisal.future_id in seen_futures:
                raise ValueError("MotivationEvaluation.appraisals: duplicate_future_id")
            seen_futures.add(appraisal.future_id)
        object.__setattr__(self, "appraisals", appraisals)
        object.__setattr__(
            self,
            "active_drive_kinds",
            _require_ordered_enum(
                "MotivationEvaluation.active_drive_kinds",
                self.active_drive_kinds,
                enum_type=DriveKind,
            ),
        )
        object.__setattr__(
            self,
            "active_goal_ids",
            require_ordered_unique(
                "MotivationEvaluation.active_goal_ids",
                self.active_goal_ids,
                item_type=GoalId,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"MotivationEvaluation(owner_id={self.owner_id.value!r}, "
            f"score_count={len(self.scores)}, "
            f"appraisal_count={len(self.appraisals)}, "
            f"active_drive_count={len(self.active_drive_kinds)}, "
            f"active_goal_count={len(self.active_goal_ids)}, "
            f"confidence={self.confidence})"
        )


@dataclass(frozen=True, slots=True)
class SelectedIntention:
    """Single selected intention from motivation evaluation."""

    owner_id: AgentId
    intention: IntentionCode
    source_motive: MotivationCode | None
    confidence: float
    decision_metadata: DecisionMetadata = DecisionMetadata()
    selected_future_id: str | None = None
    direction: ActionDirection | None = None
    appraisal_future_ids: tuple[str, ...] = ()

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
        if self.selected_future_id is not None:
            object.__setattr__(
                self,
                "selected_future_id",
                require_stable_id(
                    "SelectedIntention.selected_future_id", self.selected_future_id
                ),
            )
        if self.direction is not None and type(self.direction) is not ActionDirection:
            raise TypeError("SelectedIntention.direction: invalid_type")
        object.__setattr__(
            self,
            "appraisal_future_ids",
            _require_stable_id_tuple(
                "SelectedIntention.appraisal_future_ids",
                self.appraisal_future_ids,
                max_items=_MAX_APPRAISALS,
            ),
        )

    def __repr__(self) -> str:
        direction = None if self.direction is None else self.direction.value
        return (
            f"SelectedIntention(owner_id={self.owner_id.value!r}, "
            f"intention={self.intention.value!r}, "
            f"selected_future_id={self.selected_future_id!r}, "
            f"direction={direction!r}, "
            f"appraisal_count={len(self.appraisal_future_ids)}, "
            f"confidence={self.confidence})"
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
        GoalBoard,
        EmotionalStateEvaluation,
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
class CognitiveLoopProposal:
    """Deliberation result through planning without memory updates or next state.

    Trusted binding must call ``CognitiveLoop.complete`` with the effective
    command before command-dependent memory intents or ``last_command_kind``
    are derived. The proposed command must not be used for those stages when
    an intervention substitutes a different effective command.
    """

    invocation_id: str
    agent_id: AgentId
    loop_input: CognitiveLoopInput
    perception: InterpretedPerception
    memory: RetrievedMemoryContext
    situation: SituationModel
    self_state: SelfModel
    goal_board: GoalBoard
    emotional_state: EmotionalStateEvaluation
    futures: PossibleFutures
    motivation: MotivationEvaluation
    intention: SelectedIntention
    plan: ActionPlan
    proposed_command: AgentCommand
    boundary_records: tuple[ComponentBoundaryRecord, ...]
    final_confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "invocation_id",
            require_stable_id(
                "CognitiveLoopProposal.invocation_id", self.invocation_id
            ),
        )
        if type(self.agent_id) is not AgentId:
            raise TypeError("CognitiveLoopProposal.agent_id must be AgentId")
        if type(self.loop_input) is not CognitiveLoopInput:
            raise TypeError(
                "CognitiveLoopProposal.loop_input must be CognitiveLoopInput"
            )
        if self.loop_input.agent_id != self.agent_id:
            raise ValueError("CognitiveLoopProposal agent_id mismatch")
        if type(self.perception) is not InterpretedPerception:
            raise TypeError("perception must be InterpretedPerception")
        if type(self.memory) is not RetrievedMemoryContext:
            raise TypeError("memory must be RetrievedMemoryContext")
        if type(self.situation) is not SituationModel:
            raise TypeError("situation must be SituationModel")
        if type(self.self_state) is not SelfModel:
            raise TypeError("self_state must be SelfModel")
        if type(self.goal_board) is not GoalBoard:
            raise TypeError("goal_board must be GoalBoard")
        if self.goal_board.owner_id != self.agent_id:
            raise ValueError("goal_board owner_id mismatch")
        if type(self.emotional_state) is not EmotionalStateEvaluation:
            raise TypeError("emotional_state must be EmotionalStateEvaluation")
        if self.emotional_state.owner_id != self.agent_id:
            raise ValueError("emotional_state owner_id mismatch")
        if type(self.futures) is not PossibleFutures:
            raise TypeError("futures must be PossibleFutures")
        if type(self.motivation) is not MotivationEvaluation:
            raise TypeError("motivation must be MotivationEvaluation")
        if type(self.intention) is not SelectedIntention:
            raise TypeError("intention must be SelectedIntention")
        if type(self.plan) is not ActionPlan:
            raise TypeError("plan must be ActionPlan")
        object.__setattr__(
            self, "proposed_command", require_agent_command(self.proposed_command)
        )
        if self.plan.command != self.proposed_command:
            raise ValueError("proposed_command must match plan.command")
        if isinstance(self.boundary_records, (set, frozenset, Mapping)):
            raise TypeError("boundary_records must be ordered")
        if isinstance(self.boundary_records, (str, bytes)) or not isinstance(
            self.boundary_records, Sequence
        ):
            raise TypeError("boundary_records must be ordered")
        records = tuple(self.boundary_records)
        for record in records:
            if type(record) is not ComponentBoundaryRecord:
                raise TypeError(
                    "boundary_records entries must be ComponentBoundaryRecord"
                )
            if record.invocation_id != self.invocation_id:
                raise ValueError("boundary record invocation_id mismatch")
            if record.component_kind is ComponentKind.MEMORY_UPDATE:
                raise ValueError("proposal must not include MEMORY_UPDATE boundaries")
        object.__setattr__(self, "boundary_records", records)
        object.__setattr__(
            self,
            "final_confidence",
            require_confidence(
                "CognitiveLoopProposal.final_confidence", self.final_confidence
            ),
        )

    def __repr__(self) -> str:
        return (
            f"CognitiveLoopProposal(invocation_id={self.invocation_id!r}, "
            f"agent_id={self.agent_id.value!r}, "
            f"proposed_command_type={type(self.proposed_command).__name__}, "
            f"boundary_count={len(self.boundary_records)})"
        )


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
    pending_semanticization: BeliefRevisionRequest | None = None
    offline_consolidation: object | None = None
    reflection: object | None = None
    identity_revisions: tuple[BeliefRevisionRequest, ...] = ()
    identity_dissonance: tuple[IdentityDissonanceNotice, ...] = ()

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
        if self.pending_semanticization is not None:
            if type(self.pending_semanticization) is not BeliefRevisionRequest:
                raise TypeError(
                    "CognitiveLoopResult.pending_semanticization must be "
                    "BeliefRevisionRequest"
                )
            if self.pending_semanticization.owner_id != self.agent_id:
                raise ValueError("pending_semanticization owner must match agent_id")
        if self.offline_consolidation is not None:
            from agents.cognition.consolidation import OfflineConsolidationPlan

            if type(self.offline_consolidation) is not OfflineConsolidationPlan:
                raise TypeError(
                    "CognitiveLoopResult.offline_consolidation: invalid_type"
                )
            if self.offline_consolidation.audit.owner_id != self.agent_id:
                raise ValueError("offline_consolidation owner must match agent_id")
        if self.reflection is not None:
            from agents.cognition.reflection import ReflectionPlan

            if type(self.reflection) is not ReflectionPlan:
                raise TypeError("CognitiveLoopResult.reflection: invalid_type")
            if self.reflection.audit.owner_id != self.agent_id:
                raise ValueError("reflection owner must match agent_id")
        if isinstance(self.identity_revisions, (set, frozenset, Mapping)):
            raise TypeError("CognitiveLoopResult.identity_revisions must be ordered")
        if isinstance(self.identity_revisions, (str, bytes)) or not isinstance(
            self.identity_revisions, Sequence
        ):
            raise TypeError("CognitiveLoopResult.identity_revisions must be ordered")
        identity_revisions = tuple(self.identity_revisions)
        for request in identity_revisions:
            if type(request) is not BeliefRevisionRequest:
                raise TypeError(
                    "CognitiveLoopResult.identity_revisions entries must be "
                    "BeliefRevisionRequest"
                )
            if request.owner_id != self.agent_id:
                raise ValueError("identity revision owner must match agent_id")
        object.__setattr__(self, "identity_revisions", identity_revisions)
        if isinstance(self.identity_dissonance, (set, frozenset, Mapping)):
            raise TypeError("CognitiveLoopResult.identity_dissonance must be ordered")
        if isinstance(self.identity_dissonance, (str, bytes)) or not isinstance(
            self.identity_dissonance, Sequence
        ):
            raise TypeError("CognitiveLoopResult.identity_dissonance must be ordered")
        identity_dissonance = tuple(self.identity_dissonance)
        for notice in identity_dissonance:
            if type(notice) is not IdentityDissonanceNotice:
                raise TypeError(
                    "CognitiveLoopResult.identity_dissonance entries must be "
                    "IdentityDissonanceNotice"
                )
            if notice.owner_id != self.agent_id:
                raise ValueError("identity dissonance owner must match agent_id")
        object.__setattr__(self, "identity_dissonance", identity_dissonance)
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
            f"has_semanticization={self.pending_semanticization is not None}, "
            f"identity_revision_count={len(self.identity_revisions)}, "
            f"identity_dissonance_count={len(self.identity_dissonance)}, "
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
