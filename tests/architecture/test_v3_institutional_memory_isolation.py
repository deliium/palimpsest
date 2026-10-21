"""Institutional memory remains cognition-owned and cannot read private authority."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path("src/agents/cognition")
_FILES = (
    _ROOT / "institutional_memory.py",
    _ROOT / "institutional_memory_frames.py",
    _ROOT / "institutional_memory_actions.py",
)
_FORBIDDEN = (
    "world._state",
    "world.events",
    "analysis",
    "infrastructure",
    "simulation.engine",
)


def test_new_modules_do_not_import_private_authority() -> None:
    for path in _FILES:
        source = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN:
            assert f"import {token}" not in source
            assert f"from {token}" not in source


def test_public_exports_are_deliberate() -> None:
    from agents.cognition import (
        InstitutionalMemoryLedger,
        InstitutionalMemorySelection,
        InstitutionalMemoryUse,
    )

    assert InstitutionalMemoryLedger.__module__.startswith("agents.cognition")
    assert InstitutionalMemorySelection.__module__.startswith("agents.cognition")
    assert InstitutionalMemoryUse.__module__.startswith("agents.cognition")
