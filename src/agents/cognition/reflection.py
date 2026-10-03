"""Periodic metacognition contracts.

Model construction and the pattern policy are log-free. Trigger evaluation may
DEBUG codes only. This module never imports ``world.events`` or ``simulation``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from agents.cognition.models import GoalTransitionIntent, GoalTransitionIntentReason
from agents.models import (
    AgentId,
    Goal,
    GoalHorizon,
    GoalId,
    GoalOriginKind,
    GoalOutcome,
    GoalOutcomeKind,
    GoalProvenance,
    GoalStatus,
)
from llm import (
    LLMProvider,
    LLMRequest,
    LLMRequestContext,
    StructuredOutput,
    render_prompt,
)
from llm.errors import LLMError
from memory.belief_formation import (
    DEFAULT_BELIEF_FORMATION_POLICY,
    belief_id_for_claim,
)
from memory.beliefs import (
    BeliefActivationState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticBelief,
    SemanticClaim,
    canonical_subject_predicate_key,
)
from memory.models import (
    EntityMention,
    MemoryRelation,
    MemoryTrace,
    RelationEndpointKind,
    quantize_score,
)
from social.relationships import (
    DEFAULT_RELATIONSHIP_POLICY,
    RelationshipInteractionSignal,
    RelationshipRevisionRequest,
    RelationshipSignalKind,
)
from world.identifiers import (
    EntityId,
    require_bounded_text,
    require_exact_nonneg_int,
    require_stable_id,
)

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.reflection")

REFLECTION_POLICY_VERSION: Final[str] = "reflection-v1"
_DEFAULT_INTERVAL_TICKS: Final[int] = 8
_DEFAULT_EMOTION_INTENSITY: Final[float] = 0.7
_DEFAULT_CONTRADICTION_MASS: Final[float] = 0.5
_DEFAULT_CONTRADICTION_COUNT: Final[int] = 2
_DEFAULT_REPEATED_FAILURE_COUNT: Final[int] = 3
_DEFAULT_MIN_PATTERN_COUNT: Final[int] = 3
_DEFAULT_MAX_MEMORIES: Final[int] = 16
_DEFAULT_SIGNIFICANT_OCCURRENCE_COUNT: Final[int] = 1
_DEFAULT_MAX_DECISION_RECORDS: Final[int] = 32
_MAX_OCCURRENCE_KINDS: Final[int] = 32
_MAX_EVIDENCE_IDS: Final[int] = 64
_MAX_KIND_COUNTS: Final[int] = 16
_MAX_TEXT: Final[int] = 128

_CLOSED_MODES: Final[frozenset[str]] = frozenset(
    {"disabled", "deterministic", "llm_assisted"}
)
_HELP_PREDICATES: Final[frozenset[str]] = frozenset(
    {"help_received", "help_given", "is_helpful"}
)
_BANNED_CONTEXT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "WorldState",
        "WorldEvent",
        "RecallAuditRecord",
        "EventRepository",
    }
)


class ReflectionTriggerKind(StrEnum):
    """Closed reasons a gap-eligible pass may run."""

    ELAPSED_TICKS = "elapsed_ticks"
    SIGNIFICANT_OCCURRENCES = "significant_occurrences"
    STRONG_EMOTION = "strong_emotion"
    REPEATED_FAILURE = "repeated_failure"
    MAJOR_GOAL_COMPLETION = "major_goal_completion"
    BELIEF_CONTRADICTION = "belief_contradiction"
    RELATIONSHIP_CHANGE = "relationship_change"


class ReflectionConclusionKind(StrEnum):
    """Closed writers a reflection pass may emit."""

    REVISED_BELIEF = "revised_belief"
    NEW_HYPOTHESIS = "new_hypothesis"
    NEW_LONG_TERM_GOAL = "new_long_term_goal"
    ABANDONED_GOAL = "abandoned_goal"
    UPDATED_SELF_BELIEF = "updated_self_belief"
    RELATIONSHIP_REASSESSMENT = "relationship_reassessment"


class ReflectionPatternCode(StrEnum):
    """Closed pattern labels. Not stored belief predicates."""

    REPEATED_ACTION = "repeated_action"
    PREDICTION_ERROR = "prediction_error"
    REPEATED_HELP = "repeated_help"
    REPEATED_FAILURE = "repeated_failure"


class DecisionOutcomeCode(StrEnum):
    """Subjective outcome of a previously recorded command."""

    NO_PROGRESS = "no_progress"
    PERCEIVED_CHANGE = "perceived_change"
    UNKNOWN = "unknown"


def _positive_int(name: str, value: object) -> int:
    number = require_exact_nonneg_int(name, value)
    if number < 1:
        raise ValueError(f"{name}: not_positive")
    return number


def _quantized_unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_finite")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    quantized = quantize_score(number)
    if quantized < 0.0 or quantized > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    return quantized


def _ordered_texts(name: str, values: object, *, max_items: int) -> tuple[str, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name}: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name}: not_ordered")
    items = tuple(values)
    if len(items) > max_items:
        raise ValueError(f"{name}: exceeds_max_length")
    copied: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = require_bounded_text(name, item, max_length=_MAX_TEXT)
        if text in seen:
            raise ValueError(f"{name}: duplicate")
        seen.add(text)
        copied.append(text)
    return tuple(copied)


def _nonempty_evidence_ids(name: str, values: object) -> tuple[str, ...]:
    ids = _ordered_texts(name, values, max_items=_MAX_EVIDENCE_IDS)
    if not ids:
        raise ValueError(f"{name}: empty_evidence")
    for item in ids:
        require_stable_id(name, item)
    return ids


@dataclass(frozen=True, slots=True)
class ReflectionPolicy:
    """Quantized ``reflection-v1`` knobs. Not a runner JSON document."""

    version: str = REFLECTION_POLICY_VERSION
    interval_ticks: int = _DEFAULT_INTERVAL_TICKS
    min_gap_ticks: int | None = None
    emotion_intensity: float = _DEFAULT_EMOTION_INTENSITY
    contradiction_mass: float = _DEFAULT_CONTRADICTION_MASS
    contradiction_count: int = _DEFAULT_CONTRADICTION_COUNT
    repeated_failure_count: int = _DEFAULT_REPEATED_FAILURE_COUNT
    min_pattern_count: int = _DEFAULT_MIN_PATTERN_COUNT
    max_memories: int = _DEFAULT_MAX_MEMORIES
    significant_occurrence_count: int = _DEFAULT_SIGNIFICANT_OCCURRENCE_COUNT
    significant_occurrence_kinds: tuple[str, ...] = ()
    major_goal_horizons: tuple[GoalHorizon, ...] = (
        GoalHorizon.DESIRE,
        GoalHorizon.LONG_TERM,
    )
    max_decision_records: int = _DEFAULT_MAX_DECISION_RECORDS
    allow_provider: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "version",
            require_bounded_text(
                "ReflectionPolicy.version", self.version, max_length=_MAX_TEXT
            ),
        )
        if self.version != REFLECTION_POLICY_VERSION:
            raise ValueError("ReflectionPolicy.version: unsupported")
        interval = _positive_int("ReflectionPolicy.interval_ticks", self.interval_ticks)
        object.__setattr__(self, "interval_ticks", interval)
        gap = interval if self.min_gap_ticks is None else self.min_gap_ticks
        object.__setattr__(
            self,
            "min_gap_ticks",
            _positive_int("ReflectionPolicy.min_gap_ticks", gap),
        )
        object.__setattr__(
            self,
            "emotion_intensity",
            _quantized_unit(
                "ReflectionPolicy.emotion_intensity", self.emotion_intensity
            ),
        )
        object.__setattr__(
            self,
            "contradiction_mass",
            _quantized_unit(
                "ReflectionPolicy.contradiction_mass", self.contradiction_mass
            ),
        )
        object.__setattr__(
            self,
            "contradiction_count",
            _positive_int(
                "ReflectionPolicy.contradiction_count", self.contradiction_count
            ),
        )
        object.__setattr__(
            self,
            "repeated_failure_count",
            _positive_int(
                "ReflectionPolicy.repeated_failure_count", self.repeated_failure_count
            ),
        )
        object.__setattr__(
            self,
            "min_pattern_count",
            _positive_int("ReflectionPolicy.min_pattern_count", self.min_pattern_count),
        )
        object.__setattr__(
            self,
            "max_memories",
            _positive_int("ReflectionPolicy.max_memories", self.max_memories),
        )
        object.__setattr__(
            self,
            "significant_occurrence_count",
            _positive_int(
                "ReflectionPolicy.significant_occurrence_count",
                self.significant_occurrence_count,
            ),
        )
        object.__setattr__(
            self,
            "significant_occurrence_kinds",
            _ordered_texts(
                "ReflectionPolicy.significant_occurrence_kinds",
                self.significant_occurrence_kinds,
                max_items=_MAX_OCCURRENCE_KINDS,
            ),
        )
        horizons = _ordered_horizons(self.major_goal_horizons)
        object.__setattr__(self, "major_goal_horizons", horizons)
        object.__setattr__(
            self,
            "max_decision_records",
            _positive_int(
                "ReflectionPolicy.max_decision_records", self.max_decision_records
            ),
        )
        if type(self.allow_provider) is not bool:
            raise TypeError("ReflectionPolicy.allow_provider: invalid_type")

    def __repr__(self) -> str:
        return (
            f"ReflectionPolicy(version={self.version!r}, "
            f"interval_ticks={self.interval_ticks}, "
            f"min_gap_ticks={self.min_gap_ticks}, "
            f"allow_provider={self.allow_provider})"
        )


def default_reflection_policy(*, allow_provider: bool = False) -> ReflectionPolicy:
    """Frozen ``reflection-v1`` defaults. Provider stays off unless requested."""

    if type(allow_provider) is not bool:
        raise TypeError("default_reflection_policy: invalid_allow_provider")
    return ReflectionPolicy(allow_provider=allow_provider)


def _ordered_horizons(values: object) -> tuple[GoalHorizon, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError("ReflectionPolicy.major_goal_horizons: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("ReflectionPolicy.major_goal_horizons: not_ordered")
    items = tuple(values)
    if not items:
        raise ValueError("ReflectionPolicy.major_goal_horizons: empty")
    if len(items) > len(GoalHorizon):
        raise ValueError("ReflectionPolicy.major_goal_horizons: exceeds_max_length")
    seen: set[GoalHorizon] = set()
    copied: list[GoalHorizon] = []
    for item in items:
        if type(item) is not GoalHorizon:
            raise TypeError("ReflectionPolicy.major_goal_horizons: invalid_type")
        if item in seen:
            raise ValueError("ReflectionPolicy.major_goal_horizons: duplicate")
        seen.add(item)
        copied.append(item)
    return tuple(copied)


@dataclass(frozen=True, slots=True)
class SubjectiveDecisionRecord:
    """One owner-scoped command remembered between ticks. Not an objective event."""

    record_id: str
    owner_id: AgentId
    tick: int
    command_kind: str
    outcome_code: DecisionOutcomeCode
    day_phase: str | None = None
    place_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "record_id",
            require_stable_id("SubjectiveDecisionRecord.record_id", self.record_id),
        )
        if type(self.owner_id) is not AgentId:
            raise TypeError("SubjectiveDecisionRecord.owner_id: invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("SubjectiveDecisionRecord.tick", self.tick),
        )
        object.__setattr__(
            self,
            "command_kind",
            require_bounded_text(
                "SubjectiveDecisionRecord.command_kind",
                self.command_kind,
                max_length=_MAX_TEXT,
            ),
        )
        if type(self.outcome_code) is not DecisionOutcomeCode:
            raise TypeError("SubjectiveDecisionRecord.outcome_code: invalid_type")
        if self.day_phase is not None:
            object.__setattr__(
                self,
                "day_phase",
                require_bounded_text(
                    "SubjectiveDecisionRecord.day_phase",
                    self.day_phase,
                    max_length=_MAX_TEXT,
                ),
            )
        if self.place_id is not None:
            object.__setattr__(
                self,
                "place_id",
                require_stable_id("SubjectiveDecisionRecord.place_id", self.place_id),
            )

    def __repr__(self) -> str:
        return (
            f"SubjectiveDecisionRecord(record_id={self.record_id!r}, "
            f"owner_id={self.owner_id.value!r}, tick={self.tick}, "
            f"command_kind={self.command_kind!r}, "
            f"outcome_code={self.outcome_code.value!r})"
        )


@dataclass(frozen=True, slots=True)
class RelationshipOrdinalMark:
    """Ordinal already seen for one directed pair. Not a relationship label."""

    source_id: AgentId
    target_id: AgentId
    ordinal: int

    def __post_init__(self) -> None:
        if type(self.source_id) is not AgentId:
            raise TypeError("RelationshipOrdinalMark.source_id: invalid_type")
        if type(self.target_id) is not AgentId:
            raise TypeError("RelationshipOrdinalMark.target_id: invalid_type")
        if self.source_id == self.target_id:
            raise ValueError("RelationshipOrdinalMark: self_target")
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("RelationshipOrdinalMark.ordinal", self.ordinal),
        )

    def __repr__(self) -> str:
        return (
            f"RelationshipOrdinalMark(source_id={self.source_id.value!r}, "
            f"target_id={self.target_id.value!r}, ordinal={self.ordinal})"
        )


@dataclass(frozen=True, slots=True)
class ReflectionCursor:
    """Gap and acknowledgement state.

    ``last_reflection_tick`` stays ``None`` until a pass is applied.
    """

    owner_id: AgentId
    last_reflection_tick: int | None = None
    acknowledged_goal_ids: tuple[GoalId, ...] = ()
    relationship_ordinals: tuple[RelationshipOrdinalMark, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("ReflectionCursor.owner_id: invalid_type")
        if self.last_reflection_tick is not None:
            object.__setattr__(
                self,
                "last_reflection_tick",
                require_exact_nonneg_int(
                    "ReflectionCursor.last_reflection_tick",
                    self.last_reflection_tick,
                ),
            )
        object.__setattr__(
            self,
            "acknowledged_goal_ids",
            _ordered_goal_ids(self.acknowledged_goal_ids),
        )
        object.__setattr__(
            self,
            "relationship_ordinals",
            _ordered_ordinals(self.relationship_ordinals),
        )

    def __repr__(self) -> str:
        return (
            f"ReflectionCursor(owner_id={self.owner_id.value!r}, "
            f"last_reflection_tick={self.last_reflection_tick}, "
            f"acknowledged_goal_count={len(self.acknowledged_goal_ids)}, "
            f"relationship_mark_count={len(self.relationship_ordinals)})"
        )


def _ordered_goal_ids(values: object) -> tuple[GoalId, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError("ReflectionCursor.acknowledged_goal_ids: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("ReflectionCursor.acknowledged_goal_ids: not_ordered")
    items = tuple(values)
    if len(items) > _MAX_EVIDENCE_IDS:
        raise ValueError("ReflectionCursor.acknowledged_goal_ids: exceeds_max_length")
    seen: set[str] = set()
    copied: list[GoalId] = []
    for item in items:
        if type(item) is not GoalId:
            raise TypeError("ReflectionCursor.acknowledged_goal_ids: invalid_type")
        if item.value in seen:
            raise ValueError("ReflectionCursor.acknowledged_goal_ids: duplicate")
        seen.add(item.value)
        copied.append(item)
    return tuple(copied)


def _ordered_ordinals(
    values: object,
) -> tuple[RelationshipOrdinalMark, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError("ReflectionCursor.relationship_ordinals: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("ReflectionCursor.relationship_ordinals: not_ordered")
    items = tuple(values)
    if len(items) > _MAX_EVIDENCE_IDS:
        raise ValueError("ReflectionCursor.relationship_ordinals: exceeds_max_length")
    seen: set[tuple[str, str]] = set()
    copied: list[RelationshipOrdinalMark] = []
    for item in items:
        if type(item) is not RelationshipOrdinalMark:
            raise TypeError("ReflectionCursor.relationship_ordinals: invalid_type")
        key = (item.source_id.value, item.target_id.value)
        if key in seen:
            raise ValueError("ReflectionCursor.relationship_ordinals: duplicate")
        seen.add(key)
        copied.append(item)
    return tuple(copied)


@dataclass(frozen=True, slots=True)
class ReflectionCandidate:
    """One closed conclusion drawn only from cited subjective evidence ids."""

    candidate_id: str
    owner_id: AgentId
    tick: int
    kind: ReflectionConclusionKind
    pattern_code: ReflectionPatternCode
    evidence_ids: tuple[str, ...]
    count: int
    predicate: str | None = None
    counterpart_id: str | None = None
    place_id: str | None = None
    command_kind: str | None = None
    day_phase: str | None = None
    belief_request: BeliefRevisionRequest | None = None
    relationship_request: RelationshipRevisionRequest | None = None
    goal_intent: GoalTransitionIntent | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            require_stable_id("ReflectionCandidate.candidate_id", self.candidate_id),
        )
        if type(self.owner_id) is not AgentId:
            raise TypeError("ReflectionCandidate.owner_id: invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ReflectionCandidate.tick", self.tick),
        )
        if type(self.kind) is not ReflectionConclusionKind:
            raise TypeError("ReflectionCandidate.kind: invalid_type")
        if type(self.pattern_code) is not ReflectionPatternCode:
            raise TypeError("ReflectionCandidate.pattern_code: invalid_type")
        object.__setattr__(
            self,
            "evidence_ids",
            _nonempty_evidence_ids(
                "ReflectionCandidate.evidence_ids", self.evidence_ids
            ),
        )
        object.__setattr__(
            self,
            "count",
            _positive_int("ReflectionCandidate.count", self.count),
        )
        if self.predicate is not None:
            object.__setattr__(
                self,
                "predicate",
                require_bounded_text(
                    "ReflectionCandidate.predicate",
                    self.predicate,
                    max_length=_MAX_TEXT,
                ),
            )
        if self.counterpart_id is not None:
            object.__setattr__(
                self,
                "counterpart_id",
                require_stable_id(
                    "ReflectionCandidate.counterpart_id", self.counterpart_id
                ),
            )
        if self.place_id is not None:
            object.__setattr__(
                self,
                "place_id",
                require_stable_id("ReflectionCandidate.place_id", self.place_id),
            )
        if self.command_kind is not None:
            object.__setattr__(
                self,
                "command_kind",
                require_bounded_text(
                    "ReflectionCandidate.command_kind",
                    self.command_kind,
                    max_length=_MAX_TEXT,
                ),
            )
        if self.day_phase is not None:
            object.__setattr__(
                self,
                "day_phase",
                require_bounded_text(
                    "ReflectionCandidate.day_phase",
                    self.day_phase,
                    max_length=_MAX_TEXT,
                ),
            )
        if (
            self.belief_request is not None
            and type(self.belief_request) is not BeliefRevisionRequest
        ):
            raise TypeError("ReflectionCandidate.belief_request: invalid_type")
        if (
            self.relationship_request is not None
            and type(self.relationship_request) is not RelationshipRevisionRequest
        ):
            raise TypeError("ReflectionCandidate.relationship_request: invalid_type")
        if self.goal_intent is not None and type(self.goal_intent) is not (
            GoalTransitionIntent
        ):
            raise TypeError("ReflectionCandidate.goal_intent: invalid_type")
        if self.belief_request is not None and self.goal_intent is not None:
            raise ValueError("ReflectionCandidate: belief_and_goal")
        if self.belief_request is not None:
            for evidence_id in self.evidence_ids:
                if not any(
                    item.memory_id.value == evidence_id
                    for item in self.belief_request.evidence.supporting
                ):
                    raise ValueError("ReflectionCandidate: evidence_not_on_request")

    def __repr__(self) -> str:
        return (
            f"ReflectionCandidate(candidate_id={self.candidate_id!r}, "
            f"owner_id={self.owner_id.value!r}, tick={self.tick}, "
            f"kind={self.kind.value!r}, pattern_code={self.pattern_code.value!r}, "
            f"evidence_count={len(self.evidence_ids)}, count={self.count})"
        )


@dataclass(frozen=True, slots=True)
class ReflectionAudit:
    """In-run metadata. Counts and reason codes only; no claim text."""

    owner_id: AgentId
    tick: int
    mode: str
    trigger_codes: tuple[str, ...]
    conclusion_kind_counts: tuple[tuple[str, int], ...]
    evidence_id_count: int
    fallback_used: bool
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("ReflectionAudit.owner_id: invalid_type")
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("ReflectionAudit.tick", self.tick)
        )
        if type(self.mode) is not str or self.mode not in _CLOSED_MODES:
            raise ValueError("ReflectionAudit.mode: invalid_mode")
        object.__setattr__(
            self,
            "trigger_codes",
            _trigger_codes(self.trigger_codes),
        )
        object.__setattr__(
            self,
            "conclusion_kind_counts",
            _kind_counts(self.conclusion_kind_counts),
        )
        object.__setattr__(
            self,
            "evidence_id_count",
            require_exact_nonneg_int(
                "ReflectionAudit.evidence_id_count", self.evidence_id_count
            ),
        )
        if type(self.fallback_used) is not bool:
            raise TypeError("ReflectionAudit.fallback_used: invalid_type")
        if self.reason_code is not None:
            object.__setattr__(
                self,
                "reason_code",
                require_bounded_text(
                    "ReflectionAudit.reason_code",
                    self.reason_code,
                    max_length=_MAX_TEXT,
                ),
            )

    def __repr__(self) -> str:
        return (
            f"ReflectionAudit(owner_id={self.owner_id.value!r}, tick={self.tick}, "
            f"mode={self.mode!r}, trigger_count={len(self.trigger_codes)}, "
            f"conclusion_kind_count={len(self.conclusion_kind_counts)}, "
            f"evidence_id_count={self.evidence_id_count}, "
            f"fallback_used={self.fallback_used}, "
            f"reason_code={self.reason_code!r})"
        )


def _trigger_codes(values: object) -> tuple[str, ...]:
    texts = _ordered_texts(
        "ReflectionAudit.trigger_codes", values, max_items=len(ReflectionTriggerKind)
    )
    allowed = {item.value for item in ReflectionTriggerKind}
    for text in texts:
        if text not in allowed:
            raise ValueError("ReflectionAudit.trigger_codes: invalid_code")
    return texts


def _kind_counts(values: object) -> tuple[tuple[str, int], ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError("ReflectionAudit.conclusion_kind_counts: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("ReflectionAudit.conclusion_kind_counts: not_ordered")
    items = tuple(values)
    if len(items) > _MAX_KIND_COUNTS:
        raise ValueError("ReflectionAudit.conclusion_kind_counts: exceeds_max_length")
    allowed = {item.value for item in ReflectionConclusionKind}
    seen: set[str] = set()
    copied: list[tuple[str, int]] = []
    for item in items:
        if (
            isinstance(item, (str, bytes))
            or not isinstance(item, tuple)
            or len(item) != 2
        ):
            raise TypeError("ReflectionAudit.conclusion_kind_counts: invalid_type")
        kind, count = item
        if type(kind) is not str or kind not in allowed:
            raise ValueError("ReflectionAudit.conclusion_kind_counts: invalid_code")
        if kind in seen:
            raise ValueError("ReflectionAudit.conclusion_kind_counts: duplicate")
        seen.add(kind)
        copied.append(
            (
                kind,
                require_exact_nonneg_int(
                    "ReflectionAudit.conclusion_kind_counts", count
                ),
            )
        )
    return tuple(copied)


@dataclass(frozen=True, slots=True)
class ReflectionContext:
    """Owner-scoped subjective inputs for one reflection pass.

    Construction rejects objective event types, foreign owners, and empty
    provenance on later candidates. It does not read world state.
    """

    owner_id: AgentId
    tick: int
    policy: ReflectionPolicy
    memories: tuple[MemoryTrace, ...] = ()
    beliefs: tuple[SemanticBelief, ...] = ()
    goals: tuple[Goal, ...] = ()
    decisions: tuple[SubjectiveDecisionRecord, ...] = ()
    owner_entity_id: EntityId | None = None
    cited_memory_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("ReflectionContext.owner_id: invalid_type")
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("ReflectionContext.tick", self.tick)
        )
        if type(self.policy) is not ReflectionPolicy:
            raise TypeError("ReflectionContext.policy: invalid_type")
        if self.owner_entity_id is not None and type(self.owner_entity_id) is not (
            EntityId
        ):
            raise TypeError("ReflectionContext.owner_entity_id: invalid_type")
        object.__setattr__(self, "memories", _owned_models(self.memories, MemoryTrace))
        object.__setattr__(
            self, "beliefs", _owned_models(self.beliefs, SemanticBelief)
        )
        object.__setattr__(self, "goals", _owned_models(self.goals, Goal))
        object.__setattr__(
            self, "decisions", _owned_models(self.decisions, SubjectiveDecisionRecord)
        )
        for item in (
            *self.memories,
            *self.beliefs,
            *self.goals,
            *self.decisions,
        ):
            owner = getattr(item, "owner_id", None)
            if owner != self.owner_id:
                raise ValueError("ReflectionContext: owner_mismatch")
        object.__setattr__(
            self,
            "cited_memory_ids",
            _ordered_texts(
                "ReflectionContext.cited_memory_ids",
                self.cited_memory_ids,
                max_items=_MAX_EVIDENCE_IDS,
            ),
        )


def materialize_reflection_candidates(
    context: ReflectionContext,
) -> tuple[ReflectionCandidate, ...]:
    """Closed ``reflection-v1`` candidates. Identical inputs stay identical."""

    if type(context) is not ReflectionContext:
        raise TypeError("materialize_reflection_candidates: invalid_context")
    selected = _select_memories(context)
    candidates = [
        *_relation_candidates(context, selected),
        *_decision_candidates(context),
    ]
    candidates.sort(
        key=lambda item: (
            item.pattern_code.value,
            item.kind.value,
            item.candidate_id,
        )
    )
    return tuple(candidates)


def _owned_models(values: object, model_type: type) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError("ReflectionContext: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("ReflectionContext: not_ordered")
    items = tuple(values)
    copied: list[object] = []
    for item in items:
        _reject_forbidden_input(item)
        if type(item) is not model_type:
            raise TypeError("ReflectionContext: invalid_item_type")
        copied.append(item)
    return tuple(copied)


def _reject_forbidden_input(item: object) -> None:
    kind = type(item)
    module = kind.__module__
    if kind.__name__ in _BANNED_CONTEXT_TYPES or module.startswith(
        ("world.events", "simulation.replay", "simulation.journal")
    ):
        raise ValueError("ReflectionContext: forbidden_input")


def _select_memories(context: ReflectionContext) -> tuple[MemoryTrace, ...]:
    places = {
        record.place_id
        for record in context.decisions
        if record.place_id is not None and record.outcome_code is not (
            DecisionOutcomeCode.UNKNOWN
        )
    }
    cited = set(context.cited_memory_ids)

    def _preferred(trace: MemoryTrace) -> int:
        location = trace.context.location_id
        located = location is not None and location.value in places
        if trace.memory_id.value in cited or located:
            return 0
        return 1

    ordered = sorted(
        context.memories,
        key=lambda trace: (
            _preferred(trace),
            trace.source_tick,
            trace.memory_id.value,
        ),
    )
    return tuple(ordered[: context.policy.max_memories])


def _relation_candidates(
    context: ReflectionContext,
    traces: tuple[MemoryTrace, ...],
) -> list[ReflectionCandidate]:
    grouped: dict[tuple[str, str, str], list[MemoryTrace]] = {}
    for trace in traces:
        seen_in_trace: set[tuple[str, str, str]] = set()
        for relation in trace.relations:
            counterpart = _counterpart(trace, relation, context.owner_entity_id)
            if counterpart is None or counterpart == context.owner_id.value:
                continue
            pattern = (
                ReflectionPatternCode.REPEATED_HELP
                if relation.predicate in _HELP_PREDICATES
                else ReflectionPatternCode.REPEATED_ACTION
            )
            key = (pattern.value, relation.predicate, counterpart)
            if key in seen_in_trace:
                continue
            seen_in_trace.add(key)
            grouped.setdefault(key, []).append(trace)
    emitted: list[ReflectionCandidate] = []
    minimum = context.policy.min_pattern_count
    for key in sorted(grouped):
        members = grouped[key]
        if len(members) < minimum:
            continue
        pattern = ReflectionPatternCode(key[0])
        predicate = key[1]
        counterpart = key[2]
        evidence = tuple(trace.memory_id.value for trace in members)
        subject = _claim_subject(context.owner_id, pattern, counterpart)
        claim = SemanticClaim(
            subject=subject,
            predicate=predicate,
            value=ClaimValue(
                kind=BeliefValueKind.NUMBER,
                number_value=float(len(members)),
            ),
        )
        existing = _existing_belief(context.beliefs, claim)
        belief = _belief_request(context, claim, members, existing)
        kind = _belief_kind(context.owner_id, subject, existing)
        root = _evidence_root(kind.value, pattern.value, evidence)
        emitted.append(
            _candidate(
                context=context,
                kind=kind,
                pattern=pattern,
                evidence=evidence,
                count=len(members),
                predicate=predicate,
                counterpart_id=counterpart,
                candidate_suffix=root,
                belief_request=belief,
            )
        )
        relationship = _relationship_request(
            context, counterpart, members, pattern
        )
        if relationship is not None:
            emitted.append(
                _candidate(
                    context=context,
                    kind=ReflectionConclusionKind.RELATIONSHIP_REASSESSMENT,
                    pattern=pattern,
                    evidence=evidence,
                    count=len(members),
                    predicate=predicate,
                    counterpart_id=counterpart,
                    candidate_suffix=f"{root}-rel",
                    relationship_request=relationship,
                )
            )
    return emitted


def _decision_candidates(context: ReflectionContext) -> list[ReflectionCandidate]:
    filled = tuple(
        record
        for record in context.decisions
        if record.outcome_code is DecisionOutcomeCode.NO_PROGRESS
    )
    emitted: list[ReflectionCandidate] = []
    failure_groups: dict[tuple[str, str], list[SubjectiveDecisionRecord]] = {}
    prediction_groups: dict[str, list[SubjectiveDecisionRecord]] = {}
    for record in filled:
        phase = record.day_phase or ""
        failure_groups.setdefault((record.command_kind, phase), []).append(record)
        if record.place_id is not None:
            prediction_groups.setdefault(record.place_id, []).append(record)
    minimum = context.policy.min_pattern_count
    for key in sorted(failure_groups):
        members = failure_groups[key]
        if len(members) < minimum:
            continue
        emitted.extend(
            _goal_pattern_candidates(
                context,
                pattern=ReflectionPatternCode.REPEATED_FAILURE,
                members=members,
                command_kind=key[0],
                day_phase=key[1] or None,
                place_id=None,
            )
        )
    for place_id in sorted(prediction_groups):
        members = prediction_groups[place_id]
        if len(members) < minimum:
            continue
        emitted.extend(
            _goal_pattern_candidates(
                context,
                pattern=ReflectionPatternCode.PREDICTION_ERROR,
                members=members,
                command_kind=None,
                day_phase=None,
                place_id=place_id,
            )
        )
    return emitted


def _goal_pattern_candidates(
    context: ReflectionContext,
    *,
    pattern: ReflectionPatternCode,
    members: list[SubjectiveDecisionRecord],
    command_kind: str | None,
    day_phase: str | None,
    place_id: str | None,
) -> list[ReflectionCandidate]:
    evidence = tuple(record.record_id for record in members)
    goal_id = GoalId(
        f"goal-reflection:{context.owner_id.value}:{context.tick}:{pattern.value}"
    )
    adopted = Goal(
        goal_id=goal_id,
        owner_id=context.owner_id,
        description=pattern.value,
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.ACHIEVE_CODE,
            outcome_code=pattern.value,
        ),
        horizon=GoalHorizon.LONG_TERM,
        provenance=GoalProvenance(origin_kind=GoalOriginKind.INFERRED),
        created_tick=context.tick,
        belief_refs=evidence,
    )
    adopt_intent = GoalTransitionIntent(
        goal_id=goal_id,
        owner_id=context.owner_id,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.ACTIVE,
        reason_code=GoalTransitionIntentReason.ADOPTED,
        tick=context.tick,
        resulting_goal=adopted,
    )
    root = _evidence_root(
        ReflectionConclusionKind.NEW_LONG_TERM_GOAL.value, pattern.value, evidence
    )
    emitted = [
        _candidate(
            context=context,
            kind=ReflectionConclusionKind.NEW_LONG_TERM_GOAL,
            pattern=pattern,
            evidence=evidence,
            count=len(members),
            command_kind=command_kind,
            day_phase=day_phase,
            place_id=place_id,
            candidate_suffix=root,
            goal_intent=adopt_intent,
        )
    ]
    evidence_set = set(evidence)
    for goal in context.goals:
        if goal.status is GoalStatus.COMPLETED or goal.goal_id == goal_id:
            continue
        if goal.status is not GoalStatus.ACTIVE:
            continue
        refs_hit = bool(evidence_set.intersection(goal.belief_refs))
        outcome = goal.outcome
        command_hit = (
            command_kind is not None
            and outcome is not None
            and outcome.outcome_code == command_kind
        )
        if not refs_hit and not command_hit:
            continue
        abandoned = replace(goal, status=GoalStatus.ABANDONED)
        abandon_intent = GoalTransitionIntent(
            goal_id=goal.goal_id,
            owner_id=context.owner_id,
            from_status=goal.status,
            to_status=GoalStatus.ABANDONED,
            reason_code=GoalTransitionIntentReason.ABANDONED,
            tick=context.tick,
            resulting_goal=abandoned,
        )
        emitted.append(
            _candidate(
                context=context,
                kind=ReflectionConclusionKind.ABANDONED_GOAL,
                pattern=pattern,
                evidence=evidence,
                count=len(members),
                command_kind=command_kind,
                candidate_suffix=f"{root}-{_short_id(goal.goal_id.value)}",
                goal_intent=abandon_intent,
            )
        )
    return emitted


def causal_counter_goal_candidate(
    context: ReflectionContext,
    model: object | None,
    *,
    existing: tuple[ReflectionCandidate, ...],
) -> ReflectionCandidate | None:
    """Sibling of a prediction-error goal, citing counter-updated hypotheses.

    Hypothesis ids stay off belief revisions and decision-record evidence.
    """
    if model is None:
        return None
    from agents.cognition.world_model import (
        CausalUpdateReason,
        CausalWorldModel,
    )

    if type(context) is not ReflectionContext:
        raise TypeError("causal_counter_goal_candidate: invalid_context")
    if type(model) is not CausalWorldModel:
        raise TypeError("causal_counter_goal_candidate: invalid_model")
    if model.owner_id != context.owner_id:
        raise ValueError("causal_counter_goal_candidate: owner_mismatch")
    cited = tuple(
        sorted(
            item.hypothesis_id
            for item in model.hypotheses
            if item.latest_reason() is CausalUpdateReason.COUNTER
        )
    )
    _LOG.debug(
        "world_model_reflection_prediction_error owner_id=%s tick=%s "
        "hypothesis_count=%s",
        context.owner_id.value,
        context.tick,
        len(cited),
    )
    already = any(
        item.pattern_code is ReflectionPatternCode.PREDICTION_ERROR
        and item.kind is ReflectionConclusionKind.NEW_LONG_TERM_GOAL
        and item.goal_intent is not None
        for item in existing
    )
    if already or not cited:
        return None
    pattern = ReflectionPatternCode.PREDICTION_ERROR
    goal_id = GoalId(
        f"goal-reflection:{context.owner_id.value}:{context.tick}:"
        f"{pattern.value}:causal"
    )
    adopted = Goal(
        goal_id=goal_id,
        owner_id=context.owner_id,
        description=pattern.value,
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.ACHIEVE_CODE,
            outcome_code=pattern.value,
        ),
        horizon=GoalHorizon.LONG_TERM,
        provenance=GoalProvenance(origin_kind=GoalOriginKind.INFERRED),
        created_tick=context.tick,
        belief_refs=cited,
    )
    adopt_intent = GoalTransitionIntent(
        goal_id=goal_id,
        owner_id=context.owner_id,
        from_status=GoalStatus.ACTIVE,
        to_status=GoalStatus.ACTIVE,
        reason_code=GoalTransitionIntentReason.ADOPTED,
        tick=context.tick,
        resulting_goal=adopted,
    )
    return _candidate(
        context=context,
        kind=ReflectionConclusionKind.NEW_LONG_TERM_GOAL,
        pattern=pattern,
        evidence=cited,
        count=len(cited),
        candidate_suffix="causal-counter",
        goal_intent=adopt_intent,
    )


def _candidate(
    *,
    context: ReflectionContext,
    kind: ReflectionConclusionKind,
    pattern: ReflectionPatternCode,
    evidence: tuple[str, ...],
    count: int,
    candidate_suffix: str,
    predicate: str | None = None,
    counterpart_id: str | None = None,
    place_id: str | None = None,
    command_kind: str | None = None,
    day_phase: str | None = None,
    belief_request: BeliefRevisionRequest | None = None,
    relationship_request: RelationshipRevisionRequest | None = None,
    goal_intent: GoalTransitionIntent | None = None,
) -> ReflectionCandidate:
    return ReflectionCandidate(
        candidate_id=f"cand-{pattern.value}-{kind.value}-{candidate_suffix}",
        owner_id=context.owner_id,
        tick=context.tick,
        kind=kind,
        pattern_code=pattern,
        evidence_ids=evidence,
        count=count,
        predicate=predicate,
        counterpart_id=counterpart_id,
        place_id=place_id,
        command_kind=command_kind,
        day_phase=day_phase,
        belief_request=belief_request,
        relationship_request=relationship_request,
        goal_intent=goal_intent,
    )


def _counterpart(
    trace: MemoryTrace,
    relation: MemoryRelation,
    owner_entity_id: EntityId | None,
) -> str | None:
    endpoints = (relation.subject, relation.object)
    entity_ids: list[str] = []
    for endpoint in endpoints:
        if endpoint.kind is not RelationEndpointKind.ENTITY:
            continue
        for mention in trace.entities:
            if type(mention) is not EntityMention:
                continue
            if mention.mention_id != endpoint.mention_id or mention.entity_id is None:
                continue
            entity_ids.append(mention.entity_id.value)
    owner_value = None if owner_entity_id is None else owner_entity_id.value
    others = [item for item in entity_ids if item != owner_value]
    if not others:
        return None
    return others[0]


def _claim_subject(
    owner_id: AgentId, pattern: ReflectionPatternCode, counterpart: str
) -> ClaimSubject:
    if pattern is ReflectionPatternCode.REPEATED_HELP:
        return ClaimSubject(
            kind=ClaimSubjectKind.ENTITY, entity_id=EntityId(counterpart)
        )
    return ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner_id)


def _existing_belief(
    beliefs: tuple[SemanticBelief, ...], claim: SemanticClaim
) -> SemanticBelief | None:
    key = canonical_subject_predicate_key(claim)
    for belief in beliefs:
        if canonical_subject_predicate_key(belief.claim) == key:
            return belief
    return None


def _belief_kind(
    owner_id: AgentId,
    subject: ClaimSubject,
    existing: SemanticBelief | None,
) -> ReflectionConclusionKind:
    if (
        subject.kind is ClaimSubjectKind.AGENT
        and subject.agent_id == owner_id
    ):
        return ReflectionConclusionKind.UPDATED_SELF_BELIEF
    if existing is None:
        return ReflectionConclusionKind.NEW_HYPOTHESIS
    return ReflectionConclusionKind.REVISED_BELIEF


def _belief_request(
    context: ReflectionContext,
    claim: SemanticClaim,
    traces: list[MemoryTrace],
    existing: SemanticBelief | None,
) -> BeliefRevisionRequest:
    contributions = tuple(
        BeliefEvidenceContribution(
            memory_id=trace.memory_id,
            stance=EvidenceStance.SUPPORTING,
            contribution=1.0,
            ordinal=index,
            lineage_root_id=trace.memory_id,
        )
        for index, trace in enumerate(traces)
    )
    evidence = tuple(trace.memory_id.value for trace in traces)
    root = _evidence_root("belief", claim.predicate, evidence)
    belief_id = (
        existing.belief_id
        if existing is not None
        else belief_id_for_claim(owner_id=context.owner_id, claim=claim)
    )
    return BeliefRevisionRequest(
        owner_id=context.owner_id,
        operation_id=f"reflection:{context.tick}:{root}",
        logical_tick=context.tick,
        claim=claim,
        evidence=BeliefEvidenceBundle(supporting=contributions, contradicting=()),
        policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
        belief_id=belief_id,
        expected_revision_ordinal=(
            None if existing is None else existing.revision_ordinal
        ),
        activation_state=(
            BeliefActivationState.CANDIDATE
            if existing is None
            else existing.activation_state
        ),
    )


def _relationship_request(
    context: ReflectionContext,
    counterpart: str,
    traces: list[MemoryTrace],
    pattern: ReflectionPatternCode,
) -> RelationshipRevisionRequest | None:
    if counterpart == context.owner_id.value:
        return None
    target = AgentId(counterpart)
    if target == context.owner_id:
        return None
    kind = (
        RelationshipSignalKind.HELP_RECEIVED
        if pattern is ReflectionPatternCode.REPEATED_HELP
        else RelationshipSignalKind.PROXIMITY
    )
    evidence = tuple(trace.memory_id.value for trace in traces)
    root = _evidence_root("relationship", pattern.value, evidence)
    signals = tuple(
        RelationshipInteractionSignal(
            counterpart_id=target,
            kind=kind,
            strength=1.0,
            memory_ref=trace.memory_id.value,
            lineage_root_ref=trace.memory_id.value,
            source_tick=trace.source_tick,
        )
        for trace in traces
    )
    return RelationshipRevisionRequest(
        source_id=context.owner_id,
        target_id=target,
        operation_id=f"reflection:{context.tick}:{root}",
        logical_tick=context.tick,
        signals=signals,
        policy=DEFAULT_RELATIONSHIP_POLICY.as_ref(),
    )


@dataclass(frozen=True, slots=True)
class ReflectionPlan:
    """Conclusions for a later tick. Repr stores counts, not claim text."""

    audit: ReflectionAudit
    belief_revisions: tuple[BeliefRevisionRequest, ...]
    relationship_revisions: tuple[RelationshipRevisionRequest, ...]
    goal_intents: tuple[GoalTransitionIntent, ...]
    acknowledged_goal_ids: tuple[GoalId, ...]

    def __post_init__(self) -> None:
        if type(self.audit) is not ReflectionAudit:
            raise TypeError("ReflectionPlan.audit: invalid_type")
        object.__setattr__(
            self,
            "belief_revisions",
            _owned_requests(self.belief_revisions, BeliefRevisionRequest),
        )
        object.__setattr__(
            self,
            "relationship_revisions",
            _owned_requests(self.relationship_revisions, RelationshipRevisionRequest),
        )
        object.__setattr__(
            self,
            "goal_intents",
            _owned_requests(self.goal_intents, GoalTransitionIntent),
        )
        object.__setattr__(
            self,
            "acknowledged_goal_ids",
            _ordered_goal_ids(self.acknowledged_goal_ids),
        )
        for request in self.belief_revisions:
            if request.owner_id != self.audit.owner_id:
                raise ValueError("ReflectionPlan: owner_mismatch")
        for request in self.relationship_revisions:
            if request.source_id != self.audit.owner_id:
                raise ValueError("ReflectionPlan: owner_mismatch")
        for intent in self.goal_intents:
            if intent.owner_id != self.audit.owner_id:
                raise ValueError("ReflectionPlan: owner_mismatch")

    def __repr__(self) -> str:
        return (
            f"ReflectionPlan(owner_id={self.audit.owner_id.value!r}, "
            f"tick={self.audit.tick}, mode={self.audit.mode!r}, "
            f"belief_count={len(self.belief_revisions)}, "
            f"relationship_count={len(self.relationship_revisions)}, "
            f"goal_count={len(self.goal_intents)}, "
            f"acknowledged_goal_count={len(self.acknowledged_goal_ids)})"
        )


def plan_reflection(
    *,
    context: ReflectionContext,
    triggers: ReflectionTriggerResult,
    mode: str,
    consolidation: object | None = None,
    acknowledged_goal_ids: tuple[GoalId, ...] = (),
    selected_ids: tuple[str, ...] | None = None,
    fallback_used: bool = False,
    causal_world_model: object | None = None,
) -> ReflectionPlan | None:
    """Materialize a pass when triggers matched. ``None`` means no pass."""

    if type(context) is not ReflectionContext:
        raise TypeError("plan_reflection: invalid_context")
    if type(triggers) is not ReflectionTriggerResult:
        raise TypeError("plan_reflection: invalid_triggers")
    if not triggers.matched:
        return None
    if type(fallback_used) is not bool:
        raise TypeError("plan_reflection: invalid_fallback")
    kept = _drop_consolidation_overlaps(
        drop_unprovenanced_candidates(
            context, materialize_reflection_candidates(context)
        ),
        consolidation,
    )
    if selected_ids is not None:
        kept = _select_candidate_ids(kept, selected_ids)
    sibling = causal_counter_goal_candidate(
        context, causal_world_model, existing=kept
    )
    if sibling is not None:
        kept = (*kept, sibling)
    counts: dict[str, int] = {}
    evidence: set[str] = set()
    beliefs: list[BeliefRevisionRequest] = []
    relationships: list[RelationshipRevisionRequest] = []
    goals: list[GoalTransitionIntent] = []
    for candidate in kept:
        counts[candidate.kind.value] = counts.get(candidate.kind.value, 0) + 1
        evidence.update(candidate.evidence_ids)
        if candidate.belief_request is not None:
            beliefs.append(candidate.belief_request)
        if candidate.relationship_request is not None:
            relationships.append(candidate.relationship_request)
        if candidate.goal_intent is not None:
            goals.append(candidate.goal_intent)
    audit = ReflectionAudit(
        owner_id=context.owner_id,
        tick=context.tick,
        mode=mode,
        trigger_codes=tuple(item.value for item in triggers.matched),
        conclusion_kind_counts=tuple(sorted(counts.items())),
        evidence_id_count=len(evidence),
        fallback_used=fallback_used,
    )
    _LOG.debug(
        "reflection_pending mode=%s triggers=%s belief_count=%s "
        "relationship_count=%s goal_count=%s",
        mode,
        ",".join(audit.trigger_codes),
        len(beliefs),
        len(relationships),
        len(goals),
    )
    return ReflectionPlan(
        audit=audit,
        belief_revisions=tuple(beliefs),
        relationship_revisions=tuple(relationships),
        goal_intents=tuple(goals),
        acknowledged_goal_ids=acknowledged_goal_ids,
    )


def without_applied_operations(
    plan: ReflectionPlan, applied: set[str]
) -> ReflectionPlan:
    """Drop conclusions whose operation id was already committed."""

    if type(plan) is not ReflectionPlan:
        raise TypeError("without_applied_operations: invalid_plan")
    beliefs = tuple(
        item
        for item in plan.belief_revisions
        if item.operation_id not in applied
    )
    relationships = tuple(
        item
        for item in plan.relationship_revisions
        if item.operation_id not in applied
    )
    goals = tuple(
        item
        for item in plan.goal_intents
        if _goal_operation_id(item) not in applied
    )
    if (
        beliefs == plan.belief_revisions
        and relationships == plan.relationship_revisions
        and goals == plan.goal_intents
    ):
        return plan
    return replace(
        plan,
        belief_revisions=beliefs,
        relationship_revisions=relationships,
        goal_intents=goals,
    )


def reflection_operation_ids(plan: ReflectionPlan) -> tuple[str, ...]:
    """Stable operation ids for one applied pass."""

    if type(plan) is not ReflectionPlan:
        raise TypeError("reflection_operation_ids: invalid_plan")
    seen: set[str] = set()
    ordered: list[str] = []
    for request in plan.belief_revisions:
        _remember_operation(seen, ordered, request.operation_id)
    for request in plan.relationship_revisions:
        _remember_operation(seen, ordered, request.operation_id)
    for intent in plan.goal_intents:
        _remember_operation(seen, ordered, _goal_operation_id(intent))
    return tuple(ordered)


def commit_reflection_cursor(
    cursor: ReflectionCursor,
    *,
    tick: int,
    acknowledged_goal_ids: tuple[GoalId, ...],
) -> ReflectionCursor:
    """Record that a pass was applied. Does not append a decision record."""

    if type(cursor) is not ReflectionCursor:
        raise TypeError("commit_reflection_cursor: invalid_cursor")
    merged = list(cursor.acknowledged_goal_ids)
    seen = {item.value for item in merged}
    for goal_id in sorted(acknowledged_goal_ids, key=lambda item: item.value):
        if type(goal_id) is not GoalId:
            raise TypeError("commit_reflection_cursor: invalid_goal")
        if goal_id.value in seen:
            continue
        seen.add(goal_id.value)
        merged.append(goal_id)
    return replace(
        cursor,
        last_reflection_tick=require_exact_nonneg_int(
            "commit_reflection_cursor.tick", tick
        ),
        acknowledged_goal_ids=tuple(merged),
    )


def log_reflection_applied(plan: ReflectionPlan) -> None:
    """DEBUG counts for a committed pass. No claim text."""

    _LOG.debug(
        "reflection_applied mode=%s triggers=%s belief_count=%s "
        "relationship_count=%s goal_count=%s",
        plan.audit.mode,
        ",".join(plan.audit.trigger_codes),
        len(plan.belief_revisions),
        len(plan.relationship_revisions),
        len(plan.goal_intents),
    )


def log_reflection_aborted(*, owner_id: str, tick: int, reason_code: str) -> None:
    """ERROR a stable reason code. No payloads."""

    _LOG.error(
        "reflection_aborted owner_id=%s tick=%s reason_code=%s",
        owner_id,
        tick,
        reason_code,
    )


def _owned_requests(values: object, model_type: type) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError("ReflectionPlan: not_ordered")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("ReflectionPlan: not_ordered")
    items = tuple(values)
    for item in items:
        if type(item) is not model_type:
            raise TypeError("ReflectionPlan: invalid_item_type")
    return items


def _goal_operation_id(intent: GoalTransitionIntent) -> str:
    return f"reflection-goal:{intent.tick}:{intent.goal_id.value}"


def _remember_operation(seen: set[str], ordered: list[str], operation_id: str) -> None:
    if operation_id in seen:
        return
    seen.add(operation_id)
    ordered.append(operation_id)


def _drop_consolidation_overlaps(
    candidates: tuple[ReflectionCandidate, ...],
    consolidation: object | None,
) -> tuple[ReflectionCandidate, ...]:
    if consolidation is None:
        return candidates
    from agents.cognition.consolidation import OfflineConsolidationPlan

    if type(consolidation) is not OfflineConsolidationPlan:
        return candidates
    belief_ids = {
        request.belief_id.value
        for request in consolidation.belief_revisions
        if request.belief_id is not None
    }
    pairs = {
        (request.source_id.value, request.target_id.value)
        for request in consolidation.relationship_revisions
    }
    goal_ids = {intent.goal_id.value for intent in consolidation.goal_intents}
    kept: list[ReflectionCandidate] = []
    for candidate in candidates:
        belief = candidate.belief_request
        if (
            belief is not None
            and belief.belief_id is not None
            and belief.belief_id.value in belief_ids
        ):
            continue
        relationship = candidate.relationship_request
        if relationship is not None and (
            relationship.source_id.value,
            relationship.target_id.value,
        ) in pairs:
            continue
        intent = candidate.goal_intent
        if intent is not None and intent.goal_id.value in goal_ids:
            continue
        kept.append(candidate)
    return tuple(kept)


def _evidence_root(kind: str, pattern: str, evidence: tuple[str, ...]) -> str:
    material = f"{kind}|{pattern}|{'|'.join(evidence)}".encode()
    return hashlib.sha256(material).hexdigest()[:16]


def _short_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]


@dataclass(frozen=True, slots=True)
class ReflectionTriggerInput:
    """Already-redacted trigger facts. No occurrence narratives."""

    owner_id: AgentId
    tick: int
    policy: ReflectionPolicy
    cursor: ReflectionCursor
    mode: str
    occurrence_kinds: tuple[str, ...] = ()
    emotion_max_intensity: float | None = None
    journal: tuple[SubjectiveDecisionRecord, ...] = ()
    observation_owner_failures: int = 0
    completed_goal_ids: tuple[GoalId, ...] = ()
    contradiction_masses: tuple[float, ...] = ()
    contradiction_counts: tuple[int, ...] = ()
    relationship_ordinals: tuple[tuple[str, str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class ReflectionTriggerResult:
    """Matched triggers request a pass. Skipped triggers stayed inside the gap."""

    matched: tuple[ReflectionTriggerKind, ...]
    skipped: tuple[ReflectionTriggerKind, ...]
    gap_elapsed: bool

    def __repr__(self) -> str:
        return (
            f"ReflectionTriggerResult(matched={len(self.matched)}, "
            f"skipped={len(self.skipped)}, gap_elapsed={self.gap_elapsed})"
        )


class ReflectionEngine:
    """Evaluate whether a configured subjective trigger requests a pass."""

    def triggers(self, data: ReflectionTriggerInput) -> ReflectionTriggerResult:
        if type(data) is not ReflectionTriggerInput:
            raise TypeError("ReflectionEngine.triggers: invalid_input")
        if data.cursor.owner_id != data.owner_id:
            _LOG.error(
                "reflection_cursor_rejected owner_id=%s tick=%s "
                "reason_code=owner_mismatch",
                data.owner_id.value,
                data.tick,
            )
            raise ValueError("reflection_cursor_rejected: owner_mismatch")
        if data.mode == "disabled":
            _LOG.info(
                "reflection_skipped reason=disabled owner_id=%s tick=%s",
                data.owner_id.value,
                data.tick,
            )
            return ReflectionTriggerResult(matched=(), skipped=(), gap_elapsed=False)
        active = _active_triggers(data)
        elapsed = _gap_elapsed(data.tick, data.cursor, data.policy)
        if not elapsed:
            reason = "min_gap" if active else "no_trigger"
            _LOG.info(
                "reflection_skipped reason=%s owner_id=%s tick=%s",
                reason,
                data.owner_id.value,
                data.tick,
            )
            return ReflectionTriggerResult(
                matched=(), skipped=active, gap_elapsed=False
            )
        if not active:
            _LOG.info(
                "reflection_skipped reason=no_trigger owner_id=%s tick=%s",
                data.owner_id.value,
                data.tick,
            )
            return ReflectionTriggerResult(matched=(), skipped=(), gap_elapsed=True)
        _LOG.debug(
            "reflection_triggers owner_id=%s tick=%s mode=%s triggers=%s gap=%s",
            data.owner_id.value,
            data.tick,
            data.mode,
            ",".join(item.value for item in active),
            data.policy.min_gap_ticks,
        )
        return ReflectionTriggerResult(matched=active, skipped=(), gap_elapsed=True)


def advance_decision_journal(
    *,
    cursor: ReflectionCursor,
    journal: tuple[SubjectiveDecisionRecord, ...],
    policy: ReflectionPolicy,
    tick: int,
    command_kind: str,
    day_phase: str | None,
    place_id: str | None,
    previous_outcome: DecisionOutcomeCode | None,
) -> tuple[ReflectionCursor, tuple[SubjectiveDecisionRecord, ...]]:
    """Append one UNKNOWN record and backfill the previous open outcome."""

    if type(cursor) is not ReflectionCursor:
        raise TypeError("advance_decision_journal: invalid_cursor")
    updated = list(journal)
    if updated and previous_outcome is not None:
        last = updated[-1]
        if last.owner_id != cursor.owner_id:
            raise ValueError("advance_decision_journal: owner_mismatch")
        if last.outcome_code is DecisionOutcomeCode.UNKNOWN:
            updated[-1] = replace(last, outcome_code=previous_outcome)
    record = SubjectiveDecisionRecord(
        record_id=f"decision-{cursor.owner_id.value}-{tick}-{len(updated)}",
        owner_id=cursor.owner_id,
        tick=tick,
        command_kind=command_kind,
        outcome_code=DecisionOutcomeCode.UNKNOWN,
        day_phase=day_phase,
        place_id=place_id,
    )
    updated.append(record)
    cap = policy.max_decision_records
    if len(updated) > cap:
        updated = updated[-cap:]
    _LOG.debug(
        "reflection_decision_recorded command_kind=%s outcome_code=%s",
        command_kind,
        DecisionOutcomeCode.UNKNOWN.value,
    )
    return cursor, tuple(updated)


def remember_relationship_ordinals(
    cursor: ReflectionCursor,
    ordinals: tuple[tuple[AgentId, AgentId, int], ...],
) -> ReflectionCursor:
    """Store first-seen pair ordinals. Later increases can trigger a change."""

    if type(cursor) is not ReflectionCursor:
        raise TypeError("remember_relationship_ordinals: invalid_cursor")
    known = {
        (mark.source_id.value, mark.target_id.value)
        for mark in cursor.relationship_ordinals
    }
    added = list(cursor.relationship_ordinals)
    for source, target, ordinal in ordinals:
        if type(source) is not AgentId or type(target) is not AgentId:
            raise TypeError("remember_relationship_ordinals: invalid_agent")
        if source != cursor.owner_id:
            raise ValueError("remember_relationship_ordinals: owner_mismatch")
        key = (source.value, target.value)
        if key in known:
            continue
        known.add(key)
        added.append(
            RelationshipOrdinalMark(
                source_id=source, target_id=target, ordinal=ordinal
            )
        )
    return replace(cursor, relationship_ordinals=tuple(added))


def classify_subjective_outcome(
    *,
    perceived_success: bool,
    owner_failure_count: int,
    place_changed: bool,
) -> DecisionOutcomeCode:
    """Map self-visible observation facts onto a closed outcome code."""

    if perceived_success or place_changed:
        return DecisionOutcomeCode.PERCEIVED_CHANGE
    if owner_failure_count > 0 or not perceived_success:
        return DecisionOutcomeCode.NO_PROGRESS
    return DecisionOutcomeCode.NO_PROGRESS


def _gap_elapsed(tick: int, cursor: ReflectionCursor, policy: ReflectionPolicy) -> bool:
    last = cursor.last_reflection_tick
    gap = policy.min_gap_ticks
    assert gap is not None
    if last is None:
        return tick + 1 >= gap
    return tick - last >= gap


def _active_triggers(
    data: ReflectionTriggerInput,
) -> tuple[ReflectionTriggerKind, ...]:
    policy = data.policy
    matched: list[ReflectionTriggerKind] = []
    last = data.cursor.last_reflection_tick
    if last is None:
        elapsed = data.tick + 1 >= policy.interval_ticks
    else:
        elapsed = data.tick - last >= policy.interval_ticks
    if elapsed:
        matched.append(ReflectionTriggerKind.ELAPSED_TICKS)
    allow = set(policy.significant_occurrence_kinds)
    if allow:
        count = sum(1 for kind in data.occurrence_kinds if kind in allow)
        if count >= policy.significant_occurrence_count:
            matched.append(ReflectionTriggerKind.SIGNIFICANT_OCCURRENCES)
    if (
        data.emotion_max_intensity is not None
        and data.emotion_max_intensity >= policy.emotion_intensity
    ):
        matched.append(ReflectionTriggerKind.STRONG_EMOTION)
    failures: dict[str, int] = {}
    for record in data.journal:
        if record.outcome_code is not DecisionOutcomeCode.NO_PROGRESS:
            continue
        failures[record.command_kind] = failures.get(record.command_kind, 0) + 1
    journal_failure = any(
        count >= policy.repeated_failure_count for count in failures.values()
    )
    if (
        journal_failure
        or data.observation_owner_failures >= policy.repeated_failure_count
    ):
        matched.append(ReflectionTriggerKind.REPEATED_FAILURE)
    acknowledged = {goal_id.value for goal_id in data.cursor.acknowledged_goal_ids}
    horizons = set(policy.major_goal_horizons)
    if horizons and any(
        goal_id.value not in acknowledged for goal_id in data.completed_goal_ids
    ):
        matched.append(ReflectionTriggerKind.MAJOR_GOAL_COMPLETION)
    mass_hit = any(
        mass >= policy.contradiction_mass for mass in data.contradiction_masses
    )
    count_hit = any(
        count >= policy.contradiction_count for count in data.contradiction_counts
    )
    if mass_hit or count_hit:
        matched.append(ReflectionTriggerKind.BELIEF_CONTRADICTION)
    stored = {
        (mark.source_id.value, mark.target_id.value): mark.ordinal
        for mark in data.cursor.relationship_ordinals
    }
    for source, target, ordinal in data.relationship_ordinals:
        seen = stored.get((source, target))
        if seen is not None and ordinal > seen:
            matched.append(ReflectionTriggerKind.RELATIONSHIP_CHANGE)
            break
    return tuple(matched)


_REFLECTION_PROMPT_NAME: Final[str] = "reflection"
_REFLECTION_PROMPT_VERSION: Final[str] = "v1"
_REFLECTION_SCHEMA_VERSION: Final[str] = "reflection.selection.v1"


class ReflectionSelectionOutput(StructuredOutput):
    """Candidate ids only. The schema has no prose claim field."""

    selected_ids: tuple[str, ...]


class LLMReflectionSelector:
    """Restrict a deterministic candidate set to provider-chosen ids."""

    __slots__ = ("_provider",)

    def __init__(self, provider: LLMProvider | None) -> None:
        self._provider = provider

    async def select(
        self,
        candidates: tuple[ReflectionCandidate, ...],
        *,
        policy: ReflectionPolicy,
        owner_id: AgentId,
        tick: int,
    ) -> tuple[tuple[str, ...] | None, bool]:
        """Return selected ids and ``fallback_used``.

        ``None`` ids mean the full deterministic set.
        """

        if type(policy) is not ReflectionPolicy:
            raise TypeError("LLMReflectionSelector: invalid_policy")
        if type(owner_id) is not AgentId:
            raise TypeError("LLMReflectionSelector: invalid_owner")
        candidate_ids = tuple(item.candidate_id for item in candidates)
        if not candidate_ids:
            return None, False
        if not policy.allow_provider or self._provider is None:
            fallback = True
            _LOG.debug(
                "reflection_llm_complete prompt_version=%s schema_version=%s "
                "candidate_count=%s selected_count=%s used_provider=%s "
                "fallback_used=%s",
                _REFLECTION_PROMPT_VERSION,
                _REFLECTION_SCHEMA_VERSION,
                len(candidate_ids),
                len(candidate_ids),
                False,
                fallback,
            )
            return None, fallback
        _LOG.debug(
            "reflection_llm_start prompt_version=%s schema_version=%s "
            "candidate_count=%s",
            _REFLECTION_PROMPT_VERSION,
            _REFLECTION_SCHEMA_VERSION,
            len(candidate_ids),
        )
        try:
            output = await self._generate(
                candidates, owner_id=owner_id, tick=tick
            )
            selected = _accepted_ids(candidate_ids, output.selected_ids)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = "provider_error"
            if type(exc) is ValueError and str(exc) in {
                "foreign_id",
                "schema_invalid",
            }:
                reason = str(exc)
            elif not isinstance(exc, LLMError) and type(exc) is not ValueError:
                reason = "provider_error"
            _LOG.error("reflection_llm_rejected reason_code=%s", reason)
            return None, True
        _LOG.debug(
            "reflection_llm_complete prompt_version=%s schema_version=%s "
            "candidate_count=%s selected_count=%s used_provider=%s "
            "fallback_used=%s",
            _REFLECTION_PROMPT_VERSION,
            _REFLECTION_SCHEMA_VERSION,
            len(candidate_ids),
            len(selected),
            True,
            False,
        )
        return selected, False

    async def _generate(
        self,
        candidates: tuple[ReflectionCandidate, ...],
        *,
        owner_id: AgentId,
        tick: int,
    ) -> ReflectionSelectionOutput:
        payload = {
            "candidate_ids": [item.candidate_id for item in candidates],
            "counts": [item.count for item in candidates],
            "pattern_codes": [item.pattern_code.value for item in candidates],
            "conclusion_kinds": [item.kind.value for item in candidates],
        }
        rendered = render_prompt(
            _REFLECTION_PROMPT_NAME,
            _REFLECTION_PROMPT_VERSION,
            {
                "schema_name": _REFLECTION_SCHEMA_VERSION,
                "schema_json": json.dumps(
                    ReflectionSelectionOutput.model_json_schema(),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "candidate_json": json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ),
            },
        )
        assert self._provider is not None
        result = await self._provider.generate(
            LLMRequest(
                messages=rendered.messages,
                response_model=ReflectionSelectionOutput,
                context=LLMRequestContext(
                    run_id="reflection",
                    agent_id=owner_id.value,
                    tick=tick,
                    llm_request_id=f"reflection-{tick}-{owner_id.value}",
                    component="reflection",
                ),
                prompt=rendered.reference,
            )
        )
        output = result.output
        if type(output) is not ReflectionSelectionOutput:
            raise ValueError("schema_invalid")
        return output


def drop_unprovenanced_candidates(
    context: ReflectionContext,
    candidates: tuple[ReflectionCandidate, ...],
) -> tuple[ReflectionCandidate, ...]:
    """Drop conclusions that cite ids outside the owner context.

    Decision-record ids can support goal intents. They cannot support a belief
    revision. Nothing here is repaired from world state.
    """

    if type(context) is not ReflectionContext:
        raise TypeError("drop_unprovenanced_candidates: invalid_context")
    memory_ids = {trace.memory_id.value for trace in context.memories}
    known = memory_ids | {record.record_id for record in context.decisions}
    known.update(goal.goal_id.value for goal in context.goals)
    kept: list[ReflectionCandidate] = []
    for candidate in candidates:
        if type(candidate) is not ReflectionCandidate:
            raise TypeError("drop_unprovenanced_candidates: invalid_candidate")
        if any(item not in known for item in candidate.evidence_ids):
            continue
        request = candidate.belief_request
        if request is not None and any(
            item.memory_id.value not in memory_ids
            for item in request.evidence.supporting
        ):
            continue
        kept.append(candidate)
    return tuple(kept)


def _select_candidate_ids(
    candidates: tuple[ReflectionCandidate, ...],
    selected_ids: tuple[str, ...],
) -> tuple[ReflectionCandidate, ...]:
    if isinstance(selected_ids, (str, bytes)):
        raise TypeError("plan_reflection: invalid_selection")
    allowed = {item.candidate_id for item in candidates}
    chosen: set[str] = set()
    for item in selected_ids:
        if type(item) is not str or item not in allowed or item in chosen:
            raise ValueError("foreign_id" if item not in allowed else "schema_invalid")
        chosen.add(item)
    return tuple(item for item in candidates if item.candidate_id in chosen)


def _accepted_ids(
    candidate_ids: tuple[str, ...], selected_ids: tuple[str, ...]
) -> tuple[str, ...]:
    allowed = set(candidate_ids)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in selected_ids:
        if type(item) is not str or item not in allowed:
            raise ValueError("foreign_id")
        if item in seen:
            raise ValueError("schema_invalid")
        seen.add(item)
        ordered.append(item)
    return tuple(ordered)
