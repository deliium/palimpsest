"""V4-17 route-condition replay projection."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._replay import project_events
from world._state import WorldState
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V23,
    EVENT_SCHEMA_REPLAY_V27,
    RouteConditionChanged,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.travel_network import RouteBlockageCause, RouteStatus, SeasonalAvailability

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")
C = EntityId("loc-c")


def _spec() -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
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
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _state() -> WorldState:
    locations = (
        make_location("loc-a", adjacent=("loc-b",)),
        make_location("loc-b", adjacent=("loc-a", "loc-c")),
        make_location("loc-c", adjacent=("loc-b",)),
    )
    return WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=tuple(make_weather(location.entity_id.value) for location in locations),
        regions_migration=_spec(),
    )


def _detail(
    *,
    origin: EntityId = A,
    destination: EntityId = B,
    status: str = "restricted",
    tick: int = 1,
) -> RouteConditionChanged:
    return RouteConditionChanged(
        origin_location_id=origin,
        destination_location_id=destination,
        previous_status="open",
        current_status=status,
        previous_seasonal_availability="open",
        current_seasonal_availability="restricted",
        duration_ticks=3,
        fatigue_cost=1.5,
        capacity=6,
        risk=0.3,
        infrastructure_quality=0.4,
        blockage_cause="seasonal",
        reason_codes=("season_autumn", "route_restricted"),
        season="autumn",
        as_of_tick=tick,
    )


def _event(
    detail: RouteConditionChanged,
    *,
    sequence: int = 0,
    schema_version: int = EVENT_SCHEMA_REPLAY_V27,
) -> object:
    return make_physical_replayable_event(
        event_id=EventId(f"event-route-{detail.as_of_tick}"),
        run_id="run-travel-replay",
        world_id=WorldId("world-travel-replay"),
        tick=detail.as_of_tick,
        sequence=sequence,
        resulting_revision=WorldRevision(detail.as_of_tick),
        details=detail,
        cause=SystemCause(
            cause_id=RequestId(f"cause-route-{sequence}"),
            effect_family=SystemEffectFamily.TRAVEL,
            entity_id=A,
            family_ordinal=sequence,
        ),
        occurrence=build_occurrence_context(detail, origin_location_id=None),
        schema_version=schema_version,
    )


def _project(state: WorldState, *events: object) -> WorldState:
    return project_events(
        state,
        events,  # type: ignore[arg-type]
        expected_run_id="run-travel-replay",
        expected_world_id=WorldId("world-travel-replay"),
    )


def test_one_transition_folds() -> None:
    state = _project(_state(), _event(_detail()))
    assert len(state.travel_network) == 1
    row = state.route_condition(A, B)
    assert row is not None
    assert row.status is RouteStatus.RESTRICTED
    assert row.seasonal_availability is SeasonalAvailability.RESTRICTED
    assert row.blockage_cause is RouteBlockageCause.SEASONAL
    assert row.as_of_tick == 1


def test_repeated_transition_replaces_same_edge() -> None:
    first = _project(_state(), _event(_detail()))
    second = _project(
        first,
        _event(_detail(status="open", tick=2)),
    )
    assert len(second.travel_network) == 1
    row = second.route_condition(A, B)
    assert row is not None
    assert row.status is RouteStatus.OPEN
    assert row.as_of_tick == 2


def test_multiple_edges_stay_ordered() -> None:
    first = _project(_state(), _event(_detail()))
    second = _project(
        first,
        _event(_detail(origin=B, destination=C, tick=2)),
    )
    assert [row.edge_key for row in second.travel_network] == [
        ("loc-a", "loc-b"),
        ("loc-b", "loc-c"),
    ]


def test_non_adjacent_route_is_rejected() -> None:
    with pytest.raises(ValueError, match="route_condition_changed_non_adjacent"):
        _project(_state(), _event(_detail(origin=A, destination=C)))


def test_v23_run_without_route_events_is_unchanged() -> None:
    state = _state()
    projected = _project(state)
    assert projected is state
    assert projected.travel_network == ()


def test_route_event_rejects_v23() -> None:
    with pytest.raises(ValueError):
        _project(_state(), _event(_detail(), schema_version=EVENT_SCHEMA_REPLAY_V23))
