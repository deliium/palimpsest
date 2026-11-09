"""V4-17 owner-scoped route-quality beliefs in destination memories."""

from __future__ import annotations

import pytest

from agents.cognition.regional_migration import (
    REGIONAL_ROUTE_QUALITY_POLICY_VERSION,
    destination_memory_trace,
)
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
from world.travel_network import (
    derive_initial_route_conditions,
)

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")


def _state() -> WorldState:
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(LocationRegion(A, "west"), LocationRegion(B, "east")),
        routes=(RouteSpec(A, B, 2, 3.0),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=2,
        cognition_mode=CognitionMode.DETERMINISTIC,
    )
    base = WorldState(
        WorldRevision(0),
        locations=(
            make_location("loc-a", adjacent=("loc-b",)),
            make_location("loc-b", adjacent=("loc-a",)),
        ),
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=(make_weather("loc-a"), make_weather("loc-b")),
        regions_migration=spec,
    )
    rows = derive_initial_route_conditions(base, season=None, tick=0)
    from world._state import rebuild_world_state

    return rebuild_world_state(base, travel_network=rows)


def _observation(state: WorldState) -> Observation:
    return PerceptionService(travel_network_active=True).project(
        world_id=WorldId("world-cognition"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=0),
    )[0]


def test_route_quality_concepts_are_persisted() -> None:
    observation = _observation(_state())
    exit_view = observation.exits[0]
    trace = destination_memory_trace(
        owner_id=AgentId("agent-1"),
        observer_body_id=EntityId("body-1"),
        observation=observation,
        exit_view=exit_view,
    )
    concepts = {item.mention_id.value: item.concept for item in trace.concepts}
    assert concepts["c-status"] == "route_status:open"
    assert concepts["c-availability"] == "route_seasonal_availability:open"
    assert concepts["c-blockage"] == "route_blockage_cause:none"
    assert concepts["c-capacity"] == "route_capacity:8"
    assert concepts["c-risk"].startswith("route_risk:")
    assert concepts["c-quality"].startswith("route_infrastructure_quality:")
    predicates = {relation.predicate for relation in trace.relations}
    assert "destination_route_status" in predicates
    assert "destination_route_capacity" in predicates
    assert REGIONAL_ROUTE_QUALITY_POLICY_VERSION == "regional-route-quality.v1"


def test_legacy_exit_without_route_fields_adds_no_route_concepts() -> None:
    observation = _observation(_state())
    from dataclasses import replace

    legacy_exit = replace(
        observation.exits[0],
        route_status=None,
        route_seasonal_availability=None,
        route_blockage_cause=None,
        route_capacity=None,
        route_risk=None,
        route_infrastructure_quality=None,
    )
    trace = destination_memory_trace(
        owner_id=AgentId("agent-1"),
        observer_body_id=EntityId("body-1"),
        observation=observation,
        exit_view=legacy_exit,
    )
    assert not any(
        item.mention_id.value in {"c-status", "c-capacity", "c-quality"}
        for item in trace.concepts
    )


def test_foreign_owner_trace_is_rejected() -> None:
    observation = _observation(_state())
    with pytest.raises(ValueError, match="foreign-owner destination evidence rejected"):
        from agents.cognition.regional_migration import destination_action_biases

        trace = _remote_trace(AgentId("other"), status="open")
        destination_action_biases(
            owner_id=AgentId("agent-1"),
            observation=observation,
            memories=(trace,),
            futures=(),
            hop_limit=2,
        )


def _remote_trace(owner: AgentId, *, status: str) -> MemoryTrace:
    concepts = [
        ConceptMention(MentionId("food"), "resource:food"),
        ConceptMention(MentionId("c-status"), status),
        ConceptMention(MentionId("c-capacity"), "8"),
        ConceptMention(MentionId("c-risk"), "0.000000"),
        ConceptMention(MentionId("c-quality"), "0.000000"),
    ]
    return MemoryTrace(
        memory_id=MemoryId("remote-route"),
        owner_id=owner,
        world_revision=WorldRevision(0),
        concepts=tuple(concepts),
        entities=(
            EntityMention(MentionId("origin"), "origin", A),
            EntityMention(MentionId("destination"), "destination", EntityId("loc-c")),
        ),
        relations=(),
        context=MemorySituationContext(
            location_id=A, tags=("direct", "destination", "route")
        ),
        emotional_salience=0.3,
        confidence=0.95,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=0,
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
        lineage=MemoryLineage(),
    )
