"""Shared private ambient-temperature arithmetic, free of rule/measurement imports."""

from __future__ import annotations

from world.models import Location, PhysicalRules
from world.values import WeatherCondition, round_physical

__all__ = ["ambient_temperature"]


def ambient_temperature(
    location: Location,
    condition: WeatherCondition,
    phase_offset: float,
    season_offset: float,
    rules: PhysicalRules,
) -> float:
    """Legacy-equivalent ambient Celsius for one location and conditions."""
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
