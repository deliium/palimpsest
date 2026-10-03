"""Matrix metric sidecar persistence tests."""

from __future__ import annotations

from pathlib import Path

from analysis.evidence import EvidenceStage
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from experiments.matrix_manifest import FilesystemMatrixManifestStore


def _doc() -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family="cooperation",
        algorithm_version="1",
        library_versions=library_versions(),
        run_id="run-side",
        input_revision="rev-1",
        evidence_stages=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="test",
        denominator="test",
        coverage=None,
        availability=MetricAvailability.PRESENT,
        values={"coop_occurrence_rate": 0.5},
        provenance=MetricProvenance(
            source_kind="test", source_ids=(), notes_code="ok"
        ),
    )


def test_write_and_read_metric_sidecar(tmp_path: Path) -> None:
    store = FilesystemMatrixManifestStore(tmp_path)
    store.write_metric_documents("cell-1", (_doc(),))
    loaded = store.read_metric_documents("cell-1")
    assert loaded is not None
    assert len(loaded) == 1
    assert loaded[0].metric_family == "cooperation"
    assert loaded[0].values["coop_occurrence_rate"] == 0.5


def test_missing_sidecar_is_none(tmp_path: Path) -> None:
    store = FilesystemMatrixManifestStore(tmp_path)
    assert store.read_metric_documents("missing") is None


def test_absent_only_documents_skip_write(tmp_path: Path) -> None:
    store = FilesystemMatrixManifestStore(tmp_path)
    absent = MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family="cooperation",
        algorithm_version="1",
        library_versions=library_versions(),
        run_id="run-side",
        input_revision="rev-1",
        evidence_stages=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="test",
        denominator="test",
        coverage=None,
        availability=MetricAvailability.ABSENT,
        values={},
        provenance=MetricProvenance(
            source_kind="test", source_ids=(), notes_code="absent"
        ),
    )
    store.write_metric_documents("cell-2", (absent,))
    assert store.read_metric_documents("cell-2") is None
