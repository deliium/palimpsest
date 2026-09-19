"""Item placement, load, and resource conservation invariants."""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from agents.models import AgentId
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import (
    assert_item_conservation,
    finite_quantities,
    make_engine,
    resource_quantities,
    total_carry_load,
    two_location_fixture,
)
from tests.simulation_helpers import make_item, make_resource
from world._physical import apply_autonomous_physical_step
from world._state import WorldState
from world.actions import Drink, Drop, Eat, Take
from world.identifiers import EntityId, WorldRevision
from world.models import copy_body, default_physical_rules
from world.values import (
    DayPhase,
    Hunger,
    ItemKind,
    ResourceKind,
)

pytestmark = pytest.mark.unit


def test_take_preserves_item_identity_and_load() -> None:
    fixture = two_location_fixture()
    engine = make_engine(fixture, seed=11)
    before = engine._snapshot.world.state
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    after = engine._snapshot.world.state
    assert_item_conservation(before, after)
    assert after.items[EntityId("item-1")].holder_id == EntityId("body-1")
    assert total_carry_load(after, EntityId("body-1")) == 1


def test_drop_rejects_full_location_without_mutation() -> None:
    fixture = two_location_fixture(item_capacity=1)
    # Fill the only ground slot by leaving item-1 on the ground, then try drop.
    held = make_item(
        "item-held",
        name="Cup",
        location_id=None,
        holder_id="body-1",
    )
    body = copy_body(
        fixture.bodies[0],
        inventory=(EntityId("item-held"),),
    )
    filled = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(body, fixture.bodies[1]),
        items=(fixture.items[0], held),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    engine = make_engine(filled, seed=12)
    before = engine._snapshot.world.state
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Drop(EntityId("item-held"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    after = engine._snapshot.world.state
    # Autonomous physiology still mutates living bodies; item placement must not.
    assert after.items[EntityId("item-held")].holder_id == EntityId("body-1")
    assert after.items[EntityId("item-1")].location_id == EntityId("loc-1")
    assert before.items.keys() == after.items.keys()


@given(quantity=finite_quantities)
@settings(max_examples=8, deadline=None)
def test_resource_quantity_bounds_across_regeneration(quantity: float) -> None:
    fixture = two_location_fixture()
    resource = make_resource(
        "res-bound",
        kind=ResourceKind.MATERIAL,
        location_id="loc-1",
        quantity=quantity,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    state = WorldState(
        WorldRevision(0),
        locations=fixture.locations,
        bodies=(),
        items=(),
        resources=(resource,),
        weather=fixture.weather,
    )
    step = apply_autonomous_physical_step(
        state=state,
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    resulting = step.working_state.resources[EntityId("res-bound")].quantity
    assert 0.0 <= resulting <= 5.0
    if quantity >= 5.0:
        assert resulting == 5.0
    elif quantity + 1.0 >= 5.0:
        assert resulting == 5.0
    else:
        assert resulting == quantity + 1.0


@pytest.mark.parametrize("quantity", [0.0, 0.5, 1.0, 5.0])
def test_drink_resource_extraction_requires_at_least_one(quantity: float) -> None:
    fixture = two_location_fixture(water_quantity=quantity, item_on_ground=False)
    engine = make_engine(fixture, seed=13)
    before_qty = resource_quantities(engine._snapshot.world.state)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Drink(EntityId("res-water"))
            ),
        )
    )
    after = engine._snapshot.world.state
    after_qty = resource_quantities(after)
    if quantity >= 1.0:
        assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
        assert after_qty["res-water"] == pytest.approx(quantity - 1.0)
    else:
        assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
        assert after_qty["res-water"] == before_qty["res-water"]


def test_eat_consumes_item_identity_from_index_and_inventory() -> None:
    food = make_item(
        "item-food",
        name="Bread",
        kind=ItemKind.FOOD,
        location_id=None,
        holder_id="body-1",
    )
    fixture = two_location_fixture(item_on_ground=False)
    body = copy_body(fixture.bodies[0], inventory=(EntityId("item-food"),))
    hungry = copy_body(body, hunger=Hunger(40))
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(hungry, fixture.bodies[1]),
        items=(food,),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=14)
    before = engine._snapshot.world.state
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Eat(EntityId("item-food"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    after = engine._snapshot.world.state
    assert_item_conservation(before, after, consumed=frozenset({"item-food"}))
    assert EntityId("item-food") not in after.items
    assert EntityId("item-food") not in after.bodies[EntityId("body-1")].inventory
    # Eat -30 from 40 → 10, then metabolism +2 → 12.
    assert after.bodies[EntityId("body-1")].hunger.value == 12.0


def test_take_rejects_over_carry_capacity_without_item_move() -> None:
    heavy = make_item("item-1", name="Rock", load=5, location_id="loc-1")
    fixture = two_location_fixture(carry_capacity=3)
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=(heavy,),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=15)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    after = engine._snapshot.world.state
    assert after.items[EntityId("item-1")].location_id == EntityId("loc-1")
    assert after.items[EntityId("item-1")].holder_id is None
