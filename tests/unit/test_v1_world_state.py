"""Private World and WorldState authority contracts."""

from __future__ import annotations

from tests.simulation_helpers import make_item, make_location, make_resource, make_weather, weather_for_locations

import pytest

from world._state import World, WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, LifeStatus, Location, Resource, Weather
from world.values import WeatherCondition, CarryCapacity, Fatigue, Health, Hunger, TemperatureCelsius, Thirst


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
        carry_capacity=CarryCapacity(10),
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
    locations = (make_location("loc-1", name="Camp"),)
    next_state = WorldState(
        WorldRevision(1),
        locations=locations,
        weather=weather_for_locations(locations),
    )
    with pytest.raises(RuntimeError, match="WorldEngine"):
        world.replace_state(next_state)
    # Supported path: construct a new World around the candidate snapshot.
    replaced = World(WorldId("world-1"), next_state)
    assert replaced.state is next_state
    assert world.state.revision == WorldRevision(0)
    assert replaced.state.locations[EntityId("loc-1")].name == "Camp"


def test_world_state_rejects_duplicate_and_dangling_graph() -> None:
    location = make_location("loc-1", name="Camp")
    with pytest.raises(ValueError, match="duplicate physical EntityId"):
        WorldState(
            WorldRevision(0),
            locations=(location,),
            bodies=(_alive_body("loc-1", "loc-1"),),
            weather=weather_for_locations((location,)),
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
                make_weather("loc-1", condition=WeatherCondition.CLEAR),
                make_weather("loc-1", condition=WeatherCondition.RAIN),
            ),
        )


def test_holder_and_inventory_must_agree() -> None:
    location = make_location("loc-1", name="Camp")
    item = make_item("item-1", name="Cup", location_id=None, holder_id="body-1")
    with pytest.raises(ValueError, match="does not match any inventory"):
        WorldState(
            WorldRevision(0),
            locations=(location,),
            items=(item,),
            bodies=(_alive_body("body-1", "loc-1", inventory=()),),
            weather=weather_for_locations((location,)),
        )
    coherent = WorldState(
        WorldRevision(0),
        locations=(location,),
        items=(item,),
        bodies=(
            _alive_body("body-1", "loc-1", inventory=(EntityId("item-1"),)),
        ),
        resources=(
            make_resource("res-1", name="Water", location_id="loc-1", quantity=1.0, unit="liters"),
        ),
        weather=(
            make_weather("loc-1", condition=WeatherCondition.CLEAR),
        ),
    )
    assert coherent.items[EntityId("item-1")].holder_id == EntityId("body-1")


def test_topology_rejects_asymmetric_and_disconnected_graphs() -> None:
    left = make_location("loc-1", name="Camp", adjacent=("loc-2",))
    right = make_location("loc-2", name="Forest")
    with pytest.raises(ValueError, match="asymmetric edge"):
        WorldState(
            WorldRevision(0),
            locations=(left, right),
            weather=weather_for_locations((left, right)),
        )
    island_a = make_location("loc-a", name="A")
    island_b = make_location("loc-b", name="B")
    with pytest.raises(ValueError, match="connected"):
        WorldState(
            WorldRevision(0),
            locations=(island_a, island_b),
            weather=weather_for_locations((island_a, island_b)),
        )


def test_capacities_and_carry_load_are_enforced() -> None:
    location = make_location("loc-1", name="Camp", body_capacity=1, item_capacity=0)
    with pytest.raises(ValueError, match="body occupancy"):
        WorldState(
            WorldRevision(0),
            locations=(location,),
            bodies=(
                _alive_body("body-1", "loc-1"),
                _alive_body("body-2", "loc-1"),
            ),
            weather=weather_for_locations((location,)),
        )
    roomy = make_location("loc-1", name="Camp", item_capacity=0)
    with pytest.raises(ValueError, match="ground-item occupancy"):
        WorldState(
            WorldRevision(0),
            locations=(roomy,),
            items=(make_item("item-1", location_id="loc-1"),),
            weather=weather_for_locations((roomy,)),
        )
    tiny = make_location("loc-1", name="Camp")
    heavy = make_item(
        "item-1",
        name="Anvil",
        load=20,
        location_id=None,
        holder_id="body-1",
    )
    with pytest.raises(ValueError, match="carry load"):
        WorldState(
            WorldRevision(0),
            locations=(tiny,),
            items=(heavy,),
            bodies=(_alive_body("body-1", "loc-1", inventory=(EntityId("item-1"),)),),
            weather=weather_for_locations((tiny,)),
        )


def test_weather_coverage_is_required_for_nonempty_worlds() -> None:
    location = make_location("loc-1", name="Camp")
    with pytest.raises(ValueError, match="weather coverage incomplete"):
        WorldState(
            WorldRevision(0),
            locations=(location,),
            bodies=(_alive_body("body-1", "loc-1"),),
        )
