"""Detached objective facts do not expose seeds or mutate the engine."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.models import RunId, SimulationRunConfig
from simulation.observer_facts import (
    ObjectiveFacts,
    ObjectiveFactsError,
    ObjectiveScene,
    scene_from_facts,
)
from tests.simulation_helpers import make_item, make_location, weather_for_locations
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit


def _alive(entity_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(1),
        thirst=Thirst(2),
        fatigue=Fatigue(3),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _engine() -> WorldEngine:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldEngine(
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations=locations,
            items=(make_item("item-1", name="Rock", location_id="loc-1"),),
            bodies=(_alive("body-1"),),
            weather=weather_for_locations(locations),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            ),
        ),
        config=SimulationRunConfig(seed=7),
        run_id=RunId("run-facts"),
    )


def test_detached_facts_match_the_folded_cursor_and_hide_seed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    tick_before = engine.tick
    revision_before = engine.revision
    with caplog.at_level(logging.DEBUG, logger="simulation.observer_facts"):
        scene = scene_from_facts(engine.detached_objective_facts())
    assert isinstance(scene, ObjectiveScene)
    assert "seed" not in ObjectiveScene.__dataclass_fields__
    assert "seed" not in ObjectiveFacts.__dataclass_fields__
    assert scene.tick == 0
    assert scene.revision == 0
    assert scene.run_id == "run-facts"
    assert scene.world_id == "world-1"
    assert scene.locations[0].entity_id.value == "loc-1"
    assert scene.bodies[0].entity_id.value == "body-1"
    assert scene.items[0].entity_id.value == "item-1"
    assert engine.tick == tick_before
    assert engine.revision == revision_before
    assert any("objective_scene_built" in message for message in caplog.messages)
    assert all("seed" not in message for message in caplog.messages)


def test_scene_rejects_empty_world_and_incomplete_weather() -> None:
    locations = (make_location("loc-1"),)
    base = ObjectiveFacts(
        run_id="run-1",
        world_id="",
        tick=0,
        revision=0,
        locations=locations,
        bodies=(),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        registrations=(),
    )
    with pytest.raises(ObjectiveFactsError) as empty:
        scene_from_facts(base)
    assert empty.value.reason_code == "empty_world_id"
    missing = ObjectiveFacts(
        run_id="run-1",
        world_id="world-1",
        tick=0,
        revision=0,
        locations=locations,
        bodies=(),
        items=(),
        resources=(),
        weather=(),
        registrations=(),
    )
    with pytest.raises(ObjectiveFactsError) as weather:
        scene_from_facts(missing)
    assert weather.value.reason_code == "weather_incomplete"
