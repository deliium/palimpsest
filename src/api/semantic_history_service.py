"""Bounded retained semantic-history reads over owner checkpoints."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from api.errors import bad_request, conflict
from api.research_cultural_cursor import CulturalCursorCodec, CulturalCursorError
from observer.semantic_history import (
    SEMANTIC_HISTORY_SOURCES,
    ProjectedSemanticHistory,
    SemanticHistoryRow,
    SemanticHistoryTerm,
    project_semantic_history,
)

_PURPOSE: Final[str] = "observer-semantic-history-page"
_SCHEMA: Final[str] = "observer-semantic-history-v1"
_MAX_LIMIT: Final[int] = 200


@dataclass(frozen=True, slots=True)
class SemanticHistoryResult:
    run_id: str
    agent_id: str
    source: str
    requested_tick: int | None
    checkpoint_tick: int | None
    history_first_tick: int | None
    history_last_tick: int | None
    retained_only: bool
    prefix_complete: bool
    availability: str
    reason: str | None
    terms: tuple[SemanticHistoryTerm, ...]
    rows: tuple[SemanticHistoryRow, ...]
    next_cursor: str | None
    count: int


CheckpointLookup = Callable[[str, str], object | None]


class SemanticHistoryService:
    def __init__(
        self, *, checkpoint_lookup: CheckpointLookup, cursor_codec: CulturalCursorCodec
    ) -> None:
        self._lookup = checkpoint_lookup
        self._codec = cursor_codec

    def _projection(
        self, run_id: str, agent_id: str, source: str, tick: int | None
    ) -> tuple[ProjectedSemanticHistory | None, int | None, str | None]:
        checkpoint = self._lookup(run_id, agent_id)
        checkpoint_tick = _checkpoint_tick(checkpoint)
        if checkpoint is None:
            return None, None, "checkpoint_unavailable"
        if tick is not None and checkpoint_tick != tick:
            return None, checkpoint_tick, "checkpoint_tick_mismatch"
        ledger_name = "semantic_naming" if source == "label" else "symbolic_language"
        if getattr(checkpoint, ledger_name, None) is None:
            return None, checkpoint_tick, "semantic_ledger_disabled"
        try:
            projected = project_semantic_history(agent_id, checkpoint, source)
        except ValueError:
            return None, checkpoint_tick, "invalid_semantic_history"
        return projected, checkpoint_tick, None

    def read(
        self,
        *,
        run_id: str,
        agent_id: str,
        source: str,
        tick: int | None,
        from_tick: int | None,
        to_tick: int | None,
        after: str | None,
        limit: int,
    ) -> SemanticHistoryResult:
        if source not in SEMANTIC_HISTORY_SOURCES:
            raise bad_request(code="invalid_source")
        if from_tick is not None and to_tick is not None and from_tick > to_tick:
            raise bad_request(code="invalid_tick_window")
        if limit < 1:
            raise bad_request(code="invalid_limit")
        limit = min(limit, _MAX_LIMIT)
        projected, checkpoint_tick, reason = self._projection(
            run_id, agent_id, source, tick
        )
        if projected is None:
            return SemanticHistoryResult(
                run_id=run_id,
                agent_id=agent_id,
                source=source,
                requested_tick=tick,
                checkpoint_tick=checkpoint_tick,
                history_first_tick=None,
                history_last_tick=None,
                retained_only=True,
                prefix_complete=False,
                availability="unavailable",
                reason=reason,
                terms=(),
                rows=(),
                next_cursor=None,
                count=0,
            )

        filters = {
            "from_tick": from_tick,
            "to_tick": to_tick,
        }
        digest = _rows_digest(projected, checkpoint_tick)
        offset = 0
        if after is not None:
            try:
                payload = self._codec.decode(after, purpose=_PURPOSE, schema=_SCHEMA)
            except CulturalCursorError as exc:
                raise bad_request(code=exc.code) from None
            if (
                payload.get("run_id") != run_id
                or payload.get("agent_id") != agent_id
                or payload.get("source") != source
                or payload.get("filters") != filters
            ):
                raise bad_request(code="invalid_research_cursor")
            if payload.get("digest") != digest:
                raise conflict(code="semantic_checkpoint_changed")
            raw_offset = payload.get("offset")
            if not isinstance(raw_offset, int) or raw_offset < 0:
                raise bad_request(code="invalid_research_cursor")
            offset = raw_offset

        rows = [
            row
            for row in projected.rows
            if (from_tick is None or row.tick >= from_tick)
            and (to_tick is None or row.tick < to_tick)
        ]
        total = len(rows)
        page = tuple(rows[offset : offset + limit])
        truncated = offset + len(page) < total
        next_cursor = None
        if truncated:
            next_cursor = self._codec.encode(
                {
                    "run_id": run_id,
                    "agent_id": agent_id,
                    "source": source,
                    "filters": filters,
                    "digest": digest,
                    "offset": offset + len(page),
                },
                purpose=_PURPOSE,
                schema=_SCHEMA,
            )
        return SemanticHistoryResult(
            run_id=run_id,
            agent_id=agent_id,
            source=source,
            requested_tick=tick,
            checkpoint_tick=checkpoint_tick,
            history_first_tick=projected.history_first_tick,
            history_last_tick=projected.history_last_tick,
            retained_only=True,
            prefix_complete=False,
            availability="available",
            reason="retained_inventory_empty" if total == 0 else None,
            terms=projected.terms,
            rows=page,
            next_cursor=next_cursor,
            count=len(page),
        )


def _checkpoint_tick(checkpoint: object | None) -> int | None:
    if checkpoint is None:
        return None
    key = getattr(checkpoint, "last_observation_key", None)
    if not isinstance(key, tuple) or not key:
        return None
    value = key[0]
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _row_payload(row: SemanticHistoryRow) -> dict[str, object]:
    return {
        "ordinal": row.ordinal,
        "tick": row.tick,
        "trigger": row.trigger,
        "term_source": row.term_source,
        "term_digest": row.term_digest,
        "local_id": row.local_id,
        "referent_kind": row.referent_kind,
        "referent_digest": row.referent_digest,
        "associated_digests": list(row.associated_digests),
        "confidence": row.confidence,
    }


def _rows_digest(
    projected: ProjectedSemanticHistory, checkpoint_tick: int | None
) -> str:
    body = {
        "checkpoint_tick": checkpoint_tick,
        "rows": [_row_payload(row) for row in projected.rows],
    }
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["SemanticHistoryResult", "SemanticHistoryService"]
