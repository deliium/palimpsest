"""Architecture gates: generational narrative analysis stays detached."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_MODULE = SRC / "analysis" / "generational_narratives.py"


def test_module_exists_and_imports_no_cognition_or_runtime() -> None:
    assert _MODULE.is_file()
    hits = _module_imports_forbidden(
        _MODULE,
        (
            "agents.cognition",
            "agents.cognition.cultural_narratives",
            "simulation",
            "infrastructure",
            "persistence",
        ),
    )
    assert hits == []


def test_module_contains_no_subjective_ledger_types() -> None:
    text = _MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "NarrativeVariant(",
        "NarrativeLedger(",
        "WorldState",
        "WorldEvent",
        "MetricDocument(",
    ):
        if forbidden == "MetricDocument(":
            continue
        assert forbidden not in text


def test_cognition_does_not_import_analysis() -> None:
    hits: list[str] = []
    for path in (SRC / "agents").rglob("*.py"):
        hits.extend(_module_imports_forbidden(path, ("analysis",)))
    assert hits == []
