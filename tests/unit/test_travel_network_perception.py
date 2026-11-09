"""V4-17 adjacent route facts on VisibleExit and observation round-trip."""

from __future__ import annotations

import pytest

from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._perception import PerceptionService
from world._state import WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation, ObservationContext, VisibleExit
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
    derive_initial_route_conditions,
)

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")
C = EntityId("loc-c")


def _state(*, active: bool) -> WorldState:
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(A, "west"),
            LocationRegion(B, "east"),
            LocationRegion(C, "east"),
        ),
        routes=(RouteSpec(A, B, 2, 3.0), RouteSpec(A, C, 2, 3.0)),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    locations = (
        make_location("loc-a", adjacent=("loc-b", "loc-c")),
        make_location("loc-b", adjacent=("loc-a",)),
        make_location("loc-c", adjacent=("loc-a",)),
    )
    base = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=tuple(make_weather(location.entity_id.value) for location in locations),
        regions_migration=spec,
    )
    if not active:
        return base
    rows = derive_initial_route_conditions(base, season=None, tick=0)
    from world._state import rebuild_world_state

    return rebuild_world_state(base, travel_network=rows)


def _observe(state: WorldState, *, active: bool) -> Observation:
    service = PerceptionService(travel_network_active=active)
    return service.project(
        world_id=WorldId("world-perception"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=0),
    )[0]


def test_active_exits_carry_all_route_facts() -> None:
    observation = _observe(_state(active=True), active=True)
    assert len(observation.exits) == 2
    for exit_row in observation.exits:
        assert exit_row.route_status in {"open", "restricted", "closed"}
        assert exit_row.route_seasonal_availability in {
            "open",
            "restricted",
            "closed",
        }
        assert exit_row.route_blockage_cause in {
            "none",
            "weather",
            "seasonal",
            "hazard",
        }
        assert 1 <= (exit_row.route_capacity or 0) <= 24
        assert exit_row.route_risk is not None
        assert 0.0 <= exit_row.route_risk <= 1.0
        assert exit_row.route_infrastructure_quality is not None
        assert 0.0 <= exit_row.route_infrastructure_quality <= 1.0
        assert exit_row.travel_duration_ticks is not None
        assert exit_row.fatigue_cost is not None


def test_inactive_exits_preserve_legacy_shape() -> None:
    observation = _observe(_state(active=False), active=False)
    assert len(observation.exits) == 2
    for exit_row in observation.exits:
        assert exit_row.route_status is None
        assert exit_row.route_capacity is None
        assert exit_row.travel_duration_ticks == 2


def test_only_adjacent_exits_are_present() -> None:
    observation = _observe(_state(active=True), active=True)
    assert [exit_row.destination_id for exit_row in observation.exits] == [B, C]
    assert all(exit_row.destination_id != A for exit_row in observation.exits)


def test_partial_route_fields_are_rejected() -> None:
    with pytest.raises(
        ValueError, match="VisibleExit route fields must be all present or all absent"
    ):
        VisibleExit(
            destination_id=B,
            name="B",
            travel_duration_ticks=1,
            fatigue_cost=0.0,
            route_status="open",
        )


def test_route_fields_round_trip_and_legacy_payloads_decode() -> None:
    observation = _observe(_state(active=True), active=True)
    decoded = decode_domain(encode_domain(observation))
    assert decoded == observation
    legacy = _observe(_state(active=False), active=False)
    assert decode_domain(encode_domain(legacy)) == legacy


def test_route_status_can_be_closed() -> None:
    state = _state(active=True)
    from world._state import rebuild_world_state

    row = state.route_condition(A, B)
    assert row is not None
    closed = RouteCondition(
        origin_id=A,
        destination_id=B,
        status=RouteStatus.CLOSED,
        seasonal_availability=SeasonalAvailability.CLOSED,
        blockage_cause=RouteBlockageCause.SEASONAL,
        duration_ticks=3,
        fatigue_cost=3.0,
        capacity=4,
        risk=0.4,
        infrastructure_quality=0.0,
        reason_codes=("season_winter", "route_closed"),
        as_of_tick=0,
    )
    state = rebuild_world_state(state, travel_network=(closed,))
    observation = _observe(state, active=True)
    exit_row = next(item for item in observation.exits if item.destination_id == B)
    assert exit_row.route_status == "closed"
