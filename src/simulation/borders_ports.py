"""Typed read and publication ports for border snapshots."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.borders_models import BORDERS_MAX_DETAIL_ROWS, BordersSnapshot

__all__ = [
    "BORDERS_CURSOR_PURPOSES",
    "BORDERS_MAX_DETAIL_ROWS",
    "BordersCursor",
    "BordersPublication",
    "BordersPublisherPort",
    "BordersReadPort",
    "BordersSummary",
    "borders_cursor_matches",
    "borders_query_fingerprint",
]

BORDERS_CURSOR_PURPOSES: Final[frozenset[str]] = frozenset(
    {"summary", "claims", "claim", "agreements", "agreement", "control"}
)


@dataclass(frozen=True, slots=True)
class BordersSummary:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    candidate_count: int = 0
    claim_count: int = 0
    agreement_count: int = 0
    dispute_count: int = 0
    physical_row_count: int = 0
    pattern_count: int = 0
    coverage: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class BordersPublication:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    summary: BordersSummary


@dataclass(frozen=True, slots=True)
class BordersCursor:
    purpose: str
    fingerprint: str
    after_key: str | None = None

    def __post_init__(self) -> None:
        if self.purpose not in BORDERS_CURSOR_PURPOSES:
            raise ValueError("borders_cursor_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("borders_cursor_fingerprint")


def borders_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
) -> str:
    if purpose not in BORDERS_CURSOR_PURPOSES:
        raise ValueError("borders_cursor_purpose")
    material = [
        "palimpsest.borders.cursor.v1",
        run_id,
        publication_id,
        digest,
        purpose,
    ]
    for key, value in sorted((filters or {}).items()):
        material.append(f"{key}={value}")
    return hashlib.sha256("|".join(material).encode("utf-8")).hexdigest()


def borders_cursor_matches(cursor: BordersCursor, fingerprint: str) -> bool:
    if type(cursor) is not BordersCursor:
        return False
    return cursor.fingerprint == fingerprint


def bounded_border_detail_rows(
    rows: Sequence[object], *, limit: int = BORDERS_MAX_DETAIL_ROWS
) -> tuple[tuple[object, ...], bool]:
    if type(limit) is not int or limit < 1 or limit > BORDERS_MAX_DETAIL_ROWS:
        raise ValueError("borders_page_limit")
    ordered = tuple(sorted(rows, key=str))
    return ordered[:limit], len(ordered) > limit


@runtime_checkable
class BordersReadPort(Protocol):
    def read_summary(self, run_id: str) -> BordersSummary | None: ...

    def read_claims(
        self, run_id: str, *, after: str | None, limit: int
    ) -> tuple[object, ...]: ...

    def read_claim(self, run_id: str, claim_id: str) -> object | None: ...

    def read_agreements(
        self, run_id: str, *, after: str | None, limit: int
    ) -> tuple[object, ...]: ...

    def read_agreement(self, run_id: str, agreement_id: str) -> object | None: ...

    def read_control(
        self, run_id: str, *, layer: str, after: str | None, limit: int
    ) -> tuple[object, ...]: ...


@runtime_checkable
class BordersPublisherPort(Protocol):
    def publish(self, snapshot: BordersSnapshot) -> None: ...
