"""Detached accounting analysis object tests."""

# mypy: ignore-errors

from __future__ import annotations

from analysis.accounting_ledgers_analysis import (
    ACCOUNTING_LEDGERS_COVERAGE_KEYS,
    AccountingLedgersAnalysis,
    accounting_ledgers_analysis_digest,
    empty_accounting_ledgers_analysis,
    harvest_accounting_ledgers_analysis,
)
from analysis.accounting_ledgers_contract import AccountingCoverage
from tests.unit.test_accounting_ledgers_events import _talked


def test_empty_analysis_has_all_families_missing_and_stable_digest() -> None:
    analysis = empty_accounting_ledgers_analysis("run-1")
    assert type(analysis) is AccountingLedgersAnalysis
    assert set(analysis.coverage) == set(ACCOUNTING_LEDGERS_COVERAGE_KEYS)
    assert all(
        value is AccountingCoverage.MISSING for value in analysis.coverage.values()
    )
    assert analysis.truncated is False
    assert analysis.digest == accounting_ledgers_analysis_digest(analysis)
    assert empty_accounting_ledgers_analysis("run-1") == analysis


def test_complete_analysis_and_coverage() -> None:
    analysis = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=(_talked("ev-a", tick=1),)
    )
    assert analysis.entries
    assert analysis.records == ()
    assert analysis.coverage["entries"] is AccountingCoverage.COMPLETE
    assert analysis.coverage["records"] is AccountingCoverage.MISSING
    assert analysis.truncated is False
    assert len(analysis.digest) == 64


def test_digest_is_stable_under_permutation() -> None:
    first = harvest_accounting_ledgers_analysis(
        run_id="run-1",
        events=(_talked("ev-a", tick=1), _talked("ev-b", tick=2, sequence=1)),
    )
    second = harvest_accounting_ledgers_analysis(
        run_id="run-1",
        events=(_talked("ev-b", tick=2, sequence=1), _talked("ev-a", tick=1)),
    )
    assert first.digest == second.digest


def test_no_world_or_simulation_import() -> None:
    import ast
    from pathlib import Path

    tree = ast.parse(
        Path("src/analysis/accounting_ledgers_analysis.py").read_text()
    )
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert not any(module.startswith(("world", "simulation")) for module in modules)
