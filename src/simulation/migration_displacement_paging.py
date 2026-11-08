# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Bounded deterministic paging for migration-displacement snapshot rows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from simulation.migration_displacement_models import MigrationDisplacementSnapshot

__all__ = [
    "MAX_PAGE_LIMIT",
    "MigrationRowSelection",
    "page_migration_detail",
    "page_migration_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.migration_displacement.paging"
)

MAX_PAGE_LIMIT: Final[int] = 500
_LIST_PURPOSES: Final[frozenset[str]] = frozenset(
    {"summary", "waves", "routes", "causes", "outcomes"}
)
_DETAIL_PURPOSES: Final[frozenset[str]] = frozenset({"wave"})


@dataclass(frozen=True, slots=True)
class MigrationRowSelection:
    """One bounded page request/response for a migration cursor purpose."""

    purpose: str
    after_key: str | None
    limit: int
    rows: tuple[object, ...] = ()
    next_key: str | None = None


def _clamp_limit(limit: object) -> int:
    if type(limit) is not int or limit < 1 or limit > MAX_PAGE_LIMIT:
        raise ValueError("migration_displacement_page_limit")
    return limit


def _row_key(purpose: str, row: object) -> str:
    if purpose == "summary":
        return "summary"
    if purpose == "waves":
        return f"{row.start_tick:020d}|{row.wave_token}"
    if purpose == "routes":
        return f"{row.owner_token}|{row.first_tick:020d}|{row.route_token}"
    if purpose == "causes":
        return f"{row.owner_token}|{row.tick:020d}|{row.cause_token}"
    if purpose == "outcomes":
        return (
            f"{row.participant_token}|{row.destination_token}|{row.outcome_token}"
        )
    raise ValueError("migration_displacement_cursor_purpose")


def _ordered_rows(
    snapshot: MigrationDisplacementSnapshot, purpose: str
) -> tuple[object, ...]:
    if purpose == "summary":
        return (snapshot.summary,)
    if purpose == "waves":
        rows = sorted(
            snapshot.waves, key=lambda row: (row.start_tick, row.wave_token)
        )
        return tuple(rows)
    if purpose == "routes":
        rows = sorted(
            snapshot.routes,
            key=lambda row: (row.owner_token, row.first_tick, row.route_token),
        )
        return tuple(rows)
    if purpose == "causes":
        rows = sorted(
            snapshot.causes,
            key=lambda row: (row.owner_token, row.tick, row.cause_token),
        )
        return tuple(rows)
    if purpose == "outcomes":
        rows = sorted(
            snapshot.outcomes,
            key=lambda row: (
                row.participant_token,
                row.destination_token,
                row.outcome_token,
            ),
        )
        return tuple(rows)
    raise ValueError("migration_displacement_cursor_purpose")


def page_migration_rows(
    snapshot: MigrationDisplacementSnapshot,
    selection: MigrationRowSelection | None = None,
    *,
    purpose: str | None = None,
    after_key: str | None = None,
    limit: int | None = None,
) -> MigrationRowSelection:
    """Return one stable page of rows without mutating the published snapshot."""
    if type(snapshot) is not MigrationDisplacementSnapshot:
        raise TypeError("snapshot must be MigrationDisplacementSnapshot")
    if selection is not None:
        if type(selection) is not MigrationRowSelection:
            raise TypeError("selection must be MigrationRowSelection")
        purpose = selection.purpose
        after_key = selection.after_key
        limit = selection.limit
    if purpose is None or purpose not in _LIST_PURPOSES:
        raise ValueError("migration_displacement_cursor_purpose")
    clamped = _clamp_limit(1 if limit is None else limit)
    ordered = list(_ordered_rows(snapshot, purpose))
    if after_key is not None:
        if type(after_key) is not str or not after_key:
            raise ValueError("migration_displacement_cursor_after_key")
        ordered = [row for row in ordered if _row_key(purpose, row) > after_key]
    page = tuple(ordered[:clamped])
    next_key = (
        _row_key(purpose, page[-1]) if len(ordered) > len(page) and page else None
    )
    result = MigrationRowSelection(
        purpose=purpose,
        after_key=after_key,
        limit=clamped,
        rows=page,
        next_key=next_key,
    )
    _LOG.debug(
        "migration_displacement_page purpose=%s rows=%s",
        purpose,
        len(page),
    )
    return result


def page_migration_detail(
    snapshot: MigrationDisplacementSnapshot,
    purpose: str,
    key: str | None,
) -> object | None:
    """Return one detail row by token, or None for an unknown key."""
    if type(snapshot) is not MigrationDisplacementSnapshot:
        raise TypeError("snapshot must be MigrationDisplacementSnapshot")
    if purpose not in _DETAIL_PURPOSES:
        raise ValueError("migration_displacement_cursor_purpose")
    if key is None or type(key) is not str or not key:
        return None
    if purpose == "wave":
        for row in snapshot.waves:
            if row.wave_token == key:
                return row
        return None
    return None
