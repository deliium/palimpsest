"""Bounded experimentation must not leak law tables into cognition or llm."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_analysis_isolation import _module_imports_forbidden

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_cognition_and_llm_do_not_import_experiment_laws() -> None:
    hits: list[str] = []
    for folder in ("agents/cognition", "llm"):
        for path in (SRC / folder).rglob("*.py"):
            hits.extend(
                _module_imports_forbidden(path, ("world._experiment_laws",))
            )
    assert hits == []
