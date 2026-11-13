# mypy: ignore-errors
"""Canonical economic-inequality snapshot model tests."""

from __future__ import annotations

import pytest

from simulation.economic_inequality_codec import (
    decode_economic_inequality_snapshot,
    encode_economic_inequality_snapshot,
    finalize_economic_inequality_snapshot,
)
from simulation.economic_inequality_models import (
    ECONOMIC_INEQUALITY_SNAPSHOT_VERSION,
    MAX_ECONOMIC_INEQUALITY_COHORT_ROWS,
    EconomicCohortRecord,
    EconomicDimensionRecord,
    EconomicInequalitySnapshot,
    EconomicInequalitySummaryRecord,
    EconomicSocietyRecord,
    empty_economic_inequality_snapshot,
)


def _dimension(window: int = 0) -> EconomicDimensionRecord:
    return EconomicDimensionRecord(
        dimension="resource_possession",
        measure="observed_item_count",
        window_index=window,
        window_tick=window * 32 + 31,
        owner_count=8,
        observed_owner_count=8,
        minimum=0,
        p25=1,
        median=2,
        p75=3,
        maximum=4,
        iqr=2,
        dispersion=4,
        bin_shares_milli=(250, 250, 250, 250, 0),
        gini_milli=200,
        theil_t_milli=100,
        atkinson_eps_1_milli=80,
        top_share_milli=300,
        availability="available",
        coverage="complete",
    )


def _cohort(window: int = 0) -> EconomicCohortRecord:
    return EconomicCohortRecord(
        cohort_token="eic-0000000000000001",
        generation_index=0,
        window_index=window,
        owner_count=8,
        comparable=True,
        gini_milli=200,
        median_milli=2,
        iqr_milli=1,
        trend="stable",
        availability="available",
    )


def _society(window: int = 0) -> EconomicSocietyRecord:
    return EconomicSocietyRecord(
        society_token="eis-0000000000000001",
        window_index=window,
        owner_count=8,
        comparable=True,
        gini_milli=200,
        median_milli=2,
        iqr_milli=1,
        trend="stable",
        availability="available",
    )


def _snapshot() -> EconomicInequalitySnapshot:
    return EconomicInequalitySnapshot(
        run_id="run-1",
        schema_version=ECONOMIC_INEQUALITY_SNAPSHOT_VERSION,
        policy_version="economic-inequality.v1",
        summary=EconomicInequalitySummaryRecord(
            dimension_row_count=1,
            cohort_row_count=1,
            society_row_count=1,
            window_count=1,
            owner_count=8,
            observed_owner_count=8,
            overlap_member_count=0,
            coverage="complete",
            evidence_coverage="complete",
            dimension_coverage="complete",
            comparison_coverage="complete",
            truncated=False,
        ),
        dimensions=(_dimension(),),
        cohorts=(_cohort(),),
        societies=(_society(),),
    )


def test_snapshot_round_trips_canonically() -> None:
    snapshot = finalize_economic_inequality_snapshot(_snapshot())
    payload = encode_economic_inequality_snapshot(snapshot)
    decoded = decode_economic_inequality_snapshot(payload, run_id="run-1")
    assert decoded == snapshot
    assert decoded.digest.startswith("sha256:")
    assert decoded.publication_id.startswith("econ-pub-")
    assert "created_at" not in payload.decode()
    assert "wall_clock" not in payload.decode()


def test_duplicate_rows_are_rejected() -> None:
    with pytest.raises(ValueError, match="snapshot_invalid"):
        EconomicInequalitySnapshot(
            run_id="run-1",
            schema_version=ECONOMIC_INEQUALITY_SNAPSHOT_VERSION,
            policy_version="economic-inequality.v1",
            summary=_snapshot().summary,
            dimensions=(_dimension(), _dimension()),
        )


def test_row_caps_are_enforced() -> None:
    rows = tuple(
        EconomicCohortRecord(
            cohort_token=f"eic-{index:016x}",
            generation_index=index,
            window_index=0,
            owner_count=4,
            comparable=True,
            gini_milli=200,
            median_milli=2,
            iqr_milli=1,
            trend="stable",
            availability="available",
        )
        for index in range(MAX_ECONOMIC_INEQUALITY_COHORT_ROWS + 1)
    )
    with pytest.raises(ValueError, match="snapshot_invalid"):
        EconomicInequalitySnapshot(
            run_id="run-1",
            schema_version=ECONOMIC_INEQUALITY_SNAPSHOT_VERSION,
            policy_version="economic-inequality.v1",
            summary=_snapshot().summary,
            cohorts=rows,
        )


def test_empty_snapshot_is_missing_coverage() -> None:
    snapshot = empty_economic_inequality_snapshot("run-1")
    assert snapshot.summary.coverage == "missing"
    assert snapshot.dimensions == ()
