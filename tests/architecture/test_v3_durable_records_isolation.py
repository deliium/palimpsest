"""Durable-record analysis must not bind cognition or private world authority."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_cognition_does_not_import_durable_record_metrics() -> None:
    hits: list[str] = []
    for path in (SRC / "agents" / "cognition").rglob("*.py"):
        hits.extend(
            _module_imports_forbidden(path, ("analysis.durable_record_metrics",))
        )
    assert hits == []


def test_durable_metrics_avoid_private_world_and_cognition() -> None:
    path = SRC / "analysis" / "durable_record_metrics.py"
    text = path.read_text(encoding="utf-8")
    assert "agents.cognition" not in text
    assert "from world._" not in text
    assert "import world._" not in text
    assert "from world.artifacts" not in text
    hits = _module_imports_forbidden(
        path, ("agents.cognition", "world._operations", "world._state")
    )
    assert hits == []


def test_api_does_not_import_analysis_durable_metrics() -> None:
    hits: list[str] = []
    for path in (SRC / "api").rglob("*.py"):
        hits.extend(
            _module_imports_forbidden(path, ("analysis.durable_record_metrics",))
        )
    assert hits == []
