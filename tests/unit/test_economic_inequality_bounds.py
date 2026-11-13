# mypy: ignore-errors
"""Owner, event, and row caps plus monotone prefix stability."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.economic_inequality_analysis import (
    harvest_economic_inequality_analysis,
)
from analysis.economic_inequality_contract import EconomicInequalityCoverage
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
)
from analysis.economic_inequality_rows import EconomicPossessionRow


def _rows(count: int, window: int = 0) -> tuple[EconomicPossessionRow, ...]:
    return tuple(
        EconomicPossessionRow(
            owner_token=f"eio-{owner:016x}",
            tick=window * 32,
            window_index=window,
            observed_item_count=owner,
            observed_tool_count=0,
        )
        for owner in range(count)
    )


@settings(max_examples=25, deadline=None)
@given(
    owners=st.integers(min_value=0, max_value=30),
    cap=st.integers(min_value=1, max_value=12),
)
def test_owner_cap_is_a_deterministic_prefix(owners: int, cap: int) -> None:
    analysis = harvest_economic_inequality_analysis(
        possession_rows=_rows(owners),
        policy=EconomicInequalityAnalysisPolicy(max_owners=cap),
    )
    assert analysis.owner_count == min(owners, cap)
    if owners > cap:
        assert analysis.coverage is EconomicInequalityCoverage.PARTIAL
        assert "economic_inequality_owners_truncated" in analysis.notices


@settings(max_examples=20, deadline=None)
@given(
    count=st.integers(min_value=1, max_value=12),
    cap=st.integers(min_value=1, max_value=6),
)
def test_dimension_row_cap_keeps_the_deterministic_prefix(count: int, cap: int) -> None:
    baseline = harvest_economic_inequality_analysis(possession_rows=_rows(count))
    capped = harvest_economic_inequality_analysis(
        possession_rows=_rows(count),
        policy=EconomicInequalityAnalysisPolicy(max_dimension_rows=cap),
    )
    assert capped.dimension_rows == baseline.dimension_rows[:cap]
    assert len(capped.dimension_rows) <= cap


@settings(max_examples=15, deadline=None)
@given(st.integers(min_value=1, max_value=4))
def test_event_cap_marks_partial_coverage(window_count: int) -> None:
    rows = tuple(row for window in range(window_count) for row in _rows(4, window))
    analysis = harvest_economic_inequality_analysis(
        possession_rows=rows,
        policy=EconomicInequalityAnalysisPolicy(max_event_rows=4),
    )
    assert len(analysis.dimension_rows) <= 4 * 8
    assert analysis.coverage is EconomicInequalityCoverage.PARTIAL
