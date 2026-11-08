# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Typed read and publication ports for migration-displacement snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.migration_displacement_models import (
    MigrationDisplacementSnapshot,
)
from simulation.migration_displacement_paging import (
    MAX_PAGE_LIMIT,
    MigrationRowSelection,
    page_migration_detail,
    page_migration_rows,
)

__all__ = [
    "MAX_PAGE_LIMIT",
    "MIGRATION_DISPLACEMENT_CURSOR_PURPOSES",
    "MigrationDisplacementCursor",
    "MigrationDisplacementPublication",
    "MigrationDisplacementPublisherPort",
    "MigrationDisplacementReadPort",
    "MigrationDisplacementSummary",
    "bounded_migration_detail_rows",
    "migration_displacement_cursor_matches",
    "migration_displacement_query_fingerprint",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.migration_displacement.ports"
)

MIGRATION_DISPLACEMENT_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "waves",
    "wave",
    "routes",
    "causes",
    "outcomes",
)
_PURPOSE_SET: Final[frozenset[str]] = frozenset(MIGRATION_DISPLACEMENT_CURSOR_PURPOSES)


@dataclass(frozen=True, slots=True)
class MigrationDisplacementSummary:
    """Compact publication summary for list and status surfaces."""

    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    candidate_count: int = 0
    wave_count: int = 0
    cluster_count: int = 0
    outcome_count: int = 0
    movement_count: int = 0
    cause_count: int = 0
    coverage: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class MigrationDisplacementPublication:
    """Committed publication handle with the immutable snapshot."""

    publication_id: str
    digest: str
    snapshot: MigrationDisplacementSnapshot


@dataclass(frozen=True, slots=True)
class MigrationDisplacementCursor:
    """Opaque paging cursor bound to one publication query."""

    purpose: str
    after_key: str | None
    limit: int
    fingerprint: str
    expires_at_tick: int | None = None

    def __post_init__(self) -> None:
        if self.purpose not in _PURPOSE_SET:
            raise ValueError("migration_displacement_cursor_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("migration_displacement_cursor_fingerprint")
        if type(self.limit) is not int or self.limit < 1 or self.limit > MAX_PAGE_LIMIT:
            raise ValueError("migration_displacement_page_limit")
        if self.after_key is not None and (
            type(self.after_key) is not str or not self.after_key
        ):
            raise ValueError("migration_displacement_cursor_after_key")
        if self.expires_at_tick is not None and (
            type(self.expires_at_tick) is not int or self.expires_at_tick < 0
        ):
            raise ValueError("migration_displacement_cursor_expiry")


def migration_displacement_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
    after_key: str | None = None,
    limit: int,
) -> str:
    """SHA-256 over the canonical binding for one cursor purpose."""
    if purpose not in _PURPOSE_SET:
        raise ValueError("migration_displacement_cursor_purpose")
    if type(limit) is not int or limit < 1 or limit > MAX_PAGE_LIMIT:
        raise ValueError("migration_displacement_page_limit")
    payload = {
        "after_key": after_key,
        "digest": digest,
        "filters": {
            str(key): filters[key]
            for key in sorted((filters or {}), key=str)
        },
        "limit": limit,
        "publication_id": publication_id,
        "purpose": purpose,
        "run_id": run_id,
        "v": "palimpsest.migration_displacement.cursor.v1",
    }
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def migration_displacement_cursor_matches(
    cursor: MigrationDisplacementCursor, fingerprint: str
) -> bool:
    """Return True only when the cursor fingerprint matches the binding."""
    if type(cursor) is not MigrationDisplacementCursor:
        return False
    matched = cursor.fingerprint == fingerprint
    if not matched:
        _LOG.warning("migration_displacement_cursor_invalid")
    return matched


def bounded_migration_detail_rows(
    snapshot: MigrationDisplacementSnapshot,
    purpose: str,
    after_key: str | None,
    limit: int,
) -> object:
    """Page or detail-lookup rows for one cursor purpose from a snapshot."""
    if purpose not in _PURPOSE_SET:
        raise ValueError("migration_displacement_cursor_purpose")
    if purpose == "wave":
        return page_migration_detail(snapshot, purpose, after_key)
    selection = page_migration_rows(
        snapshot,
        MigrationRowSelection(
            purpose=purpose,
            after_key=after_key,
            limit=limit,
        ),
    )
    _LOG.debug(
        "migration_displacement_page purpose=%s rows=%s",
        purpose,
        len(selection.rows),
    )
    return selection


@runtime_checkable
class MigrationDisplacementReadPort(Protocol):
    def summary(self, run_id: str) -> MigrationDisplacementSummary | None: ...

    def waves(
        self, run_id: str, *, after: str | None, limit: int
    ) -> tuple[object, ...]: ...

    def wave(self, run_id: str, wave_token: str) -> object | None: ...

    def routes(
        self, run_id: str, *, after: str | None, limit: int
    ) -> tuple[object, ...]: ...

    def causes(
        self, run_id: str, *, after: str | None, limit: int
    ) -> tuple[object, ...]: ...

    def outcomes(
        self, run_id: str, *, after: str | None, limit: int
    ) -> tuple[object, ...]: ...


@runtime_checkable
class MigrationDisplacementPublisherPort(Protocol):
    def publish(self, snapshot: MigrationDisplacementSnapshot) -> None: ...

    def read_summary(self, run_id: str) -> MigrationDisplacementSummary | None: ...

    def read_snapshot(self, run_id: str) -> MigrationDisplacementSnapshot | None: ...
