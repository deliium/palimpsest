"""Immutable objective world entity models."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from world._freeze import freeze
from world.identifiers import EntityId
from world.models import AgentBody, Item, LifeStatus, Location, Resource, Weather
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

_NAMES = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_ "),
    min_size=1,
    max_size=24,
).filter(lambda value: value.strip() != "")


def test_location_is_frozen() -> None:
    location = Location(entity_id=EntityId("loc-1"), name="Camp")
    with pytest.raises(AttributeError):
        location.name = "Other"  # type: ignore[misc]


def test_item_requires_exactly_one_placement() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Item(entity_id=EntityId("item-1"), name="Rock")
    with pytest.raises(ValueError, match="exactly one"):
        Item(
            entity_id=EntityId("item-1"),
            name="Rock",
            location_id=EntityId("loc-1"),
            holder_id=EntityId("body-1"),
        )
    at_location = Item(
        entity_id=EntityId("item-1"),
        name="Rock",
        location_id=EntityId("loc-1"),
    )
    held = Item(
        entity_id=EntityId("item-2"),
        name="Cup",
        holder_id=EntityId("body-1"),
    )
    assert at_location.holder_id is None
    assert held.location_id is None


def test_resource_quantity_must_be_finite_non_negative() -> None:
    resource = Resource(
        entity_id=EntityId("res-1"),
        name="Water",
        location_id=EntityId("loc-1"),
        quantity=3,
        unit="liters",
    )
    assert resource.quantity == 3.0
    with pytest.raises(ValueError):
        Resource(
            entity_id=EntityId("res-1"),
            name="Water",
            location_id=EntityId("loc-1"),
            quantity=-1,
            unit="liters",
        )
    with pytest.raises(ValueError):
        Resource(
            entity_id=EntityId("res-1"),
            name="Water",
            location_id=EntityId("loc-1"),
            quantity=math.inf,
            unit="liters",
        )


def test_weather_is_location_bound_value() -> None:
    weather = Weather(
        location_id=EntityId("loc-1"),
        condition="clear",
        temperature=TemperatureCelsius(21.5),
    )
    assert weather.location_id == EntityId("loc-1")


def test_agent_body_rejects_sets_and_duplicate_inventory() -> None:
    with pytest.raises(TypeError, match="ordered sequence"):
        AgentBody(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(10),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory={EntityId("item-1")},  # type: ignore[arg-type]
            life_status=LifeStatus.ALIVE,
        )
    with pytest.raises(ValueError, match="duplicate"):
        AgentBody(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(10),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(EntityId("item-1"), EntityId("item-1")),
            life_status=LifeStatus.ALIVE,
        )


def test_agent_body_preserves_inventory_order_and_life_invariants() -> None:
    inventory = [EntityId("item-2"), EntityId("item-1")]
    body = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(50),
        hunger=Hunger(10),
        thirst=Thirst(20),
        fatigue=Fatigue(30),
        temperature=TemperatureCelsius(36.6),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
    )
    inventory.append(EntityId("item-3"))
    assert body.inventory == (EntityId("item-2"), EntityId("item-1"))
    dead = AgentBody(
        entity_id=EntityId("body-2"),
        location_id=EntityId("loc-1"),
        health=Health(0),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
        temperature=TemperatureCelsius(20.0),
        inventory=(),
        life_status=LifeStatus.DEAD,
    )
    assert dead.life_status is LifeStatus.DEAD
    with pytest.raises(ValueError, match="positive health"):
        AgentBody(
            entity_id=EntityId("body-3"),
            location_id=EntityId("loc-1"),
            health=Health(0),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
        )
    with pytest.raises(ValueError, match="zero health"):
        AgentBody(
            entity_id=EntityId("body-4"),
            location_id=EntityId("loc-1"),
            health=Health(1),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.DEAD,
        )


def test_freeze_rejects_unsupported_content() -> None:
    with pytest.raises(TypeError, match="bytes-like"):
        freeze({"bin": b"no"})
    with pytest.raises(TypeError, match="sets are not allowed"):
        freeze({"tags": {"a", "b"}})
    with pytest.raises(TypeError, match="mapping keys must be strings"):
        freeze({1: "x"})
    with pytest.raises(ValueError, match="signed 64-bit"):
        freeze({"n": 2**63})
    with pytest.raises(ValueError, match="finite"):
        freeze({"n": math.nan})
    with pytest.raises(TypeError, match="unsupported domain content type"):
        freeze({"body": object()})


@given(name=_NAMES)
@settings(max_examples=20, deadline=None)
def test_property_location_round_trips_name(name: str) -> None:
    assert Location(entity_id=EntityId("loc-1"), name=name).name == name
