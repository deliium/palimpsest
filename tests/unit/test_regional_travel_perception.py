"""Regional perception exposes local facts without sharing the world atlas."""

from __future__ import annotations

import json

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import PhysicalRules
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _bootstrap(*, regional: bool) -> WorldBootstrap:
    locations = (
        make_location(
            "loc-1", name="Local", adjacent=("loc-2", "loc-3"), body_capacity=4
        ),
        make_location(
            "loc-2", name="Known Region", adjacent=("loc-1",), body_capacity=4
        ),
        make_location("loc-3", name="Unassigned", adjacent=("loc-1",), body_capacity=4),
    )
    body = alive_body("body-1", location_id="loc-1")
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("south", "South"), RegionDefinition("west", "West")),
        location_regions=(LocationRegion(EntityId("loc-2"), "south"),),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 3, 5.0),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    journey = Journey(
        journey_id="journey-observed",
        participant_body_ids=(body.entity_id,),
        actor_body_id=body.entity_id,
        origin_location_id=EntityId("loc-1"),
        destination_location_id=EntityId("loc-2"),
        origin_region_id=None,
        destination_region_id="south",
        start_tick=0,
        due_tick=2,
        charged_fatigue_cost=5,
        arrival_wait_deadline_tick=4,
    )
    return WorldBootstrap(
        world_id=WorldId("world-perception-regions"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(body,),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
        regions_migration=spec if regional else None,
        journeys=(journey,) if regional else None,
    )


def _observation(*, regional: bool):
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=88,
            physical_rules=PhysicalRules(),
        ),
        bootstrap=_bootstrap(regional=regional),
    )
    return engine.observe().observations[0]


def test_enabled_observation_exposes_regional_and_self_journey_facts() -> None:
    observation = _observation(regional=True)
    assert tuple(item.entity_id for item in observation.locations) == (
        EntityId("loc-1"),
    )
    assert observation.resources == ()
    assert observation.regional_context is not None
    assert observation.regional_context.region_id is None
    assert observation.regional_context.label is None
    exits = {item.destination_id: item for item in observation.exits}
    assert exits[EntityId("loc-2")].travel_duration_ticks == 3
    assert exits[EntityId("loc-2")].fatigue_cost == 5.0
    assert exits[EntityId("loc-2")].destination_region_id == "south"
    assert exits[EntityId("loc-3")].travel_duration_ticks == 1
    assert exits[EntityId("loc-3")].fatigue_cost == PhysicalRules().move_fatigue
    assert exits[EntityId("loc-3")].destination_region_id is None
    assert observation.self_body is not None
    assert observation.self_body.journey is not None
    assert observation.self_body.journey.destination_location_id == EntityId("loc-2")
    assert observation.self_body.journey.destination_region_id == "south"
    encoded = json.loads(encode_domain(observation))
    assert decode_domain(encode_domain(observation)) == observation
    assert encoded["data"]["regional_context"] == {"label": None, "region_id": None}
    assert encoded["data"]["exits"][1]["destination_region_id"] is None
    assert "resources" in encoded["data"]
    assert "journey" in encoded["data"]["self_body"]


def test_channel_off_observation_wire_does_not_gain_regional_fields() -> None:
    observation = _observation(regional=False)
    encoded = json.loads(encode_domain(observation))["data"]
    assert "regional_context" not in encoded
    assert "journey" not in encoded["self_body"]
    assert all(
        set(exit_row) == {"destination_id", "name"} for exit_row in encoded["exits"]
    )
