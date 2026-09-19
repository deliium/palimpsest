"""Typed fixtures and helpers for V1 physical simulation tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from hypothesis import strategies as st

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    make_item,
    make_location,
    make_resource,
    make_weather,
    weather_for_locations,
)
from tests.unit.determinism_helpers import project_world_state
from world._state import WorldState
from world.actions import Wait
from world.events import WorldEvent
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    Location,
    PhysicalRules,
    Resource,
    Weather,
    default_physical_rules,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
)

_HASH_PLACEHOLDER = "a" * 64


@dataclass(frozen=True, slots=True)
class PhysicalWorldFixture:
    """Frozen bundle of authoritative physical entities for one test world."""

    world_id: WorldId
    locations: tuple[Location, ...]
    bodies: tuple[AgentBody, ...]
    items: tuple[Item, ...]
    resources: tuple[Resource, ...]
    weather: tuple[Weather, ...]
    registrations: tuple[AgentRegistration, ...]
    revision: WorldRevision = field(default_factory=lambda: WorldRevision(0))

    def as_state(self) -> WorldState:
        return WorldState(
            self.revision,
            locations=self.locations,
            bodies=self.bodies,
            items=self.items,
            resources=self.resources,
            weather=self.weather,
        )

    def as_bootstrap(self) -> WorldBootstrap:
        return WorldBootstrap(
            world_id=self.world_id,
            revision=self.revision,
            locations=self.locations,
            bodies=self.bodies,
            items=self.items,
            resources=self.resources,
            weather=self.weather,
            registrations=self.registrations,
        )


def physical_config(
    seed: int = 1,
    *,
    rules: PhysicalRules | None = None,
) -> SimulationRunConfig:
    """Derivation-v2 config with explicit physical rules."""
    return SimulationRunConfig(
        seed=seed,
        physical_rules=rules if rules is not None else default_physical_rules(),
    )


def make_engine(
    fixture: PhysicalWorldFixture,
    *,
    seed: int = 1,
    rules: PhysicalRules | None = None,
) -> WorldEngine:
    return WorldEngine(
        config=physical_config(seed, rules=rules),
        bootstrap=fixture.as_bootstrap(),
    )


def two_location_fixture(
    *,
    item_on_ground: bool = True,
    water_quantity: float = 3.0,
    body_capacity: int = 8,
    item_capacity: int = 16,
    carry_capacity: int = 10,
    shelter_factor: float = 0.0,
) -> PhysicalWorldFixture:
    """Minimal connected camp/forest world with two living agents."""
    locations = (
        make_location(
            "loc-1",
            name="Camp",
            adjacent=("loc-2",),
            body_capacity=body_capacity,
            item_capacity=item_capacity,
            shelter_factor=shelter_factor,
        ),
        make_location(
            "loc-2",
            name="Forest",
            adjacent=("loc-1",),
            body_capacity=body_capacity,
            item_capacity=item_capacity,
            shelter_factor=shelter_factor,
        ),
    )
    items: tuple[Item, ...] = ()
    if item_on_ground:
        items = (make_item("item-1", name="Rock", location_id="loc-1"),)
    bodies = (
        alive_body("body-1", location_id="loc-1", carry_capacity=carry_capacity),
        alive_body("body-2", location_id="loc-1", carry_capacity=carry_capacity),
    )
    resources = (
        make_resource(
            "res-water",
            name="Spring",
            kind=ResourceKind.WATER,
            location_id="loc-1",
            quantity=water_quantity,
            maximum_quantity=max(water_quantity, 5.0),
            regeneration_per_tick=0.0,
        ),
        make_resource(
            "res-food",
            name="BerryBush",
            kind=ResourceKind.FOOD,
            location_id="loc-1",
            quantity=2.0,
            maximum_quantity=5.0,
            regeneration_per_tick=1.0,
        ),
    )
    return PhysicalWorldFixture(
        world_id=WorldId("world-1"),
        locations=locations,
        bodies=bodies,
        items=items,
        resources=resources,
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def dead_body(
    entity_id: str = "body-1",
    *,
    location_id: str = "loc-1",
    inventory: tuple[EntityId, ...] = (),
    carry_capacity: int = 10,
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(0),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.DEAD,
        carry_capacity=CarryCapacity(carry_capacity),
    )


def stressed_body(
    entity_id: str,
    *,
    location_id: str = "loc-1",
    health: float = 10.0,
    hunger: float = 100.0,
    thirst: float = 100.0,
    fatigue: float = 100.0,
    temperature: float = 36.5,
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(health),
        hunger=Hunger(hunger),
        thirst=Thirst(thirst),
        fatigue=Fatigue(fatigue),
        temperature=TemperatureCelsius(temperature),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def grid_locations(
    count: int,
    *,
    body_capacity: int = 4,
    item_capacity: int = 8,
) -> tuple[Location, ...]:
    """Build a connected path of ``count`` locations."""
    if count < 1:
        raise ValueError("count must be >= 1")
    specs = tuple(
        (f"loc-{index:02d}", f"Place-{index:02d}") for index in range(count)
    )
    locations = connected_locations(*specs)
    return tuple(
        make_location(
            location.entity_id.value,
            name=location.name,
            adjacent=tuple(neighbor.value for neighbor in location.adjacent),
            body_capacity=body_capacity,
            item_capacity=item_capacity,
        )
        for location in locations
    )


def scaled_fixture(
    *,
    agents: int,
    locations: int,
    seed_tag: str = "scale",
) -> PhysicalWorldFixture:
    """Build a connected world sized for determinism/scale checks."""
    locs = grid_locations(locations, body_capacity=max(agents, 4))
    bodies = tuple(
        alive_body(
            f"body-{index:02d}",
            location_id=locs[index % locations].entity_id.value,
        )
        for index in range(agents)
    )
    registrations = tuple(
        AgentRegistration(
            AgentId(f"agent-{index:02d}"), EntityId(f"body-{index:02d}")
        )
        for index in range(agents)
    )
    items = tuple(
        make_item(
            f"item-{index:02d}",
            name=f"Thing-{index:02d}",
            kind=ItemKind.GENERIC,
            location_id=locs[index % locations].entity_id.value,
        )
        for index in range(min(agents, locations))
    )
    resources = tuple(
        make_resource(
            f"res-{index:02d}",
            name=f"Node-{index:02d}",
            kind=(
                ResourceKind.FOOD,
                ResourceKind.WATER,
                ResourceKind.MATERIAL,
            )[index % 3],
            location_id=locs[index % locations].entity_id.value,
            quantity=3.0,
            maximum_quantity=5.0,
            regeneration_per_tick=0.5 if index % 2 == 0 else 0.0,
        )
        for index in range(min(locations, 6))
    )
    return PhysicalWorldFixture(
        world_id=WorldId(f"world-{seed_tag}"),
        locations=locs,
        bodies=bodies,
        items=items,
        resources=resources,
        weather=weather_for_locations(locs),
        registrations=registrations,
    )


def item_placements(state: WorldState) -> Mapping[str, str]:
    """Map each item id to ground location, holder, or orphan sentinel."""
    placements: dict[str, str] = {}
    for item_id, item in state.items.items():
        if item.holder_id is not None:
            placements[item_id.value] = f"held:{item.holder_id.value}"
        elif item.location_id is not None:
            placements[item_id.value] = f"ground:{item.location_id.value}"
        else:
            placements[item_id.value] = "orphan"
    return placements


def total_carry_load(state: WorldState, body_id: EntityId) -> int:
    body = state.bodies[body_id]
    return sum(state.items[item_id].load.value for item_id in body.inventory)


def resource_quantities(state: WorldState) -> Mapping[str, float]:
    return {
        resource_id.value: resource.quantity
        for resource_id, resource in state.resources.items()
    }


def assert_item_conservation(
    before: WorldState,
    after: WorldState,
    *,
    consumed: frozenset[str] = frozenset(),
    created: frozenset[str] = frozenset(),
) -> None:
    """Every pre-existing item is ground, held, or explicitly consumed."""
    before_ids = {item_id.value for item_id in before.items}
    after_ids = {item_id.value for item_id in after.items}
    assert before_ids - consumed == after_ids - created
    for item_id in after_ids - created:
        item = after.items[EntityId(item_id)]
        exactly_one = (item.location_id is None) ^ (item.holder_id is None)
        assert exactly_one, f"item {item_id} must have exactly one placement"
        if item.holder_id is not None:
            assert item_id in {
                held.value for held in after.bodies[item.holder_id].inventory
            }


def objective_fingerprint(engine: WorldEngine) -> tuple[object, ...]:
    return (
        engine.tick.value,
        engine.revision.value,
        project_world_state(engine._snapshot.world.state),
    )


def event_fingerprint(engine: WorldEngine) -> tuple[object, ...]:
    export = engine.export_events()
    return (
        tuple(event.event_id.value for event in export.events),
        tuple(
            (
                event.tick,
                event.sequence,
                event.event_type,
                event.resulting_revision,
            )
            for event in export.events
        ),
    )


def complete_fingerprint(engine: WorldEngine) -> tuple[object, ...]:
    return objective_fingerprint(engine) + event_fingerprint(engine)


def run_wait_ticks(engine: WorldEngine, count: int) -> None:
    """Advance ``count`` ticks with Wait from the first registered agent."""
    if count < 0:
        raise ValueError("count must be non-negative")
    agent_id = engine._registrations[0].agent_id
    for _ in range(count):
        batch = engine.observe()
        engine.resolve_tick((ActionSubmission(batch.token, agent_id, Wait()),))


def run_autonomous_ticks(engine: WorldEngine, count: int) -> None:
    for _ in range(count):
        engine.observe()
        engine.resolve_tick(())


def snapshot_from_engine(
    engine: WorldEngine,
    *,
    snapshot_id: str = "snap-1",
    next_tick: Tick | None = None,
) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(snapshot_id),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=tuple(engine._snapshot.world.state.items.values()),
        resources=tuple(engine._snapshot.world.state.resources.values()),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=engine.tick if next_tick is None else next_tick,
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=engine._config.derivation_version or "v1",
        integrity_hash=PayloadHash(_HASH_PLACEHOLDER),
        predecessor_commit_hash=None,
    )
    return WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
    )


def restore_from_fixture_events(
    fixture: PhysicalWorldFixture,
    *,
    seed: int,
    events: Sequence[WorldEvent],
    rules: PhysicalRules | None = None,
) -> WorldEngine:
    """Bootstrap replay path: fixture snapshot + projected events."""
    engine = make_engine(fixture, seed=seed, rules=rules)
    snap = snapshot_from_engine(
        engine, snapshot_id="snap-bootstrap", next_tick=Tick(0)
    )
    return WorldEngine.restore_from_snapshot(snap, events=events)


def checkpoint_restore(
    engine: WorldEngine,
    *,
    events_after: Sequence[WorldEvent] = (),
) -> WorldEngine:
    snap = snapshot_from_engine(engine, snapshot_id="snap-checkpoint")
    return WorldEngine.restore_from_snapshot(snap, events=events_after)


def weather_at(
    locations: Sequence[Location],
    condition: WeatherCondition = WeatherCondition.CLEAR,
) -> tuple[Weather, ...]:
    return tuple(
        make_weather(location.entity_id.value, condition=condition)
        for location in locations
    )


# Hypothesis strategies
finite_quantities = st.sampled_from([0.0, 0.5, 1.0, 5.0])
shelter_factors = st.sampled_from([0.0, 1.0])
seeds = st.integers(min_value=0, max_value=10_000)
