"""Shared builders for simulation persistence and replay unit tests."""

from __future__ import annotations

from collections.abc import Sequence

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, LifeStatus, Location, Resource, Weather
from world.values import (
    BodyCapacity,
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)


def make_location(
    entity_id: str = "loc-1",
    *,
    name: str = "Camp",
    adjacent: Sequence[EntityId] | Sequence[str] = (),
    body_capacity: int = 8,
    item_capacity: int = 16,
    base_temperature: float = 20.0,
    shelter_factor: float = 0.0,
    visibility_factor: float = 1.0,
) -> Location:
    neighbors: tuple[EntityId, ...]
    if adjacent and type(adjacent[0]) is EntityId:
        neighbors = tuple(adjacent)  # type: ignore[arg-type]
    else:
        neighbors = tuple(EntityId(str(item)) for item in adjacent)
    return Location(
        entity_id=EntityId(entity_id),
        name=name,
        adjacent=neighbors,
        body_capacity=BodyCapacity(body_capacity),
        item_capacity=ItemCapacity(item_capacity),
        base_temperature=TemperatureCelsius(base_temperature),
        shelter_factor=UnitInterval(shelter_factor),
        visibility_factor=UnitInterval(visibility_factor),
    )


def connected_locations(
    *specs: tuple[str, str],
) -> tuple[Location, ...]:
    """Build an undirected path/cycle-friendly location set from (id, name) pairs.

    Adjacent pairs are linked in order: 0-1-2-... forming a connected path.
    """
    if not specs:
        return ()
    ids = [EntityId(entity_id) for entity_id, _ in specs]
    names = [name for _, name in specs]
    locations: list[Location] = []
    for index, (entity_id, name) in enumerate(specs):
        neighbors: list[EntityId] = []
        if index > 0:
            neighbors.append(ids[index - 1])
        if index + 1 < len(ids):
            neighbors.append(ids[index + 1])
        locations.append(
            make_location(entity_id, name=name, adjacent=tuple(neighbors))
        )
    return tuple(locations)


def weather_for_locations(
    locations: Sequence[Location],
    *,
    condition: WeatherCondition = WeatherCondition.CLEAR,
) -> tuple[Weather, ...]:
    return tuple(
        make_weather(location.entity_id.value, condition=condition)
        for location in locations
    )


def make_item(
    entity_id: str = "item-1",
    *,
    name: str = "Rock",
    kind: ItemKind = ItemKind.GENERIC,
    load: int = 1,
    location_id: str | None = "loc-1",
    holder_id: str | None = None,
) -> Item:
    return Item(
        entity_id=EntityId(entity_id),
        name=name,
        kind=kind,
        load=ItemLoad(load),
        location_id=None if location_id is None else EntityId(location_id),
        holder_id=None if holder_id is None else EntityId(holder_id),
    )


def make_resource(
    entity_id: str = "res-1",
    *,
    name: str = "Water",
    kind: ResourceKind = ResourceKind.WATER,
    location_id: str = "loc-1",
    quantity: float = 3.0,
    maximum_quantity: float | None = None,
    regeneration_per_tick: float = 0.0,
    unit: str = "liters",
) -> Resource:
    maximum = quantity if maximum_quantity is None else maximum_quantity
    return Resource(
        entity_id=EntityId(entity_id),
        name=name,
        kind=kind,
        location_id=EntityId(location_id),
        quantity=quantity,
        maximum_quantity=maximum,
        regeneration_per_tick=regeneration_per_tick,
        unit=unit,
    )


def make_weather(
    location_id: str = "loc-1",
    *,
    condition: WeatherCondition = WeatherCondition.CLEAR,
) -> Weather:
    return Weather(location_id=EntityId(location_id), condition=condition)


def alive_body(
    entity_id: str = "body-1",
    *,
    location_id: str = "loc-1",
    inventory: tuple[EntityId, ...] = (),
    carry_capacity: int = 10,
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(carry_capacity),
    )


def hashed_bootstrap_snapshot(
    *,
    run_id: str = "run-1",
    seed: int = 7,
    items: tuple[Item, ...] = (),
    inventory: tuple[EntityId, ...] = (),
    next_tick: int = 0,
    revision: int = 0,
) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-bootstrap"),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
        locations=(make_location(),),
        bodies=(alive_body(inventory=inventory),),
        items=items,
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(next_tick),
        revision=WorldRevision(revision),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
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
