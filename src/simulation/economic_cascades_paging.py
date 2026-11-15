"""Deterministic purpose-bound paging for economic-cascade rows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Final

from simulation.economic_cascades_models import EconomicCascadesSnapshot

__all__ = [
    "DEFAULT_ECONOMIC_CASCADES_LIMIT",
    "ECONOMIC_CASCADES_PURPOSES",
    "MAX_ECONOMIC_CASCADES_LIMIT",
    "page_economic_cascades_rows",
]

DEFAULT_ECONOMIC_CASCADES_LIMIT: Final[int] = 100
MAX_ECONOMIC_CASCADES_LIMIT: Final[int] = 500
ECONOMIC_CASCADES_PURPOSES: Final[tuple[str, ...]] = (
    "disruptions",
    "dependencies",
    "chains",
    "propagation",
    "coverage",
    "windows",
)
_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.economic_cascades_paging"
)


def _rows_for(snapshot: EconomicCascadesSnapshot, purpose: str) -> Sequence[Any]:
    if purpose == "disruptions":
        return snapshot.disruptions
    if purpose == "dependencies":
        return snapshot.dependencies
    if purpose == "chains":
        return snapshot.chains
    if purpose == "propagation":
        return snapshot.propagation
    if purpose == "coverage":
        return snapshot.coverage
    if purpose == "windows":
        return tuple(
            (row.window_index, row.window_tick) for row in snapshot.coverage
        )
    raise ValueError("economic_cascades_page_invalid")


def _row_window(row: Any) -> int:
    if isinstance(row, tuple):
        return int(row[0])
    return int(row.window_index)


def _row_key(row: Any, purpose: str) -> str:
    if purpose == "windows":
        return f"{row[0]:04d}"
    if purpose == "disruptions":
        return f"{row.window_index:04d}|{row.kind}"
    if purpose == "dependencies":
        return (
            f"{row.window_index:04d}|{row.upstream_token}|"
            f"{row.downstream_recipe_token}|{row.kind}"
        )
    if purpose == "chains":
        return f"{row.window_index:04d}|{row.chain_token}"
    if purpose == "propagation":
        return f"{row.window_index:04d}|{row.disruption_kind}"
    return f"{row.window_index:04d}"


def page_economic_cascades_rows(
    snapshot: EconomicCascadesSnapshot,
    *,
    purpose: str,
    window_index: int | None = None,
    limit: int = DEFAULT_ECONOMIC_CASCADES_LIMIT,
    after: str | None = None,
) -> tuple[tuple[object, ...], str]:
    """Filter, sort, and cut one deterministic page; return the next key."""

    if type(snapshot) is not EconomicCascadesSnapshot:
        raise ValueError("economic_cascades_page_invalid")
    if purpose not in ECONOMIC_CASCADES_PURPOSES:
        raise ValueError("economic_cascades_page_invalid")
    if (
        isinstance(limit, bool)
        or type(limit) is not int
        or not 1 <= limit <= MAX_ECONOMIC_CASCADES_LIMIT
    ):
        raise ValueError("economic_cascades_page_invalid")
    if window_index is not None and (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or not 0 <= window_index <= 511
    ):
        raise ValueError("economic_cascades_page_invalid")
    if after is not None and type(after) is not str:
        raise ValueError("economic_cascades_page_invalid")

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
        "economic_cascades_page purpose=%s window=%s rows=%d next=%s",
        purpose,
        "-" if window_index is None else window_index,
        len(page),
        bool(next_key),
    )
    return page, next_key
