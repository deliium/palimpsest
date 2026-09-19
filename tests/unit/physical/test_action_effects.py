"""Applied action outcomes and one-to-many event sequencing."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.lifecycle import (
    ActionResolutionStatus,
    ActionSubmission,
    EngineDiagnosticCode,
)
from tests.physical_helpers import make_engine, two_location_fixture
from tests.simulation_helpers import make_item
from world.actions import (
    Attack,
    Drink,
    Drop,
    Eat,
    Flee,
    Give,
    Help,
    Move,
    Search,
    Sleep,
    Take,
    Wait,
)
from world.effects import DeathCause
from world.events import Attacked, Died, Taken
from world.identifiers import EntityId
from world.models import LifeStatus, copy_body
from world.values import Fatigue, Health, Hunger, ItemKind, Thirst

pytestmark = pytest.mark.unit

_ENGINE_LOGGER = "simulation.engine"
_FORBIDDEN = ("Rock", "inventory", "WorldState", "seed=")


def _messages(caplog: pytest.LogCaptureFixture) -> str:
    return " ".join(record.getMessage() for record in caplog.records)


def test_move_adds_fatigue_and_relocates() -> None:
    engine = make_engine(two_location_fixture(), seed=21)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Move(EntityId("loc-2"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    body = engine._snapshot.world.state.bodies[EntityId("body-1")]
    assert body.location_id == EntityId("loc-2")
    # Move +5 immediately, then close-of-tick metabolism +1.
    assert body.fatigue.value == 6.0


def test_search_take_give_drop_round_trip() -> None:
    engine = make_engine(two_location_fixture(item_on_ground=True), seed=22)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert any(type(record.event.details) is Taken for record in result.events)

    batch2 = engine.observe()
    given = engine.resolve_tick(
        (
            ActionSubmission(
                batch2.token,
                AgentId("agent-1"),
                Give(EntityId("body-2"), EntityId("item-1")),
            ),
        )
    )
    assert given.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert engine._snapshot.world.state.items[EntityId("item-1")].holder_id == (
        EntityId("body-2")
    )

    batch3 = engine.observe()
    dropped = engine.resolve_tick(
        (
            ActionSubmission(
                batch3.token, AgentId("agent-2"), Drop(EntityId("item-1"))
            ),
        )
    )
    assert dropped.resolutions[0].status is ActionResolutionStatus.APPLIED
    item = engine._snapshot.world.state.items[EntityId("item-1")]
    assert item.location_id == EntityId("loc-1")
    assert item.holder_id is None


def test_eat_drink_sleep_help_wait_outcomes() -> None:
    food = make_item(
        "item-food",
        kind=ItemKind.FOOD,
        location_id=None,
        holder_id="body-1",
    )
    water = make_item(
        "item-water",
        kind=ItemKind.WATER,
        location_id=None,
        holder_id="body-1",
    )
    fixture = two_location_fixture(item_on_ground=False)
    actor = copy_body(
        fixture.bodies[0],
        inventory=(EntityId("item-food"), EntityId("item-water")),
        hunger=Hunger(50),
        thirst=Thirst(50),
        fatigue=Fatigue(40),
    )
    target = copy_body(fixture.bodies[1], health=Health(50))
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(actor, target),
        items=(food, water),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    engine = make_engine(world, seed=23)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Eat(EntityId("item-food"))
            ),
            ActionSubmission(
                batch.token, AgentId("agent-2"), Help(EntityId("body-1"))
            ),
        )
    )
    assert all(
        resolution.status is ActionResolutionStatus.APPLIED
        for resolution in result.resolutions
    )

    batch2 = engine.observe()
    result2 = engine.resolve_tick(
        (
            ActionSubmission(
                batch2.token, AgentId("agent-1"), Drink(EntityId("item-water"))
            ),
            ActionSubmission(batch2.token, AgentId("agent-2"), Sleep()),
        )
    )
    assert all(
        resolution.status is ActionResolutionStatus.APPLIED
        for resolution in result2.resolutions
    )
    body1 = engine._snapshot.world.state.bodies[EntityId("body-1")]
    assert body1.hunger.value < 50.0
    assert body1.thirst.value < 50.0


def test_attack_lethal_emits_contiguous_attack_and_died(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture = two_location_fixture(item_on_ground=False)
    frail = copy_body(fixture.bodies[1], health=Health(5))
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(fixture.bodies[0], frail),
        items=(),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    # Force hit by using high attack probability via many attempts is flaky;
    # instead use a seed known to produce a hit, or patch resolved effects.
    # Engine path: try several seeds until hit, assert structure when lethal.
    caplog.set_level(logging.DEBUG, logger=_ENGINE_LOGGER)
    for seed in range(40, 120):
        engine = make_engine(world, seed=seed)
        batch = engine.observe()
        result = engine.resolve_tick(
            (
                ActionSubmission(
                    batch.token, AgentId("agent-1"), Attack(EntityId("body-2"))
                ),
            )
        )
        assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
        attacked = [
            record.event
            for record in result.events
            if type(record.event.details) is Attacked
        ]
        if not attacked or not attacked[0].details.hit:
            continue
        if attacked[0].details.resulting_target_health != 0.0:
            continue
        died = [
            record.event
            for record in result.events
            if type(record.event.details) is Died
        ]
        assert len(died) == 1
        assert died[0].details.death_cause is DeathCause.ATTACK
        assert died[0].sequence == attacked[0].sequence + 1
        assert died[0].request_id == attacked[0].request_id
        assert (
            engine._snapshot.world.state.bodies[EntityId("body-2")].life_status
            is LifeStatus.DEAD
        )
        messages = _messages(caplog)
        assert EngineDiagnosticCode.TICK_COMMITTED.value in messages
        for fragment in _FORBIDDEN:
            assert fragment not in messages
        return
    pytest.fail("no lethal attack seed found in range")


def test_flee_and_search_are_applied_or_event_only() -> None:
    engine = make_engine(two_location_fixture(), seed=24)
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Flee()),
            ActionSubmission(batch.token, AgentId("agent-2"), Search()),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.APPLIED


def test_sleep_at_zero_fatigue_is_applied_noop() -> None:
    engine = make_engine(two_location_fixture(item_on_ground=False), seed=25)
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Sleep()),)
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    # Immediate sleep at zero is a no-op; metabolism still adds fatigue later.
    assert engine._snapshot.world.state.bodies[EntityId("body-1")].fatigue.value == 1.0
