"""Pure, snapshot-pinned selection over published predictive rows."""

from __future__ import annotations

from typing import Final

from simulation.scientific_models_models import (
    ScientificModelsSnapshot,
    ScientificPredictionRow,
)
from simulation.scientific_models_ports import ScientificModelsPage

__all__ = ["MAX_PAGE_SIZE", "MIN_PAGE_SIZE", "page_scientific_models_rows"]

MIN_PAGE_SIZE: Final[int] = 1
MAX_PAGE_SIZE: Final[int] = 500

_SECTIONS: Final[frozenset[str]] = frozenset(
    {
        "models",
        "predictions",
        "outcomes",
        "calibration",
        "revisions",
        "comparisons",
        "coverage",
    }
)


def _fail(code: str) -> ValueError:
    return ValueError(code)


def page_scientific_models_rows(
    snapshot: ScientificModelsSnapshot,
    *,
    section: str,
    page_size: int,
    offset: int = 0,
    model_token: str | None = None,
    target_kind: str | None = None,
    status: str | None = None,
    issued_from_tick: int | None = None,
    issued_through_tick: int | None = None,
) -> ScientificModelsPage:
    """Return a stable page from one immutable snapshot section."""

    if type(snapshot) is not ScientificModelsSnapshot:
        raise _fail("scientific_models_invalid_snapshot")
    if section not in _SECTIONS:
        raise _fail("scientific_models_unknown_section")
    if isinstance(page_size, bool) or type(page_size) is not int:
        raise _fail("scientific_models_invalid_page_size")
    if not MIN_PAGE_SIZE <= page_size <= MAX_PAGE_SIZE:
        raise _fail("scientific_models_invalid_page_size")
    if isinstance(offset, bool) or type(offset) is not int or offset < 0:
        raise _fail("scientific_models_invalid_offset")
    for name, value in (
        ("issued_from_tick", issued_from_tick),
        ("issued_through_tick", issued_through_tick),
    ):
        if value is not None and (
            isinstance(value, bool) or type(value) is not int or value < 0
        ):
            raise _fail(f"scientific_models_invalid_{name}")
    if (
        issued_from_tick is not None
        and issued_through_tick is not None
        and issued_from_tick > issued_through_tick
    ):
        raise _fail("scientific_models_invalid_tick_range")

    rows: list[object] = list(getattr(snapshot, section))
    if model_token is not None:
        rows = [
            row
            for row in rows
            if getattr(row, "model_token", None) == model_token
            or getattr(row, "model_a_token", None) == model_token
            or getattr(row, "model_b_token", None) == model_token
        ]
    if target_kind is not None:
        rows = [row for row in rows if getattr(row, "target_kind", None) == target_kind]
    if status is not None:
        rows = [
            row
            for row in rows
            if getattr(row, "status", None) == status
            or getattr(row, "state", None) == status
        ]
    if issued_from_tick is not None or issued_through_tick is not None:
        rows = [
            row
            for row in rows
            if isinstance(row, ScientificPredictionRow)
            and (issued_from_tick is None or row.issued_tick >= issued_from_tick)
            and (issued_through_tick is None or row.issued_tick <= issued_through_tick)
        ]
    total = len(rows)
    if offset > total:
        raise _fail("scientific_models_invalid_offset")
    page = tuple(rows[offset : offset + page_size])
    next_offset = offset + page_size
    return ScientificModelsPage(
        rows=page,
        next_offset=next_offset if next_offset < total else None,
        total=total,
    )
