"""Possession succession analysis stays out of the objective fold."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_FORBIDDEN = (
    "analysis.possession_succession",
    "analysis.possession_succession_metrics",
)


@pytest.mark.parametrize(
    "package",
    ["world", "agents", "api", "simulation", "persistence"],
)
def test_package_does_not_import_possession_succession(package: str) -> None:
    hits: list[str] = []
    for path in (SRC / package).rglob("*.py"):
        hits.extend(_module_imports_forbidden(path, _FORBIDDEN))
    assert hits == []
