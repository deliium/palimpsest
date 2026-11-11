"""Purpose-bound paging for market-institutions snapshot rows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from simulation.market_institutions_models import (
    MarketCandidateRecord,
    MarketExpectationRecord,
    MarketGatheringRecord,
    MarketLineageRecord,
    MarketRecordAnchorRecord,
    MarketRoleRecord,
    MarketVenueRecord,
)

__all__ = [
    "MARKET_INSTITUTIONS_PAGE_DEFAULT",
    "MARKET_INSTITUTIONS_PAGE_MAX",
    "page_market_institutions",
]

MARKET_INSTITUTIONS_PAGE_DEFAULT: Final[int] = 100
MARKET_INSTITUTIONS_PAGE_MAX: Final[int] = 500

_PURPOSE_ROWS: Final[dict[str, type[Any]]] = {
    "venues": MarketVenueRecord,
    "gatherings": MarketGatheringRecord,
    "expectations": MarketExpectationRecord,
    "roles": MarketRoleRecord,
    "records": MarketRecordAnchorRecord,
    "markets": MarketCandidateRecord,
    "lineage": MarketLineageRecord,
}

_SORT_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "venues": ("window_index", "venue_id"),
    "gatherings": ("window_index", "venue_id"),
    "expectations": ("window_index", "venue_id", "owner_token"),
    "roles": ("window_index", "venue_id", "actor_token"),
    "records": ("window_index", "venue_id", "anchor_token"),
    "markets": ("window_index", "market_id"),
    "lineage": ("window_index", "market_id"),
}


def page_market_institutions(
    rows: Sequence[Any],
    *,
    purpose: str,
    after_key: Sequence[Any] | None = None,
    limit: int = MARKET_INSTITUTIONS_PAGE_DEFAULT,
    window_index: int | None = None,
) -> tuple[Any, ...]:
    """Return one bounded page for a purpose and optional window filter."""

    row_type = _PURPOSE_ROWS.get(purpose)
    if row_type is None:
        raise ValueError("market_institutions_invalid_purpose")
    if type(limit) is not int or not 1 <= limit <= MARKET_INSTITUTIONS_PAGE_MAX:
        raise ValueError("market_institutions_invalid_limit")
    if window_index is not None and (
        type(window_index) is not int or not 0 <= window_index < 512
    ):
        raise ValueError("market_institutions_invalid_window")
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValueError("market_institutions_invalid_input")
    values = []
    for row in rows:
        if type(row) is not row_type:
            raise ValueError("market_institutions_invalid_input")
        if window_index is not None and row.window_index != window_index:
            continue
        values.append(row)
    keys = _SORT_KEYS[purpose]
    values.sort(key=lambda row: tuple(getattr(row, name) for name in keys))
    if after_key is not None:
        boundary = tuple(after_key)
        values = [
            row
            for row in values
            if tuple(getattr(row, name) for name in keys) > boundary
        ]
    return tuple(values[:limit])
