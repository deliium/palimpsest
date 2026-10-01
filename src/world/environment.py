"""Opt-in environmental dynamics. The spec is configuration, not world state.

Agents never receive this calendar, yield table, shortage list, or hazard
rules. ``WorldEngine`` is the only reader that turns the spec into seasons,
bands, regeneration, and hazards.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from world.identifiers import EntityId, require_exact_nonneg_int
from world.values import ResourceKind, WeatherCondition

_LOG: Final[logging.Logger] = logging.getLogger("world.environment")

COLD_AMBIENT_BELOW: Final[float] = 10.0
EXAMPLE_HAZARD_DURATION_TICKS: Final[int] = 6
EXAMPLE_HAZARD_EXPOSURE_EXTRA: Final[float] = 5.0
EXAMPLE_SEASON_LENGTH_TICKS: Final[int] = 48
HOT_AMBIENT_AT: Final[float] = 30.0
SCARCITY_SEASON_LENGTH_TICKS: Final[int] = 4
SEASON_COUNT: Final[int] = 4

__all__ = [
    "COLD_AMBIENT_BELOW",
    "EXAMPLE_HAZARD_DURATION_TICKS",
    "EXAMPLE_HAZARD_EXPOSURE_EXTRA",
    "EXAMPLE_SEASON_LENGTH_TICKS",
    "HOT_AMBIENT_AT",
    "SCARCITY_SEASON_LENGTH_TICKS",
    "SEASON_COUNT",
    "ActiveHazard",
    "EnvironmentalDynamicsSpec",
    "HazardKind",
    "HazardRule",
    "Season",
    "SeasonalYield",
    "ShortageWindow",
    "TemperatureBand",
    "environmental_dynamics_digest",
    "example_environmental_dynamics",
    "scarcity_scenario_dynamics",
    "temperature_band",
]


class Season(StrEnum):
    """Closed season order. Tick zero is spring."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class TemperatureBand(StrEnum):
    """Closed ambient bands. Derived, never stored on world state."""

    COLD = "cold"
    MILD = "mild"
    HOT = "hot"


@dataclass(frozen=True, slots=True)
class ActiveHazard:
    """One active hazard. Remaining ticks are derived, not stored."""

    location_id: EntityId
    kind: HazardKind
    start_tick: int
    duration_ticks: int

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("ActiveHazard.location_id must be EntityId")
        if type(self.kind) is not HazardKind:
            raise TypeError("ActiveHazard.kind must be HazardKind")
        object.__setattr__(
            self,
            "start_tick",
            require_exact_nonneg_int("ActiveHazard.start_tick", self.start_tick),
        )
        if (
            isinstance(self.duration_ticks, bool)
            or type(self.duration_ticks) is not int
            or self.duration_ticks < 1
        ):
            raise ValueError("ActiveHazard.duration_ticks must be an integer >= 1")

    def contains(self, tick: int) -> bool:
        return self.start_tick <= tick < self.start_tick + self.duration_ticks

    def remaining_ticks(self, tick: int) -> int:
        return self.duration_ticks - (tick - self.start_tick)


class HazardKind(StrEnum):
    """Closed hazard kinds. There is no new death cause."""

    COLD_SNAP = "cold_snap"
    HEAT = "heat"


_SEASON_ORDER: Final[tuple[Season, ...]] = (
    Season.SPRING,
    Season.SUMMER,
    Season.AUTUMN,
    Season.WINTER,
)


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "environment_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _positive_int(field_name: str, value: object, code: str) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise _fail(field_name, code)
    return value


def _nonneg_int(field_name: str, value: object, code: str) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise _fail(field_name, code)
    return value


def _finite_float(field_name: str, value: object, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, code)
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, code)
    return 0.0 if number == 0.0 else number


def _nonneg_float(field_name: str, value: object, code: str) -> float:
    number = _finite_float(field_name, value, code)
    if number < 0.0:
        raise _fail(field_name, code)
    return number


def temperature_band(ambient: float) -> TemperatureBand:
    """Derive the closed band from ambient Celsius. Cold is strictly below 10."""
    number = _finite_float("temperature_band.ambient", ambient, "offset_invalid")
    if number < COLD_AMBIENT_BELOW:
        return TemperatureBand.COLD
    if number >= HOT_AMBIENT_AT:
        return TemperatureBand.HOT
    return TemperatureBand.MILD


def season_at_tick(tick: int, season_length_ticks: int) -> Season:
    """Season is ``(tick // season_length_ticks) % 4`` with no stream draw."""
    length = _positive_int(
        "season_length_ticks",
        season_length_ticks,
        "season_length_invalid",
    )
    checked = _nonneg_int("tick", tick, "tick_invalid")
    return _SEASON_ORDER[(checked // length) % SEASON_COUNT]


def season_transitions(tick: int, season_length_ticks: int) -> bool:
    """A transition exists only when the tick is a positive season boundary."""
    length = _positive_int(
        "season_length_ticks",
        season_length_ticks,
        "season_length_invalid",
    )
    checked = _nonneg_int("tick", tick, "tick_invalid")
    return checked > 0 and checked % length == 0


@dataclass(frozen=True, slots=True)
class SeasonalYield:
    """Regeneration multiplier for one resource kind in one season."""

    resource_kind: ResourceKind
    season: Season
    multiplier: float

    def __post_init__(self) -> None:
        if type(self.resource_kind) is not ResourceKind:
            raise _fail("SeasonalYield.resource_kind", "yield_undefined")
        if type(self.season) is not Season:
            raise _fail("SeasonalYield.season", "yield_undefined")
        object.__setattr__(
            self,
            "multiplier",
            _nonneg_float(
                "SeasonalYield.multiplier",
                self.multiplier,
                "multiplier_invalid",
            ),
        )


@dataclass(frozen=True, slots=True)
class ShortageWindow:
    """Inclusive start, exclusive end. Suppresses regeneration and nothing else."""

    resource_kind: ResourceKind
    start_tick: int
    duration_ticks: int

    def __post_init__(self) -> None:
        if type(self.resource_kind) is not ResourceKind:
            raise _fail("ShortageWindow.resource_kind", "window_invalid")
        object.__setattr__(
            self,
            "start_tick",
            _nonneg_int(
                "ShortageWindow.start_tick",
                self.start_tick,
                "start_tick_invalid",
            ),
        )
        object.__setattr__(
            self,
            "duration_ticks",
            _positive_int(
                "ShortageWindow.duration_ticks",
                self.duration_ticks,
                "duration_invalid",
            ),
        )

    def contains(self, tick: int) -> bool:
        return self.start_tick <= tick < self.start_tick + self.duration_ticks


@dataclass(frozen=True, slots=True)
class HazardRule:
    """Start condition. The condition need not remain true for the duration."""

    kind: HazardKind
    season: Season
    weather: WeatherCondition
    band: TemperatureBand
    duration_ticks: int
    exposure_extra: float

    def __post_init__(self) -> None:
        if type(self.kind) is not HazardKind:
            raise _fail("HazardRule.kind", "hazard_invalid")
        if type(self.season) is not Season:
            raise _fail("HazardRule.season", "hazard_invalid")
        if type(self.weather) is not WeatherCondition:
            raise _fail("HazardRule.weather", "hazard_invalid")
        if type(self.band) is not TemperatureBand:
            raise _fail("HazardRule.band", "hazard_invalid")
        object.__setattr__(
            self,
            "duration_ticks",
            _positive_int(
                "HazardRule.duration_ticks",
                self.duration_ticks,
                "duration_invalid",
            ),
        )
        object.__setattr__(
            self,
            "exposure_extra",
            _nonneg_float(
                "HazardRule.exposure_extra",
                self.exposure_extra,
                "exposure_extra_invalid",
            ),
        )


def _yield_rows(
    yields: tuple[SeasonalYield, ...],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "multiplier": item.multiplier,
            "resource_kind": item.resource_kind.value,
            "season": item.season.value,
        }
        for item in yields
    )


def _window_rows(
    windows: tuple[ShortageWindow, ...],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "duration_ticks": window.duration_ticks,
            "resource_kind": window.resource_kind.value,
            "start_tick": window.start_tick,
        }
        for window in windows
    )


def _rule_rows(rules: tuple[HazardRule, ...]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "band": rule.band.value,
            "duration_ticks": rule.duration_ticks,
            "exposure_extra": rule.exposure_extra,
            "kind": rule.kind.value,
            "season": rule.season.value,
            "weather": rule.weather.value,
        }
        for rule in rules
    )


def environmental_dynamics_digest(payload: Mapping[str, object]) -> str:
    """SHA-256 of sorted JSON. Not Python ``hash()``."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _locked_offsets() -> dict[Season, float]:
    return {
        Season.SPRING: 0.0,
        Season.SUMMER: 12.0,
        Season.AUTUMN: 0.0,
        Season.WINTER: -14.0,
    }


def _locked_yields() -> tuple[SeasonalYield, ...]:
    rows: list[SeasonalYield] = []
    for kind in ResourceKind:
        for season in _SEASON_ORDER:
            winter_food = kind is ResourceKind.FOOD and season is Season.WINTER
            multiplier = 0.0 if winter_food else 1.0
            rows.append(
                SeasonalYield(
                    resource_kind=kind,
                    season=season,
                    multiplier=multiplier,
                )
            )
    return tuple(rows)


def _locked_rules() -> tuple[HazardRule, ...]:
    return (
        HazardRule(
            kind=HazardKind.COLD_SNAP,
            season=Season.WINTER,
            weather=WeatherCondition.STORM,
            band=TemperatureBand.COLD,
            duration_ticks=EXAMPLE_HAZARD_DURATION_TICKS,
            exposure_extra=EXAMPLE_HAZARD_EXPOSURE_EXTRA,
        ),
        HazardRule(
            kind=HazardKind.HEAT,
            season=Season.SUMMER,
            weather=WeatherCondition.CLEAR,
            band=TemperatureBand.HOT,
            duration_ticks=EXAMPLE_HAZARD_DURATION_TICKS,
            exposure_extra=EXAMPLE_HAZARD_EXPOSURE_EXTRA,
        ),
    )


@dataclass(frozen=True, slots=True)
class EnvironmentalDynamicsSpec:
    """Calendar, multipliers, windows, and hazard rules. Not a world field."""

    season_length_ticks: int
    season_offsets: Mapping[Season, float]
    yields: tuple[SeasonalYield, ...]
    shortage_windows: tuple[ShortageWindow, ...] = ()
    hazard_rules: tuple[HazardRule, ...] = ()

    def __post_init__(self) -> None:
        length = _positive_int(
            "EnvironmentalDynamicsSpec.season_length_ticks",
            self.season_length_ticks,
            "season_length_invalid",
        )
        object.__setattr__(self, "season_length_ticks", length)
        offsets = _freeze_offsets(self.season_offsets)
        object.__setattr__(self, "season_offsets", offsets)
        yields = _freeze_yields(self.yields)
        object.__setattr__(self, "yields", yields)
        windows = _freeze_windows(self.shortage_windows)
        object.__setattr__(self, "shortage_windows", windows)
        rules = _freeze_rules(self.hazard_rules)
        object.__setattr__(self, "hazard_rules", rules)
        digest = self.digest
        _LOG.debug(
            "environment_spec_built season_count=%s window_count=%s "
            "hazard_rule_count=%s digest=%s",
            SEASON_COUNT,
            len(windows),
            len(rules),
            digest,
        )

    @property
    def canonical_payload(self) -> dict[str, object]:
        return {
            "hazard_rules": list(_rule_rows(self.hazard_rules)),
            "season_length_ticks": self.season_length_ticks,
            "season_offsets": {
                season.value: self.season_offsets[season] for season in _SEASON_ORDER
            },
            "shortage_windows": list(_window_rows(self.shortage_windows)),
            "yields": list(_yield_rows(self.yields)),
        }

    @property
    def digest(self) -> str:
        return environmental_dynamics_digest(self.canonical_payload)

    def season_at(self, tick: int) -> Season:
        return season_at_tick(tick, self.season_length_ticks)

    def transitions_at(self, tick: int) -> bool:
        return season_transitions(tick, self.season_length_ticks)

    def offset_for(self, season: Season) -> float:
        if type(season) is not Season or season not in self.season_offsets:
            raise _fail("EnvironmentalDynamicsSpec.season_offsets", "offset_undefined")
        return self.season_offsets[season]

    def multiplier_for(self, resource_kind: ResourceKind, season: Season) -> float:
        for item in self.yields:
            if item.resource_kind is resource_kind and item.season is season:
                return item.multiplier
        raise _fail("EnvironmentalDynamicsSpec.yields", "yield_undefined")

    def shortage_suppresses(self, resource_kind: ResourceKind, tick: int) -> bool:
        checked = _nonneg_int("tick", tick, "tick_invalid")
        return any(
            window.resource_kind is resource_kind and window.contains(checked)
            for window in self.shortage_windows
        )

    def matching_rules(
        self,
        season: Season,
        weather: WeatherCondition,
        band: TemperatureBand,
    ) -> tuple[HazardRule, ...]:
        return tuple(
            rule
            for rule in self.hazard_rules
            if rule.season is season and rule.weather is weather and rule.band is band
        )


def _freeze_offsets(raw: object) -> Mapping[Season, float]:
    if not isinstance(raw, Mapping):
        raise _fail("EnvironmentalDynamicsSpec.season_offsets", "offset_undefined")
    offsets: dict[Season, float] = {}
    for season in _SEASON_ORDER:
        if season not in raw:
            raise _fail(
                "EnvironmentalDynamicsSpec.season_offsets",
                "offset_undefined",
            )
        offsets[season] = _finite_float(
            f"EnvironmentalDynamicsSpec.season_offsets.{season.value}",
            raw[season],
            "offset_invalid",
        )
    extra = [key for key in raw if key not in offsets]
    if extra:
        raise _fail("EnvironmentalDynamicsSpec.season_offsets", "offset_undefined")
    return MappingProxyType(offsets)


def _freeze_yields(raw: object) -> tuple[SeasonalYield, ...]:
    if not isinstance(raw, tuple):
        raise _fail("EnvironmentalDynamicsSpec.yields", "yield_undefined")
    seen: set[tuple[ResourceKind, Season]] = set()
    for item in raw:
        if type(item) is not SeasonalYield:
            raise _fail("EnvironmentalDynamicsSpec.yields", "yield_undefined")
        key = (item.resource_kind, item.season)
        if key in seen:
            raise _fail("EnvironmentalDynamicsSpec.yields", "yield_undefined")
        seen.add(key)
    required = {
        (kind, season) for kind in ResourceKind for season in _SEASON_ORDER
    }
    if seen != required:
        raise _fail("EnvironmentalDynamicsSpec.yields", "yield_undefined")
    ordered = tuple(
        sorted(raw, key=lambda item: (item.resource_kind.value, item.season.value))
    )
    return ordered


def _freeze_windows(raw: object) -> tuple[ShortageWindow, ...]:
    if not isinstance(raw, tuple):
        raise _fail("EnvironmentalDynamicsSpec.shortage_windows", "window_invalid")
    seen: set[tuple[str, int, int]] = set()
    for window in raw:
        if type(window) is not ShortageWindow:
            raise _fail(
                "EnvironmentalDynamicsSpec.shortage_windows",
                "window_invalid",
            )
        identity = (
            window.resource_kind.value,
            window.start_tick,
            window.duration_ticks,
        )
        if identity in seen:
            raise _fail(
                "EnvironmentalDynamicsSpec.shortage_windows",
                "duplicate_shortage_window",
            )
        seen.add(identity)
    return tuple(
        sorted(raw, key=lambda window: (window.start_tick, window.resource_kind.value))
    )


def _freeze_rules(raw: object) -> tuple[HazardRule, ...]:
    if not isinstance(raw, tuple):
        raise _fail("EnvironmentalDynamicsSpec.hazard_rules", "hazard_invalid")
    for rule in raw:
        if type(rule) is not HazardRule:
            raise _fail("EnvironmentalDynamicsSpec.hazard_rules", "hazard_invalid")
    return tuple(
        sorted(
            raw,
            key=lambda rule: (
                rule.kind.value,
                rule.season.value,
                rule.weather.value,
                rule.band.value,
                rule.duration_ticks,
                rule.exposure_extra,
            ),
        )
    )


def example_environmental_dynamics() -> EnvironmentalDynamicsSpec:
    """Season length 48, locked offsets, yields, and hazard rules. No windows."""
    return EnvironmentalDynamicsSpec(
        season_length_ticks=EXAMPLE_SEASON_LENGTH_TICKS,
        season_offsets=_locked_offsets(),
        yields=_locked_yields(),
        shortage_windows=(),
        hazard_rules=_locked_rules(),
    )


def scarcity_scenario_dynamics() -> EnvironmentalDynamicsSpec:
    """Same yields and rules as the example, with season length 4."""
    return EnvironmentalDynamicsSpec(
        season_length_ticks=SCARCITY_SEASON_LENGTH_TICKS,
        season_offsets=_locked_offsets(),
        yields=_locked_yields(),
        shortage_windows=(),
        hazard_rules=_locked_rules(),
    )
