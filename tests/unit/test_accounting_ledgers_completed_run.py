"""Completed-run accounting bridge tests."""

# mypy: ignore-errors

from __future__ import annotations

from experiments.accounting_ledgers_completed_run import (
    build_completed_run_accounting_ledgers_analysis,
)
from tests.unit.test_accounting_ledgers_events import _talked


def test_build_completed_run_analysis_does_not_mutate_status() -> None:
    analysis = build_completed_run_accounting_ledgers_analysis(
        run_id="run-1", events=(_talked("ev-a", tick=1),)
    )
    assert analysis.run_id == "run-1"
    assert analysis.entries


def test_empty_completed_run_returns_missing_coverage() -> None:
    analysis = build_completed_run_accounting_ledgers_analysis(
        run_id="run-1", events=()
    )
    assert analysis.coverage["entries"].value == "missing"
    assert analysis.entries == ()
