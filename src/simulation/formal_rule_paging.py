"""Bounded whole-row paging for formal-rule snapshots."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, Final, cast

from simulation.formal_rule_models import (
    MAX_PAGE_ROWS,
    MAX_RESPONSE_BYTES,
    FormalRuleArtifactError,
)

__all__ = [
    "FormalRuleRowSelection",
    "row_encoded_bytes",
    "select_formal_rule_candidate_rows",
    "select_formal_rule_lineage_rows",
    "select_formal_rule_rows",
    "select_formal_rule_version_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.formal_rule_paging")


@dataclass(frozen=True, slots=True)
class FormalRuleRowSelection:
    rows: tuple[object, ...]
    next_offset: int | None
    truncated: bool
    encoded_bytes: int

    def __post_init__(self) -> None:
        if self.next_offset is not None and self.next_offset < 0:
            raise FormalRuleArtifactError("formal_rule_page_offset")
        if self.encoded_bytes < 0:
            raise FormalRuleArtifactError("formal_rule_size_limit")


def row_encoded_bytes(row: object) -> bytes:
    """Canonical bytes for one whole row plus a newline."""
    payload = json.dumps(
        asdict(cast(Any, row)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return payload + b"\n"


def _select(
    rows: Sequence[Any],
    *,
    offset: int,
    limit: int,
    byte_budget: int,
) -> FormalRuleRowSelection:
    if type(offset) is not int or offset < 0:
        raise FormalRuleArtifactError("formal_rule_page_offset")
    if type(limit) is not int or limit < 0:
        raise FormalRuleArtifactError("formal_rule_page_limit")
    if limit > MAX_PAGE_ROWS:
        limit = MAX_PAGE_ROWS
    if byte_budget > MAX_RESPONSE_BYTES:
        byte_budget = MAX_RESPONSE_BYTES
    if byte_budget < 1:
        raise FormalRuleArtifactError("formal_rule_size_limit")
    selected: list[object] = []
    used = 0
    cursor = offset
    while cursor < len(rows) and len(selected) < limit:
        encoded = row_encoded_bytes(rows[cursor])
        if len(encoded) > byte_budget:
            raise FormalRuleArtifactError("formal_rule_size_limit")
        if used + len(encoded) > byte_budget:
            break
        selected.append(rows[cursor])
        used += len(encoded)
        cursor += 1
    truncated = cursor < len(rows)
    _LOG.info("formal_rule_page rows=%s truncated=%s", len(selected), truncated)
    return FormalRuleRowSelection(
        rows=tuple(selected),
        next_offset=cursor if truncated else None,
        truncated=truncated,
        encoded_bytes=used,
    )


def select_formal_rule_candidate_rows(
    rows: Sequence[object],
    *,
    offset: int,
    limit: int,
    byte_budget: int,
) -> FormalRuleRowSelection:
    ordered = sorted(rows, key=lambda item: getattr(item, "candidate_id", ""))
    return _select(ordered, offset=offset, limit=limit, byte_budget=byte_budget)


def select_formal_rule_rows(
    rows: Sequence[object],
    *,
    candidate_id: str,
    offset: int,
    limit: int,
    byte_budget: int,
) -> FormalRuleRowSelection:
    filtered = [
        row for row in rows if getattr(row, "candidate_id", None) == candidate_id
    ]
    filtered.sort(key=lambda item: getattr(item, "rule_id", ""))
    return _select(filtered, offset=offset, limit=limit, byte_budget=byte_budget)


def select_formal_rule_version_rows(
    rows: Sequence[object],
    *,
    candidate_id: str,
    rule_id: str | None = None,
    offset: int,
    limit: int,
    byte_budget: int,
) -> FormalRuleRowSelection:
    filtered = [
        row
        for row in rows
        if (rule_id is None or getattr(row, "rule_id", None) == rule_id)
        and (
            getattr(row, "candidate_id", candidate_id) == candidate_id
            or candidate_id == ""
        )
    ]
    filtered.sort(
        key=lambda item: (
            getattr(item, "rule_id", ""),
            getattr(item, "version_number", 0),
        )
    )
    return _select(filtered, offset=offset, limit=limit, byte_budget=byte_budget)


def select_formal_rule_lineage_rows(
    rows: Sequence[object],
    *,
    offset: int,
    limit: int,
    byte_budget: int,
) -> FormalRuleRowSelection:
    ordered = sorted(rows, key=lambda item: getattr(item, "edge_id", ""))
    return _select(ordered, offset=offset, limit=limit, byte_budget=byte_budget)
