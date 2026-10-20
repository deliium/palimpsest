"""Architecture gates: collective decisions stay subjective and detached."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_DECISIONS = SRC / "agents" / "cognition" / "collective_decisions.py"
_COMMUNICATION = SRC / "agents" / "cognition" / "collective_decision_communication.py"
_ANALYSIS = SRC / "analysis" / "collective_decisions.py"


def test_cognition_module_imports_no_objective_or_analysis_authority() -> None:
    for path in (_DECISIONS, _COMMUNICATION):
        assert path.is_file()
        hits = _module_imports_forbidden(
            path,
            (
                "analysis",
                "experiments",
                "infrastructure",
                "persistence",
                "simulation",
                "world.events",
                "world.store",
            ),
        )
        assert hits == []


def test_cognition_module_has_no_registry_or_coercive_politics() -> None:
    text = _DECISIONS.read_text(encoding="utf-8")
    for forbidden in (
        "DecisionRegistry",
        "decision_registry",
        "canonical_electorate",
        "binding_majority",
        "vote_tally",
        "enforce_decision",
    ):
        assert forbidden not in text


def test_analysis_module_does_not_import_runtime_or_cognition() -> None:
    assert _ANALYSIS.is_file()
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


def test_analysis_module_never_feeds_runtime_decisions() -> None:
    text = _ANALYSIS.read_text(encoding="utf-8")
    for forbidden in (
        "apply_collective_decision_update",
        "AgentCommand",
        "SimulationRunner",
    ):
        assert forbidden not in text
