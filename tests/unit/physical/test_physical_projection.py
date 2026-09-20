"""Physical observation/projection contracts at visibility boundaries."""

from __future__ import annotations

import pytest

from tests.physical_helpers import two_location_fixture
from tests.simulation_helpers import make_item, make_resource, make_weather
from world._perception import project_observations
from world._state import WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import copy_body, default_physical_rules
from world.observations import ObservationContext
from world.values import DayPhase, Hunger, WeatherCondition

pytestmark = pytest.mark.unit


def test_exits_visible_below_content_threshold() -> None:
    fixture = two_location_fixture()
    # Storm at night: 1.0 * 0.5 * 0.5 = 0.25 < 0.5
    weather = (
        make_weather("loc-1", condition=WeatherCondition.STORM),
        make_weather("loc-2", condition=WeatherCondition.STORM),
    )
    state = WorldState(
        WorldRevision(0),
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=weather,
    )
    context = ObservationContext(tick=0)  # night
    obs = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=context,
    )[0]
    assert obs.visibility is not None
    assert obs.visibility < 0.5
    assert obs.day_phase is DayPhase.NIGHT
    assert len(obs.exits) == 1
    assert obs.exits[0].destination_id == EntityId("loc-2")
    assert obs.resources == ()
    # Ground rock hidden; held inventory would use ObservedItemPlacement.
    assert all(item.placement.value == "held_by_self" for item in obs.items)


def test_held_inventory_remains_visible_in_darkness() -> None:
    fixture = two_location_fixture(item_on_ground=False)
    held = make_item("item-held", location_id=None, holder_id="body-1")
    from world.models import copy_body

    body = copy_body(fixture.bodies[0], inventory=(EntityId("item-held"),))
    weather = (
        make_weather("loc-1", condition=WeatherCondition.STORM),
        make_weather("loc-2", condition=WeatherCondition.STORM),
    )
    state = WorldState(
        WorldRevision(0),
        locations=fixture.locations,
        bodies=(body, fixture.bodies[1]),
        items=(held,),
        resources=fixture.resources,
        weather=weather,
    )
    obs = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=0),
    )[0]
    assert obs.visibility is not None and obs.visibility < 0.5
    assert [item.entity_id for item in obs.items] == [EntityId("item-held")]


def test_day_phase_and_visibility_modifier_always_exposed() -> None:
    fixture = two_location_fixture()
    state = fixture.as_state()
    day = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=12),
    )[0]
    night = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=0),
    )[0]
    assert day.day_phase is DayPhase.DAY
    assert night.day_phase is DayPhase.NIGHT
    assert day.visibility == pytest.approx(1.0)
    assert night.visibility == pytest.approx(0.5)
    rules = default_physical_rules()
    assert rules.effective_visibility(
        location_visibility=1.0,
        phase=DayPhase.NIGHT,
        condition=WeatherCondition.CLEAR,
    ) == pytest.approx(0.5)


def test_remote_bodies_items_and_resources_are_omitted() -> None:
    fixture = two_location_fixture()
    remote_body = copy_body(fixture.bodies[1], location_id=EntityId("loc-2"))
    remote_item = make_item("item-far", name="Ore", location_id="loc-2")
    remote_resource = make_resource(
        "res-far", name="OreVein", location_id="loc-2", quantity=4.0
    )
    state = WorldState(
        WorldRevision(0),
        locations=fixture.locations,
        bodies=(fixture.bodies[0], remote_body),
        items=(*fixture.items, remote_item),
        resources=(*fixture.resources, remote_resource),
        weather=fixture.weather,
    )
    obs = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=12),
    )[0]
    assert EntityId("body-2") not in {body.entity_id for body in obs.visible_bodies}
    assert EntityId("item-far") not in {item.entity_id for item in obs.items}
    assert EntityId("res-far") not in {resource.entity_id for resource in obs.resources}
    resource_ids = {resource.entity_id for resource in obs.resources}
    for resource in fixture.resources:
        assert resource.entity_id in resource_ids


def test_self_exact_physiology_never_leaks_to_other_observer() -> None:
    fixture = two_location_fixture()
    hungry = copy_body(fixture.bodies[0], hunger=Hunger(91.0))
    remote = copy_body(fixture.bodies[1], location_id=EntityId("loc-2"))
    state = WorldState(
        WorldRevision(0),
        locations=fixture.locations,
        bodies=(hungry, remote),
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
    )
    other = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-2"),),
        context=ObservationContext(tick=12),
    )[0]
    assert all(body.entity_id != EntityId("body-1") for body in other.visible_bodies)
    assert not any(hasattr(body, "hunger") for body in other.visible_bodies)
    # Colocated visibility still only exposes coarse health, never exact hunger.
    colocated = project_observations(
        world_id=WorldId("world-1"),
        state=WorldState(
            WorldRevision(0),
            locations=fixture.locations,
            bodies=(hungry, fixture.bodies[1]),
            items=fixture.items,
            resources=fixture.resources,
            weather=fixture.weather,
        ),
        observer_ids=(EntityId("body-2"),),
        context=ObservationContext(tick=12),
    )[0]
    peer = next(
        body
        for body in colocated.visible_bodies
        if body.entity_id == EntityId("body-1")
    )
    assert not hasattr(peer, "hunger")
    assert peer.coarse_health.value in {"stable", "injured", "critical", "dead"}
