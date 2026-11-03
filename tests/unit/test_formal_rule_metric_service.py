"""V4-06 completed-run metric assembly and collector wiring."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from analysis import specifications
from analysis.formal_rules import harvest_formal_rule_rows
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.specifications import MetricSpecificationError
from tests.unit.formal_rule_helpers import make_ledger

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
COLLECTORS = ROOT / "src" / "experiments" / "collectors.py"


def _inputs() -> Any:
    rows = harvest_formal_rule_rows(
        [make_ledger(ticks=(0, 100))], window_ticks=100
    )
    return MetricComputationInputs(
        run_id="run-formal-rule-metric-service",
        input_revision="revision-1",
        window_end=100,
        formal_rule_rows=rows,
    )


def test_completed_run_inputs_emit_all_three_documents() -> None:
    documents = assemble_metric_documents(_inputs())
    families = {
        document.metric_family: document for document in documents.documents
    }
    for family in (
        "formal_rule_development",
        "formal_rule_authority",
        "formal_rule_response",
    ):
        assert family in families
        assert families[family].values
        assert families[family].evidence_stages


def test_collector_carries_formal_rule_ledgers() -> None:
    tree = ast.parse(COLLECTORS.read_text(encoding="utf-8"))
    names = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
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
    assert "formal_rule_ledgers" in constants or "formal_rule_ledgers" in names
    assert "formal_rule_rows" in keywords


def test_metric_service_rejects_catalog_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(specifications, "METRIC_FAMILY_COUNT", 150)
    with pytest.raises(MetricSpecificationError):
        specifications.validate_metric_catalog()
