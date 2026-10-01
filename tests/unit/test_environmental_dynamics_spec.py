"""Environmental dynamics spec stays configuration and fails closed."""

from __future__ import annotations

import ast
import hashlib
import json
import logging
from pathlib import Path

import pytest

from world.environment import (
    COLD_AMBIENT_BELOW,
    EXAMPLE_HAZARD_DURATION_TICKS,
    EXAMPLE_HAZARD_EXPOSURE_EXTRA,
    EXAMPLE_SEASON_LENGTH_TICKS,
    HOT_AMBIENT_AT,
    SCARCITY_SEASON_LENGTH_TICKS,
    SEASON_COUNT,
    EnvironmentalDynamicsSpec,
    HazardKind,
    HazardRule,
    Season,
    SeasonalYield,
    ShortageWindow,
    TemperatureBand,
    environmental_dynamics_digest,
    example_environmental_dynamics,
    scarcity_scenario_dynamics,
    season_at_tick,
    temperature_band,
)
from world.models import (
    PHYSICAL_RULES_VERSION,
    canonical_physical_rules_bytes,
    default_physical_rules,
)
from world.values import ResourceKind, WeatherCondition

_SRC = Path(__file__).resolve().parents[2] / "src/world/environment.py"

_PHYSICAL_RULE_KEYS = {
    "attack_damage_max_exclusive",
    "attack_damage_min",
    "attack_hit_probability",
    "day_end_hour",
    "day_start_hour",
    "day_visibility_factor",
    "drink_thirst_relief",
    "eat_hunger_relief",
    "exposure_damage",
    "exposure_high_celsius",
    "exposure_low_celsius",
    "fatigue_damage",
    "flee_fatigue",
    "flee_success_probability",
    "help_fatigue",
    "help_health_gain",
    "hours_per_day",
    "hunger_damage",
    "metabolism_fatigue",
    "metabolism_hunger",
    "metabolism_thirst",
    "move_fatigue",
    "night_visibility_factor",
    "phase_temperature_offset",
    "resource_extraction_amount",
    "search_base_probability",
    "search_visibility_weight",
    "sleep_fatigue_recovery",
    "temperature_lerp_factor",
    "thirst_damage",
    "version",
    "weather_period_ticks",
    "weather_temperature_offset",
    "weather_transitions",
    "weather_visibility",
}


def _isort_export_key(name: str) -> tuple[int, str]:
    """Match Ruff RUF022: constants, then classes, then functions."""
    if name.isupper():
        rank = 0
    elif name[:1].isupper():
        rank = 1
    else:
        rank = 2
    return (rank, name)


def _spec(**overrides: object) -> EnvironmentalDynamicsSpec:
    base = example_environmental_dynamics()
    payload: dict[str, object] = {
        "season_length_ticks": base.season_length_ticks,
        "season_offsets": dict(base.season_offsets),
        "yields": base.yields,
        "shortage_windows": base.shortage_windows,
        "hazard_rules": base.hazard_rules,
    }
    payload.update(overrides)
    return EnvironmentalDynamicsSpec(**payload)  # type: ignore[arg-type]


def test_example_and_scarcity_use_the_locked_numbers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world.environment")
    example = example_environmental_dynamics()
    scarcity = scarcity_scenario_dynamics()
    assert example.season_length_ticks == EXAMPLE_SEASON_LENGTH_TICKS == 48
    assert scarcity.season_length_ticks == SCARCITY_SEASON_LENGTH_TICKS == 4
    assert dict(example.season_offsets) == {
        Season.SPRING: 0.0,
        Season.SUMMER: 12.0,
        Season.AUTUMN: 0.0,
        Season.WINTER: -14.0,
    }
    assert example.season_offsets == scarcity.season_offsets
    assert example.yields == scarcity.yields
    assert example.hazard_rules == scarcity.hazard_rules
    assert example.shortage_windows == ()
    food = {
        item.season: item.multiplier
        for item in example.yields
        if item.resource_kind is ResourceKind.FOOD
    }
    assert food[Season.WINTER] == 0.0
    assert food[Season.SPRING] == 1.0
    assert food[Season.SUMMER] == 1.0
    assert food[Season.AUTUMN] == 1.0
    for kind in (ResourceKind.WATER, ResourceKind.MATERIAL):
        assert all(
            item.multiplier == 1.0
            for item in example.yields
            if item.resource_kind is kind
        )
    cold, heat = example.hazard_rules
    assert cold.kind is HazardKind.COLD_SNAP
    assert cold.season is Season.WINTER
    assert cold.weather is WeatherCondition.STORM
    assert cold.band is TemperatureBand.COLD
    assert heat.kind is HazardKind.HEAT
    assert heat.season is Season.SUMMER
    assert heat.weather is WeatherCondition.CLEAR
    assert heat.band is TemperatureBand.HOT
    assert cold.duration_ticks == heat.duration_ticks == EXAMPLE_HAZARD_DURATION_TICKS
    assert cold.exposure_extra == heat.exposure_extra == EXAMPLE_HAZARD_EXPOSURE_EXTRA
    digest = example.digest
    assert digest == environmental_dynamics_digest(example.canonical_payload)
    encoded = json.dumps(
        example.canonical_payload, sort_keys=True, separators=(",", ":")
    )
    assert digest == hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    assert digest != format(hash(encoded) & 0xFFFFFFFFFFFFFFFF, "x")
    assert any(
        record.levelno == logging.DEBUG
        and f"season_count={SEASON_COUNT}" in record.getMessage()
        and "window_count=0" in record.getMessage()
        and "hazard_rule_count=2" in record.getMessage()
        and f"digest={digest}" in record.getMessage()
        for record in caplog.records
    )
    assert not any("seed" in record.getMessage().lower() for record in caplog.records)


def test_season_is_a_pure_function_of_tick() -> None:
    length = 4
    assert [season_at_tick(tick, length).value for tick in range(8)] == [
        "spring",
        "spring",
        "spring",
        "spring",
        "summer",
        "summer",
        "summer",
        "summer",
    ]
    spec = scarcity_scenario_dynamics()
    assert spec.season_at(0) is Season.SPRING
    assert spec.transitions_at(0) is False
    assert spec.transitions_at(4) is True
    assert spec.season_at(4) is Season.SUMMER
    assert spec.season_at(16) is Season.SPRING


def test_temperature_bands_use_the_locked_thresholds() -> None:
    assert COLD_AMBIENT_BELOW == 10.0
    assert HOT_AMBIENT_AT == 30.0
    assert temperature_band(34.0) is TemperatureBand.HOT
    assert temperature_band(4.0) is TemperatureBand.COLD
    assert temperature_band(22.0) is TemperatureBand.MILD
    assert temperature_band(10.0) is TemperatureBand.MILD
    assert temperature_band(30.0) is TemperatureBand.HOT


def test_constructors_reject_invalid_spec_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="world.environment")
    with pytest.raises(ValueError, match="season_length_invalid"):
        _spec(season_length_ticks=0)
    with pytest.raises(ValueError, match="multiplier_invalid"):
        SeasonalYield(ResourceKind.FOOD, Season.WINTER, -0.1)
    missing = tuple(
        item
        for item in example_environmental_dynamics().yields
        if not (
            item.resource_kind is ResourceKind.FOOD and item.season is Season.SPRING
        )
    )
    with pytest.raises(ValueError, match="yield_undefined"):
        _spec(yields=missing)
    window = ShortageWindow(ResourceKind.FOOD, 2, 3)
    with pytest.raises(ValueError, match="duplicate_shortage_window"):
        _spec(shortage_windows=(window, window))
    with pytest.raises(ValueError, match="duration_invalid"):
        ShortageWindow(ResourceKind.WATER, 0, 0)
    with pytest.raises(ValueError, match="exposure_extra_invalid"):
        HazardRule(
            HazardKind.HEAT,
            Season.SUMMER,
            WeatherCondition.CLEAR,
            TemperatureBand.HOT,
            EXAMPLE_HAZARD_DURATION_TICKS,
            -1.0,
        )
    assert any(
        "field=EnvironmentalDynamicsSpec.season_length_ticks" in record.getMessage()
        and "reason_code=season_length_invalid" in record.getMessage()
        for record in caplog.records
    )
    assert any(
        "field=SeasonalYield.multiplier" in record.getMessage()
        and "reason_code=multiplier_invalid" in record.getMessage()
        for record in caplog.records
    )


def test_windows_order_and_overlap_without_zeroing_stock() -> None:
    later = ShortageWindow(ResourceKind.WATER, 5, 2)
    earlier = ShortageWindow(ResourceKind.FOOD, 1, 4)
    overlap = ShortageWindow(ResourceKind.MATERIAL, 2, 2)
    spec = _spec(shortage_windows=(later, earlier, overlap))
    assert [window.resource_kind for window in spec.shortage_windows] == [
        ResourceKind.FOOD,
        ResourceKind.MATERIAL,
        ResourceKind.WATER,
    ]
    assert spec.shortage_suppresses(ResourceKind.FOOD, 1) is True
    assert spec.shortage_suppresses(ResourceKind.FOOD, 4) is True
    assert spec.shortage_suppresses(ResourceKind.FOOD, 5) is False
    assert spec.shortage_suppresses(ResourceKind.WATER, 6) is True


def test_physical_rules_gain_no_environment_keys() -> None:
    rules = default_physical_rules()
    assert rules.version == PHYSICAL_RULES_VERSION == "physical-v1"
    payload = json.loads(canonical_physical_rules_bytes(rules))
    assert set(payload) == _PHYSICAL_RULE_KEYS
    assert "season_length_ticks" not in payload
    assert "season_offsets" not in payload


def test_public_export_list_stays_sorted() -> None:
    import world
    import world.environment as environment

    names = list(environment.__all__)
    assert names == sorted(names, key=_isort_export_key)
    facade = list(world.__all__)
    assert facade == sorted(facade, key=_isort_export_key)
    for name in (
        "EnvironmentalDynamicsSpec",
        "HazardKind",
        "HazardRule",
        "Season",
        "SeasonalYield",
        "ShortageWindow",
        "TemperatureBand",
        "example_environmental_dynamics",
        "scarcity_scenario_dynamics",
    ):
        assert name in facade


def test_environment_module_does_not_import_private_or_outer_packages() -> None:
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    forbidden = ("simulation", "observer", "api", "agents")
    for name in imported:
        assert not name.startswith(forbidden)
        assert not name.startswith("world._")
    assert "world.values" in imported
