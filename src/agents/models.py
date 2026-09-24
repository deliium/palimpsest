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
    "GoalCondition",
    "GoalHorizon",
    "GoalId",
    "GoalOriginKind",
    "GoalOutcome",
    "GoalOutcomeKind",
    "GoalProgress",
    "GoalProvenance",
    "GoalRelationEdge",
    "GoalRelationKind",
    "GoalStatus",
    "default_drive_profile",
    "default_drive_state",
    "default_goal_outcome",
    "default_goal_progress",
    "default_goal_provenance",
    "validate_goal_hierarchy",
]

AGENT_MODEL_VERSION: Final[int] = 2
GOAL_MODEL_VERSION: Final[int] = 3

_MAX_OUTCOME_CODE_CHARS: Final[int] = 128
_MAX_TEMPLATE_CODE_CHARS: Final[int] = 64
_MAX_GOAL_REFS: Final[int] = 32
_MAX_GOAL_RELATIONS: Final[int] = 32
_MAX_GOAL_CONDITIONS: Final[int] = 8


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
    """Lifecycle status for an owner-scoped goal."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"
    SUSPENDED = "suspended"


class GoalHorizon(StrEnum):
    """Closed planning horizon for hierarchical goal management."""

    DESIRE = "desire"
    LONG_TERM = "long_term"
    MEDIUM_TERM = "medium_term"
    SUBGOAL = "subgoal"
    CURRENT_INTENTION = "current_intention"


class GoalOriginKind(StrEnum):
    """Closed provenance kinds for how a goal entered the board."""

    SEEDED = "seeded"
    DECOMPOSED = "decomposed"
    REVISED = "revised"
    INFERRED = "inferred"


class GoalRelationKind(StrEnum):
    """Non-parent relations between goals. Parentage uses ``parent_goal_id`` only."""

    DEPENDS_ON = "depends_on"
    COMPETES_WITH = "competes_with"
    REINFORCES = "reinforces"


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
class GoalProvenance:
    """Closed provenance for how a goal entered the owner's board."""

    origin_kind: GoalOriginKind
    template_code: str | None = None
    source_goal_id: GoalId | None = None

    def __post_init__(self) -> None:
        if type(self.origin_kind) is not GoalOriginKind:
            raise TypeError("GoalProvenance.origin_kind: invalid_type")
        if self.template_code is not None:
            require_bounded_text(
                "GoalProvenance.template_code",
                self.template_code,
                max_length=_MAX_TEMPLATE_CODE_CHARS,
            )
        if self.source_goal_id is not None and type(self.source_goal_id) is not GoalId:
            raise TypeError("GoalProvenance.source_goal_id: invalid_type")
        if (
            self.origin_kind is GoalOriginKind.DECOMPOSED
            and self.template_code is None
        ):
            raise ValueError("GoalProvenance.template_code: required")

    def __repr__(self) -> str:
        source = None if self.source_goal_id is None else self.source_goal_id.value
        return (
            f"GoalProvenance(origin_kind={self.origin_kind.value!r}, "
            f"source_goal_id={source!r})"
        )


def default_goal_provenance() -> GoalProvenance:
    """Seeded provenance used when callers omit hierarchical origin metadata."""
    return GoalProvenance(origin_kind=GoalOriginKind.SEEDED)


@dataclass(frozen=True, slots=True)
class GoalRelationEdge:
    """Ordered non-parent relation edge; parentage uses ``parent_goal_id`` only."""

    kind: GoalRelationKind
    target_goal_id: GoalId

    def __post_init__(self) -> None:
        if type(self.kind) is not GoalRelationKind:
            raise TypeError("GoalRelationEdge.kind: invalid_type")
        if type(self.target_goal_id) is not GoalId:
            raise TypeError("GoalRelationEdge.target_goal_id: invalid_type")

    def __repr__(self) -> str:
        return (
            f"GoalRelationEdge(kind={self.kind.value!r}, "
            f"target_goal_id={self.target_goal_id.value!r})"
        )


@dataclass(frozen=True, slots=True)
class GoalCondition:
    """Closed success/failure condition aligned with structured ``GoalOutcome``."""

    outcome: GoalOutcome

    def __post_init__(self) -> None:
        if type(self.outcome) is not GoalOutcome:
            raise TypeError("GoalCondition.outcome: invalid_type")

    def __repr__(self) -> str:
        return f"GoalCondition(outcome_kind={self.outcome.kind.value!r})"


def _require_ordered_sequence(name: str, value: object) -> tuple[object, ...]:
    if isinstance(value, (set, frozenset)):
        raise TypeError(f"{name}: not_ordered")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name}: not_ordered")
    return tuple(value)


def _validate_goal_id_tuple(
    name: str,
    values: object,
    *,
    self_id: GoalId,
    max_items: int,
) -> tuple[GoalId, ...]:
    items = _require_ordered_sequence(name, values)
    if len(items) > max_items:
        raise ValueError(f"{name}: too_many")
    seen: set[GoalId] = set()
    out: list[GoalId] = []
    for item in items:
        if type(item) is not GoalId:
            raise TypeError(f"{name}: invalid_entry_type")
        if item == self_id:
            raise ValueError(f"{name}: self_reference")
        if item in seen:
            raise ValueError(f"{name}: duplicate_goal_id")
        seen.add(item)
        out.append(item)
    return tuple(out)


def _validate_opaque_ref_tuple(
    name: str, values: object, *, max_items: int
) -> tuple[str, ...]:
    items = _require_ordered_sequence(name, values)
    if len(items) > max_items:
        raise ValueError(f"{name}: too_many")
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        ref = require_stable_id(name, item)
        if ref in seen:
            raise ValueError(f"{name}: duplicate_ref")
        seen.add(ref)
        out.append(ref)
    return tuple(out)


def validate_goal_hierarchy(goals: Sequence[Goal]) -> None:
    """Fail closed on missing parents/deps or cycles via parent/dependency edges."""

    by_id = {goal.goal_id: goal for goal in goals}
    if len(by_id) != len(goals):
        raise ValueError("Agent.goals: duplicate_goal_id")
    for goal in goals:
        if goal.parent_goal_id is not None and goal.parent_goal_id not in by_id:
            raise ValueError("Goal.parent_goal_id: missing_parent")
        for dep_id in goal.dependency_ids:
            if dep_id not in by_id:
                raise ValueError("Goal.dependency_ids: missing_dependency")
        for edge in goal.relations:
            if edge.target_goal_id not in by_id:
                raise ValueError("Goal.relations: missing_target")

    # Cycle detection over parent_goal_id and dependency_ids (directed).
    adjacency: dict[GoalId, tuple[GoalId, ...]] = {}
    for goal in goals:
        targets: list[GoalId] = []
        if goal.parent_goal_id is not None:
            targets.append(goal.parent_goal_id)
        targets.extend(goal.dependency_ids)
        adjacency[goal.goal_id] = tuple(targets)

    visiting: set[GoalId] = set()
    visited: set[GoalId] = set()

    def _visit(node: GoalId) -> None:
        if node in visited:
            return
        if node in visiting:
            raise ValueError("Agent.goals: hierarchy_cycle")
        visiting.add(node)
        for nxt in adjacency.get(node, ()):
            _visit(nxt)
        visiting.remove(node)
        visited.add(node)

    for goal_id in by_id:
        _visit(goal_id)


@dataclass(frozen=True, slots=True)
class Goal:
    """Immutable agent-owned hierarchical goal with structured outcome/progress."""

    goal_id: GoalId
    owner_id: AgentId
    description: str
    priority: float
    status: GoalStatus
    outcome: GoalOutcome | None = None
    progress: GoalProgress | None = None
    horizon: GoalHorizon = GoalHorizon.MEDIUM_TERM
    confidence: float | None = None
    provenance: GoalProvenance | None = None
    created_tick: int = 0
    deadline_tick: int | None = None
    parent_goal_id: GoalId | None = None
    dependency_ids: tuple[GoalId, ...] = ()
    relations: tuple[GoalRelationEdge, ...] = ()
    drive_links: tuple[DriveKind, ...] = ()
    belief_refs: tuple[str, ...] = ()
    self_model_refs: tuple[str, ...] = ()
    success_conditions: tuple[GoalCondition, ...] = ()
    failure_conditions: tuple[GoalCondition, ...] = ()

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
        if type(self.horizon) is not GoalHorizon:
            raise TypeError("Goal.horizon: invalid_type")
        if self.outcome is None:
            object.__setattr__(self, "outcome", default_goal_outcome())
        elif type(self.outcome) is not GoalOutcome:
            raise TypeError("Goal.outcome: invalid_type")
        if self.progress is None:
            object.__setattr__(self, "progress", default_goal_progress())
        elif type(self.progress) is not GoalProgress:
            raise TypeError("Goal.progress: invalid_type")
        progress = self.progress
        assert progress is not None
        if self.confidence is None:
            object.__setattr__(self, "confidence", progress.confidence)
        else:
            object.__setattr__(
                self, "confidence", _unit_interval("Goal.confidence", self.confidence)
            )
        if self.provenance is None:
            object.__setattr__(self, "provenance", default_goal_provenance())
        elif type(self.provenance) is not GoalProvenance:
            raise TypeError("Goal.provenance: invalid_type")
        object.__setattr__(
            self,
            "created_tick",
            require_exact_nonneg_int("Goal.created_tick", self.created_tick),
        )
        if self.deadline_tick is not None:
            object.__setattr__(
                self,
                "deadline_tick",
                require_exact_nonneg_int("Goal.deadline_tick", self.deadline_tick),
            )
        if self.parent_goal_id is not None:
            if type(self.parent_goal_id) is not GoalId:
                raise TypeError("Goal.parent_goal_id: invalid_type")
            if self.parent_goal_id == self.goal_id:
                raise ValueError("Goal.parent_goal_id: self_reference")
        object.__setattr__(
            self,
            "dependency_ids",
            _validate_goal_id_tuple(
                "Goal.dependency_ids",
                self.dependency_ids,
                self_id=self.goal_id,
                max_items=_MAX_GOAL_REFS,
            ),
        )
        relation_items = _require_ordered_sequence("Goal.relations", self.relations)
        if len(relation_items) > _MAX_GOAL_RELATIONS:
            raise ValueError("Goal.relations: too_many")
        relation_seen: set[tuple[GoalRelationKind, GoalId]] = set()
        relations: list[GoalRelationEdge] = []
        for item in relation_items:
            if type(item) is not GoalRelationEdge:
                raise TypeError("Goal.relations: invalid_entry_type")
            if item.target_goal_id == self.goal_id:
                raise ValueError("Goal.relations: self_reference")
            key = (item.kind, item.target_goal_id)
            if key in relation_seen:
                raise ValueError("Goal.relations: duplicate_edge")
            relation_seen.add(key)
            relations.append(item)
        object.__setattr__(self, "relations", tuple(relations))
        drive_items = _require_ordered_sequence("Goal.drive_links", self.drive_links)
        if len(drive_items) > len(REQUIRED_DRIVE_KINDS):
            raise ValueError("Goal.drive_links: too_many")
        drive_seen: set[DriveKind] = set()
        drive_links: list[DriveKind] = []
        for item in drive_items:
            if type(item) is not DriveKind:
                raise TypeError("Goal.drive_links: invalid_entry_type")
            if item in drive_seen:
                raise ValueError("Goal.drive_links: duplicate_kind")
            drive_seen.add(item)
            drive_links.append(item)
        object.__setattr__(self, "drive_links", tuple(drive_links))
        object.__setattr__(
            self,
            "belief_refs",
            _validate_opaque_ref_tuple(
                "Goal.belief_refs", self.belief_refs, max_items=_MAX_GOAL_REFS
            ),
        )
        object.__setattr__(
            self,
            "self_model_refs",
            _validate_opaque_ref_tuple(
                "Goal.self_model_refs", self.self_model_refs, max_items=_MAX_GOAL_REFS
            ),
        )
        for field_name, field_value in (
            ("success_conditions", self.success_conditions),
            ("failure_conditions", self.failure_conditions),
        ):
            cond_items = _require_ordered_sequence(f"Goal.{field_name}", field_value)
            if len(cond_items) > _MAX_GOAL_CONDITIONS:
                raise ValueError(f"Goal.{field_name}: too_many")
            conditions: list[GoalCondition] = []
            for item in cond_items:
                if type(item) is not GoalCondition:
                    raise TypeError(f"Goal.{field_name}: invalid_entry_type")
                conditions.append(item)
            object.__setattr__(self, field_name, tuple(conditions))

    def __repr__(self) -> str:
        return (
            f"Goal(goal_id={self.goal_id.value!r}, owner_id={self.owner_id.value!r}, "
            f"status={self.status.value!r}, horizon={self.horizon.value!r})"
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
        validate_goal_hierarchy(goals)
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
