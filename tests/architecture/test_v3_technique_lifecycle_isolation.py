"""Technique lifecycle stays out of world, agents, api, simulation, persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_FORBIDDEN = ("analysis.technique_lifecycle", "analysis.technique_lifecycle_metrics")


@pytest.mark.parametrize(
    "package",
    ["world", "agents", "api", "simulation", "persistence"],
)
def test_package_does_not_import_technique_lifecycle(package: str) -> None:
    hits: list[str] = []
    for path in (SRC / package).rglob("*.py"):
        hits.extend(_module_imports_forbidden(path, _FORBIDDEN))
    assert hits == []
