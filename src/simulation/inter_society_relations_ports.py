"""Typed read and publication ports for inter-society-relations snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.inter_society_relations_models import InterSocietyRelationsSnapshot
from simulation.inter_society_relations_paging import (
    MAX_PAGE_LIMIT,
    InterSocietyRelationsRowSelection,
    page_inter_society_relations_detail,
    page_inter_society_relations_rows,
)

__all__ = [
    "INTER_SOCIETY_RELATIONS_CURSOR_PURPOSES",
    "MAX_PAGE_LIMIT",
    "InterSocietyRelationsCursor",
    "InterSocietyRelationsPublication",
    "InterSocietyRelationsPublisherPort",
    "InterSocietyRelationsReadPort",
    "InterSocietyRelationsSummary",
    "bounded_inter_society_relations_detail_rows",
    "inter_society_relations_cursor_matches",
    "inter_society_relations_query_fingerprint",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.inter_society_relations.ports"
)

INTER_SOCIETY_RELATIONS_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "pairs",
    "pair",
    "series",
    "windows",
    "comparison",
)
_PURPOSE_SET: Final[frozenset[str]] = frozenset(INTER_SOCIETY_RELATIONS_CURSOR_PURPOSES)


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsSummary:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    pair_count: int = 0
    window_count: int = 0
    series_point_count: int = 0
    comparison_count: int = 0
    coverage: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsPublication:
    publication_id: str
    digest: str
    snapshot: InterSocietyRelationsSnapshot


@dataclass(frozen=True, slots=True)
class InterSocietyRelationsCursor:
    purpose: str
    after_key: str | None
    limit: int
    fingerprint: str
    expires_at_tick: int | None = None

    def __post_init__(self) -> None:
        if self.purpose not in _PURPOSE_SET:
            raise ValueError("inter_society_relations_cursor_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("inter_society_relations_cursor_fingerprint")
        if type(self.limit) is not int or self.limit < 1 or self.limit > MAX_PAGE_LIMIT:
            raise ValueError("inter_society_relations_page_limit")
        if self.after_key is not None and (
            type(self.after_key) is not str or not self.after_key
        ):
            raise ValueError("inter_society_relations_cursor_after_key")
        if self.expires_at_tick is not None and (
            type(self.expires_at_tick) is not int or self.expires_at_tick < 0
        ):
            raise ValueError("inter_society_relations_cursor_expiry")


def inter_society_relations_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
    after_key: str | None = None,
    limit: int,
) -> str:
    if purpose not in _PURPOSE_SET:
        raise ValueError("inter_society_relations_cursor_purpose")
    if type(limit) is not int or limit < 1 or limit > MAX_PAGE_LIMIT:
        raise ValueError("inter_society_relations_page_limit")
    payload = {
        "after_key": after_key,
        "digest": digest,
        "filters": {
            str(key): (filters or {})[key]
            for key in sorted((filters or {}), key=str)
        },
        "limit": limit,
        "publication_id": publication_id,
        "purpose": purpose,
        "run_id": run_id,
        "v": "palimpsest.inter_society_relations.cursor.v1",
    }
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def inter_society_relations_cursor_matches(
    cursor: InterSocietyRelationsCursor, fingerprint: str
) -> bool:
    if type(cursor) is not InterSocietyRelationsCursor:
        return False
    matched = cursor.fingerprint == fingerprint
    if not matched:
        _LOG.warning("inter_society_relations_cursor_invalid")
    return matched


def bounded_inter_society_relations_detail_rows(
    snapshot: InterSocietyRelationsSnapshot,
    purpose: str,
    after_key: str | None,
    limit: int,
) -> object:

    if purpose not in _PURPOSE_SET:
        raise ValueError("inter_society_relations_cursor_purpose")
    if purpose == "pair":
        return page_inter_society_relations_detail(snapshot, purpose, after_key)
    selection = page_inter_society_relations_rows(
        snapshot,
        InterSocietyRelationsRowSelection(
            purpose=purpose,
            after_key=after_key,
            limit=limit,
        ),
    )
    _LOG.debug(
        "inter_society_relations_page purpose=%s rows=%s",
        purpose,
        len(selection.rows),
    )
    return selection


@runtime_checkable
class InterSocietyRelationsReadPort(Protocol):
    def summary(self, run_id: str) -> InterSocietyRelationsSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> InterSocietyRelationsSnapshot | None: ...

    def list_publications(self, run_id: str) -> tuple[str, ...]: ...


@runtime_checkable
class InterSocietyRelationsPublisherPort(Protocol):
    def publish(self, snapshot: InterSocietyRelationsSnapshot) -> None: ...

    def read_summary(self, run_id: str) -> InterSocietyRelationsSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> InterSocietyRelationsSnapshot | None: ...
