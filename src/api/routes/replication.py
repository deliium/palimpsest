"""Eight GET-only, dual-gated scientific-replication read routes."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping as _Mapping
from typing import Any, Final

from fastapi import APIRouter, Query, Request

from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.replication_cursor import ReplicationCursorCodec, ReplicationCursorError
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.replication_ports import replication_query_fingerprint

router = APIRouter(prefix="/v1/simulations", tags=["scientific-replication"])
_LOGGER = get_logger("api.routes.replication")
SCIENTIFIC_REPLICATION_ROUTE_COUNT: Final[int] = 8

_SECTIONS: Final[dict[str, str]] = {
    "summary": "summary",
    "designs": "designs",
    "attempts": "attempts",
    "results": "results",
    "comparisons": "comparisons",
    "interpretations": "interpretations",
    "collaborations": "collaborations",
    "coverage": "coverage",
}


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "scientific_replication_reader", None)
    if reader is None:
        raise service_unavailable(code="scientific_replication_disabled")
    return reader


def _codec(request: Request) -> ReplicationCursorCodec:
    codec = getattr(request.app.state, "scientific_replication_cursor_codec", None)
    if not isinstance(codec, ReplicationCursorCodec):
        raise service_unavailable(code="scientific_replication_disabled")
    return codec


def _authorize(request: Request) -> None:
    require_http_capability(
        request,
        get_settings(request),
        capability=ApiCapability.SUBJECTIVE_DEBUG,
    )


def _snapshot(reader: Any, run_id: str, publication_id: str | None) -> Any:
    try:
        return reader.read_snapshot(run_id, publication_id)
    except ValueError as exc:
        code = str(exc)
        if "corrupt" in code:
            _LOGGER.error("scientific_replication_store_corrupt")
            raise internal(code="scientific_replication_store_corrupt") from exc
        if code == "replication_store_missing":
            raise not_found(
                code=(
                    "scientific_replication_run_not_found"
                    if publication_id is None
                    else "scientific_replication_publication_not_found"
                )
            ) from exc
        raise not_found(code="scientific_replication_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="scientific_replication_run_not_found") from exc


def _plain(value: object) -> object:
    if isinstance(value, _Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _rows(snapshot: Any, section: str) -> list[dict[str, object]]:
    return [
        _plain(dict(row))  # type: ignore[misc]
        for row in getattr(snapshot, section)
    ]


def _filter(
    rows: list[dict[str, object]],
    *,
    section: str,
    window_index: int | None,
    design_token: str | None,
    collaboration_token: str | None,
) -> list[dict[str, object]]:
    if (
        (section in {"results", "coverage"})
        and (design_token is not None or collaboration_token is not None)
    ):
        raise bad_request(code="scientific_replication_filter_invalid")
    if section == "designs" and collaboration_token is not None:
        raise bad_request(code="scientific_replication_filter_invalid")
    filtered = rows
    if window_index is not None:
        filtered = [
            row for row in filtered if row.get("window_index") == window_index
        ]
    if design_token is not None:
        kept = []
        for row in filtered:
            fact = row.get("fact")
            nested = fact if isinstance(fact, dict) else {}
            if row.get("design_token") == design_token or nested.get(
                "design_token"
            ) == design_token:
                kept.append(row)
        filtered = kept
    if collaboration_token is not None:
        kept = []
        for row in filtered:
            fact = row.get("fact")
            nested = fact if isinstance(fact, dict) else {}
            if row.get(
                "collaboration_token"
            ) == collaboration_token or nested.get(
                "collaboration_token"
            ) == collaboration_token:
                kept.append(row)
        filtered = kept
    return sorted(filtered, key=lambda row: str(row.get("row_token", "")))


def _fingerprint(
    snapshot: Any,
    section: str,
    window_index: int | None,
    design_token: str | None,
    collaboration_token: str | None,
    limit: int,
) -> str:
    return replication_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        record_kinds=(section,),
    ) + ":" + hashlib.sha256(
        repr((window_index, design_token, collaboration_token, limit)).encode()
    ).hexdigest()[:16]


def _page(
    request: Request,
    run_id: str,
    *,
    section: str,
    publication_id: str | None,
    cursor: str | None,
    limit: int,
    window_index: int | None,
    design_token: str | None,
    collaboration_token: str | None,
) -> dict[str, object]:
    reader = _reader(request)
    _authorize(request)
    codec = _codec(request)
    purpose = f"scientific-replication:{section}"
    payload: dict[str, object] | None = None
    if cursor is not None:
        try:
            payload = codec.decode(cursor, purpose=purpose)
        except ReplicationCursorError as exc:
            if exc.reason_code == "diplomacy_cursor_expired":
                raise gone(code="scientific_replication_cursor_expired") from exc
            raise bad_request(code="scientific_replication_cursor_invalid") from exc
        bound_publication = payload.get("publication_id")
        if type(bound_publication) is not str or not bound_publication:
            raise bad_request(code="scientific_replication_cursor_invalid")
        if publication_id is not None and publication_id != bound_publication:
            raise bad_request(code="scientific_replication_cursor_invalid")
        publication_id = bound_publication
    snapshot = _snapshot(reader, run_id, publication_id)
    fingerprint = _fingerprint(
        snapshot,
        section,
        window_index,
        design_token,
        collaboration_token,
        limit,
    )
    after = ""
    if payload is not None:
        if (
            payload.get("run_id") != snapshot.run_id
            or payload.get("publication_id") != snapshot.publication_id
            or payload.get("snapshot_digest") != snapshot.internal_digest
            or payload.get("query_fingerprint") != fingerprint
        ):
            raise bad_request(code="scientific_replication_cursor_invalid")
        raw = payload.get("after_key")
        after = "" if type(raw) is not str else raw
    rows = _filter(
        _rows(snapshot, section),
        section=section,
        window_index=window_index,
        design_token=design_token,
        collaboration_token=collaboration_token,
    )
    if after:
        rows = [row for row in rows if str(row.get("row_token", "")) > after]
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.internal_digest,
            query_fingerprint=fingerprint,
            after_key=str(page[-1].get("row_token", "")),
        )
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "internal_digest": snapshot.internal_digest,
        "policy_version": snapshot.policy_version,
        "coverage": snapshot.summary.get("coverage"),
        "availability": snapshot.summary.get("availability"),
        "rows": page,
        "next_cursor": next_cursor,
        "truncated": next_cursor is not None,
    }


def _section_route(section: str) -> Any:
    async def handler(
        request: Request,
        run_id: str,
        publication_id: str | None = Query(default=None),
        cursor: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        window_index: int | None = Query(default=None, ge=0, le=511),
        design_token: str | None = Query(default=None),
        collaboration_token: str | None = Query(default=None),
    ) -> dict[str, object]:
        return _page(
            request,
            run_id,
            section=section,
            publication_id=publication_id,
            cursor=cursor,
            limit=limit,
            window_index=window_index,
            design_token=design_token,
            collaboration_token=collaboration_token,
        )

    handler.__name__ = f"replication_{section}"
    return handler


@router.get("/{run_id}/scientific-replication")
async def replication_summary(
    request: Request,
    run_id: str,
    publication_id: str | None = Query(default=None),
) -> dict[str, object]:
    reader = _reader(request)
    _authorize(request)
    snapshot = _snapshot(reader, run_id, publication_id)
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "internal_digest": snapshot.internal_digest,
        "policy_version": snapshot.policy_version,
        "summary": _plain(dict(snapshot.summary)),
    }


for _section in (
    "designs",
    "attempts",
    "results",
    "comparisons",
    "interpretations",
    "collaborations",
    "coverage",
):
    router.add_api_route(
        f"/{{run_id}}/scientific-replication/{_section}",
        _section_route(_section),
        methods=["GET"],
        name=f"replication_{_section}",
    )

__all__ = ["SCIENTIFIC_REPLICATION_ROUTE_COUNT", "router"]
