"""Purpose-bound page selection for canonical theory snapshot rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from simulation.competing_theories_models import (
    CompetingTheoriesSnapshot,
    TheorySnapshotRow,
    section_names,
)

__all__ = [
    "DEFAULT_THEORY_PAGE_LIMIT",
    "MAX_THEORY_PAGE_LIMIT",
    "TheoryPage",
    "page_theory_rows",
]

DEFAULT_THEORY_PAGE_LIMIT: Final[int] = 50
MAX_THEORY_PAGE_LIMIT: Final[int] = 200


@dataclass(frozen=True, slots=True)
class TheoryPage:
    section: str
    rows: tuple[TheorySnapshotRow, ...]
    next_position: int | None
    window: int | None
    theory_id: str | None
    limit: int


def page_theory_rows(
    snapshot: CompetingTheoriesSnapshot,
    *,
    section: str,
    position: int = 0,
    limit: int = DEFAULT_THEORY_PAGE_LIMIT,
    window: int | None = None,
    theory_id: str | None = None,
) -> TheoryPage:
    if section not in section_names():
        raise ValueError("section: invalid")
    if isinstance(position, bool) or type(position) is not int or position < 0:
        raise ValueError("position: invalid")
    if isinstance(limit, bool) or type(limit) is not int:
        raise ValueError("limit: invalid")
    if limit < 1 or limit > MAX_THEORY_PAGE_LIMIT:
        raise ValueError("limit: invalid")
    if section == "coverage" and theory_id is not None:
        raise ValueError("theory_id: unsupported")
    rows = snapshot.rows_for(section)
    if window is not None:
        rows = tuple(row for row in rows if row.window_start == window)
    if theory_id is not None:
        rows = tuple(row for row in rows if row.theory_id == theory_id)
    rows = tuple(
        sorted(rows, key=lambda row: (row.window_start, row.theory_id, row.row_key))
    )
    selected = rows[position : position + limit]
    next_position = (
        position + len(selected) if position + len(selected) < len(rows) else None
    )
    return TheoryPage(
        section=section,
        rows=selected,
        next_position=next_position,
        window=window,
        theory_id=theory_id,
        limit=limit,
    )
