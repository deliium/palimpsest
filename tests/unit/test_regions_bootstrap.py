"""Optional region topology and journeys survive bootstrap and state rebuilds."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap, _materialize_world
from tests.physical_helpers import dead_body
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    weather_for_locations,
)
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId, WorldId, WorldRevision
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _topology() -> tuple[tuple, RegionsMigrationSpec]:
    locations = connected_locations(
        ("loc-1", "One"), ("loc-2", "Two"), ("loc-3", "Three")
    )
    spec = RegionsMigrationSpec(
        regions=(
            RegionDefinition("north", "North"),
            RegionDefinition("south", "South"),
        ),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "north"),
            LocationRegion(EntityId("loc-3"), "south"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 1.0),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=3,
        destination_hop_limit=2,
        cognition_mode=CognitionMode.DISABLED,
    )
    return locations, spec


def _journey(*, participant_id: str = "body-1") -> Journey:
    return Journey(
        journey_id="journey-1",
        participant_body_ids=(EntityId(participant_id),),
        actor_body_id=EntityId(participant_id),
        origin_location_id=EntityId("loc-1"),
        destination_location_id=EntityId("loc-2"),
        origin_region_id="north",
        destination_region_id=None,
        start_tick=1,
        due_tick=2,
        charged_fatigue_cost=1.0,
        arrival_wait_deadline_tick=3,
    )


def test_bootstrap_materializes_regions_and_journeys() -> None:
    locations, spec = _topology()
    body = alive_body("body-1", location_id="loc-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-regions"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(body,),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
        regions_migration=spec,
        journeys=(_journey(),),
    )
    world = _materialize_world(bootstrap)
    state = world.state
    assert state.regions_migration == spec
    assert state.journeys is not None
    assert state.journeys["journey-1"] == _journey()


def test_unrelated_rebuild_preserves_optional_spatial_state() -> None:
    locations, spec = _topology()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(alive_body("body-1", location_id="loc-1"),),
        weather=weather_for_locations(locations),
        regions_migration=spec,
        journeys=(_journey(),),
    )
    rebuilt = rebuild_world_state(state, revision=WorldRevision(1))
    assert rebuilt.regions_migration == spec
    assert rebuilt.journeys == state.journeys


def test_structural_state_allows_dead_prefix_but_finalized_boundary_rejects() -> None:
    locations, spec = _topology()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(dead_body("body-1", location_id="loc-1"),),
        weather=weather_for_locations(locations),
        regions_migration=spec,
        journeys=(_journey(),),
    )
    with pytest.raises(ValueError, match="journey_participant_dead"):
        state.validate_finalized_boundary(1)


def test_finalized_boundary_rejects_overdue_pending_journey() -> None:
    locations, spec = _topology()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(alive_body("body-1", location_id="loc-1"),),
        weather=weather_for_locations(locations),
        regions_migration=spec,
        journeys=(_journey(),),
    )
    with pytest.raises(ValueError, match="journey_overdue_at_boundary"):
        state.validate_finalized_boundary(3)


def test_world_state_rejects_duplicate_participation_and_bad_region_identity() -> None:
    locations, spec = _topology()
    body = alive_body("body-1", location_id="loc-1")
    duplicate = Journey(
        journey_id="journey-2",
        participant_body_ids=(body.entity_id,),
        actor_body_id=body.entity_id,
        origin_location_id=EntityId("loc-1"),
        destination_location_id=EntityId("loc-2"),
        origin_region_id="north",
        destination_region_id=None,
        start_tick=2,
        due_tick=3,
        charged_fatigue_cost=0,
        arrival_wait_deadline_tick=3,
    )
    with pytest.raises(ValueError, match="journey_busy"):
        WorldState(
            WorldRevision(0),
            locations=locations,
            bodies=(body,),
            weather=weather_for_locations(locations),
            regions_migration=spec,
            journeys=(_journey(), duplicate),
        )
    mismatched = Journey(
        journey_id="journey-3",
        participant_body_ids=(body.entity_id,),
        actor_body_id=body.entity_id,
        origin_location_id=EntityId("loc-1"),
        destination_location_id=EntityId("loc-2"),
        origin_region_id="south",
        destination_region_id=None,
        start_tick=1,
        due_tick=2,
        charged_fatigue_cost=0,
        arrival_wait_deadline_tick=3,
    )
    with pytest.raises(ValueError, match="journey_region_mismatch"):
        WorldState(
            WorldRevision(0),
            locations=locations,
            bodies=(body,),
            weather=weather_for_locations(locations),
            regions_migration=spec,
            journeys=(mismatched,),
        )


def test_bootstrap_rejects_route_to_non_edge_and_journey_without_spec() -> None:
    locations, spec = _topology()
    invalid = RegionsMigrationSpec(
        regions=spec.regions,
        location_regions=spec.location_regions,
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-3"), 2, 0),),
        max_arrival_wait_ticks=0,
        residence_min_ticks=1,
        destination_memory_limit=1,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    with pytest.raises(ValueError, match="route_non_edge"):
        WorldBootstrap(
            world_id=WorldId("world-bad-route"),
            revision=WorldRevision(0),
            locations=locations,
            weather=weather_for_locations(locations),
            regions_migration=invalid,
        )
    with pytest.raises(ValueError, match="journey_channel_off"):
        WorldBootstrap(
            world_id=WorldId("world-bad-journey"),
            revision=WorldRevision(0),
            locations=locations,
            weather=weather_for_locations(locations),
            journeys=(_journey(),),
        )
