# mypy: ignore-errors
"""Property bounds for cohort and society comparisons."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.economic_inequality_comparisons import (
    compare_economic_inequality_strata,
)
from analysis.economic_inequality_rows import (
    EconomicCohortMembership,
    EconomicPossessionRow,
    EconomicSocietyMembership,
)


@settings(max_examples=25, deadline=None)
@given(
    values=st.lists(st.integers(min_value=0, max_value=1_000), min_size=0, max_size=16)
)
def test_cohort_rows_are_bounded_and_sorted(values: list[int]) -> None:
    memberships = tuple(
        EconomicCohortMembership(
            owner_token=f"eio-{index:016x}",
            generation_index=index % 3,
            first_tick=0,
        )
        for index in range(len(values))
    )
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
    result = compare_economic_inequality_strata(
        possession_rows=rows, cohort_memberships=memberships
    )
    for row in result.cohort_rows:
        assert row.owner_count >= 4
        assert 0 <= (row.gini_milli or 0) <= 1_000
    assert [row.window_index for row in result.cohort_rows] == sorted(
        row.window_index for row in result.cohort_rows
    )


@settings(max_examples=20, deadline=None)
@given(
    memberships=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=5),
            st.sampled_from(["eis-a", "eis-b"]),
        ),
        max_size=12,
    )
)
def test_overlap_members_are_counted_once(
    memberships: list[tuple[int, str]],
) -> None:
    society_rows = tuple(
        EconomicSocietyMembership(
            owner_token=f"eio-{owner:016x}",
            society_token=society,
            window_indexes=(0,),
        )
        for owner, society in memberships
    )
    possession = tuple(
        EconomicPossessionRow(
            owner_token=f"eio-{owner:016x}",
            tick=0,
            window_index=0,
            observed_item_count=owner,
            observed_tool_count=0,
        )
        for owner in range(6)
    )
    result = compare_economic_inequality_strata(
        possession_rows=possession,
        society_memberships=society_rows,
    )
    counts: dict[str, int] = {}
    for membership in society_rows:
        counts[membership.owner_token] = counts.get(membership.owner_token, 0) + 1
    assert result.overlap_member_count == sum(
        1 for count in counts.values() if count > 1
    )
