"""Bounded pure paging for scientific-knowledge diffusion sections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from simulation.science_diffusion_models import ScienceDiffusionSnapshot

__all__ = [
    "DEFAULT_SCIENCE_DIFFUSION_PAGE_LIMIT",
    "MAX_SCIENCE_DIFFUSION_PAGE_LIMIT",
    "ScienceDiffusionPage",
    "page_science_diffusion_rows",
]

DEFAULT_SCIENCE_DIFFUSION_PAGE_LIMIT: Final[int] = 50
MAX_SCIENCE_DIFFUSION_PAGE_LIMIT: Final[int] = 100


@dataclass(frozen=True, slots=True)
class ScienceDiffusionPage:
    rows: tuple[object, ...]
    next_position: int | None


def page_science_diffusion_rows(
    snapshot: ScienceDiffusionSnapshot,
    *,
    section: str,
    position: int,
    limit: int,
) -> ScienceDiffusionPage:
    if isinstance(position, bool) or type(position) is not int or position < 0:
        raise ValueError("position: invalid")
    if isinstance(limit, bool) or type(limit) is not int:
        raise ValueError("limit: invalid")
    if not 1 <= limit <= MAX_SCIENCE_DIFFUSION_PAGE_LIMIT:
        raise ValueError("limit: invalid")
    rows = snapshot.rows_for(section)
    if position > len(rows):
        raise ValueError("position: invalid")
    end = position + limit
    page = rows[position:end]
    return ScienceDiffusionPage(
        rows=page,
        next_position=end if end < len(rows) else None,
    )
