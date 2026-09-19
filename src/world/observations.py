"""Deeply immutable observations delivered to agents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from world._freeze import freeze_mapping, require_non_empty
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    Location,
    PhysicalRules,
    Resource,
    Weather,
    default_physical_rules,
)
from world.values import DayPhase, WeatherCondition


def detached_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a deeply immutable copy detached from the caller's containers."""
    return freeze_mapping(value)


def _copy_models(
    name: str, values: Sequence[object], *, model_type: type
) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for value in copied:
        if type(value) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
    return copied


class CoarseHealth(StrEnum):
    """Limited health band exposed for other visible bodies."""

    DEAD = "dead"
    CRITICAL = "critical"
    INJURED = "injured"
    STABLE = "stable"


def coarse_health_for(body: AgentBody) -> CoarseHealth:
    """Map authoritative physiology to a coarse visible health band."""
    if type(body) is not AgentBody:
        raise TypeError("coarse_health_for requires AgentBody")
    if body.life_status is LifeStatus.DEAD or body.health.value <= 0.0:
        return CoarseHealth.DEAD
    if body.health.value <= 25.0:
        return CoarseHealth.CRITICAL
    if body.health.value <= 75.0:
        return CoarseHealth.INJURED
    return CoarseHealth.STABLE


@dataclass(frozen=True, slots=True)
class VisibleExit:
    """Adjacent destination identity and name only."""

    destination_id: EntityId
    name: str

    def __post_init__(self) -> None:
        if type(self.destination_id) is not EntityId:
            raise TypeError("VisibleExit.destination_id must be EntityId")
        require_non_empty("VisibleExit.name", self.name)


@dataclass(frozen=True, slots=True)
class VisibleBody:
    """Other-body projection without inventory or exact physiology."""

    entity_id: EntityId
    life_status: LifeStatus
    coarse_health: CoarseHealth

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("VisibleBody.entity_id must be EntityId")
        if type(self.life_status) is not LifeStatus:
            raise TypeError("VisibleBody.life_status must be LifeStatus")
        if type(self.coarse_health) is not CoarseHealth:
            raise TypeError("VisibleBody.coarse_health must be CoarseHealth")
        if (
            self.life_status is LifeStatus.DEAD
            and self.coarse_health is not CoarseHealth.DEAD
        ):
            raise ValueError("dead VisibleBody requires CoarseHealth.DEAD")
        if (
            self.life_status is LifeStatus.ALIVE
            and self.coarse_health is CoarseHealth.DEAD
        ):
            raise ValueError("living VisibleBody cannot be CoarseHealth.DEAD")


@dataclass(frozen=True, slots=True)
class ObservationContext:
    """World-owned perception inputs derived from tick and physical rules."""

    tick: int
    physical_rules: PhysicalRules = field(default_factory=default_physical_rules)

    def __post_init__(self) -> None:
        if isinstance(self.tick, bool) or type(self.tick) is not int or self.tick < 0:
            raise ValueError("ObservationContext.tick must be a non-negative integer")
        if type(self.physical_rules) is not PhysicalRules:
            raise TypeError("ObservationContext.physical_rules must be PhysicalRules")

    @property
    def hour(self) -> int:
        return self.physical_rules.hour_for_tick(self.tick)

    @property
    def day_phase(self) -> DayPhase:
        return self.physical_rules.day_phase_for_tick(self.tick)


@dataclass(frozen=True, slots=True)
class Observation:
    """Typed partial projection. Nested values are detached from the source."""

    world_id: WorldId
    observer_id: EntityId
    revision: WorldRevision
    self_body: AgentBody | None = None
    locations: Sequence[Location] = field(default_factory=tuple)
    items: Sequence[Item] = field(default_factory=tuple)
    resources: Sequence[Resource] = field(default_factory=tuple)
    weather: Sequence[Weather] = field(default_factory=tuple)
    exits: Sequence[VisibleExit] = field(default_factory=tuple)
    visible_bodies: Sequence[VisibleBody] = field(default_factory=tuple)
    hour: int | None = None
    day_phase: DayPhase | None = None
    visibility: float | None = None
    weather_condition: WeatherCondition | None = None

    def __post_init__(self) -> None:
        if type(self.world_id) is not WorldId:
            raise TypeError("Observation.world_id must be WorldId")
        if type(self.observer_id) is not EntityId:
            raise TypeError("Observation.observer_id must be EntityId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("Observation.revision must be WorldRevision")
        if self.self_body is not None and type(self.self_body) is not AgentBody:
            raise TypeError("Observation.self_body must be AgentBody or None")
        object.__setattr__(
            self,
            "locations",
            _copy_models("Observation.locations", self.locations, model_type=Location),
        )
        object.__setattr__(
            self,
            "items",
            _copy_models("Observation.items", self.items, model_type=Item),
        )
        object.__setattr__(
            self,
            "resources",
            _copy_models(
                "Observation.resources", self.resources, model_type=Resource
            ),
        )
        object.__setattr__(
            self,
            "weather",
            _copy_models("Observation.weather", self.weather, model_type=Weather),
        )
        object.__setattr__(
            self,
            "exits",
            _copy_models("Observation.exits", self.exits, model_type=VisibleExit),
        )
        object.__setattr__(
            self,
            "visible_bodies",
            _copy_models(
                "Observation.visible_bodies",
                self.visible_bodies,
                model_type=VisibleBody,
            ),
        )
        if self.hour is not None:
            if isinstance(self.hour, bool) or type(self.hour) is not int:
                raise TypeError("Observation.hour must be int or None")
            if self.hour < 0:
                raise ValueError("Observation.hour must be non-negative")
        if self.day_phase is not None and type(self.day_phase) is not DayPhase:
            raise TypeError("Observation.day_phase must be DayPhase or None")
        if self.visibility is not None:
            if isinstance(self.visibility, bool) or not isinstance(
                self.visibility, (int, float)
            ):
                raise TypeError("Observation.visibility must be float or None")
            number = float(self.visibility)
            if number < 0.0 or number > 1.0:
                raise ValueError("Observation.visibility must be in [0.0, 1.0]")
            object.__setattr__(
                self, "visibility", 0.0 if number == 0.0 else number
            )
        if (
            self.weather_condition is not None
            and type(self.weather_condition) is not WeatherCondition
        ):
            raise TypeError(
                "Observation.weather_condition must be WeatherCondition or None"
            )
        if self.self_body is not None and self.self_body.entity_id != self.observer_id:
            raise ValueError("Observation.self_body must match observer_id")
