"""Immutable objective world entity models."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.simulation_helpers import (
    make_item,
    make_location,
    make_resource,
    make_weather,
)
from world._freeze import freeze
from world.identifiers import EntityId
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    PhysicalRules,
    Weather,
    canonical_physical_rules_bytes,
    default_physical_rules,
    physical_rules_fingerprint,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
)

_NAMES = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_ "),
    min_size=1,
    max_size=24,
).filter(lambda value: value.strip() != "")


def test_location_is_frozen() -> None:
    location = make_location()
    with pytest.raises(AttributeError):
        location.name = "Other"  # type: ignore[misc]


def test_location_rejects_self_edges_and_duplicate_neighbors() -> None:
    with pytest.raises(ValueError, match="self-edges"):
        make_location(adjacent=("loc-1",))
    with pytest.raises(ValueError, match="duplicate"):
        make_location(adjacent=("loc-2", "loc-2"))


def test_item_requires_exactly_one_placement() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Item(
            entity_id=EntityId("item-1"),
            name="Rock",
            kind=ItemKind.GENERIC,
            load=ItemLoad(1),
        )
    with pytest.raises(ValueError, match="exactly one"):
        Item(
            entity_id=EntityId("item-1"),
            name="Rock",
            kind=ItemKind.GENERIC,
            load=ItemLoad(1),
            location_id=EntityId("loc-1"),
            holder_id=EntityId("body-1"),
        )
    at_location = make_item(location_id="loc-1", holder_id=None)
    held = make_item(
        entity_id="item-2",
        name="Cup",
        location_id=None,
        holder_id="body-1",
    )
    assert at_location.holder_id is None
    assert held.location_id is None


def test_resource_quantity_must_be_finite_non_negative() -> None:
    resource = make_resource(quantity=3, maximum_quantity=5)
    assert resource.quantity == 3.0
    assert resource.kind is ResourceKind.WATER
    with pytest.raises(ValueError):
        make_resource(quantity=-1)
    with pytest.raises(ValueError):
        make_resource(quantity=math.inf)
    with pytest.raises(ValueError, match="maximum_quantity"):
        make_resource(quantity=5, maximum_quantity=3)


def test_weather_is_location_bound_value() -> None:
    weather = make_weather(condition=WeatherCondition.CLEAR)
    assert weather.location_id == EntityId("loc-1")
    assert weather.condition is WeatherCondition.CLEAR
    with pytest.raises(TypeError):
        Weather(
            location_id=EntityId("loc-1"),
            condition="clear",  # type: ignore[arg-type]
        )


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
            carry_capacity=CarryCapacity(10),
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
            carry_capacity=CarryCapacity(10),
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
        carry_capacity=CarryCapacity(10),
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
        carry_capacity=CarryCapacity(5),
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
            carry_capacity=CarryCapacity(5),
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
            carry_capacity=CarryCapacity(5),
        )


def test_physical_rules_defaults_and_fingerprint_are_stable() -> None:
    left = default_physical_rules()
    right = PhysicalRules()
    assert left == right
    assert physical_rules_fingerprint(left) == physical_rules_fingerprint(right)
    assert canonical_physical_rules_bytes(left) == canonical_physical_rules_bytes(right)
    altered = PhysicalRules(move_fatigue=6.0)
    assert physical_rules_fingerprint(altered) != physical_rules_fingerprint(left)


def test_physical_rules_day_phase_boundaries() -> None:
    rules = default_physical_rules()
    assert rules.hour_for_tick(0) == 0
    assert rules.day_phase_for_hour(5).value == "night"
    assert rules.day_phase_for_hour(6).value == "day"
    assert rules.day_phase_for_hour(17).value == "day"
    assert rules.day_phase_for_hour(18).value == "night"


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
    assert make_location(name=name).name == name
