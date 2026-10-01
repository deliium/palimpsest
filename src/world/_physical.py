"""Pure autonomous physical close-of-tick step.

Log-free and RNG-free. Simulation pre-resolves weather draws and supplies
deterministic system cause IDs before finalization.
"""

from __future__ import annotations

from dataclasses import dataclass

from world._production import shelter_factor_for
from world._state import WorldState, rebuild_world_state
from world.effects import (
    DeathCause,
    ResolvedSystemEffects,
    SystemEffectFamily,
)
from world.events import (
    Died,
    EventDetails,
    ExposureApplied,
    NeedsApplied,
    OccurrenceContext,
    ResourceRegenerated,
    WeatherChanged,
    build_occurrence_context,
    require_event_details,
)
from world.identifiers import EntityId, require_exact_nonneg_int
from world.models import (
    LifeStatus,
    PhysicalRules,
    copy_body,
    copy_resource,
    copy_weather,
)
from world.values import (
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
    clamp_need,
    round_physical,
)

__all__: list[str] = [
    "PendingSystemDetail",
    "PendingSystemStep",
    "apply_autonomous_physical_step",
]


@dataclass(frozen=True, slots=True)
class PendingSystemDetail:
    """One unfrozen system detail pending cause-id allocation."""

    effect_family: SystemEffectFamily
    entity_id: EntityId
    family_ordinal: int
    details: EventDetails
    occurrence: OccurrenceContext

    def __post_init__(self) -> None:
        if type(self.effect_family) is not SystemEffectFamily:
            raise TypeError(
                "PendingSystemDetail.effect_family must be SystemEffectFamily"
            )
        if type(self.entity_id) is not EntityId:
            raise TypeError("PendingSystemDetail.entity_id must be EntityId")
        object.__setattr__(
            self,
            "family_ordinal",
            require_exact_nonneg_int(
                "PendingSystemDetail.family_ordinal", self.family_ordinal
            ),
        )
        object.__setattr__(self, "details", require_event_details(self.details))
        if type(self.occurrence) is not OccurrenceContext:
            raise TypeError("PendingSystemDetail.occurrence must be OccurrenceContext")


@dataclass(frozen=True, slots=True)
class PendingSystemStep:
    """Autonomous stage candidate before revision/event finalization."""

    working_state: WorldState
    semantic_mutation: bool
    pending_details: tuple[PendingSystemDetail, ...]

    def __post_init__(self) -> None:
        if type(self.working_state) is not WorldState:
            raise TypeError("PendingSystemStep.working_state must be WorldState")
        if type(self.semantic_mutation) is not bool:
            raise TypeError("PendingSystemStep.semantic_mutation must be bool")
        if isinstance(self.pending_details, (str, bytes)) or not isinstance(
            self.pending_details, tuple
        ):
            raise TypeError("PendingSystemStep.pending_details must be a tuple")
        for detail in self.pending_details:
            if type(detail) is not PendingSystemDetail:
                raise TypeError(
                    "PendingSystemStep.pending_details entries must be "
                    "PendingSystemDetail"
                )


def _pending_system(
    *,
    effect_family: SystemEffectFamily,
    entity_id: EntityId,
    family_ordinal: int,
    details: EventDetails,
    origin_location_id: EntityId | None,
) -> PendingSystemDetail:
    return PendingSystemDetail(
        effect_family=effect_family,
        entity_id=entity_id,
        family_ordinal=family_ordinal,
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=origin_location_id
        ),
    )


def apply_autonomous_physical_step(
    *,
    state: WorldState,
    rules: PhysicalRules,
    tick: int,
    hour: int,
    day_phase: DayPhase,
    resolved: ResolvedSystemEffects | None = None,
) -> PendingSystemStep:
    """Apply weather, regeneration, metabolism, and exposure in canonical order.

    Working mutations keep the starting revision. Cause IDs, event IDs, and the
    final revision are allocated by the simulation finalizer.
    """
    if type(state) is not WorldState:
        raise TypeError("apply_autonomous_physical_step requires WorldState")
    if type(rules) is not PhysicalRules:
        raise TypeError("apply_autonomous_physical_step requires PhysicalRules")
    tick_value = require_exact_nonneg_int("tick", tick)
    hour_value = require_exact_nonneg_int("hour", hour)
    if hour_value >= rules.hours_per_day:
        raise ValueError("hour must be in [0, hours_per_day)")
    if type(day_phase) is not DayPhase:
        raise TypeError("day_phase must be DayPhase")
    if rules.day_phase_for_hour(hour_value) is not day_phase:
        raise ValueError("day_phase must match hour under PhysicalRules")
    if resolved is None:
        system_effects = ResolvedSystemEffects(weather_by_location={})
    elif type(resolved) is ResolvedSystemEffects:
        system_effects = resolved
    else:
        raise TypeError("resolved must be ResolvedSystemEffects or None")

    working = state
    semantic_mutation = False
    pending: list[PendingSystemDetail] = []
    family_ordinals: dict[SystemEffectFamily, int] = {
        family: 0 for family in SystemEffectFamily
    }

    weather_scheduled = (tick_value + 1) % rules.weather_period_ticks == 0
    if weather_scheduled:
        expected = set(working.locations)
        provided = set(system_effects.weather_by_location)
        if provided != expected:
            raise ValueError(
                "resolved weather must cover every location on scheduled ticks"
            )
        weather_map = dict(working.weather)
        for location_id in sorted(expected, key=lambda value: value.value):
            effect = system_effects.weather_by_location[location_id]
            prior = weather_map[location_id]
            if effect.condition is prior.condition:
                continue
            weather_map[location_id] = copy_weather(prior, condition=effect.condition)
            semantic_mutation = True
            ordinal = family_ordinals[SystemEffectFamily.WEATHER]
            family_ordinals[SystemEffectFamily.WEATHER] = ordinal + 1
            pending.append(
                _pending_system(
                    effect_family=SystemEffectFamily.WEATHER,
                    entity_id=location_id,
                    family_ordinal=ordinal,
                    details=WeatherChanged(
                        location_id=location_id,
                        condition=effect.condition,
                    ),
                    origin_location_id=location_id,
                )
            )
        if semantic_mutation:
            working = rebuild_world_state(working, weather=weather_map)
    elif system_effects.weather_by_location:
        raise ValueError("resolved weather must be empty on non-scheduled ticks")

    resources = dict(working.resources)
    resources_changed = False
    for resource_id in sorted(resources, key=lambda value: value.value):
        resource = resources[resource_id]
        if resource.regeneration_per_tick == 0.0:
            continue
        uncapped = round_physical(resource.quantity + resource.regeneration_per_tick)
        resulting = min(uncapped, resource.maximum_quantity)
        resulting = round_physical(resulting)
        if resulting == resource.quantity:
            continue
        resources[resource_id] = copy_resource(resource, quantity=resulting)
        resources_changed = True
        semantic_mutation = True
        ordinal = family_ordinals[SystemEffectFamily.REGENERATION]
        family_ordinals[SystemEffectFamily.REGENERATION] = ordinal + 1
        pending.append(
            _pending_system(
                effect_family=SystemEffectFamily.REGENERATION,
                entity_id=resource_id,
                family_ordinal=ordinal,
                details=ResourceRegenerated(
                    resource_id=resource_id,
                    quantity_delta=round_physical(resulting - resource.quantity),
                    resulting_quantity=resulting,
                ),
                origin_location_id=resource.location_id,
            )
        )
    if resources_changed:
        working = rebuild_world_state(working, resources=resources)

    phase_offsets = rules.phase_temperature_offset
    assert phase_offsets is not None
    phase_offset = phase_offsets[day_phase]
    bodies = dict(working.bodies)
    bodies_changed = False
    for body_id in sorted(bodies, key=lambda value: value.value):
        body = bodies[body_id]
        if body.life_status is not LifeStatus.ALIVE:
            continue
        location = working.locations[body.location_id]
        weather = working.weather[body.location_id]
        hunger = Hunger(
            clamp_need(round_physical(body.hunger.value + rules.metabolism_hunger))
        )
        thirst = Thirst(
            clamp_need(round_physical(body.thirst.value + rules.metabolism_thirst))
        )
        fatigue = Fatigue(
            clamp_need(round_physical(body.fatigue.value + rules.metabolism_fatigue))
        )
        damage = 0.0
        if hunger.value >= 100.0:
            damage += rules.hunger_damage
        if thirst.value >= 100.0:
            damage += rules.thirst_damage
        if fatigue.value >= 100.0:
            damage += rules.fatigue_damage
        resulting_health = clamp_need(round_physical(body.health.value - damage))
        health_delta = round_physical(resulting_health - body.health.value)
        died_from_needs = resulting_health <= 0.0
        if died_from_needs:
            next_body = copy_body(
                body,
                hunger=hunger,
                thirst=thirst,
                fatigue=fatigue,
                health=Health(0.0),
                life_status=LifeStatus.DEAD,
            )
        else:
            next_body = copy_body(
                body,
                hunger=hunger,
                thirst=thirst,
                fatigue=fatigue,
                health=Health(resulting_health),
            )
        bodies[body_id] = next_body
        bodies_changed = True
        semantic_mutation = True
        needs_ordinal = family_ordinals[SystemEffectFamily.COMBINED_NEEDS]
        family_ordinals[SystemEffectFamily.COMBINED_NEEDS] = needs_ordinal + 1
        pending.append(
            _pending_system(
                effect_family=SystemEffectFamily.COMBINED_NEEDS,
                entity_id=body_id,
                family_ordinal=needs_ordinal,
                details=NeedsApplied(
                    body_id=body_id,
                    resulting_hunger=hunger.value,
                    resulting_thirst=thirst.value,
                    resulting_fatigue=fatigue.value,
                    health_delta=health_delta,
                    resulting_health=next_body.health.value,
                ),
                origin_location_id=body.location_id,
            )
        )
        if died_from_needs:
            death_ordinal = family_ordinals[SystemEffectFamily.COMBINED_NEEDS]
            family_ordinals[SystemEffectFamily.COMBINED_NEEDS] = death_ordinal + 1
            pending.append(
                _pending_system(
                    effect_family=SystemEffectFamily.COMBINED_NEEDS,
                    entity_id=body_id,
                    family_ordinal=death_ordinal,
                    details=Died(
                        body_id=body_id,
                        death_cause=DeathCause.COMBINED_NEEDS,
                    ),
                    origin_location_id=body.location_id,
                )
            )
            continue

        weather_offsets = rules.weather_temperature_offset
        assert weather_offsets is not None
        ambient = round_physical(
            location.base_temperature.value
            + weather_offsets[weather.condition]
            + phase_offset
        )
        shelter = shelter_factor_for(
            working, body.location_id, location.shelter_factor.value
        )
        temperature = TemperatureCelsius(
            round_physical(
                next_body.temperature.value
                + rules.temperature_lerp_factor
                * (ambient - next_body.temperature.value)
                * (1.0 - shelter)
            )
        )
        exposure_damage = 0.0
        if (
            temperature.value < rules.exposure_low_celsius
            or temperature.value > rules.exposure_high_celsius
        ):
            exposure_damage = rules.exposure_damage
        exposed_health = clamp_need(
            round_physical(next_body.health.value - exposure_damage)
        )
        exposure_health_delta = round_physical(exposed_health - next_body.health.value)
        died_from_exposure = exposed_health <= 0.0
        if died_from_exposure:
            exposed_body = copy_body(
                next_body,
                temperature=temperature,
                health=Health(0.0),
                life_status=LifeStatus.DEAD,
            )
        else:
            exposed_body = copy_body(
                next_body,
                temperature=temperature,
                health=Health(exposed_health),
            )
        bodies[body_id] = exposed_body
        exposure_ordinal = family_ordinals[SystemEffectFamily.EXPOSURE]
        family_ordinals[SystemEffectFamily.EXPOSURE] = exposure_ordinal + 1
        pending.append(
            _pending_system(
                effect_family=SystemEffectFamily.EXPOSURE,
                entity_id=body_id,
                family_ordinal=exposure_ordinal,
                details=ExposureApplied(
                    body_id=body_id,
                    ambient_celsius=ambient,
                    resulting_temperature=temperature.value,
                    health_delta=exposure_health_delta,
                    resulting_health=exposed_body.health.value,
                ),
                origin_location_id=body.location_id,
            )
        )
        if died_from_exposure:
            death_ordinal = family_ordinals[SystemEffectFamily.EXPOSURE]
            family_ordinals[SystemEffectFamily.EXPOSURE] = death_ordinal + 1
            pending.append(
                _pending_system(
                    effect_family=SystemEffectFamily.EXPOSURE,
                    entity_id=body_id,
                    family_ordinal=death_ordinal,
                    details=Died(
                        body_id=body_id,
                        death_cause=DeathCause.EXPOSURE,
                    ),
                    origin_location_id=body.location_id,
                )
            )

    if bodies_changed:
        working = rebuild_world_state(working, bodies=bodies)

    return PendingSystemStep(
        working_state=working,
        semantic_mutation=semantic_mutation,
        pending_details=tuple(pending),
    )
