"""Architecture gates: institution analysis stays detached and type-free."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_MODULES = (
    SRC / "analysis" / "institution_emergence.py",
    SRC / "analysis" / "institutional_persistence.py",
)


def test_analysis_modules_exist_and_import_no_cognition_runtime_or_persistence() -> (
    None
):
    for module in _MODULES:
        assert module.is_file()
        hits = _module_imports_forbidden(
            module,
            (
                "agents.cognition",
                "agents.cognition.institution_concepts",
                "simulation",
                "experiments",
                "infrastructure",
                "persistence",
            ),
        )
        assert hits == []


def test_analysis_modules_carry_no_subjective_ledger_types() -> None:
    for module in _MODULES:
        text = module.read_text(encoding="utf-8")
        for forbidden in (
            "InstitutionConceptLedger(",
            "InstitutionConcept(",
            "WorldState",
            "WorldEvent",
        ):
            assert forbidden not in text


def test_cognition_does_not_import_analysis() -> None:
    hits: list[str] = []
    for path in (SRC / "agents").rglob("*.py"):
        hits.extend(_module_imports_forbidden(path, ("analysis",)))
    assert hits == []
