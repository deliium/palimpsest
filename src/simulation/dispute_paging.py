"""Bounded whole-row paging for ``dispute-resolution-snapshot-v1`` rows."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, Final, cast

from simulation.dispute_models import (
    MAX_PAGE_ROWS,
    MAX_RESPONSE_BYTES,
    DisputeArtifactError,
)

__all__ = [
    "DisputeRowSelection",
    "dispute_row_encoded_bytes",
    "row_encoded_bytes",
    "select_dispute_candidate_rows",
    "select_dispute_claim_rows",
    "select_dispute_lineage_rows",
    "select_dispute_resolution_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.dispute_paging")


@dataclass(frozen=True, slots=True)
class DisputeRowSelection:
    items: tuple[object, ...]
    truncated: bool
    next_offset: int | None
    encoded_bytes: int

    def __post_init__(self) -> None:
        if type(self.truncated) is not bool:
            raise DisputeArtifactError("dispute_invalid_value")
        if self.next_offset is not None and (
            type(self.next_offset) is not int or self.next_offset < 0
        ):
            raise DisputeArtifactError("dispute_page_offset")
        if type(self.encoded_bytes) is not int or self.encoded_bytes < 0:
            raise DisputeArtifactError("dispute_size_limit")


def row_encoded_bytes(row: object) -> bytes:
    """Canonical bytes for one whole row plus a newline."""
    payload = json.dumps(
        asdict(cast(Any, row)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return payload + b"\n"


def dispute_row_encoded_bytes(row: object) -> bytes:
    """Public alias for the canonical whole-row byte size."""
    return row_encoded_bytes(row)


def _select(
    rows: Sequence[Any],
    *,
    offset: int,
    limit: int,
    max_bytes: int,
) -> DisputeRowSelection:
    if type(offset) is not int or offset < 0:
        raise DisputeArtifactError("dispute_page_offset")
    if type(limit) is not int or limit < 0:
        raise DisputeArtifactError("dispute_page_limit")
    if limit > MAX_PAGE_ROWS:
        limit = MAX_PAGE_ROWS
    if max_bytes > MAX_RESPONSE_BYTES:
        max_bytes = MAX_RESPONSE_BYTES
    if max_bytes < 1:
        raise DisputeArtifactError("dispute_size_limit")
    selected: list[object] = []
    used = 0
    cursor = offset
    while cursor < len(rows) and len(selected) < limit:
        encoded = row_encoded_bytes(rows[cursor])
        if len(encoded) > max_bytes:
            raise DisputeArtifactError("dispute_size_limit")
        if used + len(encoded) > max_bytes:
            break
        selected.append(rows[cursor])
        used += len(encoded)
        cursor += 1
    truncated = cursor < len(rows)
    _LOG.debug(
        "dispute_page rows=%s truncated=%s",
        len(selected),
        truncated,
    )
    return DisputeRowSelection(
        items=tuple(selected),
        truncated=truncated,
        next_offset=cursor if truncated else None,
        encoded_bytes=used,
    )


def select_dispute_candidate_rows(
    rows: Sequence[object],
    *,
    status: str | None,
    offset: int,
    limit: int,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> DisputeRowSelection:
    """Select whole candidate rows in deterministic identity order."""
    filtered = [
        row for row in rows if status is None or getattr(row, "status", None) == status
    ]
    filtered.sort(key=lambda item: getattr(item, "candidate_id", ""))
    return _select(filtered, offset=offset, limit=limit, max_bytes=max_bytes)


def select_dispute_claim_rows(
    rows: Sequence[object],
    *,
    candidate_id: str,
    role: str | None,
    offset: int,
    limit: int,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> DisputeRowSelection:
    """Select whole claim rows for one candidate and optional claim role."""
    filtered = [
        row
        for row in rows
        if (candidate_id == "" or getattr(row, "candidate_id", "") == candidate_id)
        and (role is None or getattr(row, "role", None) == role)
    ]
    filtered.sort(key=lambda item: getattr(item, "claim_id", ""))
    return _select(filtered, offset=offset, limit=limit, max_bytes=max_bytes)


def select_dispute_resolution_rows(
    rows: Sequence[object],
    *,
    candidate_id: str,
    status: str | None,
    offset: int,
    limit: int,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> DisputeRowSelection:
    """Select whole resolution rows for one candidate and optional status."""
    filtered = [
        row
        for row in rows
        if (candidate_id == "" or getattr(row, "candidate_id", "") == candidate_id)
        and (status is None or getattr(row, "status", None) == status)
    ]
    filtered.sort(key=lambda item: getattr(item, "resolution_id", ""))
    return _select(filtered, offset=offset, limit=limit, max_bytes=max_bytes)


def select_dispute_lineage_rows(
    rows: Sequence[object],
    *,
    kind: str | None,
    offset: int,
    limit: int,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> DisputeRowSelection:
    """Select whole lineage edges in deterministic identity order."""
    filtered = [
        row for row in rows if kind is None or getattr(row, "kind", None) == kind
    ]
    filtered.sort(key=lambda item: getattr(item, "edge_id", ""))
    return _select(filtered, offset=offset, limit=limit, max_bytes=max_bytes)
