"""Unit tests for cognition goal-manager policy (``goals.v1``)."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.cognition.goal_manager import (
    GOAL_POLICY_VERSION,
    HierarchicalGoalManager,
    PassthroughGoalManager,
    derive_cognition_goal_id,
)
from agents.cognition.models import (
    CognitiveLoopInput,
    GoalTransitionIntentReason,
    InternalAgentState,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveSnapshot,
)
from agents.models import (
    AgentId,
    DriveKind,
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
)
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticClaim,
)
from memory.models import BeliefId
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_OWNER = AgentId("agent-1")
_LOG_ALLOWLIST_KEYS = frozenset(
    {
        "policy_version",
        "owner_id",
        "tick",
        "mode",
        "status",
        "goal_count",
        "status_counts",
        "horizon_counts",
        "transition_count",
        "transition_counts_by_reason",
        "foci_count",
        "template_code_counts",
        "reason",
    }
)


def _self(*, hunger: float = 0.0, thirst: float = 0.0) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100.0),
        hunger=Hunger(hunger),
        thirst=Thirst(thirst),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observation(
    *,
    hunger: float = 0.0,
    thirst: float = 0.0,
    tick: int = 3,
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=_self(hunger=hunger, thirst=thirst),
    )


def _situation(*claims: SituationClaimCode) -> SituationModel:
    return SituationModel(
        owner_id=_OWNER,
        tick=3,
        claim_codes=claims or (SituationClaimCode.LOCAL_SCENE,),
        confidence=1.0,
    )


def _self_model(goal_ids: tuple[GoalId, ...] = ()) -> SelfModel:
    return SelfModel(
        owner_id=_OWNER,
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=goal_ids,
        confidence=1.0,
        candidate_count=0,
    )


def _memory(
    *,
    beliefs: tuple[SemanticBelief, ...] = (),
) -> RetrievedMemoryContext:
    return RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(),
        belief_ids=tuple(item.belief_id for item in beliefs),
        confidence=1.0,
        semantic_beliefs=beliefs,
    )


def _belief(*, predicate: str, belief_id: str = "belief-1") -> SemanticBelief:
    return SemanticBelief(
        belief_id=BeliefId(belief_id),
        owner_id=_OWNER,
        claim=SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("place-1")
            ),
            predicate=predicate,
            value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        ),
        confidence=BeliefConfidenceState(
            confidence=0.9, support_mass=0.9, contradiction_mass=0.0
        ),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId("rev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=2,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=1,
        evidence_contradiction_count=0,
    )


def _loop_input(
    *,
    goals: tuple[Goal, ...] = (),
    hunger: float = 0.0,
    thirst: float = 0.0,
    tick: int = 3,
) -> CognitiveLoopInput:
    snapshot = None
    if goals:
        snapshot = SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=1,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            goals=goals,
        )
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=_observation(hunger=hunger, thirst=thirst, tick=tick),
        internal_state=InternalAgentState(owner_id=_OWNER),
        snapshot=snapshot,
    )


def _goal(
    *,
    goal_id: str,
    description: str = "goal",
    priority: float = 0.8,
    status: GoalStatus = GoalStatus.ACTIVE,
    horizon: GoalHorizon = GoalHorizon.MEDIUM_TERM,
    outcome: GoalOutcome | None = None,
    progress: GoalProgress | None = None,
    parent_goal_id: GoalId | None = None,
    relations: tuple[GoalRelationEdge, ...] = (),
    drive_links: tuple[DriveKind, ...] = (),
    failure_conditions: tuple[GoalCondition, ...] = (),
    success_conditions: tuple[GoalCondition, ...] = (),
    provenance: GoalProvenance | None = None,
    confidence: float | None = None,
) -> Goal:
    return Goal(
        goal_id=GoalId(goal_id),
        owner_id=_OWNER,
        description=description,
        priority=priority,
        status=status,
        outcome=outcome
        if outcome is not None
        else GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
        progress=progress
        if progress is not None
        else GoalProgress(estimate=0.0, confidence=0.5),
        horizon=horizon,
        confidence=confidence,
        provenance=provenance,
        created_tick=1,
        parent_goal_id=parent_goal_id,
        relations=relations,
        drive_links=drive_links,
        failure_conditions=failure_conditions,
        success_conditions=success_conditions,
    )


def test_derive_cognition_goal_id_deterministic_and_collision_resistant() -> None:
    first = derive_cognition_goal_id(
        owner_id="agent-1",
        tick=3,
        parent_goal_id="parent-a",
        template_code="survive_winter.v1",
        ordinal=0,
    )
    second = derive_cognition_goal_id(
        owner_id="agent-1",
        tick=3,
        parent_goal_id="parent-a",
        template_code="survive_winter.v1",
        ordinal=0,
    )
    assert first == second
    assert first.value.startswith("cg-")
    other_parent = derive_cognition_goal_id(
        owner_id="agent-1",
        tick=3,
        parent_goal_id="parent-b",
        template_code="survive_winter.v1",
        ordinal=0,
    )
    other_ordinal = derive_cognition_goal_id(
        owner_id="agent-1",
        tick=3,
        parent_goal_id="parent-a",
        template_code="survive_winter.v1",
        ordinal=1,
    )
    other_template = derive_cognition_goal_id(
        owner_id="agent-1",
        tick=3,
        parent_goal_id="parent-a",
        template_code="food_reserve.v1",
        ordinal=0,
    )
    assert len({first, other_parent, other_ordinal, other_template}) == 4


@pytest.mark.asyncio
async def test_passthrough_reemits_without_mutations() -> None:
    seeded = (
        _goal(
            goal_id="goal-active",
            horizon=GoalHorizon.CURRENT_INTENTION,
            description="secret-passthrough",
        ),
        _goal(
            goal_id="goal-done",
            status=GoalStatus.COMPLETED,
            horizon=GoalHorizon.MEDIUM_TERM,
        ),
    )
    board = await PassthroughGoalManager().manage(
        _loop_input(goals=seeded),
        _situation(),
        _self_model(),
        _memory(),
    )
    assert board.goals == seeded
    assert board.foci_ids == (GoalId("goal-active"),)
    assert board.transition_intents == ()
    assert board.policy_version == GOAL_POLICY_VERSION
    assert "goal_management_passthrough" in board.decision_metadata.selection_codes
    assert not hasattr(board.decision_metadata, "total_reward")
    assert not hasattr(board.decision_metadata, "utility")


@pytest.mark.asyncio
async def test_hierarchical_decomposes_via_survive_winter_template() -> None:
    desire = _goal(
        goal_id="desire-survive-winter",
        description="secret-survive-winter",
        horizon=GoalHorizon.DESIRE,
        priority=0.9,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=(desire,)),
        _situation(),
        _self_model(),
        _memory(),
    )
    assert len(board.goals) == 2
    child = next(goal for goal in board.goals if goal.goal_id != desire.goal_id)
    assert child.parent_goal_id == desire.goal_id
    assert child.horizon is GoalHorizon.LONG_TERM
    assert child.outcome is not None
    assert child.outcome.kind is GoalOutcomeKind.SATISFY_DRIVE
    assert child.outcome.drive_kind is DriveKind.HUNGER
    assert child.provenance is not None
    assert child.provenance.template_code == "survive_winter.v1"
    assert child.provenance.origin_kind is GoalOriginKind.DECOMPOSED
    expected_id = derive_cognition_goal_id(
        owner_id=_OWNER.value,
        tick=3,
        parent_goal_id=desire.goal_id.value,
        template_code="survive_winter.v1",
        ordinal=0,
    )
    assert child.goal_id == expected_id
    decomposed = [
        intent
        for intent in board.transition_intents
        if intent.reason_code is GoalTransitionIntentReason.DECOMPOSED
    ]
    assert len(decomposed) == 1
    assert decomposed[0].resulting_goal == child


@pytest.mark.asyncio
async def test_hierarchical_food_reserve_decomposition() -> None:
    parent = _goal(
        goal_id="lt-food-reserve",
        horizon=GoalHorizon.LONG_TERM,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
        ),
        drive_links=(DriveKind.HUNGER,),
    )
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=(parent,)),
        _situation(),
        _self_model(),
        _memory(),
    )
    children = [goal for goal in board.goals if goal.parent_goal_id == parent.goal_id]
    # Two food_reserve subgoals plus minted CURRENT_INTENTION foci for ready subgoals.
    subgoals = [goal for goal in children if goal.horizon is GoalHorizon.SUBGOAL]
    assert len(subgoals) == 2
    assert {goal.provenance.template_code for goal in subgoals} == {"food_reserve.v1"}
    assert any(
        goal.outcome is not None and goal.outcome.kind is GoalOutcomeKind.OBTAIN_ENTITY
        for goal in subgoals
    )
    assert any(
        goal.outcome is not None
        and goal.outcome.kind is GoalOutcomeKind.GATHER_INFORMATION
        for goal in subgoals
    )


@pytest.mark.asyncio
async def test_hierarchical_suspend_resume_and_long_term_stays_active() -> None:
    long_term = _goal(
        goal_id="lt-food-reserve",
        horizon=GoalHorizon.LONG_TERM,
        priority=0.85,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
        ),
        drive_links=(DriveKind.HUNGER,),
        progress=GoalProgress(estimate=0.2, confidence=0.7),
    )
    medium = _goal(
        goal_id="mt-explore",
        horizon=GoalHorizon.MEDIUM_TERM,
        priority=0.6,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="map_area"
        ),
        drive_links=(DriveKind.CURIOSITY,),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.COMPETES_WITH, target_goal_id=GoalId("ci-drink")
            ),
        ),
    )
    focus = _goal(
        goal_id="ci-drink",
        horizon=GoalHorizon.CURRENT_INTENTION,
        priority=0.95,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.THIRST
        ),
        drive_links=(DriveKind.THIRST,),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.COMPETES_WITH, target_goal_id=medium.goal_id
            ),
        ),
    )
    manager = HierarchicalGoalManager()
    critical = await manager.manage(
        _loop_input(goals=(long_term, medium, focus), thirst=80.0),
        _situation(),
        _self_model(),
        _memory(),
    )
    by_id = {goal.goal_id: goal for goal in critical.goals}
    assert by_id[long_term.goal_id].status is GoalStatus.ACTIVE
    assert by_id[medium.goal_id].status is GoalStatus.SUSPENDED
    assert by_id[focus.goal_id].status is GoalStatus.ACTIVE
    assert focus.goal_id in critical.foci_ids
    assert long_term.goal_id not in critical.foci_ids
    assert any(
        intent.reason_code is GoalTransitionIntentReason.SUSPENDED
        for intent in critical.transition_intents
    )

    cleared = await manager.manage(
        _loop_input(
            goals=tuple(critical.goals),
            thirst=10.0,
        ),
        _situation(),
        _self_model(),
        _memory(),
    )
    cleared_by_id = {goal.goal_id: goal for goal in cleared.goals}
    assert cleared_by_id[long_term.goal_id].status is GoalStatus.ACTIVE
    assert cleared_by_id[medium.goal_id].status is GoalStatus.ACTIVE
    assert any(
        intent.reason_code is GoalTransitionIntentReason.RESUMED
        for intent in cleared.transition_intents
    )


@pytest.mark.asyncio
async def test_hierarchical_fails_on_subjective_impossibility() -> None:
    parent = _goal(
        goal_id="lt-food-reserve",
        horizon=GoalHorizon.LONG_TERM,
        progress=GoalProgress(estimate=0.4, confidence=0.7),
        confidence=0.7,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
        ),
        drive_links=(DriveKind.HUNGER,),
    )
    target = _goal(
        goal_id="sg-secure-cache",
        horizon=GoalHorizon.SUBGOAL,
        parent_goal_id=parent.goal_id,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code="secure_cache"
        ),
        failure_conditions=(
            GoalCondition(
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.ACHIEVE_CODE,
                    outcome_code="resource_impossible",
                )
            ),
        ),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.REINFORCES, target_goal_id=parent.goal_id
            ),
        ),
    )
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=(parent, target)),
        _situation(),
        _self_model(),
        _memory(beliefs=(_belief(predicate="resource_impossible"),)),
    )
    failed = next(goal for goal in board.goals if goal.goal_id == target.goal_id)
    updated_parent = next(
        goal for goal in board.goals if goal.goal_id == parent.goal_id
    )
    assert failed.status is GoalStatus.FAILED
    assert updated_parent.status is GoalStatus.ACTIVE
    assert updated_parent.confidence is not None
    assert updated_parent.confidence < 0.7
    assert updated_parent.progress is not None
    assert updated_parent.progress.estimate < 0.4
    assert any(
        intent.reason_code is GoalTransitionIntentReason.FAILED
        for intent in board.transition_intents
    )
    assert any(
        intent.reason_code is GoalTransitionIntentReason.PROGRESS_UPDATED
        for intent in board.transition_intents
    )


@pytest.mark.asyncio
async def test_hierarchical_abandons_children_of_failed_parent() -> None:
    parent = _goal(
        goal_id="sg-secure-cache",
        horizon=GoalHorizon.SUBGOAL,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code="secure_cache"
        ),
        failure_conditions=(
            GoalCondition(
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.ACHIEVE_CODE,
                    outcome_code="resource_impossible",
                )
            ),
        ),
    )
    child = _goal(
        goal_id="ci-secure-cache",
        horizon=GoalHorizon.CURRENT_INTENTION,
        parent_goal_id=parent.goal_id,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="locate_cache"
        ),
        drive_links=(DriveKind.CURIOSITY,),
    )
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=(parent, child)),
        _situation(),
        _self_model(),
        _memory(beliefs=(_belief(predicate="resource_impossible"),)),
    )
    by_id = {goal.goal_id: goal for goal in board.goals}
    assert by_id[parent.goal_id].status is GoalStatus.FAILED
    assert by_id[child.goal_id].status is GoalStatus.ABANDONED
    assert child.goal_id not in board.foci_ids
    assert any(
        intent.reason_code is GoalTransitionIntentReason.ABANDONED
        and intent.goal_id == child.goal_id
        for intent in board.transition_intents
    )


@pytest.mark.asyncio
async def test_hierarchical_abandons_past_deadline() -> None:
    overdue = Goal(
        goal_id=GoalId("mt-scout"),
        owner_id=_OWNER,
        description="scout area",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="scout"
        ),
        progress=GoalProgress(estimate=0.1, confidence=0.5),
        horizon=GoalHorizon.MEDIUM_TERM,
        created_tick=1,
        deadline_tick=2,
        drive_links=(DriveKind.CURIOSITY,),
    )
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=(overdue,), tick=5),
        _situation(),
        _self_model(),
        _memory(),
    )
    abandoned = next(goal for goal in board.goals if goal.goal_id == overdue.goal_id)
    assert abandoned.status is GoalStatus.ABANDONED
    assert any(
        intent.reason_code is GoalTransitionIntentReason.ABANDONED
        for intent in board.transition_intents
    )


@pytest.mark.asyncio
async def test_hierarchical_reinforces_parent_progress() -> None:
    parent = _goal(
        goal_id="lt-parent",
        horizon=GoalHorizon.LONG_TERM,
        progress=GoalProgress(estimate=0.1, confidence=0.4),
        confidence=0.4,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )
    child = _goal(
        goal_id="sg-child",
        horizon=GoalHorizon.SUBGOAL,
        parent_goal_id=parent.goal_id,
        progress=GoalProgress(estimate=0.8, confidence=0.9),
        confidence=0.9,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
        ),
        drive_links=(DriveKind.HUNGER,),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.REINFORCES, target_goal_id=parent.goal_id
            ),
        ),
    )
    before = parent.progress.estimate if parent.progress is not None else 0.0
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=(parent, child)),
        _situation(),
        _self_model(),
        _memory(),
    )
    updated = next(goal for goal in board.goals if goal.goal_id == parent.goal_id)
    assert updated.progress is not None
    assert updated.progress.estimate > before
    assert any(
        intent.reason_code is GoalTransitionIntentReason.PROGRESS_UPDATED
        for intent in board.transition_intents
    )


@pytest.mark.asyncio
async def test_hierarchical_metadata_has_no_total_reward(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.goal_manager")
    desire = _goal(
        goal_id="desire-1",
        horizon=GoalHorizon.DESIRE,
        description="secret-description-payload",
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=(desire,)),
        _situation(),
        _self_model(),
        _memory(),
    )
    meta = board.decision_metadata
    assert not hasattr(meta, "total_reward")
    assert not hasattr(meta, "utility")
    assert "total_reward" not in meta.__dataclass_fields__
    assert GOAL_POLICY_VERSION == board.policy_version
    assert "goal_management_hierarchical" in meta.selection_codes

    cognition_payloads = [
        record.__dict__.get("cognition")
        for record in caplog.records
        if isinstance(record.__dict__.get("cognition"), dict)
    ]
    assert cognition_payloads
    for payload in cognition_payloads:
        assert set(payload).issubset(_LOG_ALLOWLIST_KEYS)
        joined = str(payload)
        assert "secret-description-payload" not in joined
        assert "PRESERVE_LIFE" not in joined


@pytest.mark.asyncio
async def test_hierarchical_manage_is_deterministic() -> None:
    desire = _goal(
        goal_id="desire-survive-winter",
        horizon=GoalHorizon.DESIRE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )
    medium = _goal(
        goal_id="mt-side",
        horizon=GoalHorizon.MEDIUM_TERM,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="scout"
        ),
        drive_links=(DriveKind.CURIOSITY,),
    )
    manager = HierarchicalGoalManager()
    loop_input = _loop_input(goals=(desire, medium), hunger=80.0)
    situation = _situation(SituationClaimCode.LOCAL_SCENE)
    self_state = _self_model()
    memory = _memory()
    first = await manager.manage(loop_input, situation, self_state, memory)
    second = await manager.manage(loop_input, situation, self_state, memory)
    assert first.goals == second.goals
    assert first.foci_ids == second.foci_ids
    assert first.transition_intents == second.transition_intents
    assert first.decision_metadata == second.decision_metadata
    assert first.confidence == second.confidence


@pytest.mark.asyncio
async def test_hierarchical_empty_snapshot_yields_empty_board() -> None:
    board = await HierarchicalGoalManager().manage(
        _loop_input(),
        _situation(),
        _self_model(),
        _memory(),
    )
    assert board.goals == ()
    assert board.foci_ids == ()
    assert board.transition_intents == ()
    assert board.confidence == 0.0


@pytest.mark.asyncio
async def test_empty_identity_matches_unbiased_board_and_passthrough() -> None:
    from agents.cognition.identity import (
        IDENTITY_POLICY_ID,
        IDENTITY_POLICY_VERSION,
        IdentityState,
    )

    explore = _goal(
        goal_id="mt-explore",
        description="reach camp",
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="map_area"
        ),
    )
    loop_input = _loop_input(goals=(explore,), thirst=10.0)
    empty = replace(
        _self_model(),
        identity=IdentityState(
            owner_id=_OWNER,
            policy_id=IDENTITY_POLICY_ID,
            policy_version=IDENTITY_POLICY_VERSION,
            views=(),
            aggregate_confidence=0.0,
        ),
    )
    absent = await HierarchicalGoalManager().manage(
        loop_input, _situation(), _self_model(), _memory()
    )
    present = await HierarchicalGoalManager().manage(
        loop_input, _situation(), empty, _memory()
    )
    assert tuple(goal.status for goal in absent.goals) == tuple(
        goal.status for goal in present.goals
    )
    assert all(goal.self_model_refs == () for goal in present.goals)
    passthrough_absent = await PassthroughGoalManager().manage(
        loop_input, _situation(), _self_model(), _memory()
    )
    passthrough_present = await PassthroughGoalManager().manage(
        loop_input, _situation(), empty, _memory()
    )
    assert passthrough_absent.goals == passthrough_present.goals
    assert passthrough_present.goals[0].self_model_refs == ()
    assert "reach camp" not in str(passthrough_present.decision_metadata)
