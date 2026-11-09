"""V4-17 tick-boundary route transitions."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._state import WorldState
from world._travel_network import advance_route_conditions
from world.environment import ActiveHazard, HazardKind, Season
from world.identifiers import EntityId, WorldRevision
from world.infrastructure import (
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
)
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.travel_network import (
    RouteBlockageCause,
    RouteStatus,
    derive_initial_route_conditions,
)
from world.values import WeatherCondition

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")


def _state(
    *,
    infrastructure: tuple[InfrastructureAsset, ...] = (),
    weather: WeatherCondition = WeatherCondition.CLEAR,
    hazards: tuple[ActiveHazard, ...] = (),
) -> WorldState:
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(LocationRegion(A, "west"), LocationRegion(B, "east")),
        routes=(RouteSpec(A, B, 2, 3.0),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    state = WorldState(
        WorldRevision(0),
        locations=(
            make_location("loc-a", adjacent=("loc-b",)),
            make_location("loc-b", adjacent=("loc-a",)),
        ),
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=(
            make_weather("loc-a", condition=weather),
            make_weather("loc-b", condition=weather),
        ),
        active_hazards=hazards,
        infrastructure=infrastructure,
        regions_migration=spec,
    )
    rows = derive_initial_route_conditions(state, season=Season.SPRING, tick=0)
    from world._state import rebuild_world_state

    return rebuild_world_state(state, travel_network=rows)


def _road(integrity: float = 0.7) -> InfrastructureAsset:
    return InfrastructureAsset(
        asset_id=EntityId("infra-road"),
        kind=InfrastructureKind.ROAD,
        topology=InfrastructureTopology.EDGE,
        status=InfrastructureStatus.OPERATIONAL,
        integrity=integrity,
        location_id=A,
        endpoint_location_id=B,
        linked_structure_id=None,
        linked_project_id=EntityId("proj-1"),
        created_tick=0,
        last_maintained_tick=0,
    )


def test_season_change_closes_and_emits_once() -> None:
    state, transitions = advance_route_conditions(
        _state(), season=Season.WINTER, tick=1
    )
    assert len(transitions) == 1
    event = transitions[0]
    assert event.origin_location_id == A
    assert event.current_status == "closed"
    assert event.current_seasonal_availability == "closed"
    assert event.blockage_cause == "seasonal"
    assert event.reason_codes == (
        "season_winter",
        "route_closed",
        "infrastructure_absent",
    )
    row = state.route_condition(A, B)
    assert row is not None
    assert row.status is RouteStatus.CLOSED


def test_weather_change_restricts_and_emits() -> None:
    from world._state import rebuild_world_state

    rain = (
        make_weather("loc-a", condition=WeatherCondition.RAIN),
        make_weather("loc-b", condition=WeatherCondition.RAIN),
    )
    state = rebuild_world_state(
        _state(), weather={item.location_id: item for item in rain}
    )
    _, transitions = advance_route_conditions(state, season=Season.SPRING, tick=1)
    assert len(transitions) == 1
    assert transitions[0].current_status == "restricted"
    assert transitions[0].blockage_cause == "weather"


def test_road_quality_change_emits_even_when_status_stays_open() -> None:
    from world._state import rebuild_world_state

    road = _road()
    state = rebuild_world_state(_state(), infrastructure={road.asset_id: road})
    _, transitions = advance_route_conditions(state, season=Season.SPRING, tick=1)
    assert len(transitions) == 1
    assert transitions[0].current_status == "open"
    assert transitions[0].infrastructure_quality == pytest.approx(0.7)
    assert transitions[0].duration_ticks == 1


def test_hazard_start_and_end_transition() -> None:
    hazard = ActiveHazard(
        location_id=A, kind=HazardKind.COLD_SNAP, start_tick=1, duration_ticks=2
    )
    started, transitions = advance_route_conditions(
        _state(hazards=(hazard,)), season=Season.SPRING, tick=1
    )
    assert len(transitions) == 1
    assert transitions[0].blockage_cause == "hazard"
    ended, end_transitions = advance_route_conditions(
        started, season=Season.SPRING, tick=3
    )
    assert len(end_transitions) == 1
    assert end_transitions[0].current_status == "open"
    row = ended.route_condition(A, B)
    assert row is not None
    assert row.blockage_cause is RouteBlockageCause.NONE


def test_unchanged_tick_emits_nothing_and_preserves_tick() -> None:
    state = _state()
    first = state.route_condition(A, B)
    assert first is not None
    unchanged, transitions = advance_route_conditions(
        state, season=Season.SPRING, tick=9
    )
    assert transitions == ()
    row = unchanged.route_condition(A, B)
    assert row is not None
    assert row.as_of_tick == first.as_of_tick == 0


def test_every_changed_edge_emits_in_order() -> None:
    _state_value, transitions = advance_route_conditions(
        _state(weather=WeatherCondition.STORM), season=Season.WINTER, tick=1
    )
    assert len(transitions) == 1
    assert transitions[0].current_status == "closed"
    assert transitions[0].blockage_cause == "weather"
