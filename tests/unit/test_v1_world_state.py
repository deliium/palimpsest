"""Private World and WorldState authority contracts."""

from __future__ import annotations

import pytest

from world._state import World, WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, LifeStatus, Location, Resource, Weather
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst


def _alive_body(
    entity_id: str,
    location_id: str,
    inventory: tuple[EntityId, ...] = (),
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
    )


def test_revision_only_world_state_remains_valid() -> None:
    state = WorldState(WorldRevision(0))
    assert state.revision == WorldRevision(0)
    assert dict(state.locations) == {}
    assert dict(state.items) == {}
    assert dict(state.resources) == {}
    assert dict(state.bodies) == {}
    assert dict(state.weather) == {}


def test_world_scopes_and_replaces_immutable_snapshots() -> None:
    world = World(WorldId("world-1"), WorldState(WorldRevision(0)))
    assert world.world_id == WorldId("world-1")
    next_state = WorldState(
        WorldRevision(1),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
    )
    replaced = world.replace_state(next_state)
    assert replaced is next_state
    assert world.state is next_state
    assert world.state.locations[EntityId("loc-1")].name == "Camp"


def test_world_state_rejects_duplicate_and_dangling_graph() -> None:
    location = Location(entity_id=EntityId("loc-1"), name="Camp")
    with pytest.raises(ValueError, match="duplicate physical EntityId"):
        WorldState(
            WorldRevision(0),
            locations=(location,),
            bodies=(_alive_body("loc-1", "loc-1"),),
        )
    with pytest.raises(ValueError, match="unknown location"):
        WorldState(
            WorldRevision(0),
            bodies=(_alive_body("body-1", "missing"),),
        )
    with pytest.raises(ValueError, match="duplicate weather"):
        WorldState(
            WorldRevision(0),
            locations=(location,),
            weather=(
                Weather(
                    location_id=EntityId("loc-1"),
                    condition="clear",
                    temperature=TemperatureCelsius(20),
                ),
                Weather(
                    location_id=EntityId("loc-1"),
                    condition="rain",
                    temperature=TemperatureCelsius(15),
                ),
            ),
        )


def test_holder_and_inventory_must_agree() -> None:
    location = Location(entity_id=EntityId("loc-1"), name="Camp")
    item = Item(
        entity_id=EntityId("item-1"),
        name="Cup",
        holder_id=EntityId("body-1"),
    )
    with pytest.raises(ValueError, match="does not match any inventory"):
        WorldState(
            WorldRevision(0),
            locations=(location,),
            items=(item,),
            bodies=(_alive_body("body-1", "loc-1", inventory=()),),
        )
    coherent = WorldState(
        WorldRevision(0),
        locations=(location,),
        items=(item,),
        bodies=(
            _alive_body("body-1", "loc-1", inventory=(EntityId("item-1"),)),
        ),
        resources=(
            Resource(
                entity_id=EntityId("res-1"),
                name="Water",
                location_id=EntityId("loc-1"),
                quantity=1.0,
                unit="liters",
            ),
        ),
        weather=(
            Weather(
                location_id=EntityId("loc-1"),
                condition="clear",
                temperature=TemperatureCelsius(18),
            ),
        ),
    )
    assert coherent.items[EntityId("item-1")].holder_id == EntityId("body-1")
