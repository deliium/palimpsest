"""Event-only journey replay preserves each lifecycle prefix exactly."""

from __future__ import annotations

from dataclasses import replace

from simulation.journal import decode_persistence, encode_persistence
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    weather_for_locations,
)
from world._replay import project_event_prefix
from world._state import WorldState
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V21,
    DeathCause,
    Died,
    JourneyArrived,
    JourneyEnded,
    JourneyStarted,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
)


def _spec() -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(
            RegionDefinition("north", "North"),
            RegionDefinition("south", "South"),
        ),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "north"),
            LocationRegion(EntityId("loc-3"), "south"),
        ),
        routes=(),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _journey() -> Journey:
    return Journey(
        journey_id="journey-prefix",
        participant_body_ids=(EntityId("body-1"), EntityId("body-2")),
        actor_body_id=EntityId("body-1"),
        origin_location_id=EntityId("loc-1"),
        destination_location_id=EntityId("loc-2"),
        origin_region_id="north",
        destination_region_id=None,
        start_tick=4,
        due_tick=5,
        charged_fatigue_cost=3,
        arrival_wait_deadline_tick=6,
    )


def _event(
    details, *, event_id: str, tick: int, origin, destination=None, sequence: int = 0
):
    journey = _journey()
    if isinstance(details, JourneyStarted):
        cause = ActionCause(RequestId(f"req-{event_id}"), journey.actor_body_id)
    elif isinstance(details, Died):
        cause = SystemCause(
            RequestId(f"req-{event_id}"),
            SystemEffectFamily.COMBINED_NEEDS,
            details.body_id,
            sequence,
        )
    else:
        cause = SystemCause(
            RequestId(f"req-{event_id}"),
            SystemEffectFamily.TRAVEL,
            EntityId(journey.journey_id),
            sequence,
        )
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id="run-prefix",
        world_id=WorldId("world-prefix"),
        tick=tick,
        sequence=sequence,
        cause=cause,
        resulting_revision=WorldRevision(tick - 3),
        details=details,
        occurrence=build_occurrence_context(
            details,
            origin_location_id=origin,
            destination_location_id=destination,
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V21,
    )


def test_start_prefix_has_origin_placement_pending_state_and_one_cost() -> None:
    journey = _journey()
    locations = connected_locations(
        ("loc-1", "One"), ("loc-2", "Two"), ("loc-3", "Three")
    )
    initial = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-1"),
        ),
        weather=weather_for_locations(locations),
        regions_migration=_spec(),
    )
    start = _event(
        JourneyStarted(journey, "transport", 3.0, 13.0),
        event_id="start-prefix",
        tick=4,
        origin=journey.origin_location_id,
    )
    projected = project_event_prefix(
        initial,
        (start,),
        expected_run_id="run-prefix",
        expected_world_id=WorldId("world-prefix"),
        includes_last_event=False,
    )
    assert projected.journeys is not None
    assert projected.journeys[journey.journey_id] == journey
    assert (
        projected.bodies[EntityId("body-1")].location_id == journey.origin_location_id
    )
    assert (
        projected.bodies[EntityId("body-2")].location_id == journey.origin_location_id
    )
    assert projected.bodies[EntityId("body-1")].fatigue.value == 13.0
    assert projected.bodies[EntityId("body-2")].fatigue.value == 0.0


def test_arrival_prefix_changes_all_placements_and_removes_pending_state() -> None:
    journey = _journey()
    locations = connected_locations(
        ("loc-1", "One"), ("loc-2", "Two"), ("loc-3", "Three")
    )
    initial = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-1"),
        ),
        weather=weather_for_locations(locations),
        regions_migration=_spec(),
    )
    start = _event(
        JourneyStarted(journey, "transport", 3.0, 13.0),
        event_id="start-arrival",
        tick=4,
        origin=journey.origin_location_id,
    )
    started = project_event_prefix(
        initial,
        (start,),
        expected_run_id="run-prefix",
        expected_world_id=WorldId("world-prefix"),
        includes_last_event=True,
    )
    arrival = _event(
        JourneyArrived(
            journey.journey_id,
            journey.participant_body_ids,
            journey.origin_location_id,
            journey.destination_location_id,
        ),
        event_id="arrival-prefix",
        tick=5,
        origin=None,
        destination=journey.destination_location_id,
    )
    projected = project_event_prefix(
        started,
        (arrival,),
        expected_run_id="run-prefix",
        expected_world_id=WorldId("world-prefix"),
        includes_last_event=False,
    )
    assert projected.journeys == {}
    assert (
        projected.bodies[EntityId("body-1")].location_id
        == journey.destination_location_id
    )
    assert (
        projected.bodies[EntityId("body-2")].location_id
        == journey.destination_location_id
    )
    restored = decode_domain(encode_domain(arrival))
    assert restored == arrival


def test_duration_one_start_then_arrival_prefix_replays_both_effects() -> None:
    journey = replace(
        _journey(),
        participant_body_ids=(EntityId("body-1"),),
        due_tick=4,
        arrival_wait_deadline_tick=4,
    )
    locations = connected_locations(
        ("loc-1", "One"), ("loc-2", "Two"), ("loc-3", "Three")
    )
    initial = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(alive_body("body-1", location_id="loc-1"),),
        weather=weather_for_locations(locations),
        regions_migration=_spec(),
    )
    start = _event(
        JourneyStarted(journey, "move", 2.0, 12.0),
        event_id="instant-start",
        tick=4,
        origin=journey.origin_location_id,
    )
    arrival = _event(
        JourneyArrived(
            journey.journey_id,
            journey.participant_body_ids,
            journey.origin_location_id,
            journey.destination_location_id,
        ),
        event_id="instant-arrival",
        tick=4,
        sequence=1,
        origin=None,
        destination=journey.destination_location_id,
    )
    projected = project_event_prefix(
        initial,
        (start, arrival),
        expected_run_id="run-prefix",
        expected_world_id=WorldId("world-prefix"),
        includes_last_event=False,
    )
    assert projected.journeys == {}
    assert (
        projected.bodies[EntityId("body-1")].location_id
        == journey.destination_location_id
    )
    assert projected.bodies[EntityId("body-1")].fatigue.value == 12.0


def test_dead_before_end_prefix_retains_journey_until_cleanup_event() -> None:
    journey = _journey()
    locations = connected_locations(
        ("loc-1", "One"), ("loc-2", "Two"), ("loc-3", "Three")
    )
    initial = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-1"),
        ),
        weather=weather_for_locations(locations),
        regions_migration=_spec(),
    )
    start = _event(
        JourneyStarted(journey, "transport", 3.0, 13.0),
        event_id="start-death",
        tick=4,
        origin=journey.origin_location_id,
    )
    death = _event(
        Died(EntityId("body-2"), DeathCause.COMBINED_NEEDS),
        event_id="death-prefix",
        tick=4,
        sequence=1,
        origin=journey.origin_location_id,
    )
    end = _event(
        JourneyEnded(
            journey.journey_id,
            journey.participant_body_ids,
            journey.origin_location_id,
            journey.destination_location_id,
            "participant_dead",
        ),
        event_id="end-death",
        tick=4,
        sequence=2,
        origin=journey.origin_location_id,
    )
    dead_prefix = project_event_prefix(
        initial,
        (start, death),
        expected_run_id="run-prefix",
        expected_world_id=WorldId("world-prefix"),
        includes_last_event=False,
    )
    assert dead_prefix.journeys is not None
    assert dead_prefix.journeys[journey.journey_id] == journey
    assert dead_prefix.bodies[EntityId("body-2")].life_status.value == "dead"
    completed_prefix = project_event_prefix(
        initial,
        (start, death, end),
        expected_run_id="run-prefix",
        expected_world_id=WorldId("world-prefix"),
        includes_last_event=True,
    )
    assert completed_prefix.journeys == {}


def test_journey_event_round_trips_through_persistence_journal() -> None:
    journey = _journey()
    event = _event(
        JourneyStarted(journey, "move", 3.0, 3.0),
        event_id="journal-start",
        tick=4,
        origin=journey.origin_location_id,
    )
    restored = decode_persistence(encode_persistence(event), WorldEvent)
    assert restored == event
