"""Deterministic offset/limit/byte-budget paging for evidence snapshots."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from simulation.evidence_testimony_models import (
    EVIDENCE_TESTIMONY_PAGE_MAX_BYTES,
    EVIDENCE_TESTIMONY_PAGE_MAX_ROWS,
    EvidenceTestimonyArtifactError,
    EvidenceTestimonySnapshot,
)

__all__ = [
    "EvidenceTestimonyRowSelection",
    "select_evidence_candidates",
    "select_evidence_contradictions",
    "select_evidence_lineage",
    "select_evidence_sources",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.evidence_testimony_paging")


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyRowSelection:
    """One bounded page of snapshot rows."""

    rows: tuple[object, ...]
    offset: int
    next_offset: int | None
    truncated: bool


def _row_bytes(row: object) -> int:
    return len(
        json.dumps(row, default=str, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )


def _select[RowT](
    rows: Sequence[RowT],
    offset: int,
    limit: int,
    byte_budget: int = EVIDENCE_TESTIMONY_PAGE_MAX_BYTES,
) -> EvidenceTestimonyRowSelection:
    if type(offset) is not int or offset < 0:
        raise EvidenceTestimonyArtifactError("evidence_testimony_size_limit")
    if type(limit) is not int or limit < 0:
        raise EvidenceTestimonyArtifactError("evidence_testimony_size_limit")
    bounded_limit = min(limit, EVIDENCE_TESTIMONY_PAGE_MAX_ROWS)
    bounded_bytes = min(max(byte_budget, 0), EVIDENCE_TESTIMONY_PAGE_MAX_BYTES)
    selected: list[object] = []
    used = 0
    index = offset
    while index < len(rows) and len(selected) < bounded_limit:
        row = rows[index]
        size = _row_bytes(row)
        if size > bounded_bytes:
            raise EvidenceTestimonyArtifactError("evidence_testimony_size_limit")
        if used + size > bounded_bytes:
            break
        selected.append(row)
        used += size
        index += 1
    truncated = index < len(rows)
    return EvidenceTestimonyRowSelection(
        rows=tuple(selected),
        offset=offset,
        next_offset=index if truncated else None,
        truncated=truncated,
    )


def _select_snapshot(
    snapshot: EvidenceTestimonySnapshot,
    attribute: str,
    offset: int,
    limit: int,
    byte_budget: int = EVIDENCE_TESTIMONY_PAGE_MAX_BYTES,
) -> EvidenceTestimonyRowSelection:
    if type(snapshot) is not EvidenceTestimonySnapshot:
        raise TypeError("snapshot must be EvidenceTestimonySnapshot")
    rows = getattr(snapshot, attribute)
    selection = _select(rows, offset, limit, byte_budget)
    _LOG.debug(
        "evidence_page purpose=%s offset=%s returned=%s truncated=%s",
        attribute,
        selection.offset,
        len(selection.rows),
        selection.truncated,
    )
    return selection


def select_evidence_candidates(
    snapshot: EvidenceTestimonySnapshot,
    *,
    offset: int = 0,
    limit: int = 100,
    byte_budget: int = EVIDENCE_TESTIMONY_PAGE_MAX_BYTES,
) -> EvidenceTestimonyRowSelection:
    return _select_snapshot(snapshot, "candidates", offset, limit, byte_budget)


def select_evidence_sources(
    snapshot: EvidenceTestimonySnapshot,
    *,
    offset: int = 0,
    limit: int = 100,
    byte_budget: int = EVIDENCE_TESTIMONY_PAGE_MAX_BYTES,
) -> EvidenceTestimonyRowSelection:
    return _select_snapshot(snapshot, "sources", offset, limit, byte_budget)


def select_evidence_contradictions(
    snapshot: EvidenceTestimonySnapshot,
    *,
    offset: int = 0,
    limit: int = 100,
    byte_budget: int = EVIDENCE_TESTIMONY_PAGE_MAX_BYTES,
) -> EvidenceTestimonyRowSelection:
    return _select_snapshot(snapshot, "contradictions", offset, limit, byte_budget)


def select_evidence_lineage(
    snapshot: EvidenceTestimonySnapshot,
    *,
    offset: int = 0,
    limit: int = 100,
    byte_budget: int = EVIDENCE_TESTIMONY_PAGE_MAX_BYTES,
) -> EvidenceTestimonyRowSelection:
    return _select_snapshot(snapshot, "edges", offset, limit, byte_budget)
