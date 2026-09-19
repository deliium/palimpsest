"""Physical observation/projection contracts at visibility boundaries."""

from __future__ import annotations

import pytest

from tests.physical_helpers import two_location_fixture
from tests.simulation_helpers import make_item, make_weather
from world._perception import project_observations
from world._state import WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.observations import ObservationContext
from world.values import DayPhase, WeatherCondition

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
    # Ground rock hidden; no held inventory.
    assert all(item.holder_id is not None for item in obs.items)


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
