# mypy: ignore-errors

"""Competing-theory layers keep authority, import and command boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

import agents.cognition as cognition
from agents.cognition import competing_theories as contracts
from agents.cognition import competing_theory_communication as communication
from agents.cognition import competing_theory_forecasts as forecasts
from agents.cognition import competing_theory_policy as policy

pytestmark = pytest.mark.architecture

_SRC = Path(__file__).resolve().parents[2] / "src"


def _text(relative: str) -> str:
    return (_SRC / relative).read_text(encoding="utf-8")


def test_cognition_theory_modules_import_no_authority() -> None:
    for module in (contracts, forecasts, communication, policy):
        filename = module.__file__
        assert filename is not None
        source = Path(filename).read_text(encoding="utf-8")
        for forbidden in (
            "world._",
            "simulation",
            "analysis",
            "persistence",
            "infrastructure",
            "api",
        ):
            assert forbidden not in source, (module.__name__, forbidden)


def test_theory_modules_create_no_world_command() -> None:
    for module in (contracts, forecasts, communication, policy):
        filename = module.__file__
        assert filename is not None
        source = Path(filename).read_text(encoding="utf-8")
        for forbidden in (
            "AgentCommand(",
            "ActionSubmission(",
            "WorldEngine",
            "WorldState",
        ):
            assert forbidden not in source, (module.__name__, forbidden)


def test_checkpoint_codec_imports_no_analysis_or_api() -> None:
    source = _text("simulation/competing_theory_checkpoint.py")
    for forbidden in (
        "analysis",
        "experiments",
        "persistence",
        "infrastructure",
        "api",
    ):
        assert forbidden not in source, forbidden


def test_facade_exports_theory_contracts() -> None:
    for name in (
        "CompetingTheoryLedger",
        "TheoryClaim",
        "TheoryContext",
        "advance_competing_theories",
        "issue_theory_case",
        "settle_theory_case",
    ):
        assert hasattr(cognition, name), name
