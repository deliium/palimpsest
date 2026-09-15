"""Private deterministic perception projector."""

from __future__ import annotations

import pytest

from world._perception import project_observations
from world._state import WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, LifeStatus, Location, Resource, Weather
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst


def _body(
    entity_id: str,
    location_id: str,
    *,
    inventory: tuple[EntityId, ...] = (),
    dead: bool = False,
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(0 if dead else 100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.DEAD if dead else LifeStatus.ALIVE,
    )


def _rich_state() -> WorldState:
    cup = Item(
        entity_id=EntityId("item-cup"),
        name="Cup",
        holder_id=EntityId("body-1"),
    )
    rock = Item(
        entity_id=EntityId("item-rock"),
        name="Rock",
        location_id=EntityId("loc-1"),
    )
    distant = Item(
        entity_id=EntityId("item-far"),
        name="Far",
        location_id=EntityId("loc-2"),
    )
    return WorldState(
        WorldRevision(3),
        locations=(
            Location(entity_id=EntityId("loc-1"), name="Camp"),
            Location(entity_id=EntityId("loc-2"), name="Forest"),
        ),
        items=(cup, rock, distant),
        resources=(
            Resource(
                entity_id=EntityId("res-b"),
                name="Berries",
                location_id=EntityId("loc-1"),
                quantity=2.0,
                unit="kg",
            ),
            Resource(
                entity_id=EntityId("res-a"),
                name="Water",
                location_id=EntityId("loc-1"),
                quantity=1.0,
                unit="L",
            ),
            Resource(
                entity_id=EntityId("res-far"),
                name="Ore",
                location_id=EntityId("loc-2"),
                quantity=5.0,
                unit="kg",
            ),
        ),
        bodies=(
            _body("body-1", "loc-1", inventory=(EntityId("item-cup"),)),
            _body("body-2", "loc-2"),
            _body("body-dead", "loc-1", dead=True),
        ),
        weather=(
            Weather(
                location_id=EntityId("loc-1"),
                condition="clear",
                temperature=TemperatureCelsius(18),
            ),
            Weather(
                location_id=EntityId("loc-2"),
                condition="fog",
                temperature=TemperatureCelsius(10),
            ),
        ),
    )


def test_observations_follow_registration_order_and_v1_policy() -> None:
    state = _rich_state()
    observations = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-2"), EntityId("body-1")),
    )
    assert [obs.observer_id for obs in observations] == [
        EntityId("body-2"),
        EntityId("body-1"),
    ]
    first, second = observations
    assert first.self_body is not None
    assert first.self_body.entity_id == EntityId("body-2")
    assert first.locations == (
        Location(entity_id=EntityId("loc-2"), name="Forest"),
    )
    assert first.items == (
        Item(
            entity_id=EntityId("item-far"),
            name="Far",
            location_id=EntityId("loc-2"),
        ),
    )
    assert [resource.entity_id for resource in first.resources] == [
        EntityId("res-far")
    ]
    assert first.weather[0].condition == "fog"

    assert second.self_body is not None
    assert second.self_body.entity_id == EntityId("body-1")
    assert [item.entity_id for item in second.items] == [
        EntityId("item-cup"),
        EntityId("item-rock"),
    ]
    assert [resource.entity_id for resource in second.resources] == [
        EntityId("res-a"),
        EntityId("res-b"),
    ]
    # Never expose other bodies.
    assert all(obs.self_body is not None for obs in observations)
    for obs in observations:
        body = obs.self_body
        assert body is not None
        assert body.entity_id == obs.observer_id


def test_dead_bodies_still_receive_observations() -> None:
    state = _rich_state()
    observations = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-dead"),),
    )
    assert observations[0].self_body is not None
    assert observations[0].self_body.life_status is LifeStatus.DEAD
    assert observations[0].locations[0].entity_id == EntityId("loc-1")


def test_missing_observer_fails_before_any_result() -> None:
    state = _rich_state()
    with pytest.raises(ValueError, match="missing from world state"):
        project_observations(
            world_id=WorldId("world-1"),
            state=state,
            observer_ids=(EntityId("body-1"), EntityId("ghost")),
        )


def test_repeated_projection_is_idempotent_and_detached() -> None:
    state = _rich_state()
    first = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
    )
    second = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
    )
    assert first == second
    assert first[0].self_body is not state.bodies[EntityId("body-1")]
    assert first[0].items[0] is not state.items[EntityId("item-cup")]


def test_unordered_or_duplicate_observers_rejected() -> None:
    state = _rich_state()
    with pytest.raises(TypeError, match="ordered sequence"):
        project_observations(
            world_id=WorldId("world-1"),
            state=state,
            observer_ids={EntityId("body-1")},  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="duplicates"):
        project_observations(
            world_id=WorldId("world-1"),
            state=state,
            observer_ids=(EntityId("body-1"), EntityId("body-1")),
        )
