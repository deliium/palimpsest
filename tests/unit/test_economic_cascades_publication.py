# mypy: ignore-errors
"""Programmatic publication receipts for economic-cascade snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.economic_cascades_analysis import (
    empty_economic_cascades_analysis,
    harvest_economic_cascades_analysis,
)
from experiments.economic_cascades_publication import (
    build_economic_cascades_harvest_result,
    compose_economic_cascades_snapshot,
    publish_economic_cascades_snapshot,
)
from persistence.economic_cascades_filesystem import (
    EconomicCascadesPublisherOptions,
    economic_cascades_store_publisher,
    economic_cascades_store_reader,
)
from tests.unit.test_economic_cascades_analysis import (
    _harvest_events,
    _recipes,
    _stage,
)

pytestmark = pytest.mark.unit


def _analysis():
    return harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
    )


def test_compose_maps_summary_and_rows() -> None:
    analysis = _analysis()
    snapshot = compose_economic_cascades_snapshot(analysis, run_id="run-1")
    assert snapshot.run_id == "run-1"
    assert snapshot.summary.chain_count == analysis.chain_count
    assert len(snapshot.disruptions) == len(analysis.episodes)
    assert len(snapshot.dependencies) == len(analysis.edges)
    assert len(snapshot.chains) == len(analysis.chains)
    assert snapshot.summary.coverage == analysis.coverage.value
    assert snapshot.internal_digest.startswith("sha256:")


def test_published_status_uses_the_real_store(tmp_path: Path) -> None:
    publisher = economic_cascades_store_publisher(tmp_path)
    receipt = publish_economic_cascades_snapshot(
        analysis=_analysis(), run_id="run-1", publisher=publisher
    )
    assert receipt.reason_code == "published"
    assert receipt.stored is True
    stored = economic_cascades_store_reader(tmp_path).read_snapshot("run-1")
    assert stored.publication_id == receipt.publication_id


def test_disabled_publication_writes_nothing(tmp_path: Path) -> None:
    receipt = publish_economic_cascades_snapshot(
        analysis=_analysis(), run_id="run-1", publisher=None
    )
    assert receipt.reason_code == "publication_disabled"
    assert receipt.stored is False
    assert not any(tmp_path.iterdir())


def test_missing_coverage_reports_publication_missing() -> None:
    receipt = publish_economic_cascades_snapshot(
        analysis=empty_economic_cascades_analysis(),
        run_id="run-1",
        publisher=None,
    )
    assert receipt.reason_code == "publication_missing"


def test_quota_failure_maps_to_store_quota_exceeded(tmp_path: Path) -> None:
    publisher = economic_cascades_store_publisher(
        tmp_path, options=EconomicCascadesPublisherOptions(max_bytes=1)
    )
    receipt = publish_economic_cascades_snapshot(
        analysis=_analysis(), run_id="run-1", publisher=publisher
    )
    assert receipt.reason_code == "store_quota_exceeded"
    assert receipt.stored is False


def test_corrupt_store_maps_to_store_corrupt() -> None:
    class Corrupt:
        def publish(self, snapshot):
            raise ValueError("economic_cascades_store_corrupt")

    receipt = publish_economic_cascades_snapshot(
        analysis=_analysis(), run_id="run-1", publisher=Corrupt()
    )
    assert receipt.reason_code == "store_corrupt"


def test_republish_is_idempotent(tmp_path: Path) -> None:
    publisher = economic_cascades_store_publisher(tmp_path)
    analysis = _analysis()
    first = publish_economic_cascades_snapshot(
        analysis=analysis, run_id="run-1", publisher=publisher
    )
    second = publish_economic_cascades_snapshot(
        analysis=analysis, run_id="run-1", publisher=publisher
    )
    assert first.publication_id == second.publication_id
    assert second.stored is False


def test_harvest_result_carries_analysis_and_receipt() -> None:
    analysis = _analysis()
    receipt = publish_economic_cascades_snapshot(
        analysis=analysis, run_id="run-1", publisher=None
    )
    harvest = build_economic_cascades_harvest_result(analysis, receipt)
    assert harvest.analysis is analysis
    assert harvest.receipt is receipt
