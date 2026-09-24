"""Agent, goal, and independent drive subjective models."""

from __future__ import annotations

import pytest

from agents.models import (
    REQUIRED_DRIVE_KINDS,
    Agent,
    AgentId,
    DriveActivation,
    DriveDisposition,
    DriveKind,
    DriveProfile,
    DriveState,
    Goal,
    GoalCondition,
    GoalHorizon,
    GoalId,
    GoalOriginKind,
    GoalOutcome,
    GoalOutcomeKind,
    GoalProgress,
    GoalProvenance,
    GoalRelationEdge,
    GoalRelationKind,
    GoalStatus,
    default_drive_profile,
    default_drive_state,
)


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
    assert agent.drives is not None
    assert len(agent.drives.dispositions) == len(REQUIRED_DRIVE_KINDS)
    with pytest.raises(ValueError, match=r"owner_mismatch"):
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
    with pytest.raises(ValueError, match=r"not_unit_interval"):
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
        GoalStatus.FAILED,
        GoalStatus.ABANDONED,
        GoalStatus.SUSPENDED,
    }


def test_goal_hierarchy_defaults_keep_flat_constructors_usable() -> None:
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=AgentId("agent-1"),
        description="survive",
        priority=0.5,
        status=GoalStatus.ACTIVE,
    )
    assert goal.horizon is GoalHorizon.MEDIUM_TERM
    assert goal.confidence == 0.0
    assert goal.provenance is not None
    assert goal.provenance.origin_kind is GoalOriginKind.SEEDED
    assert goal.created_tick == 0
    assert goal.deadline_tick is None
    assert goal.parent_goal_id is None
    assert goal.dependency_ids == ()
    assert goal.relations == ()
    assert goal.drive_links == ()
    assert goal.belief_refs == ()
    assert goal.self_model_refs == ()
    assert goal.success_conditions == ()
    assert goal.failure_conditions == ()


def test_winter_hierarchy_expressible_as_linked_immutable_goals() -> None:
    owner = AgentId("agent-1")
    desire = Goal(
        goal_id=GoalId("desire-survive-winter"),
        owner_id=owner,
        description="survive winter",
        priority=0.9,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.DESIRE,
        confidence=0.8,
        created_tick=1,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )
    long_term = Goal(
        goal_id=GoalId("lt-food-reserve"),
        owner_id=owner,
        description="build food reserve",
        priority=0.85,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.LONG_TERM,
        confidence=0.7,
        created_tick=1,
        parent_goal_id=desire.goal_id,
        drive_links=(DriveKind.HUNGER,),
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
        ),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.REINFORCES, target_goal_id=desire.goal_id
            ),
        ),
        success_conditions=(
            GoalCondition(
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
                )
            ),
        ),
        provenance=GoalProvenance(
            origin_kind=GoalOriginKind.DECOMPOSED,
            template_code="survive_winter.v1",
            source_goal_id=desire.goal_id,
        ),
    )
    subgoal = Goal(
        goal_id=GoalId("sg-secure-cache"),
        owner_id=owner,
        description="secure cache",
        priority=0.7,
        status=GoalStatus.SUSPENDED,
        horizon=GoalHorizon.SUBGOAL,
        confidence=0.6,
        created_tick=2,
        parent_goal_id=long_term.goal_id,
        dependency_ids=(long_term.goal_id,),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.DEPENDS_ON, target_goal_id=long_term.goal_id
            ),
        ),
        failure_conditions=(
            GoalCondition(
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code="resource_impossible"
                )
            ),
        ),
        provenance=GoalProvenance(
            origin_kind=GoalOriginKind.DECOMPOSED,
            template_code="food_reserve.v1",
            source_goal_id=long_term.goal_id,
        ),
    )
    focus = Goal(
        goal_id=GoalId("ci-search-food"),
        owner_id=owner,
        description="search food now",
        priority=0.95,
        status=GoalStatus.FAILED,
        horizon=GoalHorizon.CURRENT_INTENTION,
        confidence=0.4,
        created_tick=3,
        parent_goal_id=subgoal.goal_id,
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.COMPETES_WITH, target_goal_id=long_term.goal_id
            ),
        ),
    )
    agent = Agent(
        agent_id=owner,
        name="Ada",
        goals=(desire, long_term, subgoal, focus),
    )
    assert agent.goals[2].status is GoalStatus.SUSPENDED
    assert agent.goals[3].status is GoalStatus.FAILED
    assert agent.goals[1].parent_goal_id == desire.goal_id


def test_goal_hierarchy_rejects_cycles_and_missing_parents() -> None:
    owner = AgentId("agent-1")
    a = Goal(
        goal_id=GoalId("goal-a"),
        owner_id=owner,
        description="a",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        parent_goal_id=GoalId("goal-b"),
    )
    b = Goal(
        goal_id=GoalId("goal-b"),
        owner_id=owner,
        description="b",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        parent_goal_id=GoalId("goal-a"),
    )
    with pytest.raises(ValueError, match=r"hierarchy_cycle"):
        Agent(agent_id=owner, name="Ada", goals=(a, b))
    orphan = Goal(
        goal_id=GoalId("goal-orphan"),
        owner_id=owner,
        description="orphan",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        parent_goal_id=GoalId("missing-parent"),
    )
    with pytest.raises(ValueError, match=r"missing_parent"):
        Agent(agent_id=owner, name="Ada", goals=(orphan,))


def test_goal_safe_repr_includes_horizon_omits_payloads() -> None:
    secret = "secret-winter-cache"
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=AgentId("agent-1"),
        description=secret,
        priority=0.4,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.LONG_TERM,
        belief_refs=("belief-secret-1",),
        success_conditions=(
            GoalCondition(
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.REACH_PLACE, place_id="hidden-place"
                )
            ),
        ),
    )
    text = repr(goal)
    assert "horizon='long_term'" in text
    assert secret not in text
    assert "belief-secret-1" not in text
    assert "hidden-place" not in text
    with pytest.raises(ValueError) as raised:
        Goal(
            goal_id=GoalId("goal-1"),
            owner_id=AgentId("agent-1"),
            description="x",
            priority=0.5,
            status=GoalStatus.ACTIVE,
            parent_goal_id=GoalId("goal-1"),
        )
    assert "secret" not in str(raised.value)
    assert "self_reference" in str(raised.value)


def test_goal_defaults_structured_outcome_and_progress() -> None:
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=AgentId("agent-1"),
        description="survive",
        priority=0.5,
        status=GoalStatus.ACTIVE,
    )
    assert goal.outcome is not None
    assert goal.outcome.kind is GoalOutcomeKind.PRESERVE_LIFE
    assert goal.progress is not None
    assert goal.progress.estimate == 0.0
    assert goal.progress.confidence == 0.0


def test_goal_accepts_structured_outcome_and_progress() -> None:
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=AgentId("agent-1"),
        description="find water",
        priority=0.9,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.THIRST
        ),
        progress=GoalProgress(
            estimate=0.25, confidence=0.7, stall_count=1, horizon_ticks=3
        ),
    )
    assert goal.outcome.kind is GoalOutcomeKind.SATISFY_DRIVE
    assert goal.outcome.drive_kind is DriveKind.THIRST
    assert goal.progress.horizon_ticks == 3


def test_goal_outcome_rejects_mismatched_target_fields() -> None:
    with pytest.raises(ValueError, match=r"unexpected_target_field"):
        GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE,
            drive_kind=DriveKind.HUNGER,
            place_id="camp",
        )
    with pytest.raises(ValueError, match=r"required"):
        GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE)


def test_drive_profile_requires_canonical_complete_set() -> None:
    owner = AgentId("agent-1")
    profile = default_drive_profile(owner)
    assert [item.kind for item in profile.dispositions] == list(REQUIRED_DRIVE_KINDS)
    with pytest.raises(ValueError, match=r"incomplete_set"):
        DriveProfile(
            owner_id=owner,
            dispositions=(
                DriveDisposition(
                    kind=DriveKind.HUNGER, baseline=0.1, sensitivity=0.2
                ),
            ),
        )


def test_drive_state_allows_conflicting_activations() -> None:
    owner = AgentId("agent-1")
    activations = []
    for kind in REQUIRED_DRIVE_KINDS:
        if kind is DriveKind.THIRST:
            activations.append(
                DriveActivation(
                    kind=kind, activation=0.9, urgency=0.95, confidence=0.8
                )
            )
        elif kind is DriveKind.SAFETY:
            activations.append(
                DriveActivation(
                    kind=kind, activation=0.85, urgency=0.9, confidence=0.7
                )
            )
        elif kind is DriveKind.BELONGING:
            activations.append(
                DriveActivation(
                    kind=kind, activation=0.8, urgency=0.6, confidence=0.5
                )
            )
        else:
            activations.append(
                DriveActivation(
                    kind=kind, activation=0.1, urgency=0.0, confidence=1.0
                )
            )
    state = DriveState(owner_id=owner, activations=tuple(activations))
    by_kind = {item.kind: item for item in state.activations}
    assert by_kind[DriveKind.THIRST].urgency == 0.95
    assert by_kind[DriveKind.SAFETY].activation == 0.85
    assert by_kind[DriveKind.BELONGING].activation == 0.8


def test_agent_rejects_foreign_drive_profile() -> None:
    owner = AgentId("agent-1")
    foreign = default_drive_profile(AgentId("agent-2"))
    with pytest.raises(ValueError, match=r"owner_mismatch"):
        Agent(agent_id=owner, name="Ada", goals=(), drives=foreign)


def test_safe_repr_and_errors_omit_semantic_payloads() -> None:
    secret_description = "secret-survive-plan"
    secret_place = "hidden-cache-42"
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=AgentId("agent-1"),
        description=secret_description,
        priority=0.4,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id=secret_place),
    )
    agent = Agent(agent_id=AgentId("agent-1"), name="Ada", goals=(goal,))
    drive = DriveDisposition(kind=DriveKind.CURIOSITY, baseline=0.77, sensitivity=0.33)
    state = default_drive_state(AgentId("agent-1"))

    for text in (repr(goal), repr(agent), repr(drive), repr(state), repr(goal.outcome)):
        assert secret_description not in text
        assert secret_place not in text
        assert "0.77" not in text
        assert "Ada" not in text

    with pytest.raises(ValueError) as raised:
        GoalOutcome(
            kind=GoalOutcomeKind.REACH_PLACE,
            place_id=secret_place,
            entity_id="also-secret",
        )
    assert secret_place not in str(raised.value)
    assert "also-secret" not in str(raised.value)
