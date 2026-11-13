# mypy: ignore-errors
"""Property bounds for economic-inequality detection rows."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.economic_inequality_contract import (
    EconomicInequalityAvailability,
)
from analysis.economic_inequality_detection import (
    detect_economic_inequality_rows,
)
from analysis.economic_inequality_rows import EconomicPossessionRow


@settings(max_examples=40, deadline=None)
@given(
    values=st.lists(st.integers(min_value=0, max_value=10_000), min_size=0, max_size=12)
)
def test_indices_are_bounded_or_absent(values: list[int]) -> None:
    rows = tuple(
        EconomicPossessionRow(
            owner_token=f"eio-{index:016x}",
            tick=0,
            window_index=0,
            observed_item_count=value,
            observed_tool_count=0,
        )
        for index, value in enumerate(values)
    )
    result = detect_economic_inequality_rows(possession_rows=rows)
    for row in result.rows:
        if row.availability is EconomicInequalityAvailability.AVAILABLE:
            assert row.gini_milli is not None
            assert 0 <= row.gini_milli <= 1_000
            assert row.theil_t_milli is not None
            assert 0 <= row.theil_t_milli <= 1_000
            assert row.atkinson_eps_1_milli is not None
            assert 0 <= row.atkinson_eps_1_milli <= 1_000
            assert row.top_share_milli is not None
            assert 0 <= row.top_share_milli <= 1_000
            assert len(row.bin_shares_milli) == 5
            assert all(0 <= share <= 1_000 for share in row.bin_shares_milli)
        else:
            assert row.gini_milli is None
            assert row.bin_shares_milli == (0, 0, 0, 0, 0)


@settings(max_examples=30, deadline=None)
@given(count=st.integers(min_value=0, max_value=3))
def test_short_windows_are_never_promoted(count: int) -> None:
    rows = tuple(
        EconomicPossessionRow(
            owner_token=f"eio-{index:016x}",
            tick=0,
            window_index=0,
            observed_item_count=index,
            observed_tool_count=0,
        )
        for index in range(count)
    )
    result = detect_economic_inequality_rows(possession_rows=rows)
    for row in result.rows:
        if count == 0:
            assert row.observed_owner_count == 0
        else:
            assert (
                row.availability is EconomicInequalityAvailability.INSUFFICIENT_SAMPLES
            )
            assert row.gini_milli is None
