"""Deterministic byte-bounded organization row selection."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import Final

from simulation.organization_models import (
    MAX_PAGE_ROWS,
    OrganizationArtifactError,
)

__all__ = [
    "OrganizationRowSelection",
    "row_encoded_bytes",
    "select_organization_collective_decision_rows",
    "select_organization_rows",
]

MAX_PAGE_BYTES_GUARD: Final[int] = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class OrganizationRowSelection:
    rows: tuple[object, ...]
    next_offset: int
    truncated: bool
    encoded_bytes: int

    def __post_init__(self) -> None:
        if type(self.next_offset) is not int or self.next_offset < 0:
            raise OrganizationArtifactError("organization_page_offset")
        if type(self.encoded_bytes) is not int or self.encoded_bytes < 0:
            raise OrganizationArtifactError("organization_page_limit")
        if type(self.truncated) is not bool:
            raise OrganizationArtifactError("organization_page_limit")


def _canonical(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def row_encoded_bytes(row: object) -> int:
    """Count the canonical encoded size of one row without splitting it."""
    encoded = json.dumps(
        _canonical(row), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return len(encoded.encode()) + 1


def select_organization_rows(
    rows: Sequence[object],
    *,
    offset: int,
    limit: int,
    max_bytes: int,
) -> OrganizationRowSelection:
    """Select whole rows without exceeding the byte or row budget."""
    if type(offset) is not int or offset < 0:
        raise OrganizationArtifactError("organization_page_offset")
    if type(limit) is not int or limit < 1 or limit > MAX_PAGE_ROWS:
        raise OrganizationArtifactError("organization_page_limit")
    if type(max_bytes) is not int or max_bytes < 1:
        raise OrganizationArtifactError("organization_page_limit")
    if isinstance(rows, (str, bytes)):
        raise OrganizationArtifactError("organization_page_limit")
    ordered = tuple(rows)
    if offset > len(ordered):
        raise OrganizationArtifactError("organization_page_offset")
    selected: list[object] = []
    used = 0
    truncated = False
    for row in ordered[offset:]:
        if len(selected) >= limit:
            truncated = True
            break
        size = row_encoded_bytes(row)
        if used + size > max_bytes:
            truncated = True
            break
        selected.append(row)
        used += size
        if used > MAX_PAGE_BYTES_GUARD:
            raise OrganizationArtifactError("organization_size_limit")
    return OrganizationRowSelection(
        rows=tuple(selected),
        next_offset=offset + len(selected),
        truncated=truncated or (offset + len(selected) < len(ordered)),
        encoded_bytes=used,
    )


def select_organization_collective_decision_rows(
    rows: Sequence[object],
    *,
    offset: int,
    limit: int,
    max_bytes: int,
) -> OrganizationRowSelection:
    """Select whole decision rows with their nested implementations."""

    return select_organization_rows(
        rows, offset=offset, limit=limit, max_bytes=max_bytes
    )
