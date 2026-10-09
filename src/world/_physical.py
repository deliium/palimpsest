"""Pure autonomous physical close-of-tick step.

RNG-free. Simulation pre-resolves weather draws and supplies deterministic
system cause IDs before finalization. Corpse custody logs only when that
channel is on.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from world._production import shelter_factor_for
from world._state import ActiveHazard, WorldState, rebuild_world_state
from world.effects import (
    DeathCause,
    ResolvedSystemEffects,
    SystemEffectFamily,
)
from world.environment import (
    EnvironmentalDynamicsSpec,
    temperature_band,
)
from world.events import (
    CorpseCustodyOpened,
    Died,
    EnvironmentalHazardEnded,
    EnvironmentalHazardStarted,
    EventDetails,
    ExposureApplied,
    NeedsApplied,
    OccurrenceContext,
    ResourceRegenerated,
    SeasonChanged,
    TemperatureBandChanged,
    WeatherChanged,
    build_occurrence_context,
    node_quantity_witness,
    require_event_details,
)
from world.identifiers import EntityId, require_exact_nonneg_int
from world.models import (
    AgentBody,
    LifeStatus,
    Location,
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
    WeatherCondition,
    clamp_need,
    round_physical,
)

_LOG = logging.getLogger("world.physical")

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


def _append_corpse_custody(
    pending: list[PendingSystemDetail],
    *,
    body: AgentBody,
    active: bool,
    death_cause: DeathCause,
    effect_family: SystemEffectFamily,
    family_ordinals: dict[SystemEffectFamily, int],
) -> None:
    if not active:
        return
    ordinal = family_ordinals[effect_family]
    family_ordinals[effect_family] = ordinal + 1
    item_ids = tuple(body.inventory)
    pending.append(
        _pending_system(
            effect_family=effect_family,
            entity_id=body.entity_id,
            family_ordinal=ordinal,
            details=CorpseCustodyOpened(
                body_id=body.entity_id,
                location_id=body.location_id,
                item_ids=item_ids,
            ),
            origin_location_id=body.location_id,
        )
    )
    _LOG.info(
        "corpse_custody_opened body_id=%s item_count=%s",
        body.entity_id.value,
        len(item_ids),
    )
    _LOG.debug(
        "corpse_custody_opened_cause death_cause=%s",
        death_cause.value,
    )


def apply_autonomous_physical_step(
    *,
    state: WorldState,
    rules: PhysicalRules,
    tick: int,
    hour: int,
    day_phase: DayPhase,
    resolved: ResolvedSystemEffects | None = None,
    environmental_dynamics: EnvironmentalDynamicsSpec | None = None,
    metabolism_fatigue_by_entity: Mapping[EntityId, float] | None = None,
    dependency_hunger_extra_by_entity: Mapping[EntityId, float] | None = None,
    dependency_thirst_extra_by_entity: Mapping[EntityId, float] | None = None,
    dependency_fatigue_extra_by_entity: Mapping[EntityId, float] | None = None,
    dependency_health_damage_by_entity: Mapping[EntityId, float] | None = None,
    possession_succession_active: bool = False,
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
    if type(possession_succession_active) is not bool:
        raise TypeError("possession_succession_active must be bool")
    if environmental_dynamics is None:
        spec = None
    elif type(environmental_dynamics) is EnvironmentalDynamicsSpec:
        spec = environmental_dynamics
    else:
        raise TypeError(
            "environmental_dynamics must be EnvironmentalDynamicsSpec or None"
        )

    working = state
    semantic_mutation = False
    pending: list[PendingSystemDetail] = []
    family_ordinals: dict[SystemEffectFamily, int] = {
        family: 0 for family in SystemEffectFamily
    }

    prior_conditions = (
        {
            location_id: working.weather[location_id].condition
            for location_id in working.locations
        }
        if spec is not None
        else {}
    )
    if spec is not None and spec.transitions_at(tick_value) and working.locations:
        lowest = min(working.locations, key=lambda value: value.value)
        ordinal = family_ordinals[SystemEffectFamily.SEASON]
        family_ordinals[SystemEffectFamily.SEASON] = ordinal + 1
        pending.append(
            _pending_system(
                effect_family=SystemEffectFamily.SEASON,
                entity_id=lowest,
                family_ordinal=ordinal,
                details=SeasonChanged(season=spec.season_at(tick_value)),
                origin_location_id=lowest,
            )
        )
        semantic_mutation = True

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

    if spec is not None:
        current_season = spec.season_at(tick_value)
        previous_season = (
            spec.season_at(tick_value - 1) if tick_value > 0 else current_season
        )
        phase_offsets = rules.phase_temperature_offset
        assert phase_offsets is not None
        phase_offset = phase_offsets[day_phase]
        for location_id in sorted(working.locations, key=lambda value: value.value):
            location = working.locations[location_id]
            before = _ambient(
                location,
                prior_conditions[location_id],
                phase_offset,
                spec.offset_for(previous_season),
                rules,
            )
            after = _ambient(
                location,
                working.weather[location_id].condition,
                phase_offset,
                spec.offset_for(current_season),
                rules,
            )
            before_band = temperature_band(before)
            after_band = temperature_band(after)
            if before_band is after_band:
                continue
            ordinal = family_ordinals[SystemEffectFamily.TEMPERATURE_BAND]
            family_ordinals[SystemEffectFamily.TEMPERATURE_BAND] = ordinal + 1
            pending.append(
                _pending_system(
                    effect_family=SystemEffectFamily.TEMPERATURE_BAND,
                    entity_id=location_id,
                    family_ordinal=ordinal,
                    details=TemperatureBandChanged(
                        location_id=location_id,
                        band=after_band,
                    ),
                    origin_location_id=location_id,
                )
            )
            semantic_mutation = True

    resources = dict(working.resources)
    resources_changed = False
    for resource_id in sorted(resources, key=lambda value: value.value):
        resource = resources[resource_id]
        rate = resource.regeneration_per_tick
        if spec is not None:
            season = spec.season_at(tick_value)
            try:
                multiplier = spec.multiplier_for(resource.kind, season)
            except ValueError as exc:
                if "yield_undefined" in str(exc):
                    raise ValueError("yield_undefined") from exc
                raise
            rate = round_physical(resource.regeneration_per_tick * multiplier)
            if spec.shortage_suppresses(resource.kind, tick_value):
                rate = 0.0
        if rate == 0.0:
            continue
        uncapped = round_physical(resource.quantity + rate)
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
        if spec is not None:
            witness = node_quantity_witness(
                resource_id, resource.quantity, resulting
            )
            if witness is not None:
                node_ordinal = family_ordinals[SystemEffectFamily.RESOURCE_NODE]
                family_ordinals[SystemEffectFamily.RESOURCE_NODE] = node_ordinal + 1
                pending.append(
                    _pending_system(
                        effect_family=SystemEffectFamily.RESOURCE_NODE,
                        entity_id=resource_id,
                        family_ordinal=node_ordinal,
                        details=witness,
                        origin_location_id=resource.location_id,
                    )
                )
    if resources_changed:
        working = rebuild_world_state(working, resources=resources)

    if spec is not None:
        working, started = _start_hazards(
            working,
            spec,
            tick_value,
            day_phase,
            rules,
            family_ordinals,
        )
        pending.extend(started)
        if started:
            semantic_mutation = True

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
            clamp_need(
                round_physical(
                    body.hunger.value
                    + rules.metabolism_hunger
                    + float(
                        (dependency_hunger_extra_by_entity or {}).get(body.entity_id, 0.0)
                    )
                )
            )
        )
        thirst = Thirst(
            clamp_need(
                round_physical(
                    body.thirst.value
                    + rules.metabolism_thirst
                    + float(
                        (dependency_thirst_extra_by_entity or {}).get(body.entity_id, 0.0)
                    )
                )
            )
        )
        fatigue_gain = rules.metabolism_fatigue
        if metabolism_fatigue_by_entity is not None:
            fatigue_gain = fatigue_gain * float(
                metabolism_fatigue_by_entity.get(body.entity_id, 1.0)
            )
        fatigue_gain = fatigue_gain + float(
            (dependency_fatigue_extra_by_entity or {}).get(body.entity_id, 0.0)
        )
        fatigue = Fatigue(
            clamp_need(round_physical(body.fatigue.value + fatigue_gain))
        )
        damage = 0.0
        if hunger.value >= 100.0:
            damage += rules.hunger_damage
        if thirst.value >= 100.0:
            damage += rules.thirst_damage
        if fatigue.value >= 100.0:
            damage += rules.fatigue_damage
        damage += float(
            (dependency_health_damage_by_entity or {}).get(body.entity_id, 0.0)
        )
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
            _append_corpse_custody(
                pending,
                body=next_body,
                active=possession_succession_active,
                death_cause=DeathCause.COMBINED_NEEDS,
                effect_family=SystemEffectFamily.COMBINED_NEEDS,
                family_ordinals=family_ordinals,
            )
            continue

        weather_offsets = rules.weather_temperature_offset
        assert weather_offsets is not None
        if spec is None:
            ambient = round_physical(
                location.base_temperature.value
                + weather_offsets[weather.condition]
                + phase_offset
            )
        else:
            ambient = round_physical(
                location.base_temperature.value
                + weather_offsets[weather.condition]
                + phase_offset
                + spec.offset_for(spec.season_at(tick_value))
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
        if spec is not None and rules.exposure_damage != 0.0:
            exposure_damage += _hazard_extra(working, spec, body.location_id)
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
            _append_corpse_custody(
                pending,
                body=exposed_body,
                active=possession_succession_active,
                death_cause=DeathCause.EXPOSURE,
                effect_family=SystemEffectFamily.EXPOSURE,
                family_ordinals=family_ordinals,
            )

    if possession_succession_active:
        died_ids = {
            detail.details.body_id
            for detail in pending
            if type(detail.details) is Died
        }
        for body_id, body in bodies.items():
            prior = state.bodies.get(body_id)
            became_dead = body.life_status is LifeStatus.DEAD and (
                prior is None or prior.life_status is not LifeStatus.DEAD
            )
            if became_dead and body_id not in died_ids:
                _LOG.error(
                    "death_without_died body_id=%s reason_code=death_without_died",
                    body_id.value,
                )

    if bodies_changed:
        working = rebuild_world_state(working, bodies=bodies)

    if spec is not None:
        working, ended = _end_hazards(working, tick_value, family_ordinals)
        pending.extend(ended)
        if ended:
            semantic_mutation = True

    return PendingSystemStep(
        working_state=working,
        semantic_mutation=semantic_mutation,
        pending_details=tuple(pending),
    )


def _ambient(
    location: Location,
    condition: WeatherCondition,
    phase_offset: float,
    season_offset: float,
    rules: PhysicalRules,
) -> float:
    if type(location) is not Location:
        raise TypeError("location must be Location")
    if type(condition) is not WeatherCondition:
        raise TypeError("condition must be WeatherCondition")
    weather_offsets = rules.weather_temperature_offset
    assert weather_offsets is not None
    return round_physical(
        location.base_temperature.value
        + weather_offsets[condition]
        + phase_offset
        + season_offset
    )


def _hazard_extra(
    state: WorldState,
    spec: EnvironmentalDynamicsSpec,
    location_id: EntityId,
) -> float:
    extras = {rule.kind: rule.exposure_extra for rule in spec.hazard_rules}
    total = 0.0
    for hazard in state.active_hazards:
        if hazard.location_id == location_id and hazard.kind in extras:
            total += extras[hazard.kind]
    return total


def _start_hazards(
    state: WorldState,
    spec: EnvironmentalDynamicsSpec,
    tick: int,
    day_phase: DayPhase,
    rules: PhysicalRules,
    family_ordinals: dict[SystemEffectFamily, int],
) -> tuple[WorldState, list[PendingSystemDetail]]:
    season = spec.season_at(tick)
    phase_offsets = rules.phase_temperature_offset
    assert phase_offsets is not None
    phase_offset = phase_offsets[day_phase]
    active = {
        (hazard.location_id, hazard.kind): hazard for hazard in state.active_hazards
    }
    started: list[PendingSystemDetail] = []
    for location_id in sorted(state.locations, key=lambda value: value.value):
        location = state.locations[location_id]
        condition = state.weather[location_id].condition
        band = temperature_band(
            _ambient(
                location,
                condition,
                phase_offset,
                spec.offset_for(season),
                rules,
            )
        )
        for rule in spec.matching_rules(season, condition, band):
            key = (location_id, rule.kind)
            if key in active:
                continue
            active[key] = ActiveHazard(
                location_id,
                rule.kind,
                tick,
                rule.duration_ticks,
            )
            ordinal = family_ordinals[SystemEffectFamily.HAZARD]
            family_ordinals[SystemEffectFamily.HAZARD] = ordinal + 1
            started.append(
                _pending_system(
                    effect_family=SystemEffectFamily.HAZARD,
                    entity_id=location_id,
                    family_ordinal=ordinal,
                    details=EnvironmentalHazardStarted(
                        location_id,
                        rule.kind,
                        rule.duration_ticks,
                        rule.duration_ticks,
                    ),
                    origin_location_id=location_id,
                )
            )
    if not started:
        return state, []
    return (
        rebuild_world_state(state, active_hazards=tuple(active.values())),
        started,
    )


def _end_hazards(
    state: WorldState,
    tick: int,
    family_ordinals: dict[SystemEffectFamily, int],
) -> tuple[WorldState, list[PendingSystemDetail]]:
    staying: list[ActiveHazard] = []
    ending: list[ActiveHazard] = []
    for hazard in state.active_hazards:
        closing = hazard.start_tick + hazard.duration_ticks - 1
        if tick == closing:
            ending.append(hazard)
        else:
            staying.append(hazard)
    if not ending:
        return state, []
    ended: list[PendingSystemDetail] = []
    for hazard in sorted(
        ending, key=lambda item: (item.location_id.value, item.kind.value)
    ):
        ordinal = family_ordinals[SystemEffectFamily.HAZARD]
        family_ordinals[SystemEffectFamily.HAZARD] = ordinal + 1
        ended.append(
            _pending_system(
                effect_family=SystemEffectFamily.HAZARD,
                entity_id=hazard.location_id,
                family_ordinal=ordinal,
                details=EnvironmentalHazardEnded(
                    hazard.location_id,
                    hazard.kind,
                    0,
                ),
                origin_location_id=hazard.location_id,
            )
        )
    return rebuild_world_state(state, active_hazards=tuple(staying)), ended
