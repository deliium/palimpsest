"""Bounded pure paging for scientific-institution snapshot sections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from simulation.scientific_institutions_models import (
    ScientificInstitutionsRow,
    ScientificInstitutionsSnapshot,
)

__all__ = [
    "DEFAULT_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT",
    "MAX_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT",
    "ScientificInstitutionsPage",
    "page_scientific_institution_rows",
]

DEFAULT_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT: Final[int] = 100
MAX_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT: Final[int] = 500


@dataclass(frozen=True, slots=True)
class ScientificInstitutionsPage:
    rows: tuple[ScientificInstitutionsRow, ...]
    next_position: int | None


def page_scientific_institution_rows(
    snapshot: ScientificInstitutionsSnapshot,
    *,
    section: str,
    position: int,
    limit: int,
) -> ScientificInstitutionsPage:
    if (
        isinstance(position, bool)
        or not isinstance(position, int)
        or position < 0
    ):
        raise ValueError("position: invalid")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit: invalid")
    if not 1 <= limit <= MAX_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT:
        raise ValueError("limit: invalid")
    rows = snapshot.rows_for(section)
    if position > len(rows):
        raise ValueError("position: invalid")
    end = position + limit
    page = rows[position:end]
    next_position = end if end < len(rows) else None
    return ScientificInstitutionsPage(
        rows=page,
        next_position=next_position,
    )
