"""Bounded deterministic paging for border snapshot rows."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from simulation.borders_models import BORDERS_MAX_DETAIL_ROWS

__all__ = [
    "BorderRowSelection",
    "page_border_detail",
    "page_border_rows",
]


@dataclass(frozen=True, slots=True)
class BorderRowSelection:
    rows: tuple[Any, ...]
    next_key: str | None = None
    truncated: bool = False


def _clamp(limit: int) -> int:
    if type(limit) is not int or limit < 1 or limit > BORDERS_MAX_DETAIL_ROWS:
        raise ValueError("borders_page_limit")
    return limit


def page_border_rows(
    rows: Sequence[object],
    *,
    after_key: str | None,
    limit: int,
    key: Callable[[object], str] = str,
) -> BorderRowSelection:
    if isinstance(rows, (str, bytes)):
        raise TypeError("rows must be an ordered sequence")
    ordered = sorted(tuple(rows), key=key)
    if after_key is not None:
        ordered = [row for row in ordered if key(row) > after_key]
    page = tuple(ordered[: _clamp(limit)])
    next_key = key(page[-1]) if len(ordered) > len(page) else None
    return BorderRowSelection(rows=page, next_key=next_key)


def page_border_detail(
    rows: Sequence[object],
    *,
    after_key: str | None = None,
    limit: int = BORDERS_MAX_DETAIL_ROWS,
    key: Callable[[object], str] = str,
) -> BorderRowSelection:
    selection = page_border_rows(rows, after_key=after_key, limit=limit, key=key)
    if len(selection.rows) > BORDERS_MAX_DETAIL_ROWS:
        return BorderRowSelection(
            rows=selection.rows[:BORDERS_MAX_DETAIL_ROWS],
            next_key=selection.next_key,
            truncated=True,
        )
    return selection
