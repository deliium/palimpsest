"""Immutable objective world entity models and physical agent state."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from world._freeze import require_non_empty, require_ordered_unique
from world.identifiers import EntityId
from world.values import (
    BodyCapacity,
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
    clamp_unit_interval,
)

PHYSICAL_RULES_VERSION: Final[str] = "physical-v1"
NON_LETHAL_PHYSICAL_RULES_VERSION: Final[str] = "physical-nonlethal-v1"
# Closed DeathCause values covered by non-lethal mapping (world.effects.DeathCause).
_NON_LETHAL_COVERED_DEATH_CAUSES: Final[frozenset[str]] = frozenset(
    {"attack", "combined_needs", "exposure"}
)


def _canonical_finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite float")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite float")
    return 0.0 if number == 0.0 else number


def _finite_non_negative(name: str, value: object) -> float:
    number = _canonical_finite_float(name, value)
    if number < 0.0:
        raise ValueError(f"{name} must be a finite non-negative float")
    return number


def _exact_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise ValueError(f"{name} must be a positive integer")
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _exact_nonneg_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise ValueError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


class LifeStatus(StrEnum):
    ALIVE = "alive"
    DEAD = "dead"


@dataclass(frozen=True, slots=True)
class Location:
    """Connected-graph node with occupancy, content, and environment factors."""

    entity_id: EntityId
    name: str
    adjacent: Sequence[EntityId]
    body_capacity: BodyCapacity
    item_capacity: ItemCapacity
    base_temperature: TemperatureCelsius
    shelter_factor: UnitInterval
    visibility_factor: UnitInterval

    def __post_init__(self) -> None:
        require_non_empty("Location.name", self.name)
        if type(self.body_capacity) is not BodyCapacity:
            raise TypeError("Location.body_capacity must be BodyCapacity")
        if type(self.item_capacity) is not ItemCapacity:
            raise TypeError("Location.item_capacity must be ItemCapacity")
        if type(self.base_temperature) is not TemperatureCelsius:
            raise TypeError("Location.base_temperature must be TemperatureCelsius")
        if type(self.shelter_factor) is not UnitInterval:
            raise TypeError("Location.shelter_factor must be UnitInterval")
        if type(self.visibility_factor) is not UnitInterval:
            raise TypeError("Location.visibility_factor must be UnitInterval")
        adjacent = require_ordered_unique(
            "Location.adjacent", self.adjacent, item_type=EntityId
        )
        if self.entity_id in adjacent:
            raise ValueError("Location.adjacent must not include self-edges")
        object.__setattr__(self, "adjacent", adjacent)


@dataclass(frozen=True, slots=True)
class Item:
    """Physical item with exactly one authoritative placement."""

    entity_id: EntityId
    name: str
    kind: ItemKind
    load: ItemLoad
    location_id: EntityId | None = None
    holder_id: EntityId | None = None

    def __post_init__(self) -> None:
        require_non_empty("Item.name", self.name)
        if type(self.kind) is not ItemKind:
            raise TypeError("Item.kind must be ItemKind")
        if type(self.load) is not ItemLoad:
            raise TypeError("Item.load must be ItemLoad")
        has_location = self.location_id is not None
        has_holder = self.holder_id is not None
        if has_location == has_holder:
            raise ValueError("Item must have exactly one of location_id or holder_id")
        if has_location and type(self.location_id) is not EntityId:
            raise TypeError("Item.location_id must be an EntityId")
        if has_holder and type(self.holder_id) is not EntityId:
            raise TypeError("Item.holder_id must be an EntityId")


@dataclass(frozen=True, slots=True)
class Resource:
    """Location-bound resource node with quantity bounds and regeneration."""

    entity_id: EntityId
    name: str
    kind: ResourceKind
    location_id: EntityId
    quantity: float
    maximum_quantity: float
    regeneration_per_tick: float
    unit: str = "units"

    def __post_init__(self) -> None:
        require_non_empty("Resource.name", self.name)
        require_non_empty("Resource.unit", self.unit)
        if type(self.kind) is not ResourceKind:
            raise TypeError("Resource.kind must be ResourceKind")
        if type(self.location_id) is not EntityId:
            raise TypeError("Resource.location_id must be an EntityId")
        quantity = _finite_non_negative("Resource.quantity", self.quantity)
        maximum = _finite_non_negative(
            "Resource.maximum_quantity", self.maximum_quantity
        )
        regeneration = _finite_non_negative(
            "Resource.regeneration_per_tick", self.regeneration_per_tick
        )
        if quantity > maximum:
            raise ValueError("Resource.quantity must be <= maximum_quantity")
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "maximum_quantity", maximum)
        object.__setattr__(self, "regeneration_per_tick", regeneration)


@dataclass(frozen=True, slots=True)
class Weather:
    """Location-bound weather condition. Ambient temperature is derived."""

    location_id: EntityId
    condition: WeatherCondition

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("Weather.location_id must be an EntityId")
        if type(self.condition) is not WeatherCondition:
            raise TypeError("Weather.condition must be WeatherCondition")


@dataclass(frozen=True, slots=True)
class AgentBody:
    """Objective physical state. Contains no AgentId."""

    entity_id: EntityId
    location_id: EntityId
    health: Health
    hunger: Hunger
    thirst: Thirst
    fatigue: Fatigue
    temperature: TemperatureCelsius
    inventory: Sequence[EntityId]
    life_status: LifeStatus
    carry_capacity: CarryCapacity

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("AgentBody.location_id must be an EntityId")
        for field_name, expected, value in (
            ("health", Health, self.health),
            ("hunger", Hunger, self.hunger),
            ("thirst", Thirst, self.thirst),
            ("fatigue", Fatigue, self.fatigue),
            ("temperature", TemperatureCelsius, self.temperature),
            ("carry_capacity", CarryCapacity, self.carry_capacity),
        ):
            if type(value) is not expected:
                raise TypeError(f"AgentBody.{field_name} must be {expected.__name__}")
        if type(self.life_status) is not LifeStatus:
            raise TypeError("AgentBody.life_status must be LifeStatus")
        inventory = require_ordered_unique(
            "AgentBody.inventory", self.inventory, item_type=EntityId
        )
        object.__setattr__(self, "inventory", inventory)
        if self.life_status is LifeStatus.ALIVE and self.health.value <= 0.0:
            raise ValueError("LifeStatus.ALIVE requires positive health")
        if self.life_status is LifeStatus.DEAD and self.health.value != 0.0:
            raise ValueError("LifeStatus.DEAD requires zero health")


def _probability(name: str, value: object) -> float:
    number = _canonical_finite_float(name, value)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0]")
    return number


def _require_weather_matrix(
    name: str, value: Mapping[WeatherCondition, Mapping[WeatherCondition, float]]
) -> dict[WeatherCondition, dict[WeatherCondition, float]]:
    if type(value) is not dict and not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    required = tuple(WeatherCondition)
    matrix: dict[WeatherCondition, dict[WeatherCondition, float]] = {}
    if set(value) != set(required):
        raise ValueError(f"{name} must define every WeatherCondition row")
    for source in required:
        row = value[source]
        if set(row) != set(required):
            raise ValueError(f"{name}[{source.value}] must define every column")
        frozen_row: dict[WeatherCondition, float] = {}
        total = 0.0
        for target in required:
            probability = _probability(
                f"{name}[{source.value}][{target.value}]", row[target]
            )
            frozen_row[target] = probability
            total += probability
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"{name}[{source.value}] probabilities must sum to 1.0")
        matrix[source] = frozen_row
    return matrix


@dataclass(frozen=True, slots=True)
class PhysicalRules:
    """Versioned, replay-significant physical constants for one simulation run."""

    version: str = PHYSICAL_RULES_VERSION
    hours_per_day: int = 24
    day_start_hour: int = 6
    day_end_hour: int = 17
    metabolism_hunger: float = 2.0
    metabolism_thirst: float = 3.0
    metabolism_fatigue: float = 1.0
    hunger_damage: float = 2.0
    thirst_damage: float = 5.0
    fatigue_damage: float = 1.0
    exposure_damage: float = 5.0
    exposure_low_celsius: float = 35.0
    exposure_high_celsius: float = 39.0
    temperature_lerp_factor: float = 0.25
    move_fatigue: float = 5.0
    flee_fatigue: float = 10.0
    help_fatigue: float = 5.0
    sleep_fatigue_recovery: float = 30.0
    eat_hunger_relief: float = 30.0
    drink_thirst_relief: float = 40.0
    help_health_gain: float = 10.0
    attack_hit_probability: float = 0.75
    attack_damage_min: int = 10
    attack_damage_max_exclusive: int = 21
    flee_success_probability: float = 0.80
    search_base_probability: float = 0.25
    search_visibility_weight: float = 0.75
    resource_extraction_amount: float = 1.0
    weather_period_ticks: int = 6
    day_visibility_factor: float = 1.0
    night_visibility_factor: float = 0.5
    weather_visibility: Mapping[WeatherCondition, float] | None = None
    weather_temperature_offset: Mapping[WeatherCondition, float] | None = None
    phase_temperature_offset: Mapping[DayPhase, float] | None = None
    weather_transitions: (
        Mapping[WeatherCondition, Mapping[WeatherCondition, float]] | None
    ) = None

    def __post_init__(self) -> None:
        require_non_empty("PhysicalRules.version", self.version)
        object.__setattr__(
            self,
            "hours_per_day",
            _exact_positive_int("PhysicalRules.hours_per_day", self.hours_per_day),
        )
        object.__setattr__(
            self,
            "day_start_hour",
            _exact_nonneg_int("PhysicalRules.day_start_hour", self.day_start_hour),
        )
        object.__setattr__(
            self,
            "day_end_hour",
            _exact_nonneg_int("PhysicalRules.day_end_hour", self.day_end_hour),
        )
        if self.day_start_hour >= self.hours_per_day:
            raise ValueError("PhysicalRules.day_start_hour must be < hours_per_day")
        if self.day_end_hour >= self.hours_per_day:
            raise ValueError("PhysicalRules.day_end_hour must be < hours_per_day")
        if self.day_start_hour > self.day_end_hour:
            raise ValueError("PhysicalRules.day_start_hour must be <= day_end_hour")
        for field_name in (
            "metabolism_hunger",
            "metabolism_thirst",
            "metabolism_fatigue",
            "hunger_damage",
            "thirst_damage",
            "fatigue_damage",
            "exposure_damage",
            "move_fatigue",
            "flee_fatigue",
            "help_fatigue",
            "sleep_fatigue_recovery",
            "eat_hunger_relief",
            "drink_thirst_relief",
            "help_health_gain",
            "resource_extraction_amount",
            "search_base_probability",
            "search_visibility_weight",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite_non_negative(
                    f"PhysicalRules.{field_name}", getattr(self, field_name)
                ),
            )
        object.__setattr__(
            self,
            "temperature_lerp_factor",
            _probability(
                "PhysicalRules.temperature_lerp_factor", self.temperature_lerp_factor
            ),
        )
        object.__setattr__(
            self,
            "attack_hit_probability",
            _probability(
                "PhysicalRules.attack_hit_probability", self.attack_hit_probability
            ),
        )
        object.__setattr__(
            self,
            "flee_success_probability",
            _probability(
                "PhysicalRules.flee_success_probability",
                self.flee_success_probability,
            ),
        )
        object.__setattr__(
            self,
            "day_visibility_factor",
            _probability(
                "PhysicalRules.day_visibility_factor", self.day_visibility_factor
            ),
        )
        object.__setattr__(
            self,
            "night_visibility_factor",
            _probability(
                "PhysicalRules.night_visibility_factor", self.night_visibility_factor
            ),
        )
        object.__setattr__(
            self,
            "exposure_low_celsius",
            _canonical_finite_float(
                "PhysicalRules.exposure_low_celsius", self.exposure_low_celsius
            ),
        )
        object.__setattr__(
            self,
            "exposure_high_celsius",
            _canonical_finite_float(
                "PhysicalRules.exposure_high_celsius", self.exposure_high_celsius
            ),
        )
        if self.exposure_low_celsius > self.exposure_high_celsius:
            raise ValueError(
                "PhysicalRules.exposure_low_celsius must be <= exposure_high_celsius"
            )
        object.__setattr__(
            self,
            "attack_damage_min",
            _exact_nonneg_int(
                "PhysicalRules.attack_damage_min", self.attack_damage_min
            ),
        )
        object.__setattr__(
            self,
            "attack_damage_max_exclusive",
            _exact_positive_int(
                "PhysicalRules.attack_damage_max_exclusive",
                self.attack_damage_max_exclusive,
            ),
        )
        if self.attack_damage_min >= self.attack_damage_max_exclusive:
            raise ValueError(
                "PhysicalRules.attack_damage_min must be < attack_damage_max_exclusive"
            )
        object.__setattr__(
            self,
            "weather_period_ticks",
            _exact_positive_int(
                "PhysicalRules.weather_period_ticks", self.weather_period_ticks
            ),
        )
        visibility = (
            dict(self.weather_visibility)
            if self.weather_visibility is not None
            else {
                WeatherCondition.CLEAR: 1.0,
                WeatherCondition.CLOUDY: 0.9,
                WeatherCondition.RAIN: 0.7,
                WeatherCondition.STORM: 0.5,
            }
        )
        if set(visibility) != set(WeatherCondition):
            raise ValueError(
                "PhysicalRules.weather_visibility must define every WeatherCondition"
            )
        object.__setattr__(
            self,
            "weather_visibility",
            MappingProxyType(
                {
                    condition: _probability(
                        f"PhysicalRules.weather_visibility[{condition.value}]",
                        visibility[condition],
                    )
                    for condition in WeatherCondition
                }
            ),
        )
        offsets = (
            dict(self.weather_temperature_offset)
            if self.weather_temperature_offset is not None
            else {
                WeatherCondition.CLEAR: 0.0,
                WeatherCondition.CLOUDY: -1.0,
                WeatherCondition.RAIN: -3.0,
                WeatherCondition.STORM: -5.0,
            }
        )
        if set(offsets) != set(WeatherCondition):
            raise ValueError(
                "PhysicalRules.weather_temperature_offset must define every "
                "WeatherCondition"
            )
        object.__setattr__(
            self,
            "weather_temperature_offset",
            MappingProxyType(
                {
                    condition: _canonical_finite_float(
                        f"PhysicalRules.weather_temperature_offset[{condition.value}]",
                        offsets[condition],
                    )
                    for condition in WeatherCondition
                }
            ),
        )
        phase_offsets = (
            dict(self.phase_temperature_offset)
            if self.phase_temperature_offset is not None
            else {DayPhase.DAY: 2.0, DayPhase.NIGHT: -2.0}
        )
        if set(phase_offsets) != set(DayPhase):
            raise ValueError(
                "PhysicalRules.phase_temperature_offset must define every DayPhase"
            )
        object.__setattr__(
            self,
            "phase_temperature_offset",
            MappingProxyType(
                {
                    phase: _canonical_finite_float(
                        f"PhysicalRules.phase_temperature_offset[{phase.value}]",
                        phase_offsets[phase],
                    )
                    for phase in DayPhase
                }
            ),
        )
        transitions = (
            self.weather_transitions
            if self.weather_transitions is not None
            else {
                WeatherCondition.CLEAR: {
                    WeatherCondition.CLEAR: 0.60,
                    WeatherCondition.CLOUDY: 0.30,
                    WeatherCondition.RAIN: 0.10,
                    WeatherCondition.STORM: 0.00,
                },
                WeatherCondition.CLOUDY: {
                    WeatherCondition.CLEAR: 0.30,
                    WeatherCondition.CLOUDY: 0.40,
                    WeatherCondition.RAIN: 0.25,
                    WeatherCondition.STORM: 0.05,
                },
                WeatherCondition.RAIN: {
                    WeatherCondition.CLEAR: 0.25,
                    WeatherCondition.CLOUDY: 0.35,
                    WeatherCondition.RAIN: 0.30,
                    WeatherCondition.STORM: 0.10,
                },
                WeatherCondition.STORM: {
                    WeatherCondition.CLEAR: 0.30,
                    WeatherCondition.CLOUDY: 0.30,
                    WeatherCondition.RAIN: 0.30,
                    WeatherCondition.STORM: 0.10,
                },
            }
        )
        object.__setattr__(
            self,
            "weather_transitions",
            MappingProxyType(
                {
                    source: MappingProxyType(row)
                    for source, row in _require_weather_matrix(
                        "PhysicalRules.weather_transitions", transitions
                    ).items()
                }
            ),
        )

    def hour_for_tick(self, tick: int) -> int:
        if isinstance(tick, bool) or type(tick) is not int or tick < 0:
            raise ValueError("tick must be a non-negative integer")
        return tick % self.hours_per_day

    def day_phase_for_hour(self, hour: int) -> DayPhase:
        if isinstance(hour, bool) or type(hour) is not int:
            raise ValueError("hour must be an integer")
        if hour < 0 or hour >= self.hours_per_day:
            raise ValueError("hour must be in [0, hours_per_day)")
        if self.day_start_hour <= hour <= self.day_end_hour:
            return DayPhase.DAY
        return DayPhase.NIGHT

    def day_phase_for_tick(self, tick: int) -> DayPhase:
        return self.day_phase_for_hour(self.hour_for_tick(tick))

    def effective_visibility(
        self,
        *,
        location_visibility: float,
        phase: DayPhase,
        condition: WeatherCondition,
    ) -> float:
        if type(phase) is not DayPhase:
            raise TypeError("phase must be DayPhase")
        if type(condition) is not WeatherCondition:
            raise TypeError("condition must be WeatherCondition")
        phase_factor = (
            self.day_visibility_factor
            if phase is DayPhase.DAY
            else self.night_visibility_factor
        )
        weather_visibility = self.weather_visibility
        assert weather_visibility is not None
        weather_factor = weather_visibility[condition]
        return clamp_unit_interval(location_visibility * phase_factor * weather_factor)


def default_physical_rules() -> PhysicalRules:
    """Return the canonical V1 physical ruleset used by new physical runs."""
    return PhysicalRules()


def non_lethal_physical_rules(*, base: PhysicalRules | None = None) -> PhysicalRules:
    """Return named non-lethal rules covering every classified death path.

    Preserves metabolism and action costs from ``base`` (or defaults) while
    zeroing starvation, dehydration, fatigue, exposure, and combat lethality.
    Rejects construction when ``DeathCause`` gains unclassified members so the
    mortality mapping cannot silently miss a new death path.
    """
    from world.effects import DeathCause

    classified = {cause.value for cause in DeathCause}
    if classified != set(_NON_LETHAL_COVERED_DEATH_CAUSES):
        uncovered = sorted(classified - set(_NON_LETHAL_COVERED_DEATH_CAUSES))
        raise ValueError(
            "non_lethal_physical_rules uncovered death causes "
            f"{uncovered!r} (code=mortality_mapping_incomplete)"
        )
    template = base if base is not None else PhysicalRules()
    if type(template) is not PhysicalRules:
        raise TypeError("non_lethal_physical_rules base must be PhysicalRules")
    return PhysicalRules(
        version=NON_LETHAL_PHYSICAL_RULES_VERSION,
        hours_per_day=template.hours_per_day,
        day_start_hour=template.day_start_hour,
        day_end_hour=template.day_end_hour,
        metabolism_hunger=template.metabolism_hunger,
        metabolism_thirst=template.metabolism_thirst,
        metabolism_fatigue=template.metabolism_fatigue,
        hunger_damage=0.0,
        thirst_damage=0.0,
        fatigue_damage=0.0,
        exposure_damage=0.0,
        exposure_low_celsius=template.exposure_low_celsius,
        exposure_high_celsius=template.exposure_high_celsius,
        temperature_lerp_factor=template.temperature_lerp_factor,
        move_fatigue=template.move_fatigue,
        flee_fatigue=template.flee_fatigue,
        help_fatigue=template.help_fatigue,
        sleep_fatigue_recovery=template.sleep_fatigue_recovery,
        eat_hunger_relief=template.eat_hunger_relief,
        drink_thirst_relief=template.drink_thirst_relief,
        help_health_gain=template.help_health_gain,
        attack_hit_probability=template.attack_hit_probability,
        attack_damage_min=0,
        attack_damage_max_exclusive=1,
        flee_success_probability=template.flee_success_probability,
        search_base_probability=template.search_base_probability,
        search_visibility_weight=template.search_visibility_weight,
        resource_extraction_amount=template.resource_extraction_amount,
        weather_period_ticks=template.weather_period_ticks,
        day_visibility_factor=template.day_visibility_factor,
        night_visibility_factor=template.night_visibility_factor,
        weather_visibility=template.weather_visibility,
        weather_temperature_offset=template.weather_temperature_offset,
        phase_temperature_offset=template.phase_temperature_offset,
        weather_transitions=template.weather_transitions,
    )


def canonical_physical_rules_bytes(rules: PhysicalRules) -> bytes:
    """Deterministic UTF-8 JSON for replay-significant rule constants."""
    if type(rules) is not PhysicalRules:
        raise TypeError("canonical_physical_rules_bytes requires PhysicalRules")
    weather_visibility = rules.weather_visibility
    weather_temperature_offset = rules.weather_temperature_offset
    phase_temperature_offset = rules.phase_temperature_offset
    weather_transitions = rules.weather_transitions
    assert weather_visibility is not None
    assert weather_temperature_offset is not None
    assert phase_temperature_offset is not None
    assert weather_transitions is not None
    payload = {
        "attack_damage_max_exclusive": rules.attack_damage_max_exclusive,
        "attack_damage_min": rules.attack_damage_min,
        "attack_hit_probability": rules.attack_hit_probability,
        "day_end_hour": rules.day_end_hour,
        "day_start_hour": rules.day_start_hour,
        "day_visibility_factor": rules.day_visibility_factor,
        "drink_thirst_relief": rules.drink_thirst_relief,
        "eat_hunger_relief": rules.eat_hunger_relief,
        "exposure_damage": rules.exposure_damage,
        "exposure_high_celsius": rules.exposure_high_celsius,
        "exposure_low_celsius": rules.exposure_low_celsius,
        "fatigue_damage": rules.fatigue_damage,
        "flee_fatigue": rules.flee_fatigue,
        "flee_success_probability": rules.flee_success_probability,
        "help_fatigue": rules.help_fatigue,
        "help_health_gain": rules.help_health_gain,
        "hours_per_day": rules.hours_per_day,
        "hunger_damage": rules.hunger_damage,
        "metabolism_fatigue": rules.metabolism_fatigue,
        "metabolism_hunger": rules.metabolism_hunger,
        "metabolism_thirst": rules.metabolism_thirst,
        "move_fatigue": rules.move_fatigue,
        "night_visibility_factor": rules.night_visibility_factor,
        "phase_temperature_offset": {
            phase.value: phase_temperature_offset[phase] for phase in DayPhase
        },
        "resource_extraction_amount": rules.resource_extraction_amount,
        "search_base_probability": rules.search_base_probability,
        "search_visibility_weight": rules.search_visibility_weight,
        "sleep_fatigue_recovery": rules.sleep_fatigue_recovery,
        "temperature_lerp_factor": rules.temperature_lerp_factor,
        "thirst_damage": rules.thirst_damage,
        "version": rules.version,
        "weather_period_ticks": rules.weather_period_ticks,
        "weather_temperature_offset": {
            condition.value: weather_temperature_offset[condition]
            for condition in WeatherCondition
        },
        "weather_transitions": {
            source.value: {
                target.value: weather_transitions[source][target]
                for target in WeatherCondition
            }
            for source in WeatherCondition
        },
        "weather_visibility": {
            condition.value: weather_visibility[condition]
            for condition in WeatherCondition
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def physical_rules_fingerprint(rules: PhysicalRules) -> str:
    """SHA-256 hex digest of canonical physical-rules bytes."""
    return hashlib.sha256(canonical_physical_rules_bytes(rules)).hexdigest()


def copy_location(location: Location) -> Location:
    """Return a detached Location preserving topology and environment fields."""
    if type(location) is not Location:
        raise TypeError("copy_location requires Location")
    return Location(
        entity_id=location.entity_id,
        name=location.name,
        adjacent=tuple(location.adjacent),
        body_capacity=location.body_capacity,
        item_capacity=location.item_capacity,
        base_temperature=location.base_temperature,
        shelter_factor=location.shelter_factor,
        visibility_factor=location.visibility_factor,
    )


def copy_item(
    item: Item,
    *,
    location_id: EntityId | object | None = ...,
    holder_id: EntityId | object | None = ...,
) -> Item:
    """Return a detached Item, optionally relocating placement."""
    if type(item) is not Item:
        raise TypeError("copy_item requires Item")
    next_location = item.location_id if location_id is ... else location_id
    next_holder = item.holder_id if holder_id is ... else holder_id
    return Item(
        entity_id=item.entity_id,
        name=item.name,
        kind=item.kind,
        load=item.load,
        location_id=next_location,  # type: ignore[arg-type]
        holder_id=next_holder,  # type: ignore[arg-type]
    )


def copy_resource(
    resource: Resource,
    *,
    quantity: float | object = ...,
) -> Resource:
    """Return a detached Resource, optionally updating quantity."""
    if type(resource) is not Resource:
        raise TypeError("copy_resource requires Resource")
    next_quantity = resource.quantity if quantity is ... else quantity
    return Resource(
        entity_id=resource.entity_id,
        name=resource.name,
        kind=resource.kind,
        location_id=resource.location_id,
        quantity=next_quantity,  # type: ignore[arg-type]
        maximum_quantity=resource.maximum_quantity,
        regeneration_per_tick=resource.regeneration_per_tick,
        unit=resource.unit,
    )


def copy_weather(
    weather: Weather,
    *,
    condition: WeatherCondition | object = ...,
) -> Weather:
    """Return a detached Weather value, optionally changing condition."""
    if type(weather) is not Weather:
        raise TypeError("copy_weather requires Weather")
    next_condition = weather.condition if condition is ... else condition
    return Weather(
        location_id=weather.location_id,
        condition=next_condition,  # type: ignore[arg-type]
    )


def copy_body(
    body: AgentBody,
    *,
    inventory: Sequence[EntityId] | object = ...,
    location_id: EntityId | object = ...,
    health: Health | object = ...,
    hunger: Hunger | object = ...,
    thirst: Thirst | object = ...,
    fatigue: Fatigue | object = ...,
    temperature: TemperatureCelsius | object = ...,
    life_status: LifeStatus | object = ...,
    carry_capacity: CarryCapacity | object = ...,
) -> AgentBody:
    """Return a detached AgentBody with selective field overrides."""
    if type(body) is not AgentBody:
        raise TypeError("copy_body requires AgentBody")
    return AgentBody(
        entity_id=body.entity_id,
        location_id=body.location_id if location_id is ... else location_id,  # type: ignore[arg-type]
        health=body.health if health is ... else health,  # type: ignore[arg-type]
        hunger=body.hunger if hunger is ... else hunger,  # type: ignore[arg-type]
        thirst=body.thirst if thirst is ... else thirst,  # type: ignore[arg-type]
        fatigue=body.fatigue if fatigue is ... else fatigue,  # type: ignore[arg-type]
        temperature=(
            body.temperature if temperature is ... else temperature  # type: ignore[arg-type]
        ),
        inventory=tuple(body.inventory) if inventory is ... else inventory,  # type: ignore[arg-type]
        life_status=(
            body.life_status if life_status is ... else life_status  # type: ignore[arg-type]
        ),
        carry_capacity=(
            body.carry_capacity if carry_capacity is ... else carry_capacity  # type: ignore[arg-type]
        ),
    )
