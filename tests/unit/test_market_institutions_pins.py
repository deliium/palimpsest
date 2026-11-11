"""Suite-wide V4-20 ownership, catalog, and stale-pin truth."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
SRC = ROOT / "src"


def _test_files() -> list[Path]:
    return [
        path for path in sorted(TESTS.rglob("*.py")) if "__pycache__" not in path.parts
    ]


def test_catalog_is_208() -> None:
    assert METRIC_FAMILY_COUNT == 208


def test_owned_flags_are_eight() -> None:
    assert V4_OWNED_CAPABILITY_FLAGS == frozenset(
        {
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
            "supply_chains",
            "markets_credit",
        }
    )


def test_no_stale_204_catalog_pin_remains() -> None:
    stale = [
        str(path.relative_to(ROOT))
        for path in _test_files()
        if re.search(r"==\s*204\b", path.read_text(encoding="utf-8"))
    ]
    assert stale == []


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


def test_no_runner_config_v57_in_source() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in SRC.rglob("*")
        if path.suffix in {".py", ".md", ".json", ".yaml"}
        and "__pycache__" not in path.parts
        and "runner-config-v57" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == []
