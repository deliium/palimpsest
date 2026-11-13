# mypy: ignore-errors
"""Purpose-bound paging tests for economic-inequality rows."""

from __future__ import annotations

import pytest

from simulation.economic_inequality_paging import (
    ECONOMIC_INEQUALITY_PAGE_DEFAULT,
    ECONOMIC_INEQUALITY_PAGE_MAX,
    page_economic_inequality,
)
from tests.unit.test_economic_inequality_snapshot import (
    _cohort,
    _dimension,
    _society,
)


def test_dimension_pages_filter_by_purpose_and_window() -> None:
    rows = (
        _dimension(0),
        _dimension(1),
        _cohort(0),
        _society(0),
    )
    page, next_key = page_economic_inequality(
        rows, purpose="possession", window_index=0
    )
    assert len(page) == 1
    assert page[0].dimension == "resource_possession"
    assert next_key == ""

    page, _ = page_economic_inequality(rows, purpose="cohorts", window_index=1)
    assert page == ()


def test_dimension_sets_are_disjoint_per_purpose() -> None:
    assert ECONOMIC_INEQUALITY_PAGE_DEFAULT == 100
    assert ECONOMIC_INEQUALITY_PAGE_MAX == 500
    with pytest.raises(ValueError, match="page_invalid"):
        page_economic_inequality((), purpose="unknown")


def test_after_key_advances_deterministically() -> None:
    rows = tuple(_dimension(window=index) for index in range(3))
    first, next_key = page_economic_inequality(rows, purpose="dimensions", limit=1)
    assert first[0].window_index == 0
    assert next_key
    second, next_next = page_economic_inequality(
        rows, purpose="dimensions", limit=1, after_key=next_key
    )
    assert second[0].window_index == 1
    assert next_next


def test_window_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="page_invalid"):
        page_economic_inequality((), purpose="dimensions", window_index=512)
    with pytest.raises(ValueError, match="page_invalid"):
        page_economic_inequality((), purpose="dimensions", limit=0)


def test_summary_purpose_has_no_rows() -> None:
    assert page_economic_inequality((_dimension(),), purpose="summary") == (
        (),
        "",
    )
