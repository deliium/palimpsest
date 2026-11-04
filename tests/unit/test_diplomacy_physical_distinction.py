"""V4-10 diplomacy never becomes world authority."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"


def test_world_and_engine_never_read_the_diplomacy_ledger() -> None:
    for path in sorted((_SRC / "world").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "agents.cognition.diplomacy" not in source
        assert "DiplomacyLedger" not in source
    engine = (_SRC / "simulation" / "engine.py").read_text(encoding="utf-8")
    assert "agents.cognition.diplomacy" not in engine
    assert "DiplomacyLedger" not in engine


def test_diplomacy_helpers_never_construct_a_command() -> None:
    for path in sorted((_SRC / "agents" / "cognition").glob("diplomacy*.py")):
        source = path.read_text(encoding="utf-8")
        assert "AgentCommand(" not in source
        assert "ActionSubmission(" not in source


def test_contested_agreement_grants_no_physical_access() -> None:
    source = (_SRC / "agents" / "cognition" / "diplomacy.py").read_text(
        encoding="utf-8"
    )
    assert "move_item(" not in source
    assert "holder_id =" not in source
    assert "admit(" not in source
