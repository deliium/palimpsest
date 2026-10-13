"""Private goals may start or continue a visible work site."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.collective_projects import propose_collective_project_command
from agents.cognition.goal_manager import (
    HierarchicalGoalManager,
    _hunger_linked,
)
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
    GoalProgress,
    GoalStatus,
)
from world.actions import ContributeCollectiveProject, StartCollectiveProject, Wait
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

_OWNER = AgentId("agent-1")


def _self(inventory: tuple[EntityId, ...] = ()) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _item(entity_id: str, name: str, kind: ItemKind) -> ObservedItem:
    return ObservedItem(
        entity_id=EntityId(entity_id),
        name=name,
        kind=kind,
        load=ItemLoad(1),
        placement=ObservedItemPlacement.HELD_BY_SELF,
    )


def _store() -> ObservedStructure:
    return ObservedStructure(
        entity_id=EntityId("store-1"),
        location_id=EntityId("loc-1"),
        kind=StructureKind.STORE,
        integrity=1.0,
        stored_quantity=0,
    )


def _project(
    project_id: str,
    *,
    kind: str = "shared_shelter",
    status: str = "open",
    materials_done: int = 0,
) -> ObservedCollectiveProject:
    return ObservedCollectiveProject(
        project_id=EntityId(project_id),
        location_id=EntityId("loc-1"),
        kind=kind,
        status=status,
        labor_done=0,
        materials_done=materials_done,
    )


def _observation(
    *,
    projects: tuple[ObservedCollectiveProject, ...] = (),
    items: tuple[ObservedItem, ...] = (),
    structures: tuple[ObservedStructure, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=3,
        self_body=_self(tuple(item.entity_id for item in items)),
        collective_projects=projects,
        items=items,
        structures=structures,
    )


def _loop(observation: Observation, goals: tuple[Goal, ...] = ()) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_OWNER,
        observation=observation,
        internal_state=InternalAgentState(owner_id=_OWNER),
    )


def _goal(goal_id: str, code: str) -> Goal:
    return Goal(
        goal_id=GoalId(goal_id),
        owner_id=_OWNER,
        description="collective-project",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code=code),
        progress=GoalProgress(estimate=0.0, confidence=0.5),
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


def test_winter_store_start_code_is_not_hunger_linked() -> None:
    goal = _goal("goal-winter", "collective_project:start:winter_store")
    assert _hunger_linked(goal) is False


@pytest.mark.asyncio
async def test_open_project_mints_one_private_intention() -> None:
    board = await HierarchicalGoalManager().manage(
        _loop(_observation(projects=(_project("project-1"),))),
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
        collective_projects_active=True,
    )
    codes = [
        goal.outcome.outcome_code
        for goal in board.goals
        if goal.outcome is not None and goal.outcome.outcome_code is not None
    ]
    assert codes == ["collective_project:project-1"]
    minted = board.goals[0]
    assert minted.parent_goal_id is None
    assert minted.horizon is GoalHorizon.CURRENT_INTENTION
    assert minted.goal_id in board.foci_ids


@pytest.mark.asyncio
async def test_full_focus_list_skips_project_mint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    seeded = tuple(
        _goal(f"goal-{index}", f"keep-watch-{index}") for index in range(8)
    )
    observation = _observation(projects=(_project("project-9"),))
    snapshot_goals = seeded
    from agents.cognition.models import SubjectiveSnapshot

    loop = CognitiveLoopInput(
        agent_id=_OWNER,
        observation=observation,
        internal_state=InternalAgentState(owner_id=_OWNER),
        snapshot=SubjectiveSnapshot(
            owner_id=_OWNER,
            revision=1,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            goals=snapshot_goals,
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.goal_manager"):
        board = await HierarchicalGoalManager().manage(
            loop,
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
            collective_projects_active=True,
        )
    assert all(
        goal.outcome is None
        or goal.outcome.outcome_code != "collective_project:project-9"
        for goal in board.goals
    )
    assert len(board.foci_ids) == 8
    assert "collective_project_goal_skipped reason=foci_cap" in caplog.text


def test_start_maps_winter_store_when_food_and_store_are_present() -> None:
    goal = _goal("goal-start", "collective_project:start:winter_store")
    command = propose_collective_project_command(
        Wait(),
        _observation(
            items=(_item("food-1", "grain", ItemKind.FOOD),),
            structures=(_store(),),
        ),
        _board(goal),
        channel_on=True,
        owner_id=_OWNER,
    )
    assert isinstance(command, StartCollectiveProject)
    assert command.project_kind == "winter_reserve"


def test_missing_material_leaves_the_compiled_command(
    caplog: pytest.LogCaptureFixture,
) -> None:
    goal = _goal("goal-start", "collective_project:start:shared_shelter")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.collective_projects"):
        command = propose_collective_project_command(
            Wait(),
            _observation(),
            _board(goal),
            channel_on=True,
            owner_id=_OWNER,
        )
    assert isinstance(command, Wait)
    assert "collective_project_command_skipped reason=not_held" in caplog.text


def test_contribute_names_the_next_held_material() -> None:
    goal = _goal("goal-work", "collective_project:project-1")
    command = propose_collective_project_command(
        Wait(),
        _observation(
            projects=(_project("project-1"),),
            items=(_item("wood-1", "wood", ItemKind.MATERIAL),),
        ),
        _board(goal),
        channel_on=True,
        owner_id=_OWNER,
    )
    assert isinstance(command, ContributeCollectiveProject)
    assert command.project_id == EntityId("project-1")
    assert command.item_id == EntityId("wood-1")


def test_labor_contribution_omits_the_item_once_materials_are_full() -> None:
    goal = _goal("goal-work", "collective_project:project-1")
    command = propose_collective_project_command(
        Wait(),
        _observation(projects=(_project("project-1", materials_done=2),)),
        _board(goal),
        channel_on=True,
        owner_id=_OWNER,
    )
    assert isinstance(command, ContributeCollectiveProject)
    assert command.item_id is None


def test_channel_off_does_not_replace_the_command() -> None:
    goal = _goal("goal-start", "collective_project:start:storage")
    command = propose_collective_project_command(
        Wait(),
        _observation(items=(_item("wood-1", "wood", ItemKind.MATERIAL),)),
        _board(goal),
        channel_on=False,
        owner_id=_OWNER,
    )
    assert isinstance(command, Wait)
