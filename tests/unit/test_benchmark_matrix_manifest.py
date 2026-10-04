"""Unit tests for the V2 benchmark suite matrix fixture (filesystem only)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from analysis.evidence import EvidenceStage
from analysis.matrix_metric_summary import MATRIX_METRIC_SUMMARY_SCHEMA_VERSION
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from experiments.benchmark_suite import BENCHMARK_SCENARIO_IDS, get_benchmark_scenario
from experiments.matrix_expand import expand_matrix
from experiments.matrix_manifest import (
    FilesystemMatrixManifestStore,
    MatrixManifestHeader,
)
from experiments.matrix_metric_summary import (
    load_matrix_metric_summary_from_store,
    write_matrix_metric_summary,
)
from experiments.matrix_models import matrix_spec_fingerprint
from experiments.matrix_serialization import decode_matrix_spec

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "matrices" / "v2-benchmark-suite.json"


def _metric_doc(family: str = "cooperation") -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version="1",
        library_versions=library_versions(),
        run_id="run-bench-matrix",
        input_revision="rev-1",
        evidence_stages=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        population="test",
        denominator="test",
        coverage=None,
        availability=MetricAvailability.PRESENT,
        values={"coop_occurrence_rate": 0.25},
        provenance=MetricProvenance(
            source_kind="test", source_ids=(), notes_code="ok"
        ),
    )


def test_v2_benchmark_matrix_fixture_expands() -> None:
    payload = FIXTURE.read_bytes()
    spec = decode_matrix_spec(payload)
    assert spec.matrix_id == "v2-benchmark-suite"
    factor_ids = {item.factor_id.value for item in spec.factors}
    assert {"memory_type", "tom", "seasonality", "resource_scarcity"} <= factor_ids
    assert list(spec.seed_matrix.seeds) == [11, 13, 17]
    definition, cells = expand_matrix(spec)
    # Cells = conditions x seeds (replicates_per_seed=1).
    assert len(definition.conditions) == 16
    assert len(cells) == 48
    document = json.loads(payload.decode("utf-8"))
    encoded = json.dumps(document)
    for token in ("reconstructive_v2", "tom", "seasonality", "scarce"):
        assert token in encoded


def test_statistical_scenarios_exclude_only_fork_n_a() -> None:
    statistical = [
        scenario_id
        for scenario_id in BENCHMARK_SCENARIO_IDS
        if not get_benchmark_scenario(scenario_id).statistical_comparison.startswith(
            "n/a:"
        )
    ]
    assert "bench-16-forked-intervention" not in statistical
    assert "bench-01-seasonal-planning" in statistical
    assert "bench-15-architecture-matrix" in statistical
    assert len(statistical) == 15


def test_metric_summary_schema_pin_for_sidecars() -> None:
    assert MATRIX_METRIC_SUMMARY_SCHEMA_VERSION == "matrix-metric-summary-v1"


def test_v2_benchmark_matrix_metric_summary_smoke(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    spec = decode_matrix_spec(FIXTURE.read_bytes())
    _definition, cells = expand_matrix(spec)
    store = FilesystemMatrixManifestStore(tmp_path)
    store.create(
        MatrixManifestHeader(
            matrix_id=spec.matrix_id,
            matrix_fingerprint=matrix_spec_fingerprint(spec),
        ),
        cells,
    )
    for cell in cells[:2]:
        store.write_metric_documents(cell.cell_id, (_metric_doc(),))
    with caplog.at_level(logging.INFO, logger="experiments.matrix_metric_summary"):
        summary = load_matrix_metric_summary_from_store(store, cells)
    path = write_matrix_metric_summary(tmp_path, summary)
    assert path.is_file()
    assert summary.schema_version == MATRIX_METRIC_SUMMARY_SCHEMA_VERSION
    assert len(summary.key_summaries) >= 1
    assert "matrix_metric_summary_loaded" in caplog.text
