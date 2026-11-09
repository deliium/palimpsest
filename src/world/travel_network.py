"""Locked travel-network policy contracts (objective, location-based).

Route conditions are derived objective facts. They never carry an actor,
owner, crew, planner, score, grid, or coordinate, and agents only ever see the
adjacent exit facts projected by perception.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, NoReturn

from world.environment import Season
from world.identifiers import EntityId
from world.values import WeatherCondition

if TYPE_CHECKING:
    from world._state import WorldState

_LOG = logging.getLogger("world.travel_network")

TRAVEL_NETWORK_POLICY_ID: Final[str] = "travel-network.v1"

MAX_ROUTE_CONDITIONS: Final[int] = 512
ROUTE_BASE_CAPACITY: Final[int] = 8
ROUTE_MIN_CAPACITY: Final[int] = 1
ROUTE_MAX_CAPACITY: Final[int] = 24
ROUTE_MAX_RISK: Final[float] = 1.0
ROUTE_RISK_FATIGUE_FACTOR: Final[float] = 2.0
ROAD_CAPACITY_BONUS: Final[int] = 2
BRIDGE_CAPACITY_BONUS: Final[int] = 1
INFRASTRUCTURE_QUALITY_RELIEF_THRESHOLD: Final[float] = 0.5
HAZARD_RISK_DELTA: Final[float] = 0.3
HAZARD_CAPACITY_DELTA: Final[int] = -2
MAX_ROUTE_REASON_CODES: Final[int] = 8

SEASON_DURATION_DELTA: Final[dict[Season, int]] = {
    Season.SPRING: 0,
    Season.SUMMER: 0,
    Season.AUTUMN: 1,
    Season.WINTER: 2,
}
SEASON_CAPACITY_DELTA: Final[dict[Season, int]] = {
    Season.SPRING: 0,
    Season.SUMMER: 0,
    Season.AUTUMN: -1,
    Season.WINTER: -2,
}
SEASON_RISK_DELTA: Final[dict[Season, float]] = {
    Season.SPRING: 0.0,
    Season.SUMMER: 0.0,
    Season.AUTUMN: 0.1,
    Season.WINTER: 0.2,
}
WEATHER_DURATION_DELTA: Final[dict[WeatherCondition, int]] = {
    WeatherCondition.CLEAR: 0,
    WeatherCondition.CLOUDY: 0,
    WeatherCondition.RAIN: 1,
    WeatherCondition.STORM: 2,
}
WEATHER_RISK_DELTA: Final[dict[WeatherCondition, float]] = {
    WeatherCondition.CLEAR: 0.0,
    WeatherCondition.CLOUDY: 0.0,
    WeatherCondition.RAIN: 0.15,
    WeatherCondition.STORM: 0.5,
}

TRAVEL_NETWORK_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "score",
        "route_score",
        "civilization_score",
        "planner",
        "omniscient",
        "owner_id",
        "crew",
        "nation_id",
        "grid",
        "coordinate",
    }
)

REASON_CODE_ORDER: Final[tuple[str, ...]] = (
    "weather_storm",
    "weather_rain",
    "season_winter",
    "season_autumn",
    "hazard_active",
    "route_closed",
    "route_restricted",
    "infrastructure_relief",
    "infrastructure_absent",
)

_REASON_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class RouteStatus(StrEnum):
    OPEN = "open"
    RESTRICTED = "restricted"
    CLOSED = "closed"


class SeasonalAvailability(StrEnum):
    OPEN = "open"
    RESTRICTED = "restricted"
    CLOSED = "closed"


class RouteBlockageCause(StrEnum):
    NONE = "none"
    WEATHER = "weather"
    SEASONAL = "seasonal"
    HAZARD = "hazard"


def _fail(field_name: str, code: str) -> NoReturn:
    _LOG.error(
        "travel_network_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    raise ValueError(f"{field_name}: {code}")


def _bounded_unit_float(field_name: str, value: object, *, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(field_name, "travel_network_invalid_number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > maximum:
        _fail(field_name, "travel_network_invalid_number")
    return 0.0 if number == 0.0 else number


def _reason_codes(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        _fail("reason_codes", "travel_network_invalid_reason_codes")
    codes = tuple(value)
    if len(codes) > MAX_ROUTE_REASON_CODES:
        _fail("reason_codes", "travel_network_invalid_reason_codes")
    seen: set[str] = set()
    for code in codes:
        if type(code) is not str or _REASON_CODE_RE.fullmatch(code) is None:
            _fail("reason_codes", "travel_network_invalid_reason_codes")
        if code in seen:
            _fail("reason_codes", "travel_network_invalid_reason_codes")
        seen.add(code)
    return codes


@dataclass(frozen=True, slots=True)
class RouteCondition:
    """One immutable, objective condition for an adjacent undirected edge."""

    origin_id: EntityId
    destination_id: EntityId
    status: RouteStatus
    seasonal_availability: SeasonalAvailability
    blockage_cause: RouteBlockageCause
    duration_ticks: int
    fatigue_cost: float
    capacity: int
    risk: float
    infrastructure_quality: float
    reason_codes: tuple[str, ...]
    as_of_tick: int

    def __post_init__(self) -> None:
        if (
            type(self.origin_id) is not EntityId
            or type(self.destination_id) is not EntityId
        ):
            _fail("endpoints", "travel_network_invalid_endpoints")
        if self.origin_id == self.destination_id:
            _fail("endpoints", "travel_network_invalid_endpoints")
        first, second = sorted(
            (self.origin_id, self.destination_id), key=lambda item: item.value
        )
        object.__setattr__(self, "origin_id", first)
        object.__setattr__(self, "destination_id", second)
        if type(self.status) is not RouteStatus:
            _fail("status", "travel_network_invalid_status")
        if type(self.seasonal_availability) is not SeasonalAvailability:
            _fail("seasonal_availability", "travel_network_invalid_availability")
        if type(self.blockage_cause) is not RouteBlockageCause:
            _fail("blockage_cause", "travel_network_invalid_blockage")
        if (
            isinstance(self.duration_ticks, bool)
            or type(self.duration_ticks) is not int
            or self.duration_ticks < 1
        ):
            _fail("duration_ticks", "travel_network_invalid_duration")
        object.__setattr__(
            self,
            "fatigue_cost",
            _bounded_unit_float("fatigue_cost", self.fatigue_cost, maximum=math.inf),
        )
        if (
            isinstance(self.capacity, bool)
            or type(self.capacity) is not int
            or not (ROUTE_MIN_CAPACITY <= self.capacity <= ROUTE_MAX_CAPACITY)
        ):
            _fail("capacity", "travel_network_invalid_capacity")
        object.__setattr__(
            self, "risk", _bounded_unit_float("risk", self.risk, maximum=ROUTE_MAX_RISK)
        )
        object.__setattr__(
            self,
            "infrastructure_quality",
            _bounded_unit_float(
                "infrastructure_quality",
                self.infrastructure_quality,
                maximum=1.0,
            ),
        )
        object.__setattr__(self, "reason_codes", _reason_codes(self.reason_codes))
        if (
            isinstance(self.as_of_tick, bool)
            or type(self.as_of_tick) is not int
            or self.as_of_tick < 0
        ):
            _fail("as_of_tick", "travel_network_invalid_tick")
        for forbidden in TRAVEL_NETWORK_FORBIDDEN_FIELDS:
            if hasattr(self, forbidden):
                _fail(f"RouteCondition.{forbidden}", "forbidden_field")

    @property
    def edge_key(self) -> tuple[str, str]:
        return self.origin_id.value, self.destination_id.value

    def canonical(self) -> dict[str, object]:
        return {
            "origin_id": self.origin_id.value,
            "destination_id": self.destination_id.value,
            "status": self.status.value,
            "seasonal_availability": self.seasonal_availability.value,
            "blockage_cause": self.blockage_cause.value,
            "duration_ticks": self.duration_ticks,
            "fatigue_cost": self.fatigue_cost,
            "capacity": self.capacity,
            "risk": self.risk,
            "infrastructure_quality": self.infrastructure_quality,
            "reason_codes": list(self.reason_codes),
            "as_of_tick": self.as_of_tick,
        }


def _weather_rank(condition: WeatherCondition) -> int:
    return {
        WeatherCondition.CLEAR: 0,
        WeatherCondition.CLOUDY: 1,
        WeatherCondition.RAIN: 2,
        WeatherCondition.STORM: 3,
    }[condition]


def default_route_condition(
    origin_id: EntityId,
    destination_id: EntityId,
    *,
    tick: int = 0,
) -> RouteCondition:
    """Open fallback used when no regions spec exists (channel is inactive)."""
    return RouteCondition(
        origin_id=origin_id,
        destination_id=destination_id,
        status=RouteStatus.OPEN,
        seasonal_availability=SeasonalAvailability.OPEN,
        blockage_cause=RouteBlockageCause.NONE,
        duration_ticks=1,
        fatigue_cost=0.0,
        capacity=ROUTE_BASE_CAPACITY,
        risk=0.0,
        infrastructure_quality=0.0,
        reason_codes=(),
        as_of_tick=tick,
    )


def _base_route(
    state: WorldState, origin_id: EntityId, destination_id: EntityId
) -> tuple[int, float]:
    spec = getattr(state, "regions_migration", None)
    if spec is not None:
        for route in spec.routes:
            if route.edge_key == tuple(sorted((origin_id.value, destination_id.value))):
                return route.duration_ticks, route.fatigue_cost
    from world.models import default_physical_rules

    return 1, default_physical_rules().move_fatigue


def _weather_for(state: WorldState, location_id: EntityId) -> WeatherCondition:
    weather = state.weather.get(location_id)
    return WeatherCondition.CLEAR if weather is None else weather.condition


def _hazard_at(state: WorldState, location_id: EntityId, tick: int) -> bool:
    return any(
        hazard.location_id == location_id and hazard.contains(tick)
        for hazard in state.active_hazards
    )


def derive_route_condition(
    state: WorldState,
    origin_id: EntityId,
    destination_id: EntityId,
    *,
    season: Season | None,
    tick: int,
) -> RouteCondition:
    """Derive one condition from already-authoritative objective facts."""
    from world._infrastructure import (
        effective_travel_duration,
        effective_travel_fatigue,
        route_capacity_bonus,
        route_quality,
    )

    if type(origin_id) is not EntityId or type(destination_id) is not EntityId:
        _fail("endpoints", "travel_network_invalid_endpoints")
    if origin_id == destination_id:
        _fail("endpoints", "travel_network_invalid_endpoints")
    locations = state.locations
    origin = locations.get(origin_id)
    destination = locations.get(destination_id)
    if (
        origin is None
        or destination is None
        or destination.entity_id not in origin.adjacent
    ):
        _fail("endpoints", "travel_network_invalid_endpoints")
    if season is not None and type(season) is not Season:
        _fail("season", "travel_network_invalid_season")

    assets = getattr(state, "infrastructure", None)
    base_duration, base_fatigue = _base_route(state, origin_id, destination_id)
    duration = effective_travel_duration(
        assets,
        origin_id=origin_id,
        destination_id=destination_id,
        base_duration=base_duration,
    )
    fatigue = effective_travel_fatigue(
        assets,
        origin_id=origin_id,
        destination_id=destination_id,
        base_fatigue=base_fatigue,
    )
    quality = route_quality(assets, origin_id, destination_id)

    origin_weather = _weather_for(state, origin_id)
    destination_weather = _weather_for(state, destination_id)
    worst_weather = (
        origin_weather
        if _weather_rank(origin_weather) >= _weather_rank(destination_weather)
        else destination_weather
    )
    hazard = _hazard_at(state, origin_id, tick) or _hazard_at(
        state, destination_id, tick
    )
    relief = quality >= INFRASTRUCTURE_QUALITY_RELIEF_THRESHOLD

    reasons: set[str] = set()
    if worst_weather is WeatherCondition.STORM:
        reasons.add("weather_storm")
    if worst_weather is WeatherCondition.RAIN:
        reasons.add("weather_rain")
    if season is Season.WINTER:
        reasons.add("season_winter")
    if season is Season.AUTUMN:
        reasons.add("season_autumn")
    if hazard:
        reasons.add("hazard_active")

    if worst_weather is WeatherCondition.STORM and not relief:
        status = RouteStatus.CLOSED
        blockage = RouteBlockageCause.WEATHER
        reasons.add("route_closed")
    elif season is Season.WINTER and not relief:
        status = RouteStatus.CLOSED
        blockage = RouteBlockageCause.SEASONAL
        reasons.add("route_closed")
    elif hazard:
        status = RouteStatus.RESTRICTED
        blockage = RouteBlockageCause.HAZARD
        reasons.add("route_restricted")
    elif worst_weather is WeatherCondition.STORM:
        status = RouteStatus.RESTRICTED
        blockage = RouteBlockageCause.WEATHER
        reasons.add("infrastructure_relief")
    elif season is Season.WINTER:
        status = RouteStatus.RESTRICTED
        blockage = RouteBlockageCause.SEASONAL
        reasons.add("infrastructure_relief")
    elif worst_weather is WeatherCondition.RAIN or season is Season.AUTUMN:
        status = RouteStatus.RESTRICTED
        blockage = (
            RouteBlockageCause.WEATHER
            if worst_weather is WeatherCondition.RAIN
            else RouteBlockageCause.SEASONAL
        )
        reasons.add("route_restricted")
    else:
        status = RouteStatus.OPEN
        blockage = RouteBlockageCause.NONE
    if assets is not None and quality <= 0.0:
        reasons.add("infrastructure_absent")

    if season is Season.WINTER:
        availability = (
            SeasonalAvailability.RESTRICTED if relief else SeasonalAvailability.CLOSED
        )
    elif season is Season.AUTUMN:
        availability = SeasonalAvailability.RESTRICTED
    else:
        availability = SeasonalAvailability.OPEN

    duration += WEATHER_DURATION_DELTA[worst_weather]
    if season is not None:
        duration += SEASON_DURATION_DELTA[season]
    duration = max(1, duration)

    capacity = min(
        ROUTE_BASE_CAPACITY,
        origin.body_capacity.value,
        destination.body_capacity.value,
    )
    capacity += route_capacity_bonus(assets, origin_id, destination_id)
    if season is not None:
        capacity += SEASON_CAPACITY_DELTA[season]
    if hazard:
        capacity += HAZARD_CAPACITY_DELTA
    capacity = max(ROUTE_MIN_CAPACITY, min(ROUTE_MAX_CAPACITY, capacity))

    visibility = min(
        origin.visibility_factor.value, destination.visibility_factor.value
    )
    risk = 0.1 * (1.0 - visibility)
    risk += WEATHER_RISK_DELTA[worst_weather]
    if season is not None:
        risk += SEASON_RISK_DELTA[season]
    if hazard:
        risk += HAZARD_RISK_DELTA
    risk += 0.02 * duration
    risk -= 0.3 * quality
    risk = max(0.0, min(ROUTE_MAX_RISK, risk))

    fatigue = max(0.0, fatigue + risk * ROUTE_RISK_FATIGUE_FACTOR)

    condition = RouteCondition(
        origin_id=origin_id,
        destination_id=destination_id,
        status=status,
        seasonal_availability=availability,
        blockage_cause=blockage,
        duration_ticks=duration,
        fatigue_cost=fatigue,
        capacity=capacity,
        risk=risk,
        infrastructure_quality=quality,
        reason_codes=tuple(code for code in REASON_CODE_ORDER if code in reasons)[
            :MAX_ROUTE_REASON_CODES
        ],
        as_of_tick=tick,
    )
    _LOG.debug(
        "travel_network_derived status=%s quality_milli=%s risk_milli=%s",
        condition.status.value,
        round(condition.infrastructure_quality * 1000),
        round(condition.risk * 1000),
    )
    return condition


def derive_initial_route_conditions(
    state: WorldState, *, season: Season | None, tick: int
) -> tuple[RouteCondition, ...]:
    """Seed every adjacent edge once in deterministic edge order."""
    seed: list[RouteCondition] = []
    for origin_id in sorted(state.locations, key=lambda item: item.value):
        origin = state.locations[origin_id]
        for destination_id in sorted(origin.adjacent, key=lambda item: item.value):
            if origin_id.value >= destination_id.value:
                continue
            seed.append(
                derive_route_condition(
                    state,
                    origin_id,
                    destination_id,
                    season=season,
                    tick=tick,
                )
            )
            if len(seed) > MAX_ROUTE_CONDITIONS:
                _LOG.warning(
                    "travel_network_route_cap_exceeded count=%s cap=%s",
                    len(seed),
                    MAX_ROUTE_CONDITIONS,
                )
                raise ValueError("travel_network_route_cap_exceeded")
    return tuple(seed)


def effective_route_condition(
    state: WorldState,
    origin_id: EntityId,
    destination_id: EntityId,
    *,
    season: Season | None,
    tick: int,
) -> RouteCondition:
    """Return the persisted condition; derive only when the channel is absent."""
    existing = state.route_condition(origin_id, destination_id)
    if existing is not None:
        return existing
    return derive_route_condition(
        state, origin_id, destination_id, season=season, tick=tick
    )


def require_route_condition(value: object, *, field_name: str) -> RouteCondition:
    if type(value) is not RouteCondition:
        _fail(field_name, "travel_network_invalid_condition")
    return value


def require_route_conditions(
    sequence: object,
    *,
    max_items: int = MAX_ROUTE_CONDITIONS,
) -> tuple[RouteCondition, ...]:
    if isinstance(sequence, (str, bytes, bytearray, Mapping)) or not isinstance(
        sequence, Sequence
    ):
        _fail("travel_network", "travel_network_invalid_condition")
    rows = tuple(sequence)
    if len(rows) > max_items:
        _fail("travel_network", "travel_network_route_cap_exceeded")
    for row in rows:
        require_route_condition(row, field_name="travel_network")
    return rows


__all__ = [
    "HAZARD_CAPACITY_DELTA",
    "HAZARD_RISK_DELTA",
    "INFRASTRUCTURE_QUALITY_RELIEF_THRESHOLD",
    "MAX_ROUTE_CONDITIONS",
    "MAX_ROUTE_REASON_CODES",
    "REASON_CODE_ORDER",
    "ROAD_CAPACITY_BONUS",
    "ROUTE_BASE_CAPACITY",
    "ROUTE_MAX_CAPACITY",
    "ROUTE_MAX_RISK",
    "ROUTE_MIN_CAPACITY",
    "ROUTE_RISK_FATIGUE_FACTOR",
    "SEASON_CAPACITY_DELTA",
    "SEASON_DURATION_DELTA",
    "SEASON_RISK_DELTA",
    "TRAVEL_NETWORK_FORBIDDEN_FIELDS",
    "TRAVEL_NETWORK_POLICY_ID",
    "WEATHER_DURATION_DELTA",
    "WEATHER_RISK_DELTA",
    "RouteBlockageCause",
    "RouteCondition",
    "RouteStatus",
    "SeasonalAvailability",
    "default_route_condition",
    "derive_initial_route_conditions",
    "derive_route_condition",
    "effective_route_condition",
    "require_route_condition",
    "require_route_conditions",
]
