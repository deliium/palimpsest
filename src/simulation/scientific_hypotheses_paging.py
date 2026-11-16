"""Deterministic purpose-bound paging for scientific-hypothesis rows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Final

from simulation.scientific_hypotheses_models import (
    ScientificHypothesesSnapshot,
)

__all__ = [
    "DEFAULT_SCIENTIFIC_HYPOTHESES_LIMIT",
    "MAX_SCIENTIFIC_HYPOTHESES_LIMIT",
    "SCIENTIFIC_HYPOTHESES_PURPOSES",
    "page_scientific_hypothesis_rows",
]

DEFAULT_SCIENTIFIC_HYPOTHESES_LIMIT: Final[int] = 100
MAX_SCIENTIFIC_HYPOTHESES_LIMIT: Final[int] = 500
SCIENTIFIC_HYPOTHESES_PURPOSES: Final[tuple[str, ...]] = (
    "hypotheses",
    "evidence",
    "tests",
    "revisions",
    "sources",
    "coverage",
    "windows",
)
_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.scientific_hypotheses_paging"
)


def _rows_for(snapshot: ScientificHypothesesSnapshot, purpose: str) -> Sequence[Any]:
    if purpose == "hypotheses":
        return snapshot.hypotheses
    if purpose == "evidence":
        return snapshot.evidence
    if purpose == "tests":
        return snapshot.tests
    if purpose == "revisions":
        return snapshot.revisions
    if purpose == "sources":
        return snapshot.sources
    if purpose == "coverage":
        return snapshot.coverage
    if purpose == "windows":
        return tuple(
            (row.window_index, row.window_tick) for row in snapshot.coverage
        )
    raise ValueError("scientific_hypotheses_page_invalid")


def _row_window(row: Any) -> int:
    if isinstance(row, tuple):
        return int(row[0])
    return int(row.window_index)


def _row_key(row: Any, purpose: str) -> str:
    if purpose == "windows":
        return f"{row[0]:04d}"
    if purpose == "hypotheses":
        return f"{row.window_index:04d}|{row.hypothesis_token}"
    if purpose == "evidence":
        return f"{row.window_index:04d}|{row.hypothesis_token}"
    if purpose == "tests":
        return f"{row.window_index:04d}|{row.hypothesis_token}"
    if purpose == "revisions":
        return (
            f"{row.window_index:04d}|{row.hypothesis_token}|"
            f"{row.revision_index:06d}"
        )
    if purpose == "sources":
        return f"{row.window_index:04d}|{row.source_kind}"
    return f"{row.window_index:04d}"


def page_scientific_hypothesis_rows(
    snapshot: ScientificHypothesesSnapshot,
    *,
    purpose: str,
    window_index: int | None = None,
    limit: int = DEFAULT_SCIENTIFIC_HYPOTHESES_LIMIT,
    after: str | None = None,
) -> tuple[tuple[object, ...], str]:
    """Filter, sort, and cut one deterministic page; return the next key."""

    if type(snapshot) is not ScientificHypothesesSnapshot:
        raise ValueError("scientific_hypotheses_page_invalid")
    if purpose not in SCIENTIFIC_HYPOTHESES_PURPOSES:
        raise ValueError("scientific_hypotheses_page_invalid")
    if (
        isinstance(limit, bool)
        or type(limit) is not int
        or not 1 <= limit <= MAX_SCIENTIFIC_HYPOTHESES_LIMIT
    ):
        raise ValueError("scientific_hypotheses_page_invalid")
    if window_index is not None and (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or not 0 <= window_index <= 511
    ):
        raise ValueError("scientific_hypotheses_page_invalid")
    if after is not None and type(after) is not str:
        raise ValueError("scientific_hypotheses_page_invalid")

    rows = [
        row
        for row in _rows_for(snapshot, purpose)
        if window_index is None or _row_window(row) == window_index
    ]
    rows.sort(key=lambda row: _row_key(row, purpose))
    if after:
        rows = [row for row in rows if _row_key(row, purpose) > after]
    page = tuple(rows[:limit])
    next_key = "" if len(rows) <= limit else _row_key(page[-1], purpose)
    _LOG.debug(
        "scientific_hypotheses_page purpose=%s window=%s rows=%d next=%s",
        purpose,
        "-" if window_index is None else window_index,
        len(page),
        bool(next_key),
    )
    return page, next_key
