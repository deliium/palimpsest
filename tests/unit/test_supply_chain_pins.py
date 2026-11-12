# mypy: ignore-errors

"""Suite-wide pins stay truthful after V4-19 ownership and catalog growth."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"


def _test_files() -> list[Path]:
    return [
        path for path in sorted(TESTS.rglob("*.py")) if "__pycache__" not in path.parts
    ]


def test_no_stale_current_catalog_pin_remains() -> None:
    stale: list[str] = []
    for path in _test_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"==\s*208\b", text):
            stale.append(str(path.relative_to(ROOT)))
    assert stale == []


def test_no_test_expects_supply_chains_unimplemented() -> None:
    offenders: list[str] = []
    pattern = re.compile(r"V4CapabilityFlags\([^)]*supply_chains\s*=\s*True[^)]*\)")
    for path in _test_files():
        if path.name.startswith("test_supply_chain"):
            continue
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            window = text[max(0, match.start() - 400) : match.end() + 400]
            if "unimplemented" in window or "CAPABILITY_UNIMPLEMENTED" in window:
                offenders.append(f"{path.relative_to(ROOT)}:{match.start()}")
    assert offenders == []


def test_no_test_expects_markets_credit_unimplemented() -> None:
    offenders: list[str] = []
    pattern = re.compile(r"V4CapabilityFlags\([^)]*markets_credit\s*=\s*True[^)]*\)")
    for path in _test_files():
        if path.name.startswith("test_market_institutions"):
            continue
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            window = text[max(0, match.start() - 400) : match.end() + 400]
            if "unimplemented" in window or "CAPABILITY_UNIMPLEMENTED" in window:
                offenders.append(f"{path.relative_to(ROOT)}:{match.start()}")
    assert offenders == []


def test_owned_flag_count_is_eight() -> None:
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 8
    assert "supply_chains" in V4_OWNED_CAPABILITY_FLAGS
    assert "markets_credit" in V4_OWNED_CAPABILITY_FLAGS
    assert METRIC_FAMILY_COUNT == 212
