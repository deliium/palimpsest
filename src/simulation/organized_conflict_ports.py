# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Typed read and publication ports for organized conflict."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.organized_conflict_models import OrganizedConflictSnapshot

__all__ = [
    "ORGANIZED_CONFLICT_CURSOR_PURPOSES",
    "OrganizedConflictCursor",
    "OrganizedConflictPublication",
    "OrganizedConflictPublicationPort",
    "OrganizedConflictPublisherPort",
    "OrganizedConflictReadPort",
    "OrganizedConflictSummary",
    "bounded_conflict_detail_rows",
    "organized_conflict_cursor_matches",
    "organized_conflict_query_fingerprint",
]

ORGANIZED_CONFLICT_CURSOR_PURPOSES: Final[frozenset[str]] = frozenset(
    {"summary", "episodes", "episode", "plans", "plan", "interpretations"}
)


@dataclass(frozen=True, slots=True)
class OrganizedConflictSummary:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    episode_count: int = 0
    plan_count: int = 0
    interpretation_count: int = 0
    coverage: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class OrganizedConflictPublication:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    summary: OrganizedConflictSummary


@dataclass(frozen=True, slots=True)
class OrganizedConflictCursor:
    purpose: str
    fingerprint: str
    after_key: str | None = None

    def __post_init__(self) -> None:
        if self.purpose not in ORGANIZED_CONFLICT_CURSOR_PURPOSES:
            raise ValueError("organized_conflict_cursor_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("organized_conflict_cursor_fingerprint")


def organized_conflict_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
) -> str:
    if purpose not in ORGANIZED_CONFLICT_CURSOR_PURPOSES:
        raise ValueError("organized_conflict_cursor_purpose")
    material = [
        "palimpsest.organized_conflict.cursor.v1",
        run_id,
        publication_id,
        digest,
        purpose,
    ]
    for key, value in sorted((filters or {}).items()):
        material.append(f"{key}={value}")
    return hashlib.sha256("|".join(material).encode("utf-8")).hexdigest()


def organized_conflict_cursor_matches(
    cursor: OrganizedConflictCursor, fingerprint: str
) -> bool:
    return cursor.fingerprint == fingerprint


def bounded_conflict_detail_rows(rows: object, *, limit: int) -> tuple[tuple, bool]:
    ordered = tuple(sorted(rows, key=str))  # type: ignore[arg-type]
    return ordered[:limit], len(ordered) > limit


@runtime_checkable
class OrganizedConflictReadPort(Protocol):
    def summary(self, run_id: str) -> OrganizedConflictSummary | None: ...

    def episodes(self, run_id: str, *, after: str | None, limit: int) -> tuple: ...

    def episode(self, run_id: str, episode_id: str) -> tuple: ...

    def plans(self, run_id: str, *, after: str | None, limit: int) -> tuple: ...

    def plan(self, run_id: str, plan_id: str) -> tuple: ...

    def interpretations(
        self, run_id: str, *, after: str | None, limit: int
    ) -> tuple: ...


@runtime_checkable
class OrganizedConflictPublisherPort(Protocol):
    def publish(self, snapshot: OrganizedConflictSnapshot) -> None: ...


@runtime_checkable
class OrganizedConflictPublicationPort(Protocol):
    def read(
        self, run_id: str, publication_id: str
    ) -> OrganizedConflictSnapshot | None: ...
