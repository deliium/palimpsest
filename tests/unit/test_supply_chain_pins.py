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


def test_catalog_pins_are_204() -> None:
    stale: list[str] = []
    for path in _test_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"==\s*198\b", text):
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


def test_owned_flag_count_is_seven() -> None:
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 7
    assert "supply_chains" in V4_OWNED_CAPABILITY_FLAGS
    assert METRIC_FAMILY_COUNT == 204
