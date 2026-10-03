"""Matrix metric summary builder tests."""

from __future__ import annotations

import pytest

from analysis.evidence import EvidenceStage
from analysis.matrix_metric_summary import (
    MATRIX_METRIC_SUMMARY_SCHEMA_VERSION,
    MatrixMetricCellRef,
    build_matrix_metric_summary,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions


def _doc(family: str, values: dict[str, object], *, algo: str = "1") -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version=algo,
        library_versions=library_versions(),
        run_id="run-m",
        input_revision="rev-1",
        evidence_stages=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="test",
        denominator="test",
        coverage=None,
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="test", source_ids=(), notes_code="ok"
        ),
    )


def test_summary_across_seeds() -> None:
    cells = (
        MatrixMetricCellRef(
            cell_id="c1",
            condition_id="cond-a",
            group_role="treatment",
            seed=1,
            documents=(_doc("cooperation", {"coop_occurrence_rate": 0.2}),),
        ),
        MatrixMetricCellRef(
            cell_id="c2",
            condition_id="cond-a",
            group_role="treatment",
            seed=2,
            documents=(_doc("cooperation", {"coop_occurrence_rate": 0.4}),),
        ),
    )
    summary = build_matrix_metric_summary(cells)
    assert summary.schema_version == MATRIX_METRIC_SUMMARY_SCHEMA_VERSION
    assert len(summary.key_summaries) == 1
    key = summary.key_summaries[0]
    assert key.n == 2
    assert key.mean == 0.3
    assert key.cell_ids == ("c1", "c2")


def test_mixed_algorithm_version_fails() -> None:
    cells = (
        MatrixMetricCellRef(
            cell_id="c1",
            condition_id="cond-a",
            group_role="treatment",
            seed=1,
            documents=(_doc("cooperation", {"coop_occurrence_rate": 0.2}, algo="1"),),
        ),
        MatrixMetricCellRef(
            cell_id="c2",
            condition_id="cond-a",
            group_role="treatment",
            seed=2,
            documents=(_doc("cooperation", {"coop_occurrence_rate": 0.4}, algo="2"),),
        ),
    )
    with pytest.raises(ValueError, match="mixed_algorithm_version"):
        build_matrix_metric_summary(cells)


def test_missing_sidecars_contribute_nothing() -> None:
    summary = build_matrix_metric_summary(())
    assert summary.key_summaries == ()
