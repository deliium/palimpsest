# mypy: ignore-errors
"""Programmatic publication tests for economic-inequality snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.economic_inequality_publication import (
    build_economic_inequality_harvest_result,
    compose_economic_inequality_snapshot,
    publish_economic_inequality_snapshot,
)
from persistence.economic_inequality_filesystem import (
    EconomicInequalityPublisherOptions,
    create_economic_inequality_publisher,
)
from simulation.economic_inequality_codec import (
    decode_economic_inequality_snapshot,
    encode_economic_inequality_snapshot,
)
from tests.unit.test_economic_inequality_metrics import _analysis


def test_compose_maps_all_row_families() -> None:
    analysis = _analysis()
    snapshot = compose_economic_inequality_snapshot(analysis, run_id="run-1")
    assert snapshot.run_id == "run-1"
    assert snapshot.summary.dimension_row_count == len(analysis.dimension_rows)
    assert snapshot.summary.cohort_row_count == len(analysis.cohort_rows)
    assert snapshot.summary.society_row_count == len(analysis.society_rows)
    assert snapshot.summary.truncated is False
    assert snapshot.digest.startswith("sha256:")
    assert snapshot.publication_id.startswith("econ-pub-")


def test_empty_analysis_publishes_nothing() -> None:
    from analysis.economic_inequality_analysis import (
        empty_economic_inequality_analysis,
    )

    analysis = empty_economic_inequality_analysis()
    snapshot = compose_economic_inequality_snapshot(analysis, run_id="run-1")
    receipt = publish_economic_inequality_snapshot(snapshot, None)
    assert receipt.reason_code == "publication_missing"
    assert receipt.stored is False


def test_disabled_publication_writes_nothing(tmp_path: Path) -> None:
    analysis = _analysis()
    snapshot = compose_economic_inequality_snapshot(analysis, run_id="run-1")
    receipt = publish_economic_inequality_snapshot(snapshot, None)
    assert receipt.reason_code == "publication_disabled"
    assert not (tmp_path / "run-1").exists()


def test_harvest_result_round_trips_through_the_store(tmp_path: Path) -> None:
    analysis = _analysis()
    publisher = create_economic_inequality_publisher(tmp_path)
    harvest = build_economic_inequality_harvest_result(
        analysis, run_id="run-1", publisher=publisher
    )
    assert harvest.receipt.reason_code == "published"
    payload = encode_economic_inequality_snapshot(harvest.snapshot)
    decoded = decode_economic_inequality_snapshot(payload, run_id="run-1")
    assert decoded == harvest.snapshot
    stored = tmp_path / "run-1" / f"{harvest.snapshot.publication_id}.json"
    assert stored.exists()


def test_quota_failure_maps_to_a_safe_reason(tmp_path: Path) -> None:
    analysis = _analysis()
    snapshot = compose_economic_inequality_snapshot(analysis, run_id="run-1")
    publisher = create_economic_inequality_publisher(
        tmp_path,
        options=EconomicInequalityPublisherOptions(max_bytes=10),
    )
    receipt = publish_economic_inequality_snapshot(snapshot, publisher)
    assert receipt.reason_code == "store_quota_exceeded"
    assert receipt.stored is False


def test_partial_coverage_marks_truncated() -> None:
    from analysis.economic_inequality_analysis import (
        harvest_economic_inequality_analysis,
    )
    from analysis.economic_inequality_policy import (
        EconomicInequalityAnalysisPolicy,
    )
    from analysis.economic_inequality_rows import EconomicPossessionRow

    rows = tuple(
        EconomicPossessionRow(
            owner_token=f"eio-{owner:016x}",
            tick=0,
            window_index=0,
            observed_item_count=owner,
            observed_tool_count=0,
        )
        for owner in range(10)
    )
    analysis = harvest_economic_inequality_analysis(
        possession_rows=rows,
        policy=EconomicInequalityAnalysisPolicy(max_dimension_rows=1),
    )
    snapshot = compose_economic_inequality_snapshot(analysis, run_id="run-1")
    assert snapshot.summary.truncated is True
    assert snapshot.summary.coverage == "partial"


def test_invalid_snapshot_type_is_rejected() -> None:
    with pytest.raises(TypeError):
        publish_economic_inequality_snapshot(object(), None)  # type: ignore[arg-type]
