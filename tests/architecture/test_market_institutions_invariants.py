"""V4-20 architecture invariants: no new schema, command, or authority."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    V4CapabilityFlags,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_v4_20_owns_markets_credit_without_v57() -> None:
    assert V4CapabilityFlags(markets_credit=True).owned_enabled_names() == (
        "markets_credit",
    )
    assert "markets_credit" in V4_OWNED_CAPABILITY_FLAGS
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert not list(SRC.rglob("*v57*"))


def test_market_modules_exist_and_own_no_world_event() -> None:
    expected = (
        SRC / "agents/cognition/market_institutions.py",
        SRC / "analysis/market_institutions_analysis.py",
        SRC / "simulation/market_institutions_models.py",
        SRC / "api/routes/market_institutions.py",
    )
    for path in expected:
        assert path.is_file(), path
    for path in SRC.glob("agents/cognition/market_institutions*.py"):
        text = path.read_text(encoding="utf-8")
        assert "class WorldEvent" not in text
        assert "class AgentCommand" not in text


def test_catalog_and_pins() -> None:
    assert METRIC_FAMILY_COUNT == 212
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 8
