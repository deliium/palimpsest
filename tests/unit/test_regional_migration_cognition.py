"""Private destination evidence influences only bounded adjacent decisions."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.configuration import build_cognitive_loop
from agents.cognition.deliberation import CommandPlanner, MultiCriteriaIntentionSelector
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    DriveEffect,
    FutureAppraisal,
    ImaginedFuture,
    InternalAgentState,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PossibleFutures,
    SubjectiveSnapshot,
    SubjectiveUncertainty,
)
from agents.cognition.regional_migration import (
    destination_action_biases,
    destination_memory_trace,
)
from agents.models import AgentId, DriveKind
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from world.actions import Move, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservedJourney,
    ObservedJourneyPhase,
    ObservedRegionalContext,
    ObservedResource,
    ObservedSelf,
    VisibleExit,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)


def _observation(
    *,
    location: str,
    tick: int,
    exits: tuple[VisibleExit, ...],
    hunger: float = 0.0,
    thirst: float = 0.0,
    fatigue: float = 0.0,
    journey: ObservedJourney | None = None,
    resources: tuple[ObservedResource, ...] = (),
) -> Observation:
    body_id = EntityId("body-1")
    return Observation(
        world_id=WorldId("world-regional-cognition"),
        observer_id=body_id,
        revision=WorldRevision(tick),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=body_id,
            location_id=EntityId(location),
            health=Health(100),
            hunger=Hunger(hunger),
            thirst=Thirst(thirst),
            fatigue=Fatigue(fatigue),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
            journey=journey,
        ),
        exits=exits,
        resources=resources,
        regional_context=ObservedRegionalContext("north", "North"),
    )


def _exit(destination: str, *, duration: int = 1, fatigue: float = 1.0) -> VisibleExit:
    return VisibleExit(
        destination_id=EntityId(destination),
        name=destination,
        travel_duration_ticks=duration,
        fatigue_cost=fatigue,
        destination_region_id="north",
    )


def _future(
    future_id: str, direction: ActionDirection, target: str | None
) -> ImaginedFuture:
    return ImaginedFuture(
        future_id=future_id,
        claim_codes=(),
        confidence=0.7,
        direction=direction,
        target_entity_id=target,
        drive_effects=(),
        risks=(),
        uncertainty=SubjectiveUncertainty(),
        subjective_probability=0.5,
    )


def _food_trace(
    owner: AgentId,
    *,
    tick: int,
    location: str = "loc-5",
    source_kind: MemorySourceKind = MemorySourceKind.DIRECT_OBSERVATION,
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId("remote-food"),
        owner_id=owner,
        world_revision=WorldRevision(tick),
        concepts=(ConceptMention(MentionId("food"), "resource:food"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(
            location_id=EntityId(location), tags=("direct", "scene")
        ),
        emotional_salience=0.3,
        confidence=0.95,
        provenance=MemoryProvenance(
            kind=source_kind,
            source_tick=tick,
            speaker_id=(
                EntityId("speaker-1")
                if source_kind is MemorySourceKind.COMMUNICATED
                else None
            ),
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
        lineage=MemoryLineage(),
    )


def _known_remote_route(
    owner: AgentId,
    *,
    source_tick: int = 5,
    duration: int = 3,
    fatigue: float = 4.0,
) -> tuple[MemoryTrace, ...]:
    visited = _observation(
        location="loc-4",
        tick=source_tick,
        exits=(_exit("loc-5", duration=duration, fatigue=fatigue),),
    )
    route = destination_memory_trace(
        owner_id=owner,
        observer_body_id=visited.observer_id,
        observation=visited,
        exit_view=visited.exits[0],
    )
    return route, _food_trace(owner, tick=source_tick)


def _loop_input(
    owner: AgentId,
    observation: Observation,
    memories: tuple[MemoryTrace, ...],
) -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=owner,
        observation=observation,
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=SubjectiveSnapshot(
            owner_id=owner,
            revision=observation.revision.value,
            memories=memories,
            legacy_beliefs=(),
            semantic_beliefs=(),
        ),
    )


def _motivation(futures: tuple[ImaginedFuture, ...]) -> MotivationEvaluation:
    return MotivationEvaluation(
        owner_id=AgentId("agent-1"),
        scores=(MotivationScore(motive=MotivationCode.WAIT, score=0.5),),
        confidence=0.5,
        appraisals=tuple(
            FutureAppraisal(
                future_id=future.future_id,
                drive_effects=future.drive_effects,
                goal_effects=future.goal_effects,
                risks=future.risks,
                mortality=future.mortality,
                uncertainty=future.uncertainty,
                support_drive_count=0,
                support_goal_count=0,
                support_social_count=0,
            )
            for future in futures
        ),
    )


def _current_observation(
    *,
    tick: int = 20,
    hunger: float = 90.0,
    thirst: float = 0.0,
    resources: tuple[ObservedResource, ...] = (),
) -> Observation:
    return _observation(
        location="loc-1",
        tick=tick,
        hunger=hunger,
        thirst=thirst,
        exits=(_exit("loc-2"), _exit("loc-4")),
        resources=resources,
    )


def test_cognitive_loop_builder_preserves_regional_mode_and_hop_cap() -> None:
    loop = build_cognitive_loop(
        regional_migration_cognition_mode="deterministic",
        regional_migration_hop_limit=3,
    )
    assert loop._regional_migration_cognition_mode == "deterministic"
    assert loop._regional_migration_hop_limit == 3


def test_known_route_and_private_food_evidence_bias_adjacent_move() -> None:
    owner = AgentId("agent-1")
    observation = _current_observation()
    route, food = _known_remote_route(owner)
    futures = (
        _future("move-2", ActionDirection.MOVE, "loc-2"),
        _future("move-4", ActionDirection.MOVE, "loc-4"),
    )
    biases = destination_action_biases(
        owner_id=owner,
        observation=observation,
        memories=(route, food),
        futures=futures,
        hop_limit=2,
    )
    assert biases["move-4"] > 0.0
    assert biases["move-4"] > biases["move-2"]


@pytest.mark.asyncio
async def test_deliberation_uses_route_evidence_only_in_deterministic_mode() -> None:
    owner = AgentId("agent-1")
    observation = _current_observation()
    route, food = _known_remote_route(owner)
    futures = (
        _future("move-2", ActionDirection.MOVE, "loc-2"),
        _future("move-4", ActionDirection.MOVE, "loc-4"),
    )
    default_choice = MultiCriteriaIntentionSelector()
    loop_input = _loop_input(owner, observation, (route, food))

    disabled = await default_choice.select(
        loop_input,
        _motivation(futures),
        PossibleFutures(owner, futures, confidence=1.0),
    )
    enabled = await default_choice.select(
        loop_input,
        _motivation(futures),
        PossibleFutures(owner, futures, confidence=1.0),
        regional_migration_cognition_mode="deterministic",
        regional_migration_hop_limit=2,
    )
    repeated = await default_choice.select(
        loop_input,
        _motivation(futures),
        PossibleFutures(owner, futures, confidence=1.0),
        regional_migration_cognition_mode="deterministic",
        regional_migration_hop_limit=2,
    )
    assert disabled.selected_future_id == "move-2"
    assert enabled.selected_future_id == "move-4"
    assert repeated == enabled
    plan = await CommandPlanner().plan(
        loop_input,
        enabled,
        PossibleFutures(owner, futures, confidence=1.0),
    )
    assert type(plan.command) is Move
    assert plan.command.destination_id == EntityId("loc-4")


def test_route_search_respects_hop_bound_and_stale_evidence() -> None:
    owner = AgentId("agent-1")
    observation = _current_observation(tick=1000)
    route, food = _known_remote_route(owner, source_tick=5)
    move = _future("move-4", ActionDirection.MOVE, "loc-4")
    bounded = destination_action_biases(
        owner_id=owner,
        observation=observation,
        memories=(route, food),
        futures=(move,),
        hop_limit=1,
    )
    searched = destination_action_biases(
        owner_id=owner,
        observation=observation,
        memories=(route, food),
        futures=(move,),
        hop_limit=2,
    )
    assert bounded.get("move-4", 0.0) <= 0.0
    assert searched["move-4"] > 0.0
    assert searched["move-4"] < 0.1


def test_route_cost_and_testimony_confidence_affect_destination_bias() -> None:
    owner = AgentId("agent-1")
    observation = _current_observation()
    cheap_route, direct_report = _known_remote_route(owner)
    expensive_route, _ = _known_remote_route(owner, duration=20, fatigue=80.0)
    testimony = _food_trace(
        owner,
        tick=5,
        source_kind=MemorySourceKind.COMMUNICATED,
    )
    move = _future("move-4", ActionDirection.MOVE, "loc-4")

    def score(memories: tuple[MemoryTrace, ...]) -> float:
        return destination_action_biases(
            owner_id=owner,
            observation=observation,
            memories=memories,
            futures=(move,),
            hop_limit=2,
        )["move-4"]

    direct_score = score((cheap_route, direct_report))
    testimony_score = score((cheap_route, testimony))
    expensive_score = score((expensive_route, direct_report))
    assert direct_score > testimony_score > 0.0
    assert direct_score > expensive_score


def test_private_destination_evidence_supports_return_route() -> None:
    owner = AgentId("agent-1")
    current = _observation(
        location="loc-5", tick=20, hunger=90.0, exits=(_exit("loc-4"),)
    )
    visited = _observation(
        location="loc-5", tick=5, exits=(_exit("loc-4", duration=2, fatigue=3.0),)
    )
    return_route = destination_memory_trace(
        owner_id=owner,
        observer_body_id=visited.observer_id,
        observation=visited,
        exit_view=visited.exits[0],
    )
    remembered_food = _food_trace(owner, tick=4, location="loc-4")
    bias = destination_action_biases(
        owner_id=owner,
        observation=current,
        memories=(return_route, remembered_food),
        futures=(_future("return-home", ActionDirection.MOVE, "loc-4"),),
        hop_limit=1,
    )
    assert bias["return-home"] > 0.0


def test_traveller_is_biased_to_wait_and_unknown_evidence_stays_unrewarded() -> None:
    owner = AgentId("agent-1")
    journey = ObservedJourney(
        origin_location_id=EntityId("loc-1"),
        destination_location_id=EntityId("loc-2"),
        origin_region_id="north",
        destination_region_id="south",
        start_tick=10,
        due_tick=12,
        arrival_wait_deadline_tick=13,
        phase=ObservedJourneyPhase.PREPARATION,
        participant_count=1,
    )
    travelling = _observation(
        location="loc-1", tick=10, exits=(_exit("loc-2"),), journey=journey
    )
    wait = _future("wait", ActionDirection.WAIT, None)
    move = _future("move-2", ActionDirection.MOVE, "loc-2")
    travel_bias = destination_action_biases(
        owner_id=owner,
        observation=travelling,
        memories=(),
        futures=(wait, move),
        hop_limit=1,
    )
    unknown_bias = destination_action_biases(
        owner_id=owner,
        observation=_current_observation(hunger=0.0),
        memories=(),
        futures=(move,),
        hop_limit=1,
    )
    assert travel_bias["wait"] > travel_bias["move-2"]
    assert unknown_bias.get("move-2", 0.0) <= 0.0


@pytest.mark.asyncio
async def test_local_survival_drive_remains_ahead_of_remote_food_evidence() -> None:
    owner = AgentId("agent-1")
    water = ObservedResource(
        entity_id=EntityId("water-1"),
        name="Spring",
        kind=ResourceKind.WATER,
        quantity=2.0,
        unit="L",
    )
    observation = _current_observation(hunger=90.0, thirst=90.0, resources=(water,))
    route, food = _known_remote_route(owner)
    drink = replace(
        _future("drink", ActionDirection.DRINK, "water-1"),
        drive_effects=(DriveEffect(kind=DriveKind.THIRST, delta=-0.9, confidence=1.0),),
    )
    futures = (
        drink,
        _future("move-2", ActionDirection.MOVE, "loc-2"),
        _future("move-4", ActionDirection.MOVE, "loc-4"),
    )
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(owner, observation, (route, food)),
        replace(
            _motivation(futures),
            active_drive_kinds=(DriveKind.THIRST,),
        ),
        PossibleFutures(owner, futures, confidence=1.0),
        regional_migration_cognition_mode="deterministic",
        regional_migration_hop_limit=2,
    )
    assert selected.selected_future_id == "drink"


@pytest.mark.asyncio
async def test_enabled_traveller_selects_wait_through_normal_planner() -> None:
    owner = AgentId("agent-1")
    journey = ObservedJourney(
        origin_location_id=EntityId("loc-1"),
        destination_location_id=EntityId("loc-2"),
        origin_region_id="north",
        destination_region_id="south",
        start_tick=10,
        due_tick=12,
        arrival_wait_deadline_tick=13,
        phase=ObservedJourneyPhase.PREPARATION,
        participant_count=1,
    )
    observation = _observation(
        location="loc-1", tick=10, exits=(_exit("loc-2"),), journey=journey
    )
    futures = (
        _future("wait", ActionDirection.WAIT, None),
        _future("move-2", ActionDirection.MOVE, "loc-2"),
    )
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(owner, observation, ()),
        _motivation(futures),
        PossibleFutures(owner, futures, confidence=1.0),
        regional_migration_cognition_mode="deterministic",
        regional_migration_hop_limit=1,
    )
    plan = await CommandPlanner().plan(
        _loop_input(owner, observation, ()),
        selected,
        PossibleFutures(owner, futures, confidence=1.0),
    )
    assert selected.selected_future_id == "wait"
    assert type(plan.command) is Wait


@pytest.mark.asyncio
async def test_missing_destination_evidence_preserves_existing_stay_choice() -> None:
    owner = AgentId("agent-1")
    observation = _current_observation(hunger=0.0)
    wait = replace(
        _future("wait", ActionDirection.WAIT, None),
        drive_effects=(
            DriveEffect(kind=DriveKind.PREDICTABILITY, delta=0.8, confidence=1.0),
        ),
    )
    move = _future("move-2", ActionDirection.MOVE, "loc-2")
    futures = (wait, move)
    motivation = replace(
        _motivation(futures),
        active_drive_kinds=(DriveKind.PREDICTABILITY,),
    )
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(owner, observation, ()),
        motivation,
        PossibleFutures(owner, futures, confidence=1.0),
        regional_migration_cognition_mode="deterministic",
        regional_migration_hop_limit=1,
    )
    assert selected.selected_future_id == "wait"


@pytest.mark.asyncio
async def test_unknown_route_can_still_be_explored_for_novelty() -> None:
    owner = AgentId("agent-1")
    observation = _current_observation(hunger=0.0)
    wait = _future("wait", ActionDirection.WAIT, None)
    explore = replace(
        _future("move-2", ActionDirection.MOVE, "loc-2"),
        drive_effects=(DriveEffect(kind=DriveKind.NOVELTY, delta=0.8, confidence=1.0),),
    )
    futures = (wait, explore)
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(owner, observation, ()),
        replace(
            _motivation(futures),
            active_drive_kinds=(DriveKind.NOVELTY,),
        ),
        PossibleFutures(owner, futures, confidence=1.0),
        regional_migration_cognition_mode="deterministic",
        regional_migration_hop_limit=1,
    )
    assert selected.selected_future_id == "move-2"
