"""Immutable objective world entity models and physical agent state."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from world._freeze import require_non_empty, require_ordered_unique
from world.identifiers import EntityId
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst


def _finite_non_negative(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative float")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be a finite non-negative float")
    return 0.0 if number == 0.0 else number


class LifeStatus(StrEnum):
    ALIVE = "alive"
    DEAD = "dead"


@dataclass(frozen=True, slots=True)
class Location:
    entity_id: EntityId
    name: str

    def __post_init__(self) -> None:
        require_non_empty("Location.name", self.name)


@dataclass(frozen=True, slots=True)
class Item:
    """Physical item with exactly one authoritative placement."""

    entity_id: EntityId
    name: str
    location_id: EntityId | None = None
    holder_id: EntityId | None = None

    def __post_init__(self) -> None:
        require_non_empty("Item.name", self.name)
        has_location = self.location_id is not None
        has_holder = self.holder_id is not None
        if has_location == has_holder:
            raise ValueError(
                "Item must have exactly one of location_id or holder_id"
            )
        if has_location and type(self.location_id) is not EntityId:
            raise TypeError("Item.location_id must be an EntityId")
        if has_holder and type(self.holder_id) is not EntityId:
            raise TypeError("Item.holder_id must be an EntityId")


@dataclass(frozen=True, slots=True)
class Resource:
    entity_id: EntityId
    name: str
    location_id: EntityId
    quantity: float
    unit: str

    def __post_init__(self) -> None:
        require_non_empty("Resource.name", self.name)
        require_non_empty("Resource.unit", self.unit)
        if type(self.location_id) is not EntityId:
            raise TypeError("Resource.location_id must be an EntityId")
        object.__setattr__(
            self, "quantity", _finite_non_negative("Resource.quantity", self.quantity)
        )


@dataclass(frozen=True, slots=True)
class Weather:
    """Location-bound weather value. Not a separately identified entity."""

    location_id: EntityId
    condition: str
    temperature: TemperatureCelsius

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("Weather.location_id must be an EntityId")
        require_non_empty("Weather.condition", self.condition)
        if type(self.temperature) is not TemperatureCelsius:
            raise TypeError("Weather.temperature must be TemperatureCelsius")


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

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("AgentBody.location_id must be an EntityId")
        for field_name, expected, value in (
            ("health", Health, self.health),
            ("hunger", Hunger, self.hunger),
            ("thirst", Thirst, self.thirst),
            ("fatigue", Fatigue, self.fatigue),
            ("temperature", TemperatureCelsius, self.temperature),
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
