"""Deterministic offset/limit paging for representation snapshots."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from simulation.delegation_representation_models import (
    DELEGATION_REPRESENTATION_PAGE_MAX_ROWS,
    DelegationRepresentationArtifactError,
    DelegationRepresentationSnapshot,
)

__all__ = [
    "RepresentationRowSelection",
    "select_representation_candidates",
    "select_representation_lineage",
    "select_representation_mandates",
    "select_representation_positions",
    "select_representation_revocations",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.delegation_representation_paging"
)


@dataclass(frozen=True, slots=True)
class RepresentationRowSelection:
    rows: tuple[object, ...]
    offset: int
    next_offset: int | None
    truncated: bool


def _select[RowT](
    rows: Sequence[RowT], offset: int, limit: int
) -> RepresentationRowSelection:
    if type(offset) is not int or offset < 0:
        raise DelegationRepresentationArtifactError(
            "delegation_representation_size_limit"
        )
    if type(limit) is not int or limit < 0:
        raise DelegationRepresentationArtifactError(
            "delegation_representation_size_limit"
        )
    bounded = min(limit, DELEGATION_REPRESENTATION_PAGE_MAX_ROWS)
    if bounded == 0:
        return RepresentationRowSelection((), offset, None, False)
    selected = tuple(rows[offset : offset + bounded])
    next_offset = offset + len(selected)
    truncated = next_offset < len(rows)
    return RepresentationRowSelection(
        rows=selected,
        offset=offset,
        next_offset=next_offset if truncated else None,
        truncated=truncated,
    )


def _select_snapshot(
    snapshot: DelegationRepresentationSnapshot,
    attribute: str,
    offset: int,
    limit: int,
) -> RepresentationRowSelection:
    if type(snapshot) is not DelegationRepresentationSnapshot:
        raise TypeError("snapshot must be DelegationRepresentationSnapshot")
    selection = _select(getattr(snapshot, attribute), offset, limit)
    _LOG.debug(
        "representation_page purpose=%s offset=%s returned=%s",
        attribute,
        selection.offset,
        len(selection.rows),
    )
    return selection


def select_representation_candidates(
    snapshot: DelegationRepresentationSnapshot,
    *,
    cursor_offset: int = 0,
    limit: int = 100,
) -> RepresentationRowSelection:
    return _select_snapshot(snapshot, "candidates", cursor_offset, limit)


def select_representation_mandates(
    snapshot: DelegationRepresentationSnapshot,
    *,
    cursor_offset: int = 0,
    limit: int = 100,
) -> RepresentationRowSelection:
    return _select_snapshot(snapshot, "mandates", cursor_offset, limit)


def select_representation_positions(
    snapshot: DelegationRepresentationSnapshot,
    *,
    cursor_offset: int = 0,
    limit: int = 100,
) -> RepresentationRowSelection:
    return _select_snapshot(snapshot, "positions", cursor_offset, limit)


def select_representation_revocations(
    snapshot: DelegationRepresentationSnapshot,
    *,
    cursor_offset: int = 0,
    limit: int = 100,
) -> RepresentationRowSelection:
    return _select_snapshot(snapshot, "revocations", cursor_offset, limit)


def select_representation_lineage(
    snapshot: DelegationRepresentationSnapshot,
    *,
    cursor_offset: int = 0,
    limit: int = 100,
) -> RepresentationRowSelection:
    return _select_snapshot(snapshot, "lineage", cursor_offset, limit)
