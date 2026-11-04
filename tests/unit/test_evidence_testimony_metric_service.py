"""V4-08 completed-run metric assembly and collector wiring."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from analysis.evidence_testimony_rows import harvest_evidence_rows
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from tests.unit.evidence_testimony_helpers import make_parts

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
COLLECTORS = ROOT / "src" / "experiments" / "collectors.py"


def _rows() -> Any:
    return harvest_evidence_rows((make_parts().ledger(),))


def _inputs(*, rows: Any | None) -> MetricComputationInputs:
    return MetricComputationInputs(
        run_id="run-evidence-metric-service",
        input_revision="revision-1",
        window_end=100,
        evidence_rows=rows,
        evidence_objective_rows=(),
    )


def test_completed_run_assembly_emits_three_documents() -> None:
    documents = assemble_metric_documents(_inputs(rows=_rows()))
    families = {document.metric_family: document for document in documents.documents}
    for family in (
        "evidence_source_structure",
        "evidence_provenance_continuity",
        "evidence_objective_alignment",
    ):
        assert family in families
        assert families[family].values
        assert families[family].evidence_stages
        assert families[family].availability is MetricAvailability.PRESENT


def test_collector_carries_evidence_rows() -> None:
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
    assert "evidence_ledgers" in constants
    assert "evidence_rows" in keywords
    assert "evidence_objective_rows" in keywords


def test_missing_evidence_rows_leave_families_absent() -> None:
    documents = assemble_metric_documents(_inputs(rows=None))
    families = {document.metric_family for document in documents.documents}
    assert "evidence_source_structure" not in families
    assert "evidence_provenance_continuity" not in families
    assert "evidence_objective_alignment" not in families


def test_objective_anchors_align_completed_run_assembly() -> None:
    from dataclasses import dataclass

    from analysis.evidence_testimony_objective import (
        evidence_objective_anchor_rows_from_events,
    )

    @dataclass(frozen=True)
    class _Entity:
        value: str

    @dataclass(frozen=True)
    class _Event:
        details: object
        tick: int
        event_id: _Entity

    class ArtifactCreated:
        artifact_id = "artifact-1"
        author_id = _Entity("agent-1")

    anchors = evidence_objective_anchor_rows_from_events(
        (_Event(ArtifactCreated(), 1, _Entity("event-1")),), {}
    )
    inputs = MetricComputationInputs(
        run_id="run-evidence-aligned",
        input_revision="revision-1",
        window_end=100,
        evidence_rows=_rows(),
        evidence_objective_rows=anchors,
    )
    documents = assemble_metric_documents(inputs)
    families = {document.metric_family: document for document in documents.documents}
    alignment = families["evidence_objective_alignment"]
    assert alignment.values["consistent_count"] == 1
    assert alignment.values["consistency_ratio"] == 1.0
