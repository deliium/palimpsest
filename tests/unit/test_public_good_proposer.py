"""Private public-good foci may propose use, maintenance, or opposition."""

from __future__ import annotations

import pytest

from agents.cognition.collective_projects import propose_public_good_command
from agents.cognition.goal_manager import HierarchicalGoalManager, _hunger_linked
from agents.cognition.models import (
    CognitiveLoopInput,
    DecisionMetadata,
    GoalBoard,
    InternalAgentState,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
)
from agents.models import (
    AgentId,
    Goal,
    GoalHorizon,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalStatus,
)
from world.actions import MaintainPublicGood, OpposePublicGood, UsePublicGood, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservedCollectiveProject,
    ObservedItem,
    ObservedItemPlacement,
    ObservedSelf,
    ObservedStructure,
)
from world.production import StructureKind
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit
_OWNER = AgentId("agent-1")


def _project(kind: str = "well") -> ObservedCollectiveProject:
    return ObservedCollectiveProject(
        project_id=EntityId(f"project-{kind}"),
        location_id=EntityId("loc-1"),
        kind=kind,
        status="completed",
        labor_done=3,
        materials_done=2,
        linked_structure_id=EntityId(f"structure-{kind}"),
    )


def _observation(kind: str = "well") -> Observation:
    project = _project(kind)
    assert project.linked_structure_id is not None
    structure_kind = {
        "well": StructureKind.WELL,
        "storage": StructureKind.STORE,
        "winter_reserve": StructureKind.STORE,
        "shared_shelter": StructureKind.SHELTER,
    }[kind]
    material_name = "stone" if structure_kind is StructureKind.WELL else "wood"
    material = ObservedItem(
        entity_id=EntityId("material-1"),
        name=material_name,
        kind=ItemKind.MATERIAL,
        load=ItemLoad(1),
        placement=ObservedItemPlacement.HELD_BY_SELF,
    )
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=3,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(100.0),
            hunger=Hunger(0.0),
            thirst=Thirst(0.0),
            fatigue=Fatigue(0.0),
            temperature=TemperatureCelsius(36.5),
            inventory=(material.entity_id,),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        collective_projects=(project,),
        items=(material,),
        structures=(
            ObservedStructure(
                entity_id=project.linked_structure_id,
                location_id=EntityId("loc-1"),
                kind=structure_kind,
                integrity=0.75,
                stored_quantity=1,
            ),
        ),
    )


def _goal(code: str) -> Goal:
    return Goal(
        goal_id=GoalId("goal-public"),
        owner_id=_OWNER,
        description="public-good",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code=code),
        horizon=GoalHorizon.CURRENT_INTENTION,
        created_tick=1,
    )


def _board(goal: Goal) -> GoalBoard:
    return GoalBoard(
        owner_id=_OWNER,
        tick=3,
        goals=(goal,),
        foci_ids=(goal.goal_id,),
        transition_intents=(),
        confidence=1.0,
        policy_version="goals.v1",
        decision_metadata=DecisionMetadata(),
    )


@pytest.mark.asyncio
async def test_drawable_completion_mints_use_goal_without_hunger_link() -> None:
    observation = _observation("well")
    board = await HierarchicalGoalManager().manage(
        CognitiveLoopInput(
            agent_id=_OWNER,
            observation=observation,
            internal_state=InternalAgentState(owner_id=_OWNER),
        ),
        SituationModel(
            owner_id=_OWNER,
            tick=3,
            claim_codes=(SituationClaimCode.LOCAL_SCENE,),
            confidence=1.0,
        ),
        SelfModel(
            owner_id=_OWNER,
            policy_id="self-model-projection",
            policy_version="1",
            life_status=LifeStatus.ALIVE,
            beliefs=(),
            goal_ids=(),
            confidence=1.0,
            candidate_count=0,
        ),
        RetrievedMemoryContext(
            owner_id=_OWNER,
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
        ),
        public_goods_active=True,
    )
    minted = next(
        goal
        for goal in board.goals
        if goal.outcome is not None
        and goal.outcome.outcome_code == "public_good:use:project-well"
    )
    assert minted.goal_id in board.foci_ids
    assert _hunger_linked(minted) is False


@pytest.mark.parametrize(
    ("code", "expected"),
    (
        ("public_good:use:project-well", UsePublicGood),
        ("public_good:maintain:project-well", MaintainPublicGood),
        ("public_good:oppose:project-well", OpposePublicGood),
    ),
)
def test_seeded_codes_propose_each_public_good_command(
    code: str, expected: type
) -> None:
    goal = _goal(code)
    command = propose_public_good_command(
        Wait(),
        _observation("well"),
        _board(goal),
        channel_on=True,
        owner_id=_OWNER,
    )
    assert isinstance(command, expected)
    assert _hunger_linked(goal) is False


def test_presence_use_code_leaves_compiled_command_unchanged() -> None:
    goal = _goal("public_good:use:project-shared_shelter")
    command = propose_public_good_command(
        Wait(),
        _observation("shared_shelter"),
        _board(goal),
        channel_on=True,
        owner_id=_OWNER,
    )
    assert isinstance(command, Wait)
