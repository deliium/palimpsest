"""V4-17 WorldState route channel and deterministic derivation."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._state import WorldState, rebuild_world_state
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
    RouteCondition,
    RouteStatus,
    SeasonalAvailability,
    default_route_condition,
    derive_initial_route_conditions,
    derive_route_condition,
    effective_route_condition,
)
from world.values import WeatherCondition

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")
C = EntityId("loc-c")


def _spec(*routes: RouteSpec) -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(A, "west"),
            LocationRegion(B, "east"),
            LocationRegion(C, "east"),
        ),
        routes=routes,
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _state(
    *,
    season_routes: tuple[RouteSpec, ...] = (RouteSpec(A, B, 2, 3.0),),
    infrastructure: tuple[InfrastructureAsset, ...] | None = None,
    weather: dict[str, WeatherCondition] | None = None,
    hazards: tuple[ActiveHazard, ...] = (),
    destination_capacity: int = 8,
    visibility: dict[str, float] | None = None,
    travel_network: tuple[RouteCondition, ...]
    | Mapping[tuple[str, str], RouteCondition]
    | None = None,
) -> WorldState:
    visibility = visibility or {}
    weather = weather or {}
    locations = (
        make_location(
            "loc-a",
            adjacent=("loc-b",),
            visibility_factor=visibility.get("loc-a", 1.0),
        ),
        make_location(
            "loc-b",
            adjacent=("loc-a", "loc-c"),
            body_capacity=destination_capacity,
            visibility_factor=visibility.get("loc-b", 1.0),
        ),
        make_location("loc-c", adjacent=("loc-b",)),
    )
    return WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=tuple(
            make_weather(
                location.entity_id.value,
                condition=weather.get(location.entity_id.value, WeatherCondition.CLEAR),
            )
            for location in locations
        ),
        active_hazards=hazards,
        infrastructure=infrastructure,
        regions_migration=_spec(*season_routes),
        travel_network=travel_network,
    )


def _asset(
    asset_id: str,
    kind: InfrastructureKind,
    *,
    integrity: float,
    location_id: EntityId = A,
    endpoint_location_id: EntityId | None = B,
    status: InfrastructureStatus = InfrastructureStatus.OPERATIONAL,
) -> InfrastructureAsset:
    return InfrastructureAsset(
        asset_id=EntityId(asset_id),
        kind=kind,
        topology=InfrastructureTopology.EDGE
        if kind is InfrastructureKind.ROAD
        else InfrastructureTopology.NODE,
        status=status,
        integrity=integrity,
        location_id=location_id,
        endpoint_location_id=endpoint_location_id
        if kind is InfrastructureKind.ROAD
        else None,
        linked_structure_id=None,
        linked_project_id=EntityId("proj-1"),
        created_tick=0,
        last_maintained_tick=0,
    )


def _condition(**changes: object) -> RouteCondition:
    values: dict[str, object] = {
        "origin_id": A,
        "destination_id": B,
        "status": RouteStatus.OPEN,
        "seasonal_availability": SeasonalAvailability.OPEN,
        "blockage_cause": RouteBlockageCause.NONE,
        "duration_ticks": 2,
        "fatigue_cost": 3.0,
        "capacity": 8,
        "risk": 0.0,
        "infrastructure_quality": 0.0,
        "reason_codes": (),
        "as_of_tick": 0,
    }
    values.update(changes)
    return RouteCondition(**values)  # type: ignore[arg-type]


def test_state_sorts_deduplicates_and_looks_up_routes() -> None:
    second = _condition(origin_id=B, destination_id=C)
    first = _condition()
    state = _state(travel_network=(second, first))
    assert state.travel_network == (first, second)
    assert state.route_condition(B, A) is first
    assert state.route_condition(A, C) is None
    mapping_state = _state(travel_network={first.edge_key: first})
    assert mapping_state.travel_network == (first,)


def test_state_rejects_duplicate_and_non_adjacent_routes() -> None:
    route = _condition()
    with pytest.raises(ValueError, match="travel_network_duplicate_route"):
        _state(travel_network=(route, route))
    with pytest.raises(ValueError, match="travel_network_non_adjacent"):
        _state(travel_network=(_condition(origin_id=A, destination_id=C),))


def test_state_route_cap_fails_closed() -> None:
    hub = make_location("hub", adjacent=tuple(f"leaf-{index}" for index in range(513)))
    leaves = tuple(
        make_location(f"leaf-{index}", adjacent=("hub",)) for index in range(513)
    )
    locations = (hub, *leaves)
    routes = tuple(
        _condition(
            origin_id=EntityId("hub"),
            destination_id=EntityId(f"leaf-{index}"),
        )
        for index in range(513)
    )
    with pytest.raises(ValueError, match="travel_network_route_cap_exceeded"):
        WorldState(
            WorldRevision(0),
            locations=locations,
            weather=tuple(
                make_weather(location.entity_id.value) for location in locations
            ),
            travel_network=routes,
        )


def test_rebuild_preserves_or_replaces_channel() -> None:
    route = _condition()
    state = _state(travel_network=(route,))
    preserved = rebuild_world_state(state)
    assert preserved.travel_network == (route,)
    empty = rebuild_world_state(state, travel_network=())
    assert empty.travel_network == ()


def test_inactive_state_has_empty_channel() -> None:
    state = _state()
    assert state.travel_network == ()
    assert state.route_condition(A, B) is None


def test_default_route_is_open() -> None:
    route = default_route_condition(A, B)
    assert route.status is RouteStatus.OPEN
    assert route.duration_ticks == 1
    assert route.fatigue_cost == 0.0
    assert route.capacity == 8
    assert route.infrastructure_quality == 0.0


def test_missing_route_spec_uses_default_move_fatigue() -> None:
    from world.models import default_physical_rules

    state = _state(season_routes=())
    route = derive_route_condition(state, A, B, season=Season.SPRING, tick=0)
    assert route.duration_ticks == 1
    assert route.fatigue_cost == pytest.approx(
        default_physical_rules().move_fatigue + route.risk * 2.0
    )


def test_road_reduces_duration_and_fatigue_and_raises_quality() -> None:
    state = _state(
        infrastructure=(_asset("infra-road", InfrastructureKind.ROAD, integrity=0.8),)
    )
    route = derive_route_condition(state, A, B, season=Season.SPRING, tick=5)
    assert route.status is RouteStatus.OPEN
    assert route.duration_ticks == 1
    assert route.fatigue_cost == pytest.approx(2.0)
    assert route.infrastructure_quality == pytest.approx(0.8)
    assert route.capacity == 10


def test_bridge_relief_applies_at_either_endpoint_only() -> None:
    bridge = _asset(
        "infra-bridge",
        InfrastructureKind.BRIDGE,
        integrity=0.6,
        location_id=B,
        endpoint_location_id=None,
    )
    state = _state(infrastructure=(bridge,))
    route = derive_route_condition(state, A, B, season=Season.WINTER, tick=0)
    assert route.status is RouteStatus.RESTRICTED
    assert route.seasonal_availability is SeasonalAvailability.RESTRICTED
    assert route.blockage_cause is RouteBlockageCause.SEASONAL
    assert "infrastructure_relief" in route.reason_codes
    other = derive_route_condition(state, B, C, season=Season.SPRING, tick=0)
    assert other.infrastructure_quality == pytest.approx(0.6)
    assert other.capacity == 9


def test_damaged_or_destroyed_assets_do_not_contribute() -> None:
    damaged = _asset(
        "infra-road",
        InfrastructureKind.ROAD,
        integrity=0.2,
        status=InfrastructureStatus.DAMAGED,
    )
    destroyed = _asset(
        "infra-bridge",
        InfrastructureKind.BRIDGE,
        integrity=0.0,
        location_id=A,
        endpoint_location_id=None,
        status=InfrastructureStatus.DESTROYED,
    )
    state = _state(infrastructure=(damaged, destroyed))
    route = derive_route_condition(state, A, B, season=Season.SPRING, tick=0)
    assert route.infrastructure_quality == 0.0
    assert route.duration_ticks == 2
    assert route.capacity == 8


def test_winter_closes_without_relief_and_restricts_with_relief() -> None:
    closed = derive_route_condition(_state(), A, B, season=Season.WINTER, tick=0)
    assert closed.status is RouteStatus.CLOSED
    assert closed.seasonal_availability is SeasonalAvailability.CLOSED
    assert closed.blockage_cause is RouteBlockageCause.SEASONAL
    assert closed.reason_codes == ("season_winter", "route_closed")

    road = _asset("infra-road", InfrastructureKind.ROAD, integrity=0.6)
    relief = derive_route_condition(
        _state(infrastructure=(road,)), A, B, season=Season.WINTER, tick=0
    )
    assert relief.status is RouteStatus.RESTRICTED
    assert relief.seasonal_availability is SeasonalAvailability.RESTRICTED
    assert relief.blockage_cause is RouteBlockageCause.SEASONAL


def test_storm_rain_and_autumn_rules() -> None:
    storm = derive_route_condition(
        _state(weather={"loc-a": WeatherCondition.STORM}),
        A,
        B,
        season=Season.SPRING,
        tick=0,
    )
    assert storm.status is RouteStatus.CLOSED
    assert storm.blockage_cause is RouteBlockageCause.WEATHER
    road = _asset("infra-road", InfrastructureKind.ROAD, integrity=0.6)
    relief = derive_route_condition(
        _state(weather={"loc-a": WeatherCondition.STORM}, infrastructure=(road,)),
        A,
        B,
        season=Season.SPRING,
        tick=0,
    )
    assert relief.status is RouteStatus.RESTRICTED
    assert relief.blockage_cause is RouteBlockageCause.WEATHER
    rain = derive_route_condition(
        _state(weather={"loc-b": WeatherCondition.RAIN}),
        A,
        B,
        season=Season.SPRING,
        tick=0,
    )
    assert rain.status is RouteStatus.RESTRICTED
    assert rain.duration_ticks == 3
    autumn = derive_route_condition(_state(), A, B, season=Season.AUTUMN, tick=0)
    assert autumn.status is RouteStatus.RESTRICTED
    assert autumn.blockage_cause is RouteBlockageCause.SEASONAL
    assert autumn.seasonal_availability is SeasonalAvailability.RESTRICTED


def test_hazard_restricts_and_changes_risk_and_capacity() -> None:
    hazard = ActiveHazard(
        location_id=A, kind=HazardKind.COLD_SNAP, start_tick=0, duration_ticks=3
    )
    route = derive_route_condition(
        _state(hazards=(hazard,)), A, B, season=Season.SPRING, tick=1
    )
    assert route.status is RouteStatus.RESTRICTED
    assert route.blockage_cause is RouteBlockageCause.HAZARD
    assert route.capacity == 6
    assert route.risk >= 0.3


def test_visibility_and_endpoint_capacity() -> None:
    state = _state(
        destination_capacity=2,
        visibility={"loc-a": 0.5, "loc-b": 0.5},
    )
    route = derive_route_condition(state, A, B, season=Season.SPRING, tick=0)
    assert route.capacity == 2
    assert route.risk == pytest.approx(0.05 + 0.02 * 2)


def test_initial_seed_is_deterministic_and_ordered() -> None:
    state = _state()
    first = derive_initial_route_conditions(state, season=Season.SPRING, tick=0)
    second = derive_initial_route_conditions(state, season=Season.SPRING, tick=0)
    assert first == second
    assert [row.edge_key for row in first] == [
        ("loc-a", "loc-b"),
        ("loc-b", "loc-c"),
    ]


def test_effective_condition_prefers_persisted_row() -> None:
    persisted = _condition(duration_ticks=9)
    state = _state(travel_network=(persisted,))
    assert (
        effective_route_condition(state, A, B, season=Season.WINTER, tick=0)
        is persisted
    )
    derived = effective_route_condition(_state(), B, C, season=Season.SPRING, tick=0)
    assert derived.edge_key == ("loc-b", "loc-c")
