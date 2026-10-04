"""Godot↔Python observer protocol / layout identity mirror pin."""

from __future__ import annotations

import re
from pathlib import Path

from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION, OBSERVER_PROTOCOL_VERSION
from simulation.compatibility import (
    OBSERVER_LAYOUT_SCHEMA_VERSION as compat_layout,
)
from simulation.compatibility import (
    OBSERVER_PROTOCOL_VERSION as compat_protocol,
)

ROOT = Path(__file__).resolve().parents[2]
MODELS_GD = (
    ROOT / "clients" / "godot-observer" / "scripts" / "protocol" / "models.gd"
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


def test_version_payload_source_has_no_v3_capability_fields() -> None:
    """Non-goal: GET /version must not grow V3 capability fields in scaffolding."""
    source = (
        ROOT / "src" / "api" / "presentation_static.py"
    ).read_text(encoding="utf-8")
    # Locked application/protocol/export/revision/research_ui keys only.
    assert '"protocol_version"' in source
    assert '"research_ui_configured"' in source
    for forbidden in (
        "v3_capability_flags",
        "generational_population",
        "kinship_inheritance",
        "multi_polity_migration",
        "institutional_economy",
        "cultural_historical_memory",
    ):
        assert forbidden not in source
