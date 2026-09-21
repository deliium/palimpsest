"""Unit tests for CommandPlanner action compilation."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.deliberation import (
    PLANNER_POLICY_VERSION,
    SAFE_SOCIAL_PHRASE,
    CommandPlanner,
)
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    ImaginedFuture,
    IntentionCode,
    InternalAgentState,
    MotivationCode,
    PossibleFutures,
    SelectedIntention,
    SituationClaimCode,
)
from agents.models import AgentId
from world.actions import Drink, Eat, Flee, Help, Move, Search, Sleep, Talk, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservedItem,
    ObservedItemPlacement,
    ObservedResource,
    ObservedSelf,
    VisibleBody,
    VisibleExit,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _loop_input(**obs_kwargs: object) -> CognitiveLoopInput:
    agent = AgentId("agent-1")
    defaults: dict[str, object] = {
        "world_id": WorldId("world-1"),
        "observer_id": EntityId("body-1"),
        "revision": WorldRevision(0),
        "tick": 6,
        "self_body": _self(),
    }
    defaults.update(obs_kwargs)
    return CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(**defaults),  # type: ignore[arg-type]
        internal_state=InternalAgentState(owner_id=agent),
    )


def _intention(
    direction: ActionDirection,
    future_id: str,
    *,
    intention: IntentionCode | None = None,
) -> SelectedIntention:
    return SelectedIntention(
        owner_id=AgentId("agent-1"),
        intention=intention or IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=0.8,
        selected_future_id=future_id,
        direction=direction,
        appraisal_future_ids=(future_id,),
    )


def _futures(*items: ImaginedFuture) -> PossibleFutures:
    return PossibleFutures(owner_id=AgentId("agent-1"), futures=items, confidence=1.0)


@pytest.mark.asyncio
async def test_planner_compiles_drink_eat_sleep_move_flee_talk_help(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.deliberation")
    planner = CommandPlanner()
    loop_input = _loop_input(
        resources=(
            ObservedResource(
                entity_id=EntityId("water-1"),
                name="spring",
                kind=ResourceKind.WATER,
                quantity=2.0,
                unit="L",
            ),
        ),
        items=(
            ObservedItem(
                entity_id=EntityId("food-1"),
                name="fruit",
                kind=ItemKind.FOOD,
                load=ItemLoad(1),
                placement=ObservedItemPlacement.GROUND_HERE,
            ),
        ),
        exits=(VisibleExit(destination_id=EntityId("loc-2"), name="path"),),
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-2"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
    )

    cases = [
        (
            ActionDirection.DRINK,
            IntentionCode.DRINK,
            ImaginedFuture(
                future_id="drink",
                claim_codes=(SituationClaimCode.RESOURCE_PRESENT,),
                confidence=0.8,
                direction=ActionDirection.DRINK,
                target_entity_id="water-1",
            ),
            Drink,
        ),
        (
            ActionDirection.EAT,
            IntentionCode.EAT,
            ImaginedFuture(
                future_id="eat",
                claim_codes=(SituationClaimCode.RESOURCE_PRESENT,),
                confidence=0.8,
                direction=ActionDirection.EAT,
                target_entity_id="food-1",
            ),
            Eat,
        ),
        (
            ActionDirection.SLEEP,
            IntentionCode.SLEEP,
            ImaginedFuture(
                future_id="sleep",
                claim_codes=(SituationClaimCode.LOCAL_SCENE,),
                confidence=0.8,
                direction=ActionDirection.SLEEP,
            ),
            Sleep,
        ),
        (
            ActionDirection.MOVE,
            IntentionCode.MOVE,
            ImaginedFuture(
                future_id="move-0",
                claim_codes=(SituationClaimCode.LOCAL_SCENE,),
                confidence=0.8,
                direction=ActionDirection.MOVE,
                target_entity_id="loc-2",
            ),
            Move,
        ),
        (
            ActionDirection.FLEE,
            IntentionCode.FLEE,
            ImaginedFuture(
                future_id="flee",
                claim_codes=(SituationClaimCode.THREAT_SIGNAL,),
                confidence=0.8,
                direction=ActionDirection.FLEE,
                target_entity_id="body-2",
            ),
            Flee,
        ),
        (
            ActionDirection.COMMUNICATE,
            IntentionCode.COMMUNICATE,
            ImaginedFuture(
                future_id="talk-0",
                claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
                confidence=0.8,
                direction=ActionDirection.COMMUNICATE,
                target_entity_id="body-2",
            ),
            Talk,
        ),
        (
            ActionDirection.HELP,
            IntentionCode.HELP,
            ImaginedFuture(
                future_id="help-0",
                claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
                confidence=0.8,
                direction=ActionDirection.HELP,
                target_entity_id="body-2",
            ),
            Help,
        ),
        (
            ActionDirection.SEARCH,
            IntentionCode.SEARCH,
            ImaginedFuture(
                future_id="search",
                claim_codes=(SituationClaimCode.LOCAL_SCENE,),
                confidence=0.8,
                direction=ActionDirection.SEARCH,
            ),
            Search,
        ),
    ]
    for direction, intention_code, future, command_type in cases:
        plan = await planner.plan(
            loop_input,
            _intention(direction, future.future_id, intention=intention_code),
            _futures(future),
        )
        assert type(plan.command) is command_type

    talk_plan = await planner.plan(
        loop_input,
        _intention(
            ActionDirection.COMMUNICATE,
            "talk-0",
            intention=IntentionCode.COMMUNICATE,
        ),
        _futures(
            ImaginedFuture(
                future_id="talk-0",
                claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
                confidence=0.8,
                direction=ActionDirection.COMMUNICATE,
                target_entity_id="body-2",
            )
        ),
    )
    assert type(talk_plan.command) is Talk
    assert talk_plan.command.text == SAFE_SOCIAL_PHRASE
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "planner_complete" in messages
    assert PLANNER_POLICY_VERSION
    assert SAFE_SOCIAL_PHRASE not in messages


@pytest.mark.asyncio
async def test_planner_falls_back_to_wait_when_target_missing() -> None:
    plan = await CommandPlanner().plan(
        _loop_input(),
        _intention(ActionDirection.DRINK, "drink", intention=IntentionCode.DRINK),
        _futures(
            ImaginedFuture(
                future_id="drink",
                claim_codes=(SituationClaimCode.RESOURCE_PRESENT,),
                confidence=0.8,
                direction=ActionDirection.DRINK,
                target_entity_id="missing",
            )
        ),
    )
    assert type(plan.command) is Wait


@pytest.mark.asyncio
async def test_default_loop_emits_non_wait_when_water_and_thirst_present() -> None:
    from agents.cognition.defaults import default_cognitive_loop

    agent = AgentId("agent-1")
    loop_input = CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=1,
            self_body=ObservedSelf(
                entity_id=EntityId("body-1"),
                location_id=EntityId("loc-1"),
                health=Health(100),
                hunger=Hunger(0),
                thirst=Thirst(90),
                fatigue=Fatigue(0),
                temperature=TemperatureCelsius(36.5),
                inventory=(),
                life_status=LifeStatus.ALIVE,
                carry_capacity=CarryCapacity(10),
            ),
            resources=(
                ObservedResource(
                    entity_id=EntityId("water-1"),
                    name="spring",
                    kind=ResourceKind.WATER,
                    quantity=4.0,
                    unit="L",
                ),
            ),
        ),
        internal_state=InternalAgentState(owner_id=agent),
    )
    result = await default_cognitive_loop().run(loop_input, invocation_id="inv-drink")
    assert type(result.command) is Drink
    assert result.command.source_id == EntityId("water-1")
