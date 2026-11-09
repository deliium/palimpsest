"""V4-17 bounded subjective path planning from route-quality beliefs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.models import ActionDirection, ImaginedFuture
from agents.cognition.regional_migration import destination_action_biases
from agents.models import AgentId
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._perception import PerceptionService
from world._state import WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation, ObservationContext
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.travel_network import derive_initial_route_conditions
from world.values import Hunger

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")
C = EntityId("loc-c")


def _state() -> WorldState:
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(A, "west"),
            LocationRegion(B, "east"),
            LocationRegion(C, "east"),
        ),
        routes=(RouteSpec(A, B, 2, 3.0), RouteSpec(B, C, 2, 3.0)),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=2,
        cognition_mode=CognitionMode.DETERMINISTIC,
    )
    body = replace(alive_body("body-1", location_id="loc-a"), hunger=Hunger(70))
    base = WorldState(
        WorldRevision(0),
        locations=(
            make_location("loc-a", adjacent=("loc-b",)),
            make_location("loc-b", adjacent=("loc-a", "loc-c")),
            make_location("loc-c", adjacent=("loc-b",)),
        ),
        bodies=(body,),
        weather=tuple(make_weather(item) for item in ("loc-a", "loc-b", "loc-c")),
        regions_migration=spec,
    )
    rows = derive_initial_route_conditions(base, season=None, tick=0)
    from world._state import rebuild_world_state

    return rebuild_world_state(base, travel_network=rows)


def _observation(*, tick: int = 0) -> Observation:
    return PerceptionService(travel_network_active=True).project(
        world_id=WorldId("world-planning"),
        state=_state(),
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=tick),
    )[0]


def _future(
    direction: ActionDirection = ActionDirection.MOVE, target: str = "loc-b"
) -> ImaginedFuture:
    return ImaginedFuture(
        future_id=f"future-{direction.value}",
        claim_codes=(),
        confidence=0.5,
        direction=direction,
        target_entity_id=target,
    )


def _belief(
    owner: AgentId, *, status: str, source_tick: int = 0, confidence: float = 0.95
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(f"remote-route-{status}-{source_tick}"),
        owner_id=owner,
        world_revision=WorldRevision(source_tick),
        concepts=(
            ConceptMention(MentionId("food"), "resource:food"),
            ConceptMention(MentionId("c-status"), f"route_status:{status}"),
            ConceptMention(MentionId("c-capacity"), "route_capacity:8"),
            ConceptMention(MentionId("c-risk"), "route_risk:0.100000"),
            ConceptMention(
                MentionId("c-quality"), "route_infrastructure_quality:0.000000"
            ),
        ),
        entities=(
            EntityMention(MentionId("origin"), "origin", B),
            EntityMention(MentionId("destination"), "destination", C),
        ),
        relations=(),
        context=MemorySituationContext(
            location_id=C, tags=("direct", "destination", "route")
        ),
        emotional_salience=0.3,
        confidence=confidence,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=source_tick,
        ),
        created_tick=source_tick,
        source_tick=source_tick,
        last_access_tick=source_tick,
        access_count=0,
        lineage=MemoryLineage(),
    )


def test_open_belief_biases_first_hop() -> None:
    owner = AgentId("agent-1")
    biases = destination_action_biases(
        owner_id=owner,
        observation=_observation(),
        memories=(_belief(owner, status="open"),),
        futures=(_future(),),
        hop_limit=2,
    )
    assert biases["future-move"] > 0.0


def test_closed_belief_is_penalized_not_enforced() -> None:
    owner = AgentId("agent-1")
    open_bias = destination_action_biases(
        owner_id=owner,
        observation=_observation(),
        memories=(_belief(owner, status="open"),),
        futures=(_future(),),
        hop_limit=2,
    )["future-move"]
    closed_bias = destination_action_biases(
        owner_id=owner,
        observation=_observation(),
        memories=(_belief(owner, status="closed"),),
        futures=(_future(),),
        hop_limit=2,
    )["future-move"]
    assert closed_bias < open_bias


def test_restricted_belief_is_mildly_penalized() -> None:
    owner = AgentId("agent-1")
    open_bias = destination_action_biases(
        owner_id=owner,
        observation=_observation(),
        memories=(_belief(owner, status="open"),),
        futures=(_future(),),
        hop_limit=2,
    )["future-move"]
    restricted_bias = destination_action_biases(
        owner_id=owner,
        observation=_observation(),
        memories=(_belief(owner, status="restricted"),),
        futures=(_future(),),
        hop_limit=2,
    )["future-move"]
    assert restricted_bias < open_bias


def test_stale_belief_loses_influence() -> None:
    owner = AgentId("agent-1")
    fresh = destination_action_biases(
        owner_id=owner,
        observation=_observation(tick=10),
        memories=(_belief(owner, status="open", source_tick=9),),
        futures=(_future(),),
        hop_limit=2,
    )["future-move"]
    stale = destination_action_biases(
        owner_id=owner,
        observation=_observation(tick=100),
        memories=(_belief(owner, status="open", source_tick=1),),
        futures=(_future(),),
        hop_limit=2,
    )["future-move"]
    assert stale < fresh


def test_no_belief_means_no_bias() -> None:
    biases = destination_action_biases(
        owner_id=AgentId("agent-1"),
        observation=_observation(),
        memories=(),
        futures=(_future(),),
        hop_limit=2,
    )
    assert not any(value > 0.0 for value in biases.values())


def test_transport_capacity_penalty_is_applied() -> None:
    owner = AgentId("agent-1")
    observation = _observation()
    low_capacity_exit = replace(observation.exits[0], route_capacity=1)
    low_capacity_observation = replace(
        observation,
        exits=(low_capacity_exit, *observation.exits[1:]),
    )
    move_biases = destination_action_biases(
        owner_id=owner,
        observation=low_capacity_observation,
        memories=(_belief(owner, status="open"),),
        futures=(_future(),),
        hop_limit=2,
    )
    transport_biases = destination_action_biases(
        owner_id=owner,
        observation=low_capacity_observation,
        memories=(_belief(owner, status="open"),),
        futures=(_future(ActionDirection.TRANSPORT),),
        hop_limit=2,
    )
    assert move_biases["future-move"] > transport_biases["future-transport"] + 1.9
