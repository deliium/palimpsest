"""Purpose-bound paging for emergent-price snapshot rows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from simulation.emergent_prices_models import (
    PriceDistributionRecord,
    PriceExpectationRecord,
    PriceMarketRecord,
    PriceQuoteRecord,
    PriceRelationRecord,
    PriceUnitRecord,
)

__all__ = [
    "EMERGENT_PRICES_PAGE_DEFAULT",
    "EMERGENT_PRICES_PAGE_MAX",
    "page_emergent_prices",
]

EMERGENT_PRICES_PAGE_DEFAULT: Final[int] = 100
EMERGENT_PRICES_PAGE_MAX: Final[int] = 500

_PURPOSE_ROWS: Final[dict[str, type[Any]]] = {
    "units": PriceUnitRecord,
    "expectations": PriceExpectationRecord,
    "quotes": PriceQuoteRecord,
    "distributions": PriceDistributionRecord,
    "markets": PriceMarketRecord,
    "relations": PriceRelationRecord,
}

_SORT_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "units": ("unit_token", "unit_source"),
    "expectations": ("window_index", "expectation_id"),
    "quotes": ("window_index", "venue_id", "quote_id"),
    "distributions": ("window_index", "distribution_id"),
    "markets": ("window_index", "market_token"),
    "relations": ("window_index", "relation_id"),
}


def page_emergent_prices(
    rows: Sequence[Any],
    *,
    purpose: str,
    after_key: Sequence[Any] | None = None,
    limit: int = EMERGENT_PRICES_PAGE_DEFAULT,
    window_index: int | None = None,
) -> tuple[Any, ...]:
    """Return one bounded page for a purpose and optional window filter."""

    row_type = _PURPOSE_ROWS.get(purpose)
    if row_type is None:
        raise ValueError("emergent_prices_invalid_purpose")
    if type(limit) is not int or not 1 <= limit <= EMERGENT_PRICES_PAGE_MAX:
        raise ValueError("emergent_prices_invalid_limit")
    if window_index is not None and (
        type(window_index) is not int or not 0 <= window_index < 512
    ):
        raise ValueError("emergent_prices_invalid_window")
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValueError("emergent_prices_invalid_input")
    values = []
    for row in rows:
        if type(row) is not row_type:
            raise ValueError("emergent_prices_invalid_input")
        if (
            purpose != "units"
            and window_index is not None
            and getattr(row, "window_index", -1) != window_index
        ):
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
