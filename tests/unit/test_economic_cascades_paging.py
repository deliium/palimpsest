# mypy: ignore-errors
"""Purpose-bound deterministic paging for cascade snapshots."""

from __future__ import annotations

import pytest

from simulation.economic_cascades_models import (
    EconomicCascadeCoverageRecord,
    EconomicCascadeDisruptionRecord,
    EconomicCascadesSnapshot,
    empty_economic_cascades_snapshot,
)
from simulation.economic_cascades_paging import (
    DEFAULT_ECONOMIC_CASCADES_LIMIT,
    MAX_ECONOMIC_CASCADES_LIMIT,
    page_economic_cascades_rows,
)

pytestmark = pytest.mark.unit


def _snapshot() -> EconomicCascadesSnapshot:
    base = empty_economic_cascades_snapshot("run-1")
    disruptions = tuple(
        EconomicCascadeDisruptionRecord(
            window_index=window,
            window_tick=window * 32,
            kind="resource_loss",
            disruption_count=1,
            magnitude_total=1,
            subject_count=1,
            coverage="complete",
        )
        for window in (0, 1, 2)
    )
    coverage = tuple(
        EconomicCascadeCoverageRecord(
            window_index=window,
            window_tick=window * 32,
            window_count=3,
            event_count=1,
            disruption_count=1,
            stage_count=0,
            dependency_edge_count=0,
            labor_join_count=0,
            chain_count=0,
            linked_chain_count=0,
            truncated=False,
            coverage="complete",
            availability="unavailable",
        )
        for window in (0, 1, 2)
    )
    return EconomicCascadesSnapshot(
        snapshot_version=base.snapshot_version,
        policy_version=base.policy_version,
        run_id=base.run_id,
        generated_from_tick=64,
        summary=base.summary,
        disruptions=disruptions,
        coverage=coverage,
    )


def test_default_and_max_limits() -> None:
    assert DEFAULT_ECONOMIC_CASCADES_LIMIT == 100
    assert MAX_ECONOMIC_CASCADES_LIMIT == 500


def test_window_filter_is_applied_before_paging() -> None:
    rows, next_key = page_economic_cascades_rows(
        _snapshot(), purpose="disruptions", window_index=1
    )
    assert len(rows) == 1
    assert rows[0].window_index == 1
    assert next_key == ""


def test_windows_purpose_projects_pairs() -> None:
    rows, _ = page_economic_cascades_rows(
        _snapshot(), purpose="windows", limit=2
    )
    assert rows == ((0, 0), (1, 32))


def test_next_key_is_deterministic_and_exclusive() -> None:
    first, next_key = page_economic_cascades_rows(
        _snapshot(), purpose="disruptions", limit=2
    )
    second, final = page_economic_cascades_rows(
        _snapshot(),
        purpose="disruptions",
        limit=2,
        after=next_key,
    )
    assert len(first) == 2
    assert len(second) == 1
    assert final == ""
    assert second[0].window_index == 2


def test_invalid_purpose_and_limit_fail_closed() -> None:
    with pytest.raises(ValueError):
        page_economic_cascades_rows(_snapshot(), purpose="summary")
    with pytest.raises(ValueError):
        page_economic_cascades_rows(_snapshot(), purpose="chains", limit=0)
    with pytest.raises(ValueError):
        page_economic_cascades_rows(
            _snapshot(), purpose="chains", window_index=512
        )
