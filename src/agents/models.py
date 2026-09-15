"""Agent identity and subjective state."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from world.identifiers import require_bounded_text, require_stable_id


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


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite float in [0.0, 1.0]")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be a finite float in [0.0, 1.0]")
    if number == 0.0:
        return 0.0
    return number


@dataclass(frozen=True, slots=True)
class Goal:
    """Immutable agent-owned goal."""

    goal_id: GoalId
    owner_id: AgentId
    description: str
    priority: float
    status: GoalStatus

    def __post_init__(self) -> None:
        if type(self.goal_id) is not GoalId:
            raise TypeError("Goal.goal_id must be GoalId")
        if type(self.owner_id) is not AgentId:
            raise TypeError("Goal.owner_id must be AgentId")
        require_bounded_text("Goal.description", self.description)
        object.__setattr__(
            self, "priority", _unit_interval("Goal.priority", self.priority)
        )
        if type(self.status) is not GoalStatus:
            raise TypeError("Goal.status must be GoalStatus")


@dataclass(frozen=True, slots=True)
class Agent:
    """Immutable subjective agent identity and owned goals."""

    agent_id: AgentId
    name: str
    goals: tuple[Goal, ...]

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("Agent.agent_id must be AgentId")
        require_bounded_text("Agent.name", self.name)
        if isinstance(self.goals, (set, frozenset)):
            raise TypeError("Agent.goals must be an ordered sequence")
        if isinstance(self.goals, (str, bytes)) or not isinstance(
            self.goals, Sequence
        ):
            raise TypeError("Agent.goals must be an ordered sequence")
        goals = tuple(self.goals)
        seen: set[GoalId] = set()
        for goal in goals:
            if type(goal) is not Goal:
                raise TypeError("Agent.goals entries must be Goal")
            if goal.owner_id != self.agent_id:
                raise ValueError("Goal.owner_id must match Agent.agent_id")
            if goal.goal_id in seen:
                raise ValueError("Agent.goals must not contain duplicate goal_id")
            seen.add(goal.goal_id)
        object.__setattr__(self, "goals", goals)
