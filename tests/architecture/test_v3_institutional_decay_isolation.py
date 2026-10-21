"""Institutional decay and lifecycle analysis stay on their side of authority."""

from __future__ import annotations

from pathlib import Path

_COGNITION = Path("src/agents/cognition/institutional_decay.py")
_ANALYSIS = (
    Path("src/analysis/institutional_decay.py"),
    Path("src/analysis/institution_lineage.py"),
    Path("src/analysis/institutional_decay_metrics.py"),
)
_FORBIDDEN_COGNITION = (
    "world._state",
    "world.events",
    "analysis",
    "infrastructure",
    "simulation.engine",
    "fastapi",
    "sqlalchemy",
)
_FORBIDDEN_ANALYSIS = (
    "agents.cognition.configuration",
    "agents.cognition.loop",
    "simulation.engine",
    "simulation.runner",
    "persistence",
    "infrastructure",
    "api",
)


def test_decay_cognition_does_not_import_private_authority_or_analysis() -> None:
    source = _COGNITION.read_text(encoding="utf-8")
    for token in _FORBIDDEN_COGNITION:
        assert f"import {token}" not in source
        assert f"from {token}" not in source


def test_analysis_modules_do_not_import_live_cognition_or_outer_adapters() -> None:
    for path in _ANALYSIS:
        source = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_ANALYSIS:
            assert f"import {token}" not in source
            assert f"from {token}" not in source


def test_decay_state_is_not_an_objective_registry() -> None:
    from agents.cognition.institutional_decay import (
        FORBIDDEN_INSTITUTION_DECAY_FIELD_NAMES,
        InstitutionDecayLedger,
    )

    assert "institution_id" in FORBIDDEN_INSTITUTION_DECAY_FIELD_NAMES
    assert not hasattr(InstitutionDecayLedger, "collapse")
