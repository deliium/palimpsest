"""Deterministic purpose-bound paging for accounting snapshot rows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Final

__all__ = [
    "ACCOUNTING_LEDGERS_PAGE_DEFAULT",
    "ACCOUNTING_LEDGERS_PAGE_MAX",
    "page_accounting_ledgers",
]

ACCOUNTING_LEDGERS_PAGE_DEFAULT: Final[int] = 100
ACCOUNTING_LEDGERS_PAGE_MAX: Final[int] = 500
_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.accounting_ledgers_paging"
)

_ID_FIELDS: Final[dict[str, str]] = {
    "entries": "entry_token",
    "records": "record_token",
    "conditions": "condition",
    "flows": "flow_token",
    "counterparties": "counterparty_token",
    "alignment": "alignment_token",
}


def _id(row: Any, purpose: str) -> str:
    field = _ID_FIELDS[purpose]
    value = getattr(row, field)
    if purpose == "conditions":
        value = f"{value}:{row.window_index}"
    return f"{row.window_index:03d}:{value}"


def page_accounting_ledgers(
    rows: Sequence[Any],
    *,
    purpose: str,
    limit: int = ACCOUNTING_LEDGERS_PAGE_DEFAULT,
    after_key: str = "",
    window_index: int | None = None,
) -> tuple[tuple[object, ...], str]:
    """Filter, sort, and cut one deterministic page; return the next key."""

    if purpose not in _ID_FIELDS:
        raise ValueError("accounting_ledgers_page_invalid")
    if (
        isinstance(limit, bool)
        or type(limit) is not int
        or not 1 <= limit <= ACCOUNTING_LEDGERS_PAGE_MAX
    ):
        raise ValueError("accounting_ledgers_page_invalid")
    if window_index is not None and (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or not 0 <= window_index <= 511
    ):
        raise ValueError("accounting_ledgers_page_invalid")
    filtered = [
        row
        for row in rows
        if window_index is None or row.window_index == window_index
    ]
    filtered.sort(key=lambda row: _id(row, purpose))
    if after_key:
        filtered = [
            row for row in filtered if _id(row, purpose) > after_key
        ]
    page = tuple(filtered[:limit])
    next_key = "" if len(filtered) <= limit else _id(page[-1], purpose)
    _LOG.debug(
        "[FIX] accounting_page purpose=%s window=%s rows=%s next=%s",
        purpose,
        "-" if window_index is None else window_index,
        len(page),
        bool(next_key),
    )
    return page, next_key
