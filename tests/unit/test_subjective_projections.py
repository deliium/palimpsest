"""Metadata-safe subjective projection contracts for Research UI."""

from __future__ import annotations

import pytest

from agents.cognition.models import InternalAgentState
from agents.models import (
    AgentId,
    Goal,
    GoalHorizon,
    GoalId,
    GoalStatus,
    default_goal_outcome,
    default_goal_progress,
    default_goal_provenance,
)
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.subjective_projections import (
    project_goals,
    project_self_model,
    project_social_norms,
)

pytestmark = pytest.mark.unit


def _checkpoint(*, goals: tuple[Goal, ...] = ()) -> AgentRuntimeCheckpoint:
    owner = AgentId("alice")
    return AgentRuntimeCheckpoint(
        agent_id=owner,
        status=AgentRuntimeStatus.ACTIVE,
        internal_state=InternalAgentState(owner_id=owner),
        last_observation_key=None,
        processed_invocation_count=0,
        finalized_hash_count=0,
        goals=goals,
    )


def test_goals_unavailable_without_checkpoint() -> None:
    doc = project_goals("alice", None)
    assert doc.availability == "unavailable"
    assert doc.head_count == 0


def test_goals_available_metadata_only() -> None:
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=AgentId("alice"),
        description="seek water",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=default_goal_outcome(),
        progress=default_goal_progress(),
        horizon=GoalHorizon.MEDIUM_TERM,
        provenance=default_goal_provenance(),
        created_tick=3,
    )
    doc = project_goals("alice", _checkpoint(goals=(goal,)))
    assert doc.availability == "available"
    assert doc.head_count == 1
    assert doc.items[0].goal_id == "goal-1"
    dumped = str(doc.items)
    assert "seek water" not in dumped


def test_self_model_is_projection_not_row() -> None:
    doc = project_self_model("alice", _checkpoint())
    assert doc.availability == "unavailable"
    assert "second" not in doc.note


def test_social_norms_unavailable_when_ledger_none() -> None:
    doc = project_social_norms("alice", _checkpoint())
    assert doc.availability == "unavailable"
