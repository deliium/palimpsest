"""Structural rejections leave authoritative state unmutated by the action."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import (
    dead_body,
    make_engine,
    two_location_fixture,
)
from tests.simulation_helpers import make_item, make_location, weather_for_locations
from world.actions import Attack, Drink, Drop, Give, Help, Move, Take
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import copy_body

pytestmark = pytest.mark.unit


def test_move_to_non_adjacent_is_rejected() -> None:
    fixture = two_location_fixture(item_on_ground=False)
    # Add a third location not adjacent to loc-1.
    locs = (
        make_location("loc-1", name="Camp", adjacent=("loc-2",)),
        make_location("loc-2", name="Forest", adjacent=("loc-1", "loc-3")),
        make_location("loc-3", name="Cave", adjacent=("loc-2",)),
    )
    world = type(fixture)(
        world_id=WorldId("world-1"),
        locations=locs,
        bodies=fixture.bodies,
        items=(),
        resources=(),
        weather=weather_for_locations(locs),
        registrations=fixture.registrations,
        revision=WorldRevision(0),
    )
    engine = make_engine(world, seed=31)
    before_loc = engine._snapshot.world.state.bodies[EntityId("body-1")].location_id
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Move(EntityId("loc-3"))),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert (
        engine._snapshot.world.state.bodies[EntityId("body-1")].location_id
        == before_loc
    )


def test_take_missing_item_is_rejected() -> None:
    engine = make_engine(two_location_fixture(item_on_ground=False), seed=32)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-missing"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_give_to_dead_recipient_is_rejected() -> None:
    fixture = two_location_fixture()
    held = make_item("item-1", location_id=None, holder_id="body-1")
    actor = copy_body(fixture.bodies[0], inventory=(EntityId("item-1"),))
    dead = dead_body("body-2")
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(actor, dead),
        items=(held,),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=33)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Give(EntityId("body-2"), EntityId("item-1")),
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert engine._snapshot.world.state.items[EntityId("item-1")].holder_id == (
        EntityId("body-1")
    )


def test_help_cannot_revive_dead_target() -> None:
    fixture = two_location_fixture(item_on_ground=False)
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(fixture.bodies[0], dead_body("body-2")),
        items=(),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=34)
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Help(EntityId("body-2"))),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert engine._snapshot.world.state.bodies[EntityId("body-2")].health.value == 0.0


def test_attack_self_is_rejected() -> None:
    engine = make_engine(two_location_fixture(item_on_ground=False), seed=35)
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Attack(EntityId("body-1"))),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_drink_depleted_resource_quantity_half_rejected() -> None:
    engine = make_engine(
        two_location_fixture(water_quantity=0.5, item_on_ground=False),
        seed=36,
    )
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Drink(EntityId("res-water"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert engine._snapshot.world.state.resources[EntityId("res-water")].quantity == 0.5


def test_drop_unowned_item_is_rejected() -> None:
    engine = make_engine(two_location_fixture(), seed=37)
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Drop(EntityId("item-1"))),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_dead_actor_actions_are_rejected() -> None:
    fixture = two_location_fixture()
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(dead_body("body-1"), fixture.bodies[1]),
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=38)
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Take(EntityId("item-1"))),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.DEAD_ACTOR
    assert engine._snapshot.world.state.items[EntityId("item-1")].holder_id is None
