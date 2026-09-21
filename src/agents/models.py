"""Agent identity, goals, and independent drive profiles.

Domain values are log-free. Safe ``repr`` exposes IDs, counts, status, and
kind codes only — never goal descriptions, outcome targets, or numeric drive
payloads. Validation errors use field names and stable reason codes only.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import (
    require_bounded_text,
    require_exact_nonneg_int,
    require_stable_id,
)

__all__ = [
    "AGENT_MODEL_VERSION",
    "GOAL_MODEL_VERSION",
    "GOAL_OUTCOME_KINDS",
    "REQUIRED_DRIVE_KINDS",
    "Agent",
    "AgentId",
    "DriveActivation",
    "DriveDisposition",
    "DriveKind",
    "DriveProfile",
    "DriveState",
    "Goal",
    "GoalId",
    "GoalOutcome",
    "GoalOutcomeKind",
    "GoalProgress",
    "GoalStatus",
    "default_drive_profile",
    "default_drive_state",
    "default_goal_outcome",
    "default_goal_progress",
]

AGENT_MODEL_VERSION: Final[int] = 2
GOAL_MODEL_VERSION: Final[int] = 2

_MAX_OUTCOME_CODE_CHARS: Final[int] = 128


@dataclass(frozen=True, slots=True)
class AgentId:
    """Opaque agent identity. Distinct from world EntityId."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("AgentId.value", self.value)


@dataclass(frozen=True, slots=True)
class GoalId:
    """Stable identity for an agent-owned goal."""

    value: str

    def __post_init__(self) -> None:
        require_stable_id("GoalId.value", self.value)


class GoalStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DriveKind(StrEnum):
    """Independent drive identities. Not personality or archetype labels."""

    HUNGER = "hunger"
    THIRST = "thirst"
    SAFETY = "safety"
    FATIGUE = "fatigue"
    BELONGING = "belonging"
    CURIOSITY = "curiosity"
    STATUS = "status"
    AUTONOMY = "autonomy"
    COMPETENCE = "competence"
    PREDICTABILITY = "predictability"
    NOVELTY = "novelty"


REQUIRED_DRIVE_KINDS: Final[tuple[DriveKind, ...]] = (
    DriveKind.HUNGER,
    DriveKind.THIRST,
    DriveKind.SAFETY,
    DriveKind.FATIGUE,
    DriveKind.BELONGING,
    DriveKind.CURIOSITY,
    DriveKind.STATUS,
    DriveKind.AUTONOMY,
    DriveKind.COMPETENCE,
    DriveKind.PREDICTABILITY,
    DriveKind.NOVELTY,
)


class GoalOutcomeKind(StrEnum):
    """Closed cognition-readable desired-outcome kinds."""

    SATISFY_DRIVE = "satisfy_drive"
    REACH_PLACE = "reach_place"
    OBTAIN_ENTITY = "obtain_entity"
    RELATE_TO_AGENT = "relate_to_agent"
    AVOID_ENTITY = "avoid_entity"
    GATHER_INFORMATION = "gather_information"
    PRESERVE_LIFE = "preserve_life"
    ACHIEVE_CODE = "achieve_code"


GOAL_OUTCOME_KINDS: Final[frozenset[GoalOutcomeKind]] = frozenset(GoalOutcomeKind)


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    if number == 0.0:
        return 0.0
    return number


def _optional_stable_id(name: str, value: object | None) -> str | None:
    if value is None:
        return None
    return require_stable_id(name, value)


@dataclass(frozen=True, slots=True)
class DriveDisposition:
    """Stable owner disposition for one drive (baseline, not activation)."""

    kind: DriveKind
    baseline: float
    sensitivity: float

    def __post_init__(self) -> None:
        if type(self.kind) is not DriveKind:
            raise TypeError("DriveDisposition.kind: invalid_type")
        object.__setattr__(
            self, "baseline", _unit_interval("DriveDisposition.baseline", self.baseline)
        )
        object.__setattr__(
            self,
            "sensitivity",
            _unit_interval("DriveDisposition.sensitivity", self.sensitivity),
        )

    def __repr__(self) -> str:
        return f"DriveDisposition(kind={self.kind.value!r})"


@dataclass(frozen=True, slots=True)
class DriveProfile:
    """Immutable agent-owned disposition profile covering every required drive."""

    owner_id: AgentId
    dispositions: tuple[DriveDisposition, ...]

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("DriveProfile.owner_id: invalid_type")
        if isinstance(self.dispositions, (set, frozenset)):
            raise TypeError("DriveProfile.dispositions: not_ordered")
        if isinstance(self.dispositions, (str, bytes)) or not isinstance(
            self.dispositions, Sequence
        ):
            raise TypeError("DriveProfile.dispositions: not_ordered")
        dispositions = tuple(self.dispositions)
        if len(dispositions) != len(REQUIRED_DRIVE_KINDS):
            raise ValueError("DriveProfile.dispositions: incomplete_set")
        seen: set[DriveKind] = set()
        for index, disposition in enumerate(dispositions):
            if type(disposition) is not DriveDisposition:
                raise TypeError("DriveProfile.dispositions: invalid_entry_type")
            expected = REQUIRED_DRIVE_KINDS[index]
            if disposition.kind != expected:
                raise ValueError("DriveProfile.dispositions: unordered_or_incomplete")
            if disposition.kind in seen:
                raise ValueError("DriveProfile.dispositions: duplicate_kind")
            seen.add(disposition.kind)
        object.__setattr__(self, "dispositions", dispositions)

    def __repr__(self) -> str:
        return (
            f"DriveProfile(owner_id={self.owner_id.value!r}, "
            f"drive_count={len(self.dispositions)})"
        )


@dataclass(frozen=True, slots=True)
class DriveActivation:
    """Contextual activation for one drive (independent of other drives)."""

    kind: DriveKind
    activation: float
    urgency: float
    confidence: float

    def __post_init__(self) -> None:
        if type(self.kind) is not DriveKind:
            raise TypeError("DriveActivation.kind: invalid_type")
        object.__setattr__(
            self,
            "activation",
            _unit_interval("DriveActivation.activation", self.activation),
        )
        object.__setattr__(
            self, "urgency", _unit_interval("DriveActivation.urgency", self.urgency)
        )
        object.__setattr__(
            self,
            "confidence",
            _unit_interval("DriveActivation.confidence", self.confidence),
        )

    def __repr__(self) -> str:
        return f"DriveActivation(kind={self.kind.value!r})"


@dataclass(frozen=True, slots=True)
class DriveState:
    """Owner-scoped contextual drive activations for one deliberation snapshot."""

    owner_id: AgentId
    activations: tuple[DriveActivation, ...]

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("DriveState.owner_id: invalid_type")
        if isinstance(self.activations, (set, frozenset)):
            raise TypeError("DriveState.activations: not_ordered")
        if isinstance(self.activations, (str, bytes)) or not isinstance(
            self.activations, Sequence
        ):
            raise TypeError("DriveState.activations: not_ordered")
        activations = tuple(self.activations)
        if len(activations) != len(REQUIRED_DRIVE_KINDS):
            raise ValueError("DriveState.activations: incomplete_set")
        seen: set[DriveKind] = set()
        for index, activation in enumerate(activations):
            if type(activation) is not DriveActivation:
                raise TypeError("DriveState.activations: invalid_entry_type")
            expected = REQUIRED_DRIVE_KINDS[index]
            if activation.kind != expected:
                raise ValueError("DriveState.activations: unordered_or_incomplete")
            if activation.kind in seen:
                raise ValueError("DriveState.activations: duplicate_kind")
            seen.add(activation.kind)
        object.__setattr__(self, "activations", activations)

    def __repr__(self) -> str:
        return (
            f"DriveState(owner_id={self.owner_id.value!r}, "
            f"drive_count={len(self.activations)})"
        )


def default_drive_profile(owner_id: AgentId) -> DriveProfile:
    """Return a neutral disposition profile for ``owner_id``."""
    if type(owner_id) is not AgentId:
        raise TypeError("default_drive_profile: invalid_owner_type")
    dispositions = tuple(
        DriveDisposition(kind=kind, baseline=0.5, sensitivity=0.5)
        for kind in REQUIRED_DRIVE_KINDS
    )
    return DriveProfile(owner_id=owner_id, dispositions=dispositions)


def default_drive_state(owner_id: AgentId) -> DriveState:
    """Return a zero-activation contextual drive state for ``owner_id``."""
    if type(owner_id) is not AgentId:
        raise TypeError("default_drive_state: invalid_owner_type")
    activations = tuple(
        DriveActivation(kind=kind, activation=0.0, urgency=0.0, confidence=1.0)
        for kind in REQUIRED_DRIVE_KINDS
    )
    return DriveState(owner_id=owner_id, activations=activations)


@dataclass(frozen=True, slots=True)
class GoalOutcome:
    """Closed structured desired outcome for cognition-readable goal effects."""

    kind: GoalOutcomeKind
    drive_kind: DriveKind | None = None
    place_id: str | None = None
    entity_id: str | None = None
    counterpart_id: AgentId | None = None
    outcome_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not GoalOutcomeKind:
            raise TypeError("GoalOutcome.kind: invalid_type")
        if self.drive_kind is not None and type(self.drive_kind) is not DriveKind:
            raise TypeError("GoalOutcome.drive_kind: invalid_type")
        if self.counterpart_id is not None and type(self.counterpart_id) is not AgentId:
            raise TypeError("GoalOutcome.counterpart_id: invalid_type")
        object.__setattr__(
            self, "place_id", _optional_stable_id("GoalOutcome.place_id", self.place_id)
        )
        object.__setattr__(
            self,
            "entity_id",
            _optional_stable_id("GoalOutcome.entity_id", self.entity_id),
        )
        if self.outcome_code is not None:
            object.__setattr__(
                self,
                "outcome_code",
                require_bounded_text(
                    "GoalOutcome.outcome_code",
                    self.outcome_code,
                    max_length=_MAX_OUTCOME_CODE_CHARS,
                ),
            )
        self._validate_kind_fields()

    def _validate_kind_fields(self) -> None:
        if self.kind is GoalOutcomeKind.SATISFY_DRIVE:
            if self.drive_kind is None:
                raise ValueError("GoalOutcome.drive_kind: required")
            if (
                self.place_id is not None
                or self.entity_id is not None
                or self.counterpart_id is not None
                or self.outcome_code is not None
            ):
                raise ValueError("GoalOutcome: unexpected_target_field")
            return
        if self.kind is GoalOutcomeKind.REACH_PLACE:
            if self.place_id is None:
                raise ValueError("GoalOutcome.place_id: required")
            if (
                self.drive_kind is not None
                or self.entity_id is not None
                or self.counterpart_id is not None
                or self.outcome_code is not None
            ):
                raise ValueError("GoalOutcome: unexpected_target_field")
            return
        if self.kind is GoalOutcomeKind.OBTAIN_ENTITY:
            if self.entity_id is None:
                raise ValueError("GoalOutcome.entity_id: required")
            if (
                self.drive_kind is not None
                or self.place_id is not None
                or self.counterpart_id is not None
                or self.outcome_code is not None
            ):
                raise ValueError("GoalOutcome: unexpected_target_field")
            return
        if self.kind is GoalOutcomeKind.RELATE_TO_AGENT:
            if self.counterpart_id is None:
                raise ValueError("GoalOutcome.counterpart_id: required")
            if (
                self.drive_kind is not None
                or self.place_id is not None
                or self.entity_id is not None
                or self.outcome_code is not None
            ):
                raise ValueError("GoalOutcome: unexpected_target_field")
            return
        if self.kind is GoalOutcomeKind.AVOID_ENTITY:
            if self.entity_id is None:
                raise ValueError("GoalOutcome.entity_id: required")
            if (
                self.drive_kind is not None
                or self.place_id is not None
                or self.counterpart_id is not None
                or self.outcome_code is not None
            ):
                raise ValueError("GoalOutcome: unexpected_target_field")
            return
        if self.kind is GoalOutcomeKind.GATHER_INFORMATION:
            if self.outcome_code is None:
                raise ValueError("GoalOutcome.outcome_code: required")
            if (
                self.drive_kind is not None
                or self.place_id is not None
                or self.entity_id is not None
                or self.counterpart_id is not None
            ):
                raise ValueError("GoalOutcome: unexpected_target_field")
            return
        if self.kind is GoalOutcomeKind.PRESERVE_LIFE:
            if (
                self.drive_kind is not None
                or self.place_id is not None
                or self.entity_id is not None
                or self.counterpart_id is not None
                or self.outcome_code is not None
            ):
                raise ValueError("GoalOutcome: unexpected_target_field")
            return
        if self.kind is GoalOutcomeKind.ACHIEVE_CODE:
            if self.outcome_code is None:
                raise ValueError("GoalOutcome.outcome_code: required")
            if (
                self.drive_kind is not None
                or self.place_id is not None
                or self.entity_id is not None
                or self.counterpart_id is not None
            ):
                raise ValueError("GoalOutcome: unexpected_target_field")
            return
        raise ValueError("GoalOutcome.kind: unsupported")

    def __repr__(self) -> str:
        return f"GoalOutcome(kind={self.kind.value!r})"


@dataclass(frozen=True, slots=True)
class GoalProgress:
    """Lifecycle progress metadata for active-goal appraisal."""

    estimate: float
    confidence: float
    stall_count: int = 0
    horizon_ticks: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "estimate", _unit_interval("GoalProgress.estimate", self.estimate)
        )
        object.__setattr__(
            self,
            "confidence",
            _unit_interval("GoalProgress.confidence", self.confidence),
        )
        object.__setattr__(
            self,
            "stall_count",
            require_exact_nonneg_int("GoalProgress.stall_count", self.stall_count),
        )
        object.__setattr__(
            self,
            "horizon_ticks",
            require_exact_nonneg_int("GoalProgress.horizon_ticks", self.horizon_ticks),
        )

    def __repr__(self) -> str:
        return (
            f"GoalProgress(stall_count={self.stall_count}, "
            f"horizon_ticks={self.horizon_ticks})"
        )


def default_goal_outcome() -> GoalOutcome:
    """Neutral structured outcome used when callers omit an explicit target."""
    return GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE)


def default_goal_progress() -> GoalProgress:
    """Zero-progress metadata used when callers omit progress fields."""
    return GoalProgress(estimate=0.0, confidence=0.0, stall_count=0, horizon_ticks=0)


@dataclass(frozen=True, slots=True)
class Goal:
    """Immutable agent-owned goal with structured outcome and progress."""

    goal_id: GoalId
    owner_id: AgentId
    description: str
    priority: float
    status: GoalStatus
    outcome: GoalOutcome | None = None
    progress: GoalProgress | None = None

    def __post_init__(self) -> None:
        if type(self.goal_id) is not GoalId:
            raise TypeError("Goal.goal_id: invalid_type")
        if type(self.owner_id) is not AgentId:
            raise TypeError("Goal.owner_id: invalid_type")
        require_bounded_text("Goal.description", self.description)
        object.__setattr__(
            self, "priority", _unit_interval("Goal.priority", self.priority)
        )
        if type(self.status) is not GoalStatus:
            raise TypeError("Goal.status: invalid_type")
        if self.outcome is None:
            object.__setattr__(self, "outcome", default_goal_outcome())
        elif type(self.outcome) is not GoalOutcome:
            raise TypeError("Goal.outcome: invalid_type")
        if self.progress is None:
            object.__setattr__(self, "progress", default_goal_progress())
        elif type(self.progress) is not GoalProgress:
            raise TypeError("Goal.progress: invalid_type")

    def __repr__(self) -> str:
        outcome_kind = (
            None if self.outcome is None else self.outcome.kind.value
        )
        return (
            f"Goal(goal_id={self.goal_id.value!r}, owner_id={self.owner_id.value!r}, "
            f"status={self.status.value!r}, outcome_kind={outcome_kind!r})"
        )


@dataclass(frozen=True, slots=True)
class Agent:
    """Immutable subjective agent identity, owned goals, and drive profile."""

    agent_id: AgentId
    name: str
    goals: tuple[Goal, ...]
    drives: DriveProfile | None = None

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("Agent.agent_id: invalid_type")
        require_bounded_text("Agent.name", self.name)
        if isinstance(self.goals, (set, frozenset)):
            raise TypeError("Agent.goals: not_ordered")
        if isinstance(self.goals, (str, bytes)) or not isinstance(self.goals, Sequence):
            raise TypeError("Agent.goals: not_ordered")
        goals = tuple(self.goals)
        seen: set[GoalId] = set()
        for goal in goals:
            if type(goal) is not Goal:
                raise TypeError("Agent.goals: invalid_entry_type")
            if goal.owner_id != self.agent_id:
                raise ValueError("Goal.owner_id: owner_mismatch")
            if goal.goal_id in seen:
                raise ValueError("Agent.goals: duplicate_goal_id")
            seen.add(goal.goal_id)
        object.__setattr__(self, "goals", goals)
        if self.drives is None:
            object.__setattr__(self, "drives", default_drive_profile(self.agent_id))
        else:
            if type(self.drives) is not DriveProfile:
                raise TypeError("Agent.drives: invalid_type")
            if self.drives.owner_id != self.agent_id:
                raise ValueError("Agent.drives: owner_mismatch")

    def __repr__(self) -> str:
        drive_count = 0 if self.drives is None else len(self.drives.dispositions)
        return (
            f"Agent(agent_id={self.agent_id.value!r}, goal_count={len(self.goals)}, "
            f"drive_count={drive_count})"
        )
