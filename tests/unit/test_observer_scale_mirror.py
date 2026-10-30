"""Python/GDScript parity for the presentation-only observer scale contract."""

from __future__ import annotations

import re
from pathlib import Path

from observer.scale import (
    OBSERVER_SCALE_CONTRACT_VERSION,
    OBSERVER_SCALE_PROFILES,
    ObserverScaleLevel,
    scale_profile_for,
    select_scale_level,
)

ROOT = Path(__file__).resolve().parents[2]
GD_SCALE = (
    ROOT / "clients" / "godot-observer" / "scripts" / "presentation" / "scale.gd"
)
GD_MODELS = ROOT / "clients" / "godot-observer" / "scripts" / "protocol" / "models.gd"


def _gd_int(name: str) -> int:
    text = GD_SCALE.read_text(encoding="utf-8")
    match = re.search(rf"const\s+{re.escape(name)}\s*:=\s*(-?\d+)", text)
    assert match is not None, f"missing const {name}"
    return int(match.group(1))


def _gd_levels() -> list[str]:
    text = GD_SCALE.read_text(encoding="utf-8")
    block = re.search(r"const SCALE_LEVELS: Array\[String\] = \[(.*?)\]", text, re.S)
    assert block is not None
    return re.findall(r'"([^"]+)"', block.group(1))


def test_level_names_and_order_match() -> None:
    assert _gd_levels() == [level.value for level in ObserverScaleLevel]
    assert [profile.level.value for profile in OBSERVER_SCALE_PROFILES] == _gd_levels()


def test_thresholds_match_the_gdscript_client() -> None:
    expected = {
        ObserverScaleLevel.AGENT: (0, _gd_int("AGENT_MAX_POPULATION")),
        ObserverScaleLevel.COHORT: (
            _gd_int("COHORT_MIN_POPULATION"),
            _gd_int("COHORT_MAX_POPULATION"),
        ),
        ObserverScaleLevel.SETTLEMENT: (
            _gd_int("SETTLEMENT_MIN_POPULATION"),
            _gd_int("SETTLEMENT_MAX_POPULATION"),
        ),
        ObserverScaleLevel.REGION: (
            _gd_int("REGION_MIN_POPULATION"),
            _gd_int("REGION_MAX_POPULATION"),
        ),
        ObserverScaleLevel.CIVILIZATION: (
            _gd_int("CIVILIZATION_MIN_POPULATION"),
            None,
        ),
    }
    for level, (floor, ceiling) in expected.items():
        profile = scale_profile_for(level)
        assert profile.population_floor == floor, level
        assert profile.population_ceiling == ceiling, level


def test_level_boundaries_agree_with_gdscript_constants() -> None:
    assert select_scale_level(_gd_int("AGENT_MAX_POPULATION")) is (
        ObserverScaleLevel.AGENT
    )
    assert select_scale_level(_gd_int("COHORT_MIN_POPULATION")) is (
        ObserverScaleLevel.COHORT
    )
    assert select_scale_level(_gd_int("SETTLEMENT_MIN_POPULATION")) is (
        ObserverScaleLevel.SETTLEMENT
    )
    assert select_scale_level(_gd_int("REGION_MIN_POPULATION")) is (
        ObserverScaleLevel.REGION
    )
    assert select_scale_level(_gd_int("CIVILIZATION_MIN_POPULATION")) is (
        ObserverScaleLevel.CIVILIZATION
    )
    assert select_scale_level(20000) is ObserverScaleLevel.CIVILIZATION


def test_contract_version_and_protocol_constants_are_shared() -> None:
    text = GD_SCALE.read_text(encoding="utf-8")
    expected = f'const SCALE_CONTRACT_VERSION := "{OBSERVER_SCALE_CONTRACT_VERSION}"'
    assert expected in text

    models = GD_MODELS.read_text(encoding="utf-8")
    assert "const SUPPORTED_PROTOCOLS: Array[String] = [PROTOCOL_VERSION]" in models
    assert 'const RESERVED_PROTOCOL_VERSION := "observer-protocol-v2"' in models
    assert "SUPPORTED_PROTOCOLS.has(str(data[\"protocol_version\"]))" in models
