# mypy: ignore-errors
"""Cohort and society comparison composition tests."""

from __future__ import annotations

from analysis.economic_inequality_comparisons import (
    compare_economic_inequality_strata,
    trend_direction,
)
from analysis.economic_inequality_contract import (
    EconomicInequalityCoverage,
    EconomicInequalityTrend,
)
from analysis.economic_inequality_rows import (
    EconomicCohortMembership,
    EconomicPossessionRow,
    EconomicSocietyMembership,
)


def _possession(owner: int, window: int, items: int) -> EconomicPossessionRow:
    return EconomicPossessionRow(
        owner_token=f"eio-{owner:016x}",
        tick=window * 32 + 4,
        window_index=window,
        observed_item_count=items,
        observed_tool_count=0,
    )


def _memberships() -> tuple[
    tuple[EconomicCohortMembership, ...], tuple[EconomicSocietyMembership, ...]
]:
    cohorts = tuple(
        EconomicCohortMembership(
            owner_token=f"eio-{owner:016x}",
            generation_index=owner // 4,
            first_tick=owner,
        )
        for owner in range(8)
    )
    societies = (
        *(
            EconomicSocietyMembership(
                owner_token=f"eio-{owner:016x}",
                society_token=(
                    "eis-0000000000000001"
                    if owner < 4
                    else "eis-0000000000000002"
                ),
                window_indexes=(0, 1),
            )
            for owner in range(8)
        ),
        EconomicSocietyMembership(
            owner_token="eio-0000000000000000",
            society_token="eis-0000000000000002",
            window_indexes=(0, 1),
        ),
    )
    return cohorts, societies


def test_cohorts_and_societies_compare_without_ranking() -> None:
    cohorts, societies = _memberships()
    rows = [
        _possession(owner, window, owner + window)
        for window in range(2)
        for owner in range(8)
    ]
    result = compare_economic_inequality_strata(
        possession_rows=tuple(rows),
        cohort_memberships=cohorts,
        society_memberships=societies,
    )
    assert result.coverage is EconomicInequalityCoverage.COMPLETE
    assert len(result.cohort_rows) == 4
    assert len(result.society_rows) == 4
    assert result.comparable_cohort_count == 2
    assert result.comparable_society_count == 2
    assert result.overlap_member_count == 1
    for row in result.cohort_rows + result.society_rows:
        assert row.availability.value == "available"
        assert row.gini_milli is not None
        assert 0 <= row.gini_milli <= 1_000
        assert row.trend in {
            EconomicInequalityTrend.UNAVAILABLE,
            EconomicInequalityTrend.STABLE,
            EconomicInequalityTrend.RISING,
            EconomicInequalityTrend.FALLING,
        }
    # A trend exists once the second window is available; the first is unknown.
    assert any(
        row.trend is not EconomicInequalityTrend.UNAVAILABLE
        for row in result.cohort_rows
    )


def test_missing_cohort_membership_is_partial() -> None:
    result = compare_economic_inequality_strata(
        possession_rows=tuple(_possession(owner, 0, owner) for owner in range(4)),
        cohort_memberships=(),
        society_memberships=(),
    )
    assert result.cohort_rows == ()
    assert result.coverage is EconomicInequalityCoverage.PARTIAL
    assert "economic_inequality_missing_cohort_membership" in result.notices
    assert "economic_inequality_insufficient_cohorts" in result.notices


def test_strata_below_minimum_samples_are_skipped() -> None:
    cohorts = tuple(
        EconomicCohortMembership(
            owner_token=f"eio-{owner:016x}",
            generation_index=0,
            first_tick=0,
        )
        for owner in range(3)
    )
    result = compare_economic_inequality_strata(
        possession_rows=tuple(_possession(owner, 0, owner) for owner in range(3)),
        cohort_memberships=cohorts,
    )
    assert result.cohort_rows == ()
    assert "economic_inequality_insufficient_cohorts" in result.notices


def test_trend_threshold_is_closed() -> None:
    assert trend_direction(None, 100, threshold_milli=50) is (
        EconomicInequalityTrend.UNAVAILABLE
    )
    assert trend_direction(100, 100, threshold_milli=50) is (
        EconomicInequalityTrend.STABLE
    )
    assert trend_direction(149, 100, threshold_milli=50) is (
        EconomicInequalityTrend.STABLE
    )
    assert trend_direction(150, 100, threshold_milli=50) is (
        EconomicInequalityTrend.RISING
    )
    assert trend_direction(50, 100, threshold_milli=50) is (
        EconomicInequalityTrend.FALLING
    )


def test_empty_evidence_is_explicit() -> None:
    result = compare_economic_inequality_strata()
    assert result.cohort_rows == ()
    assert result.society_rows == ()
    assert result.coverage is EconomicInequalityCoverage.MISSING
