"""Objective frame projection keeps catalog changes out of facts."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from observer.contracts import ScreenPoint
from observer.layout import LocationVisualSpec, ObserverLayoutCatalog
from observer.project import project_frame
from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.models import RunId, SimulationRunConfig
from simulation.observer_facts import scene_from_facts
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


def _scene():
    locations = (
        make_location("loc-1", name="Camp", adjacent=("loc-2",)),
        make_location("loc-2", name="Ridge", adjacent=("loc-1",)),
    )
    bodies = (
        AgentBody(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(90),
            hunger=Hunger(4),
            thirst=Thirst(5),
            fatigue=Fatigue(6),
            temperature=TemperatureCelsius(36.5),
            inventory=(EntityId("item-held"),),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        AgentBody(
            entity_id=EntityId("body-extra"),
            location_id=EntityId("loc-1"),
            health=Health(80),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
    )
    engine = WorldEngine(
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(2),
            locations=locations,
            items=(
                make_item("item-ground", name="Rock", location_id="loc-2"),
                make_item(
                    "item-held", name="Cup", location_id=None, holder_id="body-1"
                ),
            ),
            bodies=bodies,
            weather=weather_for_locations(locations),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            ),
        ),
        config=SimulationRunConfig(seed=3),
        run_id=RunId("run-project"),
        start_tick=None,
    )
    return scene_from_facts(engine.detached_objective_facts())


def _catalog(x: float) -> ObserverLayoutCatalog:
    return ObserverLayoutCatalog(
        layout_id="test-layout",
        schema_version=OBSERVER_LAYOUT_SCHEMA_VERSION,
        specs=(
            LocationVisualSpec(
                location_id="loc-1",
                display_name="Camp Display",
                screen_position=ScreenPoint(x, 1.0),
                visual_bounds=None,
                theme="camp",
                icon_ref="icon",
                background_ref="bg",
                connection_anchors=(("loc-2", ScreenPoint(2.0, 3.0)),),
                slot_anchors=(ScreenPoint(4.0, 5.0),),
            ),
            LocationVisualSpec(
                location_id="loc-2",
                display_name="Ridge Display",
                screen_position=ScreenPoint(9.0, 9.0),
                visual_bounds=None,
                theme=None,
                icon_ref=None,
                background_ref=None,
                connection_anchors=(("loc-1", ScreenPoint(0.0, 0.0)),),
                slot_anchors=(),
            ),
        ),
    )


def _objective(frame) -> tuple[object, ...]:
    world = frame.world
    return (
        tuple(item.location_id for item in world.locations),
        tuple(item.neighbor_ids for item in world.locations),
        tuple((item.entity_id, item.life_status) for item in world.agents),
        tuple((item.item_id, item.holder_id, item.location_id) for item in world.items),
        tuple((item.resource_id, item.quantity) for item in world.resources),
    )


def test_catalog_shift_does_not_change_objective_fields() -> None:
    scene = _scene()
    left = project_frame(scene, _catalog(0.0), mode="live")
    right = project_frame(scene, _catalog(40.0), mode="replay")
    assert _objective(left) == _objective(right)
    assert left.cursor.mode == "live"
    assert right.cursor.mode == "replay"
    camp_left = left.world.locations[0].presentation
    camp_right = right.world.locations[0].presentation
    assert camp_left is not None and camp_right is not None
    assert camp_left.screen_position is not None
    assert camp_right.screen_position is not None
    assert camp_left.screen_position.x != camp_right.screen_position.x
    extra = next(item for item in left.world.agents if item.entity_id == "body-extra")
    assert extra.agent_id is None
    registered = next(item for item in left.world.agents if item.entity_id == "body-1")
    assert registered.agent_id == "agent-1"
    assert registered.life_status == "alive"
    assert "relationship" not in left.world.__dataclass_fields__
