"""Tick-boundary advancement, capacity waiting, and journey timeout behavior."""

from __future__ import annotations

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from tests.physical_helpers import dead_body
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._state import WorldState
from world._travel import advance_due_journeys, cancel_dead_journeys
from world.actions import Attack, Move
from world.events import JourneyArrived, JourneyEnded, JourneyStarted
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import PhysicalRules, non_lethal_physical_rules
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _engine(*, destination_capacity: int, blocker: bool) -> WorldEngine:
    origin = make_location("loc-1", name="Origin", adjacent=("loc-2",), body_capacity=4)
    destination = make_location(
        "loc-2",
        name="Destination",
        adjacent=("loc-1",),
        body_capacity=destination_capacity,
    )
    mover = alive_body("body-mover", location_id="loc-1")
    bodies = (
        (mover, alive_body("body-blocker", location_id="loc-2"))
        if blocker
        else (mover,)
    )
    registrations = tuple(
        AgentRegistration(AgentId(f"agent-{body.entity_id.value}"), body.entity_id)
        for body in bodies
    )
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "west"),
            LocationRegion(EntityId("loc-2"), "east"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 3),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-travel-lifecycle"),
        revision=WorldRevision(0),
        locations=(origin, destination),
        bodies=bodies,
        weather=(make_weather("loc-1"), make_weather("loc-2")),
        registrations=registrations,
        regions_migration=spec,
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=77, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
    )


def _move(engine: WorldEngine) -> object:
    batch = engine.observe()
    return engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-body-mover"),
                Move(EntityId("loc-2")),
            ),
        )
    )


def test_duration_two_journey_arrives_on_its_due_empty_tick() -> None:
    engine = _engine(destination_capacity=2, blocker=False)
    started = _move(engine)
    assert started is not None
    assert any(isinstance(row.event.details, JourneyStarted) for row in started.events)
    assert engine._snapshot.world.state.bodies[
        EntityId("body-mover")
    ].location_id == EntityId("loc-1")
    assert len(engine._snapshot.world.state.journeys or {}) == 1

    engine.observe()
    arrived = engine.resolve_tick(())
    assert arrived is not None
    assert any(isinstance(row.event.details, JourneyArrived) for row in arrived.events)
    assert engine._snapshot.world.state.bodies[
        EntityId("body-mover")
    ].location_id == EntityId("loc-2")
    assert engine._snapshot.world.state.journeys == {}


def test_full_destination_waits_then_ends_after_final_inclusive_attempt() -> None:
    engine = _engine(destination_capacity=1, blocker=True)
    started = _move(engine)
    assert started is not None
    assert len(engine._snapshot.world.state.journeys or {}) == 1

    engine.observe()
    blocked = engine.resolve_tick(())
    assert blocked is not None
    assert not any(
        isinstance(row.event.details, JourneyEnded) for row in blocked.events
    )
    assert len(engine._snapshot.world.state.journeys or {}) == 1
    assert engine._snapshot.world.state.bodies[
        EntityId("body-mover")
    ].location_id == EntityId("loc-1")

    engine.observe()
    timed_out = engine.resolve_tick(())
    assert timed_out is not None
    endings = [
        row.event.details
        for row in timed_out.events
        if isinstance(row.event.details, JourneyEnded)
    ]
    assert len(endings) == 1
    assert endings[0].reason == "arrival_timeout"
    assert engine._snapshot.world.state.journeys == {}


def test_due_capacity_competition_is_ordered_and_never_partially_arrives() -> None:
    origin_a = make_location("loc-a", name="A", adjacent=("loc-d",), body_capacity=4)
    origin_b = make_location("loc-b", name="B", adjacent=("loc-d",), body_capacity=4)
    destination = make_location(
        "loc-d",
        name="D",
        adjacent=("loc-a", "loc-b"),
        body_capacity=2,
    )
    locations = (origin_a, origin_b, destination)
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("all", "All"),),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "all"),
            LocationRegion(EntityId("loc-b"), "all"),
            LocationRegion(EntityId("loc-d"), "all"),
        ),
        routes=(),
        max_arrival_wait_ticks=1,
        residence_min_ticks=1,
        destination_memory_limit=1,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    body_a = alive_body("body-a", location_id="loc-a")
    body_b = alive_body("body-b", location_id="loc-b")
    blocker = alive_body("blocker", location_id="loc-d")

    def journey(journey_id: str, body: EntityId, origin: str) -> Journey:
        return Journey(
            journey_id=journey_id,
            participant_body_ids=(body,),
            actor_body_id=body,
            origin_location_id=EntityId(origin),
            destination_location_id=EntityId("loc-d"),
            origin_region_id="all",
            destination_region_id="all",
            start_tick=0,
            due_tick=1,
            charged_fatigue_cost=1,
            arrival_wait_deadline_tick=2,
        )

    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(body_a, body_b, blocker),
        weather=tuple(make_weather(location.entity_id.value) for location in locations),
        regions_migration=spec,
        journeys=(
            journey("b-journey", body_b.entity_id, "loc-b"),
            journey("a-journey", body_a.entity_id, "loc-a"),
        ),
    )
    after_due, transitions = advance_due_journeys(state, tick=1)
    assert len(transitions) == 1
    assert isinstance(transitions[0], JourneyArrived)
    assert transitions[0].journey_id == "a-journey"
    assert after_due.bodies[body_a.entity_id].location_id == EntityId("loc-d")
    assert after_due.bodies[body_b.entity_id].location_id == EntityId("loc-b")
    assert after_due.journeys is not None
    assert tuple(after_due.journeys) == ("b-journey",)

    group_state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("group-a", location_id="loc-a"),
            alive_body("group-b", location_id="loc-a"),
            blocker,
        ),
        weather=tuple(make_weather(location.entity_id.value) for location in locations),
        regions_migration=spec,
        journeys=(
            Journey(
                journey_id="group-journey",
                participant_body_ids=(EntityId("group-a"), EntityId("group-b")),
                actor_body_id=EntityId("group-a"),
                origin_location_id=EntityId("loc-a"),
                destination_location_id=EntityId("loc-d"),
                origin_region_id="all",
                destination_region_id="all",
                start_tick=0,
                due_tick=1,
                charged_fatigue_cost=1,
                arrival_wait_deadline_tick=2,
            ),
        ),
    )
    still_waiting, no_transition = advance_due_journeys(group_state, tick=1)
    assert no_transition == ()
    assert still_waiting.bodies[EntityId("group-a")].location_id == EntityId("loc-a")
    assert still_waiting.bodies[EntityId("group-b")].location_id == EntityId("loc-a")
    roomy_destination = make_location(
        "loc-d",
        name="D",
        adjacent=("loc-a", "loc-b"),
        body_capacity=3,
    )
    roomy_locations = (origin_a, origin_b, roomy_destination)
    group_ready = WorldState(
        WorldRevision(0),
        locations=roomy_locations,
        bodies=(
            alive_body("group-a", location_id="loc-a"),
            alive_body("group-b", location_id="loc-a"),
            blocker,
        ),
        weather=tuple(
            make_weather(location.entity_id.value) for location in roomy_locations
        ),
        regions_migration=spec,
        journeys=(
            Journey(
                journey_id="group-journey",
                participant_body_ids=(EntityId("group-a"), EntityId("group-b")),
                actor_body_id=EntityId("group-a"),
                origin_location_id=EntityId("loc-a"),
                destination_location_id=EntityId("loc-d"),
                origin_region_id="all",
                destination_region_id="all",
                start_tick=0,
                due_tick=1,
                charged_fatigue_cost=1,
                arrival_wait_deadline_tick=2,
            ),
        ),
    )
    arrived_group, group_transitions = advance_due_journeys(group_ready, tick=1)
    assert len(group_transitions) == 1
    assert isinstance(group_transitions[0], JourneyArrived)
    assert arrived_group.bodies[EntityId("group-a")].location_id == EntityId("loc-d")
    assert arrived_group.bodies[EntityId("group-b")].location_id == EntityId("loc-d")


def test_group_journey_death_cancels_all_participants_at_origin() -> None:
    origin = make_location("loc-a", name="A", adjacent=("loc-d",), body_capacity=4)
    destination = make_location("loc-d", name="D", adjacent=("loc-a",), body_capacity=4)
    locations = (origin, destination)
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("all", "All"),),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "all"),
            LocationRegion(EntityId("loc-d"), "all"),
        ),
        routes=(),
        max_arrival_wait_ticks=1,
        residence_min_ticks=1,
        destination_memory_limit=1,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("caregiver", location_id="loc-a"),
            dead_body("dependent", location_id="loc-a"),
        ),
        weather=tuple(make_weather(location.entity_id.value) for location in locations),
        regions_migration=spec,
        journeys=(
            Journey(
                journey_id="group-death",
                participant_body_ids=(EntityId("caregiver"), EntityId("dependent")),
                actor_body_id=EntityId("caregiver"),
                origin_location_id=EntityId("loc-a"),
                destination_location_id=EntityId("loc-d"),
                origin_region_id="all",
                destination_region_id="all",
                start_tick=0,
                due_tick=10,
                charged_fatigue_cost=2,
                arrival_wait_deadline_tick=11,
            ),
        ),
    )
    canceled, transitions = cancel_dead_journeys(state)
    assert len(transitions) == 1
    assert transitions[0].reason == "participant_dead"
    assert transitions[0].participant_body_ids == (
        EntityId("caregiver"),
        EntityId("dependent"),
    )
    assert canceled.journeys == {}
    assert canceled.bodies[EntityId("caregiver")].location_id == EntityId("loc-a")
    assert canceled.bodies[EntityId("dependent")].location_id == EntityId("loc-a")


def test_full_capacity_swap_routes_wait_without_reserving_or_overfilling() -> None:
    location_a = make_location("loc-a", name="A", adjacent=("loc-b",), body_capacity=1)
    location_b = make_location("loc-b", name="B", adjacent=("loc-a",), body_capacity=1)
    locations = (location_a, location_b)
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("all", "All"),),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "all"),
            LocationRegion(EntityId("loc-b"), "all"),
        ),
        routes=(),
        max_arrival_wait_ticks=1,
        residence_min_ticks=1,
        destination_memory_limit=1,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )

    def journey(journey_id: str, body_id: str, origin: str, destination: str):
        return Journey(
            journey_id=journey_id,
            participant_body_ids=(EntityId(body_id),),
            actor_body_id=EntityId(body_id),
            origin_location_id=EntityId(origin),
            destination_location_id=EntityId(destination),
            origin_region_id="all",
            destination_region_id="all",
            start_tick=0,
            due_tick=1,
            charged_fatigue_cost=1,
            arrival_wait_deadline_tick=2,
        )

    state = WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-a", location_id="loc-a"),
            alive_body("body-b", location_id="loc-b"),
        ),
        weather=(make_weather("loc-a"), make_weather("loc-b")),
        regions_migration=spec,
        journeys=(
            journey("journey-a", "body-a", "loc-a", "loc-b"),
            journey("journey-b", "body-b", "loc-b", "loc-a"),
        ),
    )
    waiting, transitions = advance_due_journeys(state, tick=1)
    assert transitions == ()
    assert len(waiting.journeys or {}) == 2
    assert waiting.bodies[EntityId("body-a")].location_id == EntityId("loc-a")
    assert waiting.bodies[EntityId("body-b")].location_id == EntityId("loc-b")
    ended, endings = advance_due_journeys(waiting, tick=2)
    assert [row.journey_id for row in endings] == ["journey-a", "journey-b"]
    assert all(row.reason == "arrival_timeout" for row in endings)
    assert ended.journeys == {}


def test_physical_death_cancels_pending_journey_after_died_event() -> None:
    origin = make_location(
        "loc-1",
        name="Origin",
        adjacent=("loc-2",),
        base_temperature=60,
        body_capacity=4,
    )
    destination = make_location(
        "loc-2", name="Destination", adjacent=("loc-1",), body_capacity=4
    )
    traveler = alive_body("body-mover", location_id="loc-1")
    registration = AgentRegistration(AgentId("agent-mover"), traveler.entity_id)
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "west"),
            LocationRegion(EntityId("loc-2"), "east"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 3, 2),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=80,
            physical_rules=PhysicalRules(
                exposure_damage=200,
                exposure_high_celsius=37,
            ),
        ),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-travel-physical-death"),
            revision=WorldRevision(0),
            locations=(origin, destination),
            bodies=(traveler,),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
            registrations=(registration,),
            regions_migration=spec,
        ),
    )
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-mover"),
                Move(EntityId("loc-2")),
            ),
        )
    )
    assert result is not None
    kinds = [record.event.details.kind for record in result.events]
    assert "journey_started" in kinds
    assert "died" in kinds
    assert "journey_ended" in kinds
    assert kinds.index("died") < kinds.index("journey_ended")
    assert engine._snapshot.world.state.journeys == {}


def test_participant_killed_during_actions_ends_journey_before_due_arrival() -> None:
    origin = make_location("loc-1", name="Origin", adjacent=("loc-2",), body_capacity=4)
    destination = make_location(
        "loc-2", name="Destination", adjacent=("loc-1",), body_capacity=4
    )
    traveler = alive_body("body-mover", location_id="loc-1")
    attacker = alive_body("body-attacker", location_id="loc-1")
    registrations = (
        AgentRegistration(AgentId("agent-mover"), traveler.entity_id),
        AgentRegistration(AgentId("agent-attacker"), attacker.entity_id),
    )
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "west"),
            LocationRegion(EntityId("loc-2"), "east"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 2),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=78,
            physical_rules=PhysicalRules(
                attack_hit_probability=1,
                attack_damage_min=100,
                attack_damage_max_exclusive=101,
            ),
        ),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-travel-death"),
            revision=WorldRevision(0),
            locations=(origin, destination),
            bodies=(traveler, attacker),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
            registrations=registrations,
            regions_migration=spec,
        ),
    )
    batch = engine.observe()
    start = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-mover"),
                Move(EntityId("loc-2")),
            ),
        )
    )
    assert start is not None
    batch = engine.observe()
    killed = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-attacker"),
                Attack(EntityId("body-mover")),
            ),
        )
    )
    assert killed is not None
    kinds = [record.event.details.kind for record in killed.events]
    assert "died" in kinds
    assert "journey_ended" in kinds
    assert kinds.index("died") < kinds.index("journey_ended")
    assert engine._snapshot.world.state.journeys == {}


def test_traveller_can_be_attacked_at_origin_before_due_arrival_exposure() -> None:
    origin = make_location(
        "loc-1",
        name="Origin",
        adjacent=("loc-2",),
        base_temperature=36.5,
        body_capacity=4,
    )
    destination = make_location(
        "loc-2",
        name="Destination",
        adjacent=("loc-1",),
        base_temperature=45,
        body_capacity=4,
    )
    traveler = alive_body("body-mover", location_id="loc-1")
    attacker = alive_body("body-attacker", location_id="loc-1")
    registrations = (
        AgentRegistration(AgentId("agent-mover"), traveler.entity_id),
        AgentRegistration(AgentId("agent-attacker"), attacker.entity_id),
    )
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "west"),
            LocationRegion(EntityId("loc-2"), "east"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 2),),
        max_arrival_wait_ticks=0,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=79,
            physical_rules=PhysicalRules(
                attack_hit_probability=1,
                attack_damage_min=1,
                attack_damage_max_exclusive=2,
            ),
        ),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-travel-attacked"),
            revision=WorldRevision(0),
            locations=(origin, destination),
            bodies=(traveler, attacker),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
            registrations=registrations,
            regions_migration=spec,
        ),
    )
    start_batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                start_batch.token,
                AgentId("agent-mover"),
                Move(EntityId("loc-2")),
            ),
        )
    )
    arrival_batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                arrival_batch.token,
                AgentId("agent-attacker"),
                Attack(EntityId("body-mover")),
            ),
        )
    )
    assert result is not None
    kinds = [record.event.details.kind for record in result.events]
    assert "attack" in kinds
    assert "journey_arrived" in kinds
    assert kinds.index("attack") < kinds.index("journey_arrived")
    moved = engine._snapshot.world.state.bodies[EntityId("body-mover")]
    assert moved.location_id == EntityId("loc-2")
    assert moved.temperature.value > traveler.temperature.value
