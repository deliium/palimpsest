"""Agent and goal subjective models."""

from __future__ import annotations

import pytest

from agents.models import Agent, AgentId, Goal, GoalId, GoalStatus


def test_agent_owns_goals_and_rejects_foreign_goals() -> None:
    owner = AgentId("agent-1")
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=owner,
        description="survive",
        priority=0.8,
        status=GoalStatus.ACTIVE,
    )
    agent = Agent(agent_id=owner, name="Ada", goals=(goal,))
    assert agent.goals[0].description == "survive"
    with pytest.raises(ValueError, match=r"must match Agent\.agent_id"):
        Agent(
            agent_id=owner,
            name="Ada",
            goals=(
                Goal(
                    goal_id=GoalId("goal-2"),
                    owner_id=AgentId("agent-2"),
                    description="other",
                    priority=0.1,
                    status=GoalStatus.ACTIVE,
                ),
            ),
        )


def test_goal_rejects_invalid_priority_and_blank_description() -> None:
    owner = AgentId("agent-1")
    with pytest.raises(ValueError, match=r"\[0.0, 1.0\]"):
        Goal(
            goal_id=GoalId("goal-1"),
            owner_id=owner,
            description="x",
            priority=1.5,
            status=GoalStatus.ACTIVE,
        )
    with pytest.raises(ValueError, match="whitespace-only"):
        Goal(
            goal_id=GoalId("goal-1"),
            owner_id=owner,
            description="   ",
            priority=0.0,
            status=GoalStatus.ACTIVE,
        )


def test_goal_status_is_closed() -> None:
    assert set(GoalStatus) == {
        GoalStatus.ACTIVE,
        GoalStatus.COMPLETED,
        GoalStatus.ABANDONED,
    }
