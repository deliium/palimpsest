# mypy: ignore-errors
"""Collector gate for scientific-hypothesis analysis injection."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTORS = ROOT / "src" / "experiments" / "collectors.py"


def test_collector_carries_the_science_gate_and_injection() -> None:
    tree = ast.parse(COLLECTORS.read_text(encoding="utf-8"))
    constants = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    keywords = {
        node.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword) and node.arg is not None
    }
    assert "science" in constants
    assert "experiment_ledgers" in constants
    assert "scientific_hypotheses_analysis" in keywords
    assert any(
        isinstance(value, str)
        and "scientific_hypotheses_collection_failed" in value
        for value in constants
    )


def test_collector_imports_the_builder_lazily() -> None:
    text = COLLECTORS.read_text(encoding="utf-8")
    assert "build_completed_run_scientific_hypotheses_analysis" in text
    assert "scientific_hypotheses_collector_disabled" in text
