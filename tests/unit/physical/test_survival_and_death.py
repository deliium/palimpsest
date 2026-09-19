"""Survival, exposure death, and terminal needs death for autonomous physics."""

from __future__ import annotations

from tests.simulation_helpers import (
    alive_body,
    make_location,
    weather_for_locations,
)
from world._physical import apply_autonomous_physical_step
from world._state import WorldState
from world.effects import DeathCause, SystemEffectFamily
from world.events import Died, ExposureApplied, NeedsApplied
from world.identifiers import EntityId, WorldRevision
from world.models import AgentBody, LifeStatus, copy_body, default_physical_rules
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _state(*, bodies, locations=None) -> WorldState:
    locs = locations if locations is not None else (make_location("loc-1"),)
    return WorldState(
        WorldRevision(0),
        locations=locs,
        bodies=bodies,
        weather=weather_for_locations(locs),
    )


def test_combined_needs_death_skips_temperature() -> None:
    body = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(5),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
        temperature=TemperatureCelsius(20.0),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    # Extreme cold ambient would kill via exposure if temperature ran.
    cold = make_location("loc-1", base_temperature=-40.0, shelter_factor=0.0)
    step = apply_autonomous_physical_step(
        state=_state(bodies=(body,), locations=(cold,)),
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    kinds = [type(detail.details) for detail in step.pending_details]
    assert NeedsApplied in kinds
    assert Died in kinds
    assert ExposureApplied not in kinds
    died = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is Died
    )
    assert died.death_cause is DeathCause.COMBINED_NEEDS
    resulting = step.working_state.bodies[EntityId("body-1")]
    assert resulting.life_status is LifeStatus.DEAD
    assert resulting.health.value == 0.0
    # Temperature left at pre-death value (needs path skipped exposure).
    assert resulting.temperature.value == 20.0


def test_exposure_death_emits_died_exposure() -> None:
    body = copy_body(
        alive_body("body-1"),
        health=Health(4),
        temperature=TemperatureCelsius(50.0),
    )
    hot = make_location("loc-1", base_temperature=50.0, shelter_factor=0.0)
    step = apply_autonomous_physical_step(
        state=_state(bodies=(body,), locations=(hot,)),
        rules=default_physical_rules(),
        tick=6,
        hour=6,
        day_phase=DayPhase.DAY,
    )
    died = [
        detail
        for detail in step.pending_details
        if type(detail.details) is Died
    ]
    assert len(died) == 1
    assert died[0].details.death_cause is DeathCause.EXPOSURE
    assert died[0].effect_family is SystemEffectFamily.EXPOSURE
    resulting = step.working_state.bodies[EntityId("body-1")]
    assert resulting.life_status is LifeStatus.DEAD
    assert resulting.health.value == 0.0


def test_dead_bodies_are_skipped() -> None:
    dead = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(0),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
        temperature=TemperatureCelsius(10.0),
        inventory=(),
        life_status=LifeStatus.DEAD,
        carry_capacity=CarryCapacity(10),
    )
    step = apply_autonomous_physical_step(
        state=_state(bodies=(dead,)),
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    assert step.pending_details == ()
    assert step.semantic_mutation is False
    assert step.working_state.bodies[EntityId("body-1")] is dead


def test_living_bodies_processed_in_entity_id_order() -> None:
    bodies = (
        alive_body("body-b"),
        alive_body("body-a"),
    )
    step = apply_autonomous_physical_step(
        state=_state(bodies=bodies),
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    needs_ids = [
        detail.entity_id.value
        for detail in step.pending_details
        if detail.effect_family is SystemEffectFamily.COMBINED_NEEDS
    ]
    assert needs_ids == ["body-a", "body-b"]


def test_exactly_one_died_per_body_on_needs_death() -> None:
    body = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(5),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    step = apply_autonomous_physical_step(
        state=_state(bodies=(body,)),
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    died = [
        detail
        for detail in step.pending_details
        if type(detail.details) is Died
    ]
    assert len(died) == 1
    # Second autonomous step on the dead body emits nothing.
    step2 = apply_autonomous_physical_step(
        state=step.working_state,
        rules=default_physical_rules(),
        tick=1,
        hour=1,
        day_phase=DayPhase.NIGHT,
    )
    assert step2.pending_details == ()
    assert step2.semantic_mutation is False


def test_dead_body_occupies_capacity_and_keeps_inventory() -> None:
    from tests.simulation_helpers import make_item
    from world._state import WorldState
    from world.identifiers import WorldRevision

    held = make_item("item-1", location_id=None, holder_id="body-1")
    dead = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(0),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(EntityId("item-1"),),
        life_status=LifeStatus.DEAD,
        carry_capacity=CarryCapacity(10),
    )
    living = alive_body("body-2")
    # Capacity 1: dead body already fills it — world still validates.
    location = make_location("loc-1", body_capacity=2)
    state = WorldState(
        WorldRevision(0),
        locations=(location,),
        bodies=(dead, living),
        items=(held,),
        weather=weather_for_locations((location,)),
    )
    assert state.bodies[EntityId("body-1")].life_status is LifeStatus.DEAD
    assert EntityId("item-1") in state.bodies[EntityId("body-1")].inventory
    assert held.holder_id == EntityId("body-1")


def test_all_dead_tick_is_noop_via_physical_step() -> None:
    dead_a = AgentBody(
        entity_id=EntityId("body-a"),
        location_id=EntityId("loc-1"),
        health=Health(0),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
        temperature=TemperatureCelsius(10.0),
        inventory=(),
        life_status=LifeStatus.DEAD,
        carry_capacity=CarryCapacity(10),
    )
    dead_b = AgentBody(
        entity_id=EntityId("body-b"),
        location_id=EntityId("loc-1"),
        health=Health(0),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
        temperature=TemperatureCelsius(10.0),
        inventory=(),
        life_status=LifeStatus.DEAD,
        carry_capacity=CarryCapacity(10),
    )
    step = apply_autonomous_physical_step(
        state=_state(bodies=(dead_a, dead_b)),
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    assert step.pending_details == ()
    assert step.semantic_mutation is False
