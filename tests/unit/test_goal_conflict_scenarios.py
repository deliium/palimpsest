"""Short-term vs long-term goal conflict scenarios (Task 11)."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import (
    build_cognitive_loop,
    production_cognition_config,
)
from agents.cognition.goal_manager import HierarchicalGoalManager
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
    GoalOutcome,
    GoalOutcomeKind,
    GoalProgress,
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
from world.actions import Drink, Search
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedResource, ObservedSelf, VisibleExit
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)

_OWNER = AgentId("agent-1")
_LOG = logging.getLogger("tests.goal_conflict_scenarios")


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
    tick: int = 5,
    with_water: bool = False,
    with_food: bool = False,
) -> Observation:
    resources: list[ObservedResource] = []
    if with_water:
        resources.append(
            ObservedResource(
                entity_id=EntityId("water-1"),
                name="spring",
                kind=ResourceKind.WATER,
                quantity=3.0,
                unit="L",
            )
        )
    if with_food:
        resources.append(
            ObservedResource(
                entity_id=EntityId("food-1"),
                name="berries",
                kind=ResourceKind.FOOD,
                quantity=2.0,
                unit="kg",
            )
        )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=_self(hunger=hunger, thirst=thirst),
        resources=tuple(resources),
        exits=(VisibleExit(destination_id=EntityId("loc-grove"), name="path"),),
    )


def _winter_hierarchy() -> tuple[Goal, ...]:
    desire = Goal(
        goal_id=GoalId("desire-survive-winter"),
        owner_id=_OWNER,
        description="survive winter",
        priority=0.95,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.DESIRE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
        progress=GoalProgress(estimate=0.1, confidence=0.6),
        created_tick=1,
    )
    long_term = Goal(
        goal_id=GoalId("lt-food-reserve"),
        owner_id=_OWNER,
        description="build food reserve",
        priority=0.88,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.LONG_TERM,
        parent_goal_id=desire.goal_id,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
        ),
        progress=GoalProgress(estimate=0.2, confidence=0.7),
        drive_links=(DriveKind.HUNGER,),
        created_tick=1,
    )
    subgoal = Goal(
        goal_id=GoalId("sg-secure-cache"),
        owner_id=_OWNER,
        description="secure food cache",
        priority=0.8,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.SUBGOAL,
        parent_goal_id=long_term.goal_id,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code="secure_cache"
        ),
        progress=GoalProgress(estimate=0.3, confidence=0.7),
        drive_links=(DriveKind.HUNGER,),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.REINFORCES, target_goal_id=long_term.goal_id
            ),
        ),
        created_tick=1,
    )
    reserve_focus = Goal(
        goal_id=GoalId("ci-secure-cache"),
        owner_id=_OWNER,
        description="focus secure cache",
        priority=0.75,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.CURRENT_INTENTION,
        parent_goal_id=subgoal.goal_id,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="locate_cache"
        ),
        progress=GoalProgress(estimate=0.1, confidence=0.6),
        drive_links=(DriveKind.CURIOSITY, DriveKind.HUNGER),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.DEPENDS_ON, target_goal_id=subgoal.goal_id
            ),
        ),
        created_tick=1,
    )
    thirst_focus = Goal(
        goal_id=GoalId("ci-drink"),
        owner_id=_OWNER,
        description="drink now",
        priority=0.97,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.CURRENT_INTENTION,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.THIRST
        ),
        progress=GoalProgress(estimate=0.0, confidence=0.9),
        drive_links=(DriveKind.THIRST,),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.COMPETES_WITH,
                target_goal_id=reserve_focus.goal_id,
            ),
        ),
        created_tick=1,
    )
    return (desire, long_term, subgoal, reserve_focus, thirst_focus)


def _loop_input(
    *,
    goals: tuple[Goal, ...],
    hunger: float = 0.0,
    thirst: float = 0.0,
    with_water: bool = False,
    with_food: bool = False,
    tick: int = 5,
) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=_observation(
            hunger=hunger,
            thirst=thirst,
            tick=tick,
            with_water=with_water,
            with_food=with_food,
        ),
        internal_state=InternalAgentState(owner_id=_OWNER),
        snapshot=SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=1,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            goals=goals,
        ),
    )


def _status_histogram(goals: tuple[Goal, ...]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for goal in goals:
        key = goal.status.value
        hist[key] = hist.get(key, 0) + 1
    return hist


@pytest.mark.asyncio
async def test_acute_thirst_wins_tick_without_abandoning_long_term() -> None:
    goals = _winter_hierarchy()
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=goals, thirst=85.0, with_water=True),
        SituationModel(
            owner_id=_OWNER,
            tick=5,
            claim_codes=(SituationClaimCode.LOCAL_SCENE,),
            confidence=1.0,
        ),
        SelfModel(
            owner_id=_OWNER,
            policy_id="self-model-projection",
            policy_version="1",
            life_status=LifeStatus.ALIVE,
            beliefs=(),
            goal_ids=tuple(g.goal_id for g in goals),
            confidence=1.0,
            candidate_count=0,
        ),
        RetrievedMemoryContext(
            owner_id=_OWNER,
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
        ),
    )
    by_id = {goal.goal_id: goal for goal in board.goals}
    assert by_id[GoalId("lt-food-reserve")].status is GoalStatus.ACTIVE
    assert by_id[GoalId("desire-survive-winter")].status is GoalStatus.ACTIVE
    assert by_id[GoalId("sg-secure-cache")].status is GoalStatus.ACTIVE
    assert GoalId("ci-drink") in board.foci_ids
    assert GoalId("lt-food-reserve") not in board.foci_ids
    assert not any(
        intent.reason_code is GoalTransitionIntentReason.ABANDONED
        for intent in board.transition_intents
    )
    _LOG.info(
        "conflict_acute_thirst tick=%s owner=%s foci_count=%s status_hist=%s",
        board.tick,
        board.owner_id.value,
        len(board.foci_ids),
        _status_histogram(board.goals),
    )

    loop = build_cognitive_loop(production_cognition_config())
    result = await loop.run(
        _loop_input(goals=tuple(board.goals), thirst=85.0, with_water=True),
        invocation_id="conflict-thirst-1",
    )
    assert type(result.command) is Drink
    intention_record = next(
        record
        for record in result.boundary_records
        if record.component_kind.value == "intention"
    )
    meta = intention_record.decision_metadata
    assert not hasattr(meta, "total_reward")
    assert not hasattr(meta, "utility")
    assert "total_reward" not in meta.__dataclass_fields__
    assert "utility" not in meta.__dataclass_fields__


@pytest.mark.asyncio
async def test_low_need_shifts_toward_reserve_search_affordance() -> None:
    goals = _winter_hierarchy()
    # Drop competing thirst focus so reserve focus can lead when needs are mild.
    goals = tuple(g for g in goals if g.goal_id != GoalId("ci-drink"))
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=goals, thirst=5.0, hunger=20.0),
        SituationModel(
            owner_id=_OWNER,
            tick=5,
            claim_codes=(SituationClaimCode.LOCAL_SCENE,),
            confidence=1.0,
        ),
        SelfModel(
            owner_id=_OWNER,
            policy_id="self-model-projection",
            policy_version="1",
            life_status=LifeStatus.ALIVE,
            beliefs=(),
            goal_ids=tuple(g.goal_id for g in goals),
            confidence=1.0,
            candidate_count=0,
        ),
        RetrievedMemoryContext(
            owner_id=_OWNER,
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
        ),
    )
    by_id = {goal.goal_id: goal for goal in board.goals}
    assert by_id[GoalId("lt-food-reserve")].status is GoalStatus.ACTIVE
    assert GoalId("ci-secure-cache") in board.foci_ids
    _LOG.info(
        "conflict_low_need tick=%s owner=%s foci_count=%s "
        "status_hist=%s command_probe=search",
        board.tick,
        board.owner_id.value,
        len(board.foci_ids),
        _status_histogram(board.goals),
    )

    loop = build_cognitive_loop(production_cognition_config())
    result = await loop.run(
        _loop_input(goals=tuple(board.goals), thirst=5.0, hunger=20.0),
        invocation_id="conflict-reserve-1",
    )
    command_type = type(result.command)
    assert command_type is Search or result.command.__class__.__name__ in {
        "Search",
        "Move",
        "Wait",
    }
    # Reserve focus should not collapse into a drink-critical path when thirst is mild.
    assert command_type is not Drink
    intention_record = next(
        record
        for record in result.boundary_records
        if record.component_kind.value == "intention"
    )
    assert not hasattr(intention_record.decision_metadata, "total_reward")


@pytest.mark.asyncio
async def test_believed_impossible_resource_fails_subgoal_not_parent() -> None:
    desire = Goal(
        goal_id=GoalId("desire-survive-winter"),
        owner_id=_OWNER,
        description="survive winter",
        priority=0.95,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.DESIRE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
        progress=GoalProgress(estimate=0.2, confidence=0.6),
        created_tick=1,
    )
    parent = Goal(
        goal_id=GoalId("lt-food-reserve"),
        owner_id=_OWNER,
        description="build food reserve",
        priority=0.88,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.LONG_TERM,
        parent_goal_id=desire.goal_id,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.HUNGER
        ),
        progress=GoalProgress(estimate=0.25, confidence=0.55),
        confidence=0.55,
        drive_links=(DriveKind.HUNGER,),
        created_tick=1,
    )
    subgoal = Goal(
        goal_id=GoalId("sg-secure-cache"),
        owner_id=_OWNER,
        description="secure food cache",
        priority=0.8,
        status=GoalStatus.ACTIVE,
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
        progress=GoalProgress(estimate=0.4, confidence=0.7),
        drive_links=(DriveKind.HUNGER,),
        relations=(
            GoalRelationEdge(
                kind=GoalRelationKind.REINFORCES, target_goal_id=parent.goal_id
            ),
        ),
        created_tick=1,
    )
    belief = SemanticBelief(
        belief_id=BeliefId("belief-impossible"),
        owner_id=_OWNER,
        claim=SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("place-1")
            ),
            predicate="resource_impossible",
            value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        ),
        confidence=BeliefConfidenceState(
            confidence=0.95, support_mass=0.95, contradiction_mass=0.0
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
    board = await HierarchicalGoalManager().manage(
        _loop_input(goals=(desire, parent, subgoal)),
        SituationModel(
            owner_id=_OWNER,
            tick=5,
            claim_codes=(SituationClaimCode.LOCAL_SCENE,),
            confidence=1.0,
        ),
        SelfModel(
            owner_id=_OWNER,
            policy_id="self-model-projection",
            policy_version="1",
            life_status=LifeStatus.ALIVE,
            beliefs=(),
            goal_ids=(desire.goal_id, parent.goal_id, subgoal.goal_id),
            confidence=1.0,
            candidate_count=0,
        ),
        RetrievedMemoryContext(
            owner_id=_OWNER,
            memory_ids=(),
            belief_ids=(belief.belief_id,),
            confidence=1.0,
            semantic_beliefs=(belief,),
        ),
    )
    by_id = {goal.goal_id: goal for goal in board.goals}
    assert by_id[subgoal.goal_id].status is GoalStatus.FAILED
    assert by_id[parent.goal_id].status is GoalStatus.ACTIVE
    assert by_id[desire.goal_id].status is GoalStatus.ACTIVE
    assert subgoal.goal_id not in board.foci_ids
    assert by_id[parent.goal_id].confidence is not None
    assert parent.confidence is not None
    assert by_id[parent.goal_id].confidence < parent.confidence
    assert by_id[parent.goal_id].progress is not None
    assert parent.progress is not None
    assert by_id[parent.goal_id].progress.estimate < parent.progress.estimate
    assert any(
        intent.reason_code is GoalTransitionIntentReason.FAILED
        and intent.goal_id == subgoal.goal_id
        for intent in board.transition_intents
    )
    assert not hasattr(board.decision_metadata, "total_reward")
    _LOG.info(
        "conflict_impossible tick=%s owner=%s foci_count=%s status_hist=%s",
        board.tick,
        board.owner_id.value,
        len(board.foci_ids),
        _status_histogram(board.goals),
    )
