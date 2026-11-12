"""Purpose-bound paging for credit relationship snapshot rows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from simulation.credit_relationships_models import (
    CreditAlignmentRecord,
    CreditClaimRecord,
    CreditCounterpartyRecord,
    CreditDistributionRecord,
    CreditPerformanceRecord,
    CreditRelationshipRecord,
)

__all__ = [
    "CREDIT_RELATIONSHIPS_PAGE_DEFAULT",
    "CREDIT_RELATIONSHIPS_PAGE_MAX",
    "page_credit_relationships",
]

CREDIT_RELATIONSHIPS_PAGE_DEFAULT: Final[int] = 100
CREDIT_RELATIONSHIPS_PAGE_MAX: Final[int] = 500

_PURPOSE_ROWS: Final[dict[str, type[Any]]] = {
    "relationships": CreditRelationshipRecord,
    "claims": CreditClaimRecord,
    "performances": CreditPerformanceRecord,
    "distributions": CreditDistributionRecord,
    "counterparties": CreditCounterpartyRecord,
    "alignment": CreditAlignmentRecord,
}

_SORT_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "relationships": ("window_index", "relationship_id"),
    "claims": ("window_index", "claim_id"),
    "performances": ("window_index", "performance_id"),
    "distributions": ("window_index", "distribution_id"),
    "counterparties": ("window_index", "counterparty_token"),
    "alignment": ("window_index", "alignment_id"),
}


def page_credit_relationships(
    rows: Sequence[Any],
    *,
    purpose: str,
    after_key: Sequence[Any] | None = None,
    limit: int = CREDIT_RELATIONSHIPS_PAGE_DEFAULT,
    window_index: int | None = None,
) -> tuple[Any, ...]:
    """Return one bounded page for a purpose and optional window filter."""

    row_type = _PURPOSE_ROWS.get(purpose)
    if row_type is None:
        raise ValueError("credit_relationships_invalid_purpose")
    if type(limit) is not int or not 1 <= limit <= CREDIT_RELATIONSHIPS_PAGE_MAX:
        raise ValueError("credit_relationships_invalid_limit")
    if window_index is not None and (
        type(window_index) is not int or not 0 <= window_index < 512
    ):
        raise ValueError("credit_relationships_invalid_window")
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValueError("credit_relationships_invalid_input")
    values = []
    for row in rows:
        if type(row) is not row_type:
            raise ValueError("credit_relationships_invalid_input")
        if (
            window_index is not None
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
