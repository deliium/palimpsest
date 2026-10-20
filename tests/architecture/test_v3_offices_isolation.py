"""Architecture gates: offices stay subjective and analysis stays detached."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_OFFICES = SRC / "agents" / "cognition" / "offices.py"
_ANALYSIS = SRC / "analysis" / "offices.py"


def test_office_module_exists_and_imports_no_analysis_or_persistence() -> None:
    assert _OFFICES.is_file()
    hits = _module_imports_forbidden(
        _OFFICES,
        ("analysis", "experiments", "infrastructure", "persistence", "simulation"),
    )
    assert hits == []


def test_office_module_has_no_objective_registry_or_world_authority() -> None:
    text = _OFFICES.read_text(encoding="utf-8")
    for forbidden in (
        "OfficeRegistry",
        "office_registry",
        "legitimacy_registry",
        "enforce_authority",
    ):
        assert forbidden not in text


def test_cognition_does_not_import_analysis_for_offices() -> None:
    hits: list[str] = []
    for path in (SRC / "agents").rglob("*.py"):
        hits.extend(_module_imports_forbidden(path, ("analysis",)))
    assert hits == []


def test_analysis_office_module_when_present_does_not_import_runtime() -> None:
    if not _ANALYSIS.is_file():
        pytest.skip("analysis offices module not added yet")
    hits = _module_imports_forbidden(
        _ANALYSIS,
        (
            "agents.cognition",
            "simulation",
            "experiments",
            "infrastructure",
            "persistence",
        ),
    )
    assert hits == []
