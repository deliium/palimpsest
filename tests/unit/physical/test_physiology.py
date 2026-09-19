"""Physiology formulas for the pure autonomous physical step."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    weather_for_locations,
)
from world._physical import apply_autonomous_physical_step
from world._state import WorldState
from world.effects import (
    ResolvedSystemEffects,
    ResolvedWeatherEffect,
    SystemEffectFamily,
)
from world.events import (
    ExposureApplied,
    NeedsApplied,
    ResourceRegenerated,
    WeatherChanged,
)
from world.identifiers import EntityId, WorldRevision
from world.models import AgentBody, LifeStatus, PhysicalRules, copy_body
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
    round_physical,
)


def _state(
    *,
    bodies=(),
    resources=(),
    locations=None,
    weather=None,
    revision: int = 1,
):
    locs = locations if locations is not None else (make_location("loc-1"),)
    return WorldState(
        WorldRevision(revision),
        locations=locs,
        resources=resources,
        bodies=bodies,
        weather=(
            weather if weather is not None else weather_for_locations(locs)
        ),
    )


def test_metabolism_and_needs_damage_formulas() -> None:
    stressed = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(10),
        hunger=Hunger(99),
        thirst=Thirst(99),
        fatigue=Fatigue(99),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    # Full shelter keeps temperature stable so exposure does not stack.
    sheltered = make_location("loc-1", shelter_factor=1.0)
    step = apply_autonomous_physical_step(
        state=_state(bodies=(stressed,), locations=(sheltered,)),
        rules=PhysicalRules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    needs = [
        detail
        for detail in step.pending_details
        if type(detail.details) is NeedsApplied
    ]
    assert len(needs) == 1
    applied = needs[0].details
    assert applied.resulting_hunger == 100.0
    assert applied.resulting_thirst == 100.0
    assert applied.resulting_fatigue == 100.0
    # 2 + 5 + 1 = 8 damage from full needs
    assert applied.health_delta == -8.0
    assert applied.resulting_health == 2.0
    resulting = step.working_state.bodies[EntityId("body-1")]
    assert resulting.health.value == 2.0
    assert resulting.life_status is LifeStatus.ALIVE


def test_sheltered_body_keeps_temperature_and_records_ambient() -> None:
    sheltered = make_location(
        "loc-1",
        base_temperature=0.0,
        shelter_factor=1.0,
    )
    step = apply_autonomous_physical_step(
        state=_state(bodies=(alive_body("body-1"),), locations=(sheltered,)),
        rules=PhysicalRules(),
        tick=6,
        hour=6,
        day_phase=DayPhase.DAY,
    )
    exposure = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is ExposureApplied
    )
    assert type(exposure) is ExposureApplied
    # ambient = 0 + clear(0) + day(+2) = 2.0
    assert exposure.ambient_celsius == 2.0
    assert exposure.resulting_temperature == 36.5
    assert exposure.health_delta == 0.0


def test_exact_exposure_thresholds_are_safe() -> None:
    cold_at_threshold = copy_body(
        alive_body("body-1"),
        temperature=TemperatureCelsius(35.0),
    )
    step = apply_autonomous_physical_step(
        state=_state(
            bodies=(cold_at_threshold,),
            locations=(make_location("loc-1", base_temperature=35.0),),
        ),
        rules=PhysicalRules(),
        tick=6,
        hour=6,
        day_phase=DayPhase.DAY,
    )
    exposure = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is ExposureApplied
    )
    # ambient = 35 + 0 + 2 = 37; lerp from 35 → 35.5 (still safe)
    assert exposure.resulting_temperature == 35.5
    assert exposure.health_delta == 0.0


def test_resource_regeneration_caps_and_skips_unchanged() -> None:
    finite = make_resource("res-finite", quantity=2.0, regeneration_per_tick=0.0)
    renewable = make_resource(
        "res-renew",
        quantity=4.5,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    full = make_resource(
        "res-full",
        quantity=5.0,
        maximum_quantity=5.0,
        regeneration_per_tick=1.0,
    )
    step = apply_autonomous_physical_step(
        state=_state(resources=(finite, renewable, full), bodies=()),
        rules=PhysicalRules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    regen = [
        detail
        for detail in step.pending_details
        if detail.effect_family is SystemEffectFamily.REGENERATION
    ]
    assert len(regen) == 1
    assert regen[0].entity_id == EntityId("res-renew")
    details = regen[0].details
    assert type(details) is ResourceRegenerated
    assert details.resulting_quantity == 5.0
    assert details.quantity_delta == 0.5


def test_weather_emits_only_on_change_when_scheduled() -> None:
    locations = (make_location("loc-1"),)
    state = _state(locations=locations, bodies=())
    resolved = ResolvedSystemEffects(
        weather_by_location={
            EntityId("loc-1"): ResolvedWeatherEffect(
                EntityId("loc-1"), WeatherCondition.RAIN
            )
        }
    )
    # tick 5 → (5+1)%6==0 scheduled
    step = apply_autonomous_physical_step(
        state=state,
        rules=PhysicalRules(),
        tick=5,
        hour=5,
        day_phase=DayPhase.NIGHT,
        resolved=resolved,
    )
    weather_events = [
        detail
        for detail in step.pending_details
        if detail.effect_family is SystemEffectFamily.WEATHER
    ]
    assert len(weather_events) == 1
    assert weather_events[0].details == WeatherChanged(
        EntityId("loc-1"), WeatherCondition.RAIN
    )
    assert (
        step.working_state.weather[EntityId("loc-1")].condition
        is WeatherCondition.RAIN
    )

    same = ResolvedSystemEffects(
        weather_by_location={
            EntityId("loc-1"): ResolvedWeatherEffect(
                EntityId("loc-1"), WeatherCondition.CLEAR
            )
        }
    )
    step2 = apply_autonomous_physical_step(
        state=state,
        rules=PhysicalRules(),
        tick=5,
        hour=5,
        day_phase=DayPhase.NIGHT,
        resolved=same,
    )
    assert not any(
        detail.effect_family is SystemEffectFamily.WEATHER
        for detail in step2.pending_details
    )


def test_unsheltered_temperature_formula_matches_contract() -> None:
    location = make_location(
        "loc-1",
        base_temperature=20.0,
        shelter_factor=0.0,
    )
    body = copy_body(alive_body("body-1"), temperature=TemperatureCelsius(36.0))
    step = apply_autonomous_physical_step(
        state=_state(bodies=(body,), locations=(location,)),
        rules=PhysicalRules(),
        tick=6,
        hour=6,
        day_phase=DayPhase.DAY,
    )
    exposure = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is ExposureApplied
    )
    ambient = round_physical(20.0 + 0.0 + 2.0)
    expected = round_physical(36.0 + 0.25 * (ambient - 36.0) * 1.0)
    assert exposure.ambient_celsius == ambient
    assert exposure.resulting_temperature == expected


@pytest.mark.parametrize(
    ("hour", "phase"),
    [
        (5, DayPhase.NIGHT),
        (6, DayPhase.DAY),
        (17, DayPhase.DAY),
        (18, DayPhase.NIGHT),
    ],
)
def test_day_phase_boundaries_05_06_17_18(hour: int, phase: DayPhase) -> None:
    rules = PhysicalRules()
    assert rules.day_phase_for_hour(hour) is phase
    assert rules.day_phase_for_tick(hour) is phase


@pytest.mark.parametrize("tick", [0, 5, 6, 11])
def test_weather_schedule_ticks(tick: int) -> None:
    rules = PhysicalRules()
    scheduled = (tick + 1) % rules.weather_period_ticks == 0
    assert scheduled is (tick in {5, 11})


def test_visibility_threshold_exactly_half_hides_ground_contents() -> None:
    from world._perception import project_observations
    from world.identifiers import WorldId
    from world.observations import ObservationContext

    # Night * clear * base 1.0 = 0.5 — at threshold, contents remain visible.
    # Night * cloudy * base 1.0 = 0.45 — below threshold.
    locations = (
        make_location("loc-1", visibility_factor=1.0),
    )
    state = _state(
        bodies=(alive_body("body-1"),),
        locations=locations,
        resources=(make_resource("res-1", quantity=2.0),),
        weather=weather_for_locations(locations, condition=WeatherCondition.CLOUDY),
    )
    context = ObservationContext(tick=0)  # hour 0 → night
    observations = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=context,
    )
    obs = observations[0]
    assert obs.visibility == pytest.approx(0.45)
    assert obs.resources == ()
    assert [item.entity_id for item in obs.items] == []  # no held items

    # Exactly 0.5: night * clear * 1.0
    clear_state = _state(
        bodies=(alive_body("body-1"),),
        locations=locations,
        resources=(make_resource("res-1", quantity=2.0),),
        weather=weather_for_locations(locations, condition=WeatherCondition.CLEAR),
    )
    clear_obs = project_observations(
        world_id=WorldId("world-1"),
        state=clear_state,
        observer_ids=(EntityId("body-1"),),
        context=context,
    )[0]
    assert clear_obs.visibility == pytest.approx(0.5)
    assert [resource.entity_id for resource in clear_obs.resources] == [
        EntityId("res-1")
    ]


@pytest.mark.parametrize("shelter", [0.0, 1.0])
def test_shelter_zero_and_one_temperature_paths(shelter: float) -> None:
    location = make_location(
        "loc-1",
        base_temperature=10.0,
        shelter_factor=shelter,
    )
    body = copy_body(alive_body("body-1"), temperature=TemperatureCelsius(36.0))
    step = apply_autonomous_physical_step(
        state=_state(bodies=(body,), locations=(location,)),
        rules=PhysicalRules(),
        tick=6,
        hour=6,
        day_phase=DayPhase.DAY,
    )
    exposure = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is ExposureApplied
    )
    ambient = round_physical(10.0 + 0.0 + 2.0)
    expected = round_physical(
        36.0 + 0.25 * (ambient - 36.0) * (1.0 - shelter)
    )
    assert exposure.resulting_temperature == expected
    if shelter == 1.0:
        assert exposure.resulting_temperature == 36.0


def test_ties_to_even_rounding_in_temperature_path() -> None:
    # Choose ambient so the lerp lands on a ties-to-even boundary.
    # current=36.0, ambient=35.2, shelter=0 → delta = 0.25*(35.2-36.0)= -0.2
    # 36.0 + (-0.2) = 35.8 (already one decimal)
    # Use ambient that yields 1.25-style intermediate before round.
    assert round_physical(1.25) == 1.2
    assert round_physical(1.35) == 1.4
    location = make_location("loc-1", base_temperature=20.0, shelter_factor=0.0)
    # Pick temperature so formula produces a value needing ties-to-even.
    # new = t + 0.25*(ambient-t); ambient=22 (20+0+2); t=35.6
    # = 35.6 + 0.25*(22-35.6) = 35.6 - 3.4 = 32.2
    body = copy_body(alive_body("body-1"), temperature=TemperatureCelsius(35.6))
    step = apply_autonomous_physical_step(
        state=_state(bodies=(body,), locations=(location,)),
        rules=PhysicalRules(),
        tick=6,
        hour=6,
        day_phase=DayPhase.DAY,
    )
    exposure = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is ExposureApplied
    )
    expected = round_physical(35.6 + 0.25 * (22.0 - 35.6) * 1.0)
    assert exposure.resulting_temperature == expected
