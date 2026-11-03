"""V4-07 completed-run metric assembly and collector wiring."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from analysis.disputes import harvest_dispute_rows
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from tests.unit.dispute_helpers import (
    OWNER,
    make_case,
    make_claim,
    make_ledger,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
COLLECTORS = ROOT / "src" / "experiments" / "collectors.py"


def _rows() -> Any:
    case = make_case(subject="bread")
    claim = make_claim(case=case, subject="bread")
    return harvest_dispute_rows((make_ledger(cases=(case,), claims=(claim,)),))


def _inputs(*, rows: Any | None) -> MetricComputationInputs:
    return MetricComputationInputs(
        run_id="run-dispute-metric-service",
        input_revision="revision-1",
        window_end=100,
        dispute_rows=rows,
        dispute_objective_rows=(),
    )


def test_completed_run_assembly_emits_three_documents() -> None:
    documents = assemble_metric_documents(_inputs(rows=_rows()))
    families = {document.metric_family: document for document in documents.documents}
    for family in (
        "dispute_claim_structure",
        "dispute_testimony_independence",
        "dispute_resolution_alignment",
    ):
        assert family in families
        assert families[family].values
        assert families[family].evidence_stages
        assert families[family].availability is MetricAvailability.PRESENT


def test_collector_carries_dispute_rows() -> None:
    tree = ast.parse(COLLECTORS.read_text(encoding="utf-8"))
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
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
    assert "dispute_ledgers" in constants or "dispute_ledgers" in names
    assert "dispute_rows" in keywords
    assert "dispute_objective_rows" in keywords


def test_missing_dispute_rows_leave_families_absent() -> None:
    documents = assemble_metric_documents(_inputs(rows=None))
    families = {document.metric_family for document in documents.documents}
    assert "dispute_claim_structure" not in families
    assert "dispute_testimony_independence" not in families
    assert "dispute_resolution_alignment" not in families
    assert (
        any(
            document.metric_family == "formal_rule_development"
            for document in documents.documents
        )
        is False
    )
    assert OWNER
