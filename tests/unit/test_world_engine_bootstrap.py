"""Public world bootstrap and agent registration boundary."""

from __future__ import annotations

import inspect

import pytest

from agents.models import AgentId
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    _materialize_world,
    registration_translator,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, LifeStatus, Location, Resource, Weather
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst


def _alive_body(entity_id: str, location_id: str = "loc-1") -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
    )


def _dead_body(entity_id: str, location_id: str = "loc-1") -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(0),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(20.0),
        inventory=(),
        life_status=LifeStatus.DEAD,
    )


def _minimal_bootstrap(
    *,
    registrations: tuple[AgentRegistration, ...] | None = None,
    bodies: tuple[AgentBody, ...] | None = None,
) -> WorldBootstrap:
    location = Location(entity_id=EntityId("loc-1"), name="Camp")
    if bodies is None:
        bodies = (_alive_body("body-1"),)
    if registrations is None:
        registrations = (
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        )
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=(location,),
        bodies=bodies,
        registrations=registrations,
    )


def test_bootstrap_accepts_ordered_public_models_and_registrations() -> None:
    bootstrap = _minimal_bootstrap()
    assert bootstrap.world_id == WorldId("world-1")
    assert bootstrap.revision == WorldRevision(0)
    assert len(bootstrap.registrations) == 1
    translator = registration_translator(bootstrap)
    assert translator.to_entity_id(AgentId("agent-1")) == EntityId("body-1")
    assert translator.to_agent_id(EntityId("body-1")) == AgentId("agent-1")
    assert translator.ordered_registrations == bootstrap.registrations


def test_dead_bodies_may_be_registered() -> None:
    bootstrap = _minimal_bootstrap(
        bodies=(_dead_body("body-dead"),),
        registrations=(
            AgentRegistration(AgentId("ghost"), EntityId("body-dead")),
        ),
    )
    assert bootstrap.bodies[0].life_status is LifeStatus.DEAD
    assert bootstrap.registrations[0].entity_id == EntityId("body-dead")


def test_registration_order_is_preserved_canonically() -> None:
    bodies = (_alive_body("body-a"), _alive_body("body-b"))
    registrations = (
        AgentRegistration(AgentId("agent-b"), EntityId("body-b")),
        AgentRegistration(AgentId("agent-a"), EntityId("body-a")),
    )
    bootstrap = _minimal_bootstrap(bodies=bodies, registrations=registrations)
    assert bootstrap.registrations[0].agent_id == AgentId("agent-b")
    assert registration_translator(bootstrap).ordered_registrations == registrations


def test_duplicate_agent_or_entity_registrations_fail() -> None:
    bodies = (_alive_body("body-1"), _alive_body("body-2"))
    with pytest.raises(ValueError, match="duplicate agent_id"):
        _minimal_bootstrap(
            bodies=bodies,
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
                AgentRegistration(AgentId("agent-1"), EntityId("body-2")),
            ),
        )
    with pytest.raises(ValueError, match="duplicate entity_id"):
        _minimal_bootstrap(
            bodies=bodies,
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
                AgentRegistration(AgentId("agent-2"), EntityId("body-1")),
            ),
        )


def test_missing_body_and_cross_category_registrations_fail() -> None:
    with pytest.raises(ValueError, match="no matching body"):
        _minimal_bootstrap(
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("missing")),
            ),
        )
    with pytest.raises(ValueError, match="refers to a location"):
        _minimal_bootstrap(
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("loc-1")),
            ),
        )
    item = Item(
        entity_id=EntityId("item-1"),
        name="Rock",
        location_id=EntityId("loc-1"),
    )
    with pytest.raises(ValueError, match="refers to an item"):
        WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
            items=(item,),
            bodies=(_alive_body("body-1"),),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("item-1")),
            ),
        )


def test_unordered_containers_are_rejected() -> None:
    with pytest.raises(TypeError, match="ordered sequence"):
        WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations={Location(entity_id=EntityId("loc-1"), name="Camp")},  # type: ignore[arg-type]
            bodies=(_alive_body("body-1"),),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            ),
        )


def test_public_bootstrap_annotations_exclude_private_authority() -> None:
    hints = inspect.get_annotations(WorldBootstrap, eval_str=True)
    forbidden = {"World", "WorldState"}
    for name, annotation in hints.items():
        rendered = str(annotation)
        assert "WorldState" not in rendered, name
        assert annotation not in (type(None),)
        assert getattr(annotation, "__name__", "") not in forbidden


def test_materialize_world_is_internal_and_matches_bootstrap() -> None:
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(2),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        items=(
            Item(
                entity_id=EntityId("item-1"),
                name="Cup",
                location_id=EntityId("loc-1"),
            ),
        ),
        resources=(
            Resource(
                entity_id=EntityId("res-1"),
                name="Water",
                location_id=EntityId("loc-1"),
                quantity=1.0,
                unit="L",
            ),
        ),
        bodies=(_alive_body("body-1"),),
        weather=(
            Weather(
                location_id=EntityId("loc-1"),
                condition="clear",
                temperature=TemperatureCelsius(22.0),
            ),
        ),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
    )
    world = _materialize_world(bootstrap)
    assert world.world_id == bootstrap.world_id
    assert world.state.revision == bootstrap.revision
    assert EntityId("body-1") in world.state.bodies
    assert "World" not in __import__("simulation").__all__
    assert "_materialize_world" not in __import__("simulation").__all__
