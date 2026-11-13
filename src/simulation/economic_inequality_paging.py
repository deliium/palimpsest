"""Deterministic purpose-bound paging for economic-inequality rows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Final

__all__ = [
    "ECONOMIC_INEQUALITY_PAGE_DEFAULT",
    "ECONOMIC_INEQUALITY_PAGE_MAX",
    "ECONOMIC_INEQUALITY_PURPOSE_DIMENSIONS",
    "page_economic_inequality",
]

ECONOMIC_INEQUALITY_PAGE_DEFAULT: Final[int] = 100
ECONOMIC_INEQUALITY_PAGE_MAX: Final[int] = 500
_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.economic_inequality_paging"
)

ECONOMIC_INEQUALITY_PURPOSE_DIMENSIONS: Final[dict[str, frozenset[str]]] = {
    "summary": frozenset(),
    "dimensions": frozenset(
        {
            "resource_possession",
            "productive_tool_access",
            "infrastructure_access",
            "storage_access",
            "credit_relationship",
            "organizational_resource_control",
        }
    ),
    "possession": frozenset({"resource_possession"}),
    "access": frozenset(
        {
            "productive_tool_access",
            "infrastructure_access",
            "storage_access",
        }
    ),
    "claims": frozenset(
        {"credit_relationship", "organizational_resource_control"}
    ),
    "cohorts": frozenset(),
    "societies": frozenset(),
}


def _id(row: Any, purpose: str) -> str:
    if purpose in {"cohorts", "societies"}:
        token = (
            row.cohort_token if purpose == "cohorts" else row.society_token
        )
        return f"{row.window_index:03d}|{token}"
    return f"{row.window_index:03d}|{row.dimension}|{row.measure}"


def page_economic_inequality(
    rows: Sequence[Any],
    *,
    purpose: str,
    limit: int = ECONOMIC_INEQUALITY_PAGE_DEFAULT,
    after_key: str = "",
    window_index: int | None = None,
) -> tuple[tuple[object, ...], str]:
    """Filter, sort, and cut one deterministic page; return the next key."""

    if purpose not in ECONOMIC_INEQUALITY_PURPOSE_DIMENSIONS:
        raise ValueError("economic_inequality_page_invalid")
    if (
        isinstance(limit, bool)
        or type(limit) is not int
        or not 1 <= limit <= ECONOMIC_INEQUALITY_PAGE_MAX
    ):
        raise ValueError("economic_inequality_page_invalid")
    if window_index is not None and (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or not 0 <= window_index <= 511
    ):
        raise ValueError("economic_inequality_page_invalid")
    if purpose == "summary":
        return (), ""
    if purpose in {"cohorts", "societies"}:
        token_field = "cohort_token" if purpose == "cohorts" else "society_token"
        filtered = [
            row
            for row in rows
            if hasattr(row, token_field)
            and (window_index is None or row.window_index == window_index)
        ]
    else:
        allowed = ECONOMIC_INEQUALITY_PURPOSE_DIMENSIONS[purpose]
        filtered = [
            row
            for row in rows
            if getattr(row, "dimension", None) in allowed
            and (window_index is None or row.window_index == window_index)
        ]
    filtered.sort(key=lambda row: _id(row, purpose))
    if after_key:
        filtered = [row for row in filtered if _id(row, purpose) > after_key]
    page = tuple(filtered[:limit])
    next_key = "" if len(filtered) <= limit else _id(page[-1], purpose)
    _LOG.debug(
        "economic_inequality_page purpose=%s window=%s rows=%d next=%s",
        purpose,
        "-" if window_index is None else window_index,
        len(page),
        bool(next_key),
    )
    return page, next_key
