# mypy: disable-error-code="attr-defined"
"""Bounded deterministic paging for inter-society-relations snapshot rows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from simulation.inter_society_relations_models import InterSocietyRelationsSnapshot

__all__ = [
    "MAX_PAGE_LIMIT",
    "InterSocietyRelationsRowSelection",
    "page_inter_society_relations_detail",
    "page_inter_society_relations_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.inter_society_relations.paging"
)

MAX_PAGE_LIMIT: Final[int] = 500
_LIST_PURPOSES: Final[frozenset[str]] = frozenset({"pairs", "windows", "series"})
_DETAIL_PURPOSES: Final[frozenset[str]] = frozenset({"pair"})


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    rows: tuple[object, ...] = ()
    next_key: str | None = None


def _clamp_limit(limit: object) -> int:
    if type(limit) is not int or limit < 1 or limit > MAX_PAGE_LIMIT:
        raise ValueError("inter_society_relations_page_limit")
    return limit


def _row_key(purpose: str, row: object) -> str:
    if purpose == "pairs":
        return f"{row.window_tick:020d}|{row.pair_id}"
    if purpose in {"windows", "series"}:
        return f"{row.window_index:020d}|{row.pair_id}"
    raise ValueError("inter_society_relations_cursor_purpose")


def _ordered_rows(
    snapshot: InterSocietyRelationsSnapshot, purpose: str
) -> tuple[object, ...]:
    if purpose == "pairs":
        return tuple(
            sorted(snapshot.pairs, key=lambda row: (row.window_tick, row.pair_id))
        )
    if purpose in {"windows", "series"}:
        return tuple(
            sorted(
                snapshot.series_points,
                key=lambda row: (row.window_index, row.pair_id),
            )
        )
    raise ValueError("inter_society_relations_cursor_purpose")


def page_inter_society_relations_rows(
    snapshot: InterSocietyRelationsSnapshot,
    selection: InterSocietyRelationsRowSelection | None = None,
    *,
    purpose: str | None = None,
    after_key: str | None = None,
    limit: int | None = None,
) -> InterSocietyRelationsRowSelection:
    if type(snapshot) is not InterSocietyRelationsSnapshot:
        raise TypeError("snapshot must be InterSocietyRelationsSnapshot")
    if selection is not None:
        if type(selection) is not InterSocietyRelationsRowSelection:
            raise TypeError("selection must be InterSocietyRelationsRowSelection")
        purpose = selection.purpose
        after_key = selection.after_key
        limit = selection.limit
    if purpose is None or purpose not in _LIST_PURPOSES:
        raise ValueError("inter_society_relations_cursor_purpose")
    clamped = _clamp_limit(1 if limit is None else limit)
    ordered = list(_ordered_rows(snapshot, purpose))
    if after_key is not None:
        if type(after_key) is not str or not after_key:
            raise ValueError("inter_society_relations_cursor_invalid")
        ordered = [row for row in ordered if _row_key(purpose, row) > after_key]
    page = tuple(ordered[:clamped])
    next_key = (
        _row_key(purpose, page[-1]) if len(ordered) > len(page) and page else None
    )
    result = InterSocietyRelationsRowSelection(
        purpose=purpose,
        after_key=after_key,
        limit=clamped,
        rows=page,
        next_key=next_key,
    )
    _LOG.debug("inter_society_relations_page purpose=%s rows=%s", purpose, len(page))
    return result


def page_inter_society_relations_detail(
    snapshot: InterSocietyRelationsSnapshot,
    purpose: str,
    key: str | None,
) -> object | None:
    if type(snapshot) is not InterSocietyRelationsSnapshot:
        raise TypeError("snapshot must be InterSocietyRelationsSnapshot")
    if purpose not in _DETAIL_PURPOSES:
        raise ValueError("inter_society_relations_cursor_purpose")
    if key is None or type(key) is not str or not key:
        return None
    for pair in snapshot.pairs:
        if pair.pair_id == key:
            return pair
    return None
