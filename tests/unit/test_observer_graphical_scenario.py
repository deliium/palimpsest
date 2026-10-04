"""Python proofs for observer-graphical-v2 scenario and fixture checklist."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.observer_graphical_scenario import (
    OBSERVER_GRAPHICAL_SCENARIO_ID,
    OBSERVER_GRAPHICAL_SEEK_HIGH_WATER,
    REQUIRED_FIXTURE_EVENT_TYPES,
    REQUIRED_GRAPHICAL_FEATURES,
    build_observer_graphical_scenario,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "clients"
    / "godot-observer"
    / "fixtures"
    / "smoke"
    / "observer_graphical_v2.json"
)
V1_GATE = ROOT / "tests" / "unit" / "test_v1_regression_gate.py"


def test_observer_graphical_builder_covers_required_features() -> None:
    bundle = build_observer_graphical_scenario(max_ticks=16)
    assert bundle.scenario_id == OBSERVER_GRAPHICAL_SCENARIO_ID
    assert len(bundle.config.agents) >= 5
    assert len(bundle.config.scenario.locations) >= 2
    assert bundle.config.scenario.resources
    assert bundle.config.environmental_dynamics is not None
    assert bundle.config.artifacts_enabled is True
    assert bundle.config.scenario.artifacts
    assert bundle.reference.death_tick >= 0
    assert set(REQUIRED_GRAPHICAL_FEATURES) <= set(bundle.features)
    assert bundle.seek_high_water >= OBSERVER_GRAPHICAL_SEEK_HIGH_WATER


def test_observer_graphical_fixture_lists_required_event_types() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert document["scenario_id"] == OBSERVER_GRAPHICAL_SCENARIO_ID
    assert int(document["seek_high_water"]) >= 1000
    assert int(document["cursor_high_water"]["tick"]) >= 1000
    stems = {
        Path(str(path)).stem
        for path in document["events"]
    }
    assert set(REQUIRED_FIXTURE_EVENT_TYPES) <= stems
    for feature in REQUIRED_GRAPHICAL_FEATURES:
        assert feature in document["features"]


def test_observer_graphical_stays_off_v1_gate() -> None:
    source = V1_GATE.read_text(encoding="utf-8")
    assert "observer-graphical-v2" not in source
    assert "observer_graphical_scenario" not in source
