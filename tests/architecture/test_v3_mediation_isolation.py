"""Architecture gates: mediation stays subjective, optional, and detached."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_MEDIATION = SRC / "agents" / "cognition" / "mediation.py"
_COMMUNICATION = SRC / "agents" / "cognition" / "mediation_communication.py"
_ACTIONS = SRC / "agents" / "cognition" / "mediation_actions.py"
_ANALYSIS = SRC / "analysis" / "mediation.py"


def test_cognition_modules_import_no_objective_or_analysis_authority() -> None:
    for path in (_MEDIATION, _COMMUNICATION, _ACTIONS):
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


def test_no_court_verdict_or_global_registry_exists() -> None:
    text = _MEDIATION.read_text(encoding="utf-8")
    for forbidden in (
        "class MediationRegistry",
        "def force_transfer",
        "class Judge",
        "forced_transfer(",
    ):
        assert forbidden not in text


def test_forbidden_contract_field_names_are_declared() -> None:
    from agents.cognition.mediation import FORBIDDEN_MEDIATION_FIELD_NAMES

    for name in ("verdict", "binding", "court", "dispute_registry"):
        assert name in FORBIDDEN_MEDIATION_FIELD_NAMES


def test_restitution_compiles_only_existing_give_command() -> None:
    text = _ACTIONS.read_text(encoding="utf-8")
    assert "Give(" in text
    assert "Feed(" not in text
    assert "require_agent_command" not in text


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


def test_analysis_never_feeds_runtime() -> None:
    text = _ANALYSIS.read_text(encoding="utf-8")
    for forbidden in (
        "apply_mediation_update",
        "AgentCommand",
        "SimulationRunner",
    ):
        assert forbidden not in text
