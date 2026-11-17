"""Stable keyset paging for replication snapshot rows."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Final

from simulation.replication_ports import ReplicationPublicationError

PAGE_LIMIT_MAX: Final[int] = 500
_PREFIX: Final[str] = "rcur-"


@dataclass(frozen=True, slots=True)
class ReplicationPage:
    rows: tuple[dict[str, object], ...]
    next_cursor: str | None
    truncated: bool


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def page_replication_rows(
    rows: tuple[dict[str, object], ...],
    *,
    run_id: str,
    publication_id: str,
    query_fingerprint: str,
    limit: int,
    cursor: str | None,
    cursor_key: bytes,
) -> ReplicationPage:
    if isinstance(limit, bool) or type(limit) is not int or limit < 1:
        raise ReplicationPublicationError("replication_paging_invalid_limit")
    limit = min(limit, PAGE_LIMIT_MAX)
    ordered = sorted(rows, key=lambda row: str(row.get("row_token", "")))
    start = 0
    if cursor is not None:
        if not cursor.startswith(_PREFIX):
            raise ReplicationPublicationError("replication_paging_invalid_cursor")
        encoded, signature = cursor[len(_PREFIX):].split(".", 1)
        payload = _unb64(encoded)
        expected = hmac.new(cursor_key, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ReplicationPublicationError("replication_paging_invalid_cursor")
        data = json.loads(payload.decode("utf-8"))
        if (
            data.get("run_id") != run_id
            or data.get("publication_id") != publication_id
            or data.get("query") != query_fingerprint
            or type(data.get("offset")) is not int
        ):
            raise ReplicationPublicationError("replication_paging_invalid_cursor")
        start = data["offset"]
    selected = ordered[start : start + limit]
    next_cursor = None
    if start + limit < len(ordered):
        payload = json.dumps(
            {
                "run_id": run_id,
                "publication_id": publication_id,
                "query": query_fingerprint,
                "offset": start + limit,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(cursor_key, payload, hashlib.sha256).hexdigest()
        next_cursor = _PREFIX + _b64(payload) + "." + signature
    return ReplicationPage(
        rows=tuple(dict(row) for row in selected),
        next_cursor=next_cursor,
        truncated=next_cursor is not None,
    )


__all__ = ["PAGE_LIMIT_MAX", "ReplicationPage", "page_replication_rows"]
