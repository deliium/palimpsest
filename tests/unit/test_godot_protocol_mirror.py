"""Godot↔Python observer protocol / layout identity mirror pin."""

from __future__ import annotations

import re
from pathlib import Path

from analysis.civilization_overlays import CIVILIZATION_OVERLAYS_POLICY_VERSION
from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION, OBSERVER_PROTOCOL_VERSION
from simulation.civilization_models import (
    CIVILIZATION_CATALOGUE_SCHEMA,
    CIVILIZATION_MAP_SCHEMA,
    CIVILIZATION_MARKERS_SCHEMA,
    CIVILIZATION_OVERLAY_SCHEMA,
    CivilizationMarkerType,
)
from simulation.compatibility import (
    OBSERVER_LAYOUT_SCHEMA_VERSION as compat_layout,
)
from simulation.compatibility import (
    OBSERVER_PROTOCOL_VERSION as compat_protocol,
)

ROOT = Path(__file__).resolve().parents[2]
MODELS_GD = ROOT / "clients" / "godot-observer" / "scripts" / "protocol" / "models.gd"
CIVILIZATION_GD = (
    ROOT / "clients" / "godot-observer" / "scripts" / "protocol" / "civilization.gd"
)


def _gd_const(name: str) -> str:
    text = MODELS_GD.read_text(encoding="utf-8")
    match = re.search(
        rf'const\s+{re.escape(name)}\s*:=\s*"([^"]+)"',
        text,
    )
    assert match is not None, f"missing const {name} in {MODELS_GD}"
    return match.group(1)


def test_godot_protocol_and_layout_mirror_python() -> None:
    assert MODELS_GD.is_file()
    assert _gd_const("PROTOCOL_VERSION") == OBSERVER_PROTOCOL_VERSION
    assert _gd_const("LAYOUT_SCHEMA_VERSION") == OBSERVER_LAYOUT_SCHEMA_VERSION
    assert OBSERVER_PROTOCOL_VERSION == compat_protocol == "observer-protocol-v1"
    assert OBSERVER_LAYOUT_SCHEMA_VERSION == compat_layout == "observer-layout-v1"


def test_version_payload_has_no_capability_flag_payloads() -> None:
    """`GET /version` advertises metadata only, never capability-flag values.

    Protocol, layout, and capability *names* are additive advisory metadata.
    Capability-flag values, configuration payloads, and run content must never
    appear on this unauthenticated endpoint.
    """
    source = (ROOT / "src" / "api" / "presentation_static.py").read_text(
        encoding="utf-8"
    )
    for allowed in (
        '"protocol_version"',
        '"research_ui_configured"',
        '"supported_observer_protocols"',
        '"observer_layout_version"',
        '"observer_capabilities"',
        '"observer_reserved_capabilities"',
    ):
        assert allowed in source
    for forbidden in (
        "v3_capability_flags",
        "v4_capability_flags",
        "generational_population",
        "kinship_inheritance",
        "multi_polity_migration",
        "institutional_economy",
        "cultural_historical_memory",
        "organizations",
        "formal_rules",
        "legal_disputes",
        "diplomacy",
        "organized_conflict",
        "infrastructure_networks",
        "supply_chains",
        "markets_credit",
        "science",
        "epidemics",
        "ecological_feedback",
        "disasters",
    ):
        assert forbidden not in source


def test_civilization_schema_and_marker_mirror_python() -> None:
    text = CIVILIZATION_GD.read_text(encoding="utf-8")
    expected = {
        "MAP_SCHEMA": CIVILIZATION_MAP_SCHEMA,
        "CATALOGUE_SCHEMA": CIVILIZATION_CATALOGUE_SCHEMA,
        "OVERLAY_SCHEMA": CIVILIZATION_OVERLAY_SCHEMA,
        "MARKERS_SCHEMA": CIVILIZATION_MARKERS_SCHEMA,
    }
    for name, value in expected.items():
        match = re.search(rf'const\s+{name}\s*:=\s*"([^"]+)"', text)
        assert match is not None and match.group(1) == value
    marker_block = re.search(
        r"const MARKER_TYPES := \{(?P<body>.*?)\n\}", text, re.DOTALL
    )
    assert marker_block is not None
    pairs = dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', marker_block.group("body")))
    assert pairs == {
        marker.value: {
            CivilizationMarkerType.SETTLEMENT_ACTIVATED: "settlements",
            CivilizationMarkerType.SETTLEMENT_DEACTIVATED: "settlements",
            CivilizationMarkerType.JOURNEY_STARTED: "migration",
            CivilizationMarkerType.JOURNEY_ARRIVED: "migration",
            CivilizationMarkerType.JOURNEY_ENDED: "migration",
            CivilizationMarkerType.TECHNOLOGY_ACQUIRED: "technology",
            CivilizationMarkerType.INSTITUTION_TRANSITION: "institutions",
        }[marker]
        for marker in CivilizationMarkerType
    }
    assert CIVILIZATION_OVERLAYS_POLICY_VERSION == "civilization-overlays.v1"


def test_civilization_client_caps_remain_bounded() -> None:
    source = (
        ROOT
        / "clients"
        / "godot-observer"
        / "scripts"
        / "net"
        / "civilization_source.gd"
    ).read_text(encoding="utf-8")
    assert "const MAX_MARKERS := 200" in source
    assert "const MAX_MARKER_PAGES := 8" in source
    assert "const MAX_MARKER_WINDOWS := 4" in source
    assert "const MAX_INFLIGHT := 2" in source
    timeline = (
        ROOT
        / "clients"
        / "godot-observer"
        / "scripts"
        / "ui"
        / "civilization_timeline.gd"
    ).read_text(encoding="utf-8")
    assert "const MAX_MARKERS := 200" in timeline
    assert "const MAX_WINDOWS := 4" in timeline
