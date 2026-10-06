"""Dual-representation boundary: subjective cognition vs analytical traits."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_analytical_cultural_modules_not_imported_by_cognition() -> None:
    hits: list[str] = []
    for path in (SRC / "agents" / "cognition").rglob("*.py"):
        hits.extend(_module_imports_forbidden(path, ("analysis",)))
    assert hits == []


def test_analysis_does_not_import_subjective_cultural_belief_type() -> None:
    hits: list[str] = []
    for path in (SRC / "analysis").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "SubjectiveCulturalBelief" not in text
        assert "CulturalFeatureLedger" not in text
        hits.extend(
            _module_imports_forbidden(path, ("agents.cognition.cultural_features",))
        )
    assert hits == []
