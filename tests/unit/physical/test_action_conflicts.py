"""Conflicted outcomes when earlier ordered effects invalidate a later action."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import make_engine, two_location_fixture
from tests.simulation_helpers import make_item, make_location, weather_for_locations
from world.actions import Drop, Give, Move, Take
from world.identifiers import EntityId
from world.models import copy_body

pytestmark = pytest.mark.unit


def test_second_take_of_same_item_is_conflicted() -> None:
    engine = make_engine(two_location_fixture(), seed=41)
    before = engine._snapshot.world.state
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(batch.token, AgentId("agent-2"), Take(EntityId("item-1"))),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.CONFLICTED
    after = engine._snapshot.world.state
    assert after.items[EntityId("item-1")].holder_id == EntityId("body-1")
    assert EntityId("item-1") not in after.bodies[EntityId("body-2")].inventory
    assert (
        before.items[EntityId("item-1")].entity_id
        == after.items[EntityId("item-1")].entity_id
    )


def test_move_into_full_destination_after_earlier_arrival_conflicts() -> None:
    fixture = two_location_fixture(body_capacity=2, item_on_ground=False)
    # loc-2 starts empty; body capacity 2. Put one body already there so one slot
    # remains; two movers contend for the last slot.
    body_a = copy_body(fixture.bodies[0], location_id=EntityId("loc-1"))
    body_b = copy_body(fixture.bodies[1], location_id=EntityId("loc-1"))
    # Need a third body occupying loc-2 so capacity=2 means one free slot.
    from simulation.bootstrap import AgentRegistration
    from tests.simulation_helpers import alive_body

    body_c = alive_body("body-3", location_id="loc-2")
    locations = (
        make_location(
            "loc-1",
            name="Camp",
            adjacent=("loc-2",),
            body_capacity=3,
        ),
        make_location(
            "loc-2",
            name="Forest",
            adjacent=("loc-1",),
            body_capacity=2,
        ),
    )
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=locations,
        bodies=(body_a, body_b, body_c),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
            AgentRegistration(AgentId("agent-3"), EntityId("body-3")),
        ),
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=42)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Move(EntityId("loc-2"))),
            ActionSubmission(batch.token, AgentId("agent-2"), Move(EntityId("loc-2"))),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.CONFLICTED
    assert engine._snapshot.world.state.bodies[
        EntityId("body-1")
    ].location_id == EntityId("loc-2")
    assert engine._snapshot.world.state.bodies[
        EntityId("body-2")
    ].location_id == EntityId("loc-1")


def test_give_second_submission_same_agent_is_duplicate() -> None:
    fixture = two_location_fixture(item_on_ground=False)
    held = make_item("item-1", location_id=None, holder_id="body-1")
    actor = copy_body(fixture.bodies[0], inventory=(EntityId("item-1"),))
    from simulation.bootstrap import AgentRegistration
    from tests.simulation_helpers import alive_body

    body3 = alive_body("body-3", location_id="loc-1")
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(actor, fixture.bodies[1], body3),
        items=(held,),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=(
            *fixture.registrations,
            AgentRegistration(AgentId("agent-3"), EntityId("body-3")),
        ),
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=43)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Give(EntityId("body-2"), EntityId("item-1")),
            ),
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Give(EntityId("body-3"), EntityId("item-1")),
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.DUPLICATE
    assert engine._snapshot.world.state.items[EntityId("item-1")].holder_id == EntityId(
        "body-2"
    )


def test_drop_conflicts_when_earlier_drop_fills_capacity() -> None:
    fixture = two_location_fixture(item_capacity=1, item_on_ground=False)
    item_a = make_item("item-a", location_id=None, holder_id="body-1", load=1)
    item_b = make_item("item-b", location_id=None, holder_id="body-2", load=1)
    body_a = copy_body(fixture.bodies[0], inventory=(EntityId("item-a"),))
    body_b = copy_body(fixture.bodies[1], inventory=(EntityId("item-b"),))
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(body_a, body_b),
        items=(item_a, item_b),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=44)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Drop(EntityId("item-a"))),
            ActionSubmission(batch.token, AgentId("agent-2"), Drop(EntityId("item-b"))),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.CONFLICTED
    assert engine._snapshot.world.state.items[EntityId("item-a")].location_id == (
        EntityId("loc-1")
    )
    assert engine._snapshot.world.state.items[EntityId("item-b")].holder_id == (
        EntityId("body-2")
    )
