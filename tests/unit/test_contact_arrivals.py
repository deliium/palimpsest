"""Neutral contact emission after qualifying cross-region journey arrivals."""

from __future__ import annotations

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._state import WorldState
from world._travel import advance_due_journeys
from world.events import ContactRecorded, JourneyArrived, JourneyEnded
from world.identifiers import EntityId, WorldRevision
from world.models import Location
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _spec(*, same_region: bool = False) -> RegionsMigrationSpec:
    east = "west" if same_region else "east"
    return RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "west"),
            LocationRegion(EntityId("loc-b"), "west"),
            LocationRegion(EntityId("loc-d"), east),
        ),
        routes=(
            RouteSpec(EntityId("loc-a"), EntityId("loc-d"), 1, 1),
            RouteSpec(EntityId("loc-b"), EntityId("loc-d"), 1, 1),
        ),
        max_arrival_wait_ticks=1,
        residence_min_ticks=1,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _journey(
    journey_id: str,
    body_id: str,
    origin: str,
    *,
    origin_region: str = "west",
    destination_region: str = "east",
    due_tick: int = 1,
) -> Journey:
    body = EntityId(body_id)
    return Journey(
        journey_id=journey_id,
        participant_body_ids=(body,),
        actor_body_id=body,
        origin_location_id=EntityId(origin),
        destination_location_id=EntityId("loc-d"),
        origin_region_id=origin_region,
        destination_region_id=destination_region,
        start_tick=0,
        due_tick=due_tick,
        charged_fatigue_cost=1,
        arrival_wait_deadline_tick=2,
    )


def _locations(capacity: int = 8) -> tuple[Location, ...]:
    return (
        make_location("loc-a", name="A", adjacent=("loc-d",), body_capacity=2),
        make_location("loc-b", name="B", adjacent=("loc-d",), body_capacity=2),
        make_location(
            "loc-d", name="D", adjacent=("loc-a", "loc-b"), body_capacity=capacity
        ),
    )


def test_cross_region_arrival_emits_one_contact_with_exact_sets() -> None:
    locations = _locations()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("mover", location_id="loc-a"),
            alive_body("local", location_id="loc-d"),
        ),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=_spec(),
        journeys=(_journey("journey-1", "mover", "loc-a"),),
    )
    after, transitions = advance_due_journeys(state, tick=1, emit_contact=True)
    assert [type(item) for item in transitions] == [JourneyArrived, ContactRecorded]
    contact = transitions[1]
    assert isinstance(contact, ContactRecorded)
    assert contact.relocation_kind == "journey_arrived"
    assert contact.journey_id == "journey-1"
    assert contact.location_id == EntityId("loc-d")
    assert contact.participant_ids == (EntityId("mover"),)
    assert contact.present_ids == (EntityId("local"),)
    assert contact.origin_region_id == "west"
    assert contact.destination_region_id == "east"
    assert after.bodies[EntityId("mover")].location_id == EntityId("loc-d")


def test_group_arrival_emits_one_shared_contact() -> None:
    locations = _locations()
    journey = Journey(
        journey_id="group",
        participant_body_ids=(EntityId("a"), EntityId("b")),
        actor_body_id=EntityId("a"),
        origin_location_id=EntityId("loc-a"),
        destination_location_id=EntityId("loc-d"),
        origin_region_id="west",
        destination_region_id="east",
        start_tick=0,
        due_tick=1,
        charged_fatigue_cost=1,
        arrival_wait_deadline_tick=2,
    )
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("a", location_id="loc-a"),
            alive_body("b", location_id="loc-a"),
            alive_body("local", location_id="loc-d"),
        ),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=_spec(),
        journeys=(journey,),
    )
    _, transitions = advance_due_journeys(state, tick=1, emit_contact=True)
    contacts = [item for item in transitions if isinstance(item, ContactRecorded)]
    assert len(contacts) == 1
    assert contacts[0].participant_ids == (EntityId("a"), EntityId("b"))


def test_same_tick_earlier_arrival_is_present() -> None:
    locations = _locations()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-a", location_id="loc-a"),
            alive_body("body-b", location_id="loc-b"),
        ),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=_spec(),
        journeys=(
            _journey("a-journey", "body-a", "loc-a"),
            _journey("b-journey", "body-b", "loc-b"),
        ),
    )
    _, transitions = advance_due_journeys(state, tick=1, emit_contact=True)
    contacts = [item for item in transitions if isinstance(item, ContactRecorded)]
    assert len(contacts) == 1
    assert contacts[0].participant_ids == (EntityId("body-b"),)
    assert contacts[0].present_ids == (EntityId("body-a"),)


def test_empty_destination_emits_no_contact() -> None:
    locations = _locations()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(alive_body("mover", location_id="loc-a"),),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=_spec(),
        journeys=(_journey("journey-1", "mover", "loc-a"),),
    )
    _, transitions = advance_due_journeys(state, tick=1, emit_contact=True)
    assert [type(item) for item in transitions] == [JourneyArrived]


def test_same_region_arrival_emits_no_contact() -> None:
    locations = _locations()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("mover", location_id="loc-a"),
            alive_body("local", location_id="loc-d"),
        ),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=_spec(same_region=True),
        journeys=(
            _journey(
                "journey-1",
                "mover",
                "loc-a",
                origin_region="west",
                destination_region="west",
            ),
        ),
    )
    _, transitions = advance_due_journeys(state, tick=1, emit_contact=True)
    assert [type(item) for item in transitions] == [JourneyArrived]


def test_contact_disabled_emits_nothing() -> None:
    locations = _locations()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("mover", location_id="loc-a"),
            alive_body("local", location_id="loc-d"),
        ),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=_spec(),
        journeys=(_journey("journey-1", "mover", "loc-a"),),
    )
    _, transitions = advance_due_journeys(state, tick=1, emit_contact=False)
    assert [type(item) for item in transitions] == [JourneyArrived]


def test_dead_present_body_is_not_counted() -> None:
    from tests.physical_helpers import dead_body

    locations = _locations()
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("mover", location_id="loc-a"),
            dead_body("local", location_id="loc-d"),
        ),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=_spec(),
        journeys=(_journey("journey-1", "mover", "loc-a"),),
    )
    _, transitions = advance_due_journeys(state, tick=1, emit_contact=True)
    assert [type(item) for item in transitions] == [JourneyArrived]


def test_timeout_emits_no_contact() -> None:
    locations = _locations(capacity=1)
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("mover", location_id="loc-a"),
            alive_body("local", location_id="loc-d"),
        ),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=_spec(),
        journeys=(_journey("journey-1", "mover", "loc-a"),),
    )
    _, transitions = advance_due_journeys(state, tick=2, emit_contact=True)
    assert [type(item) for item in transitions] == [JourneyEnded]
