"""Seven GET-only, dual-gated credit relationship read routes."""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any, Final

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.credit_relationships_cursor import (
    CreditRelationshipsCursorCodec,
    CreditRelationshipsCursorError,
)
from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.credit_relationships_paging import page_credit_relationships
from simulation.credit_relationships_ports import (
    credit_relationships_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["credit-relationships"])
_LOGGER = get_logger("api.routes.credit_relationships")
CREDIT_RELATIONSHIPS_ROUTE_COUNT: Final[int] = 7


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "credit_relationships_reader", None)
    if reader is None:
        _LOGGER.info("credit_relationships_route_disabled")
        raise service_unavailable(code="credit_relationships_disabled")
    return reader


def _codec(request: Request) -> CreditRelationshipsCursorCodec:
    codec = getattr(request.app.state, "credit_relationships_cursor_codec", None)
    if not isinstance(codec, CreditRelationshipsCursorCodec):
        _LOGGER.info("credit_relationships_route_disabled")
        raise service_unavailable(code="credit_relationships_disabled")
    return codec


def _authorize(request: Request) -> None:
    require_http_capability(
        request,
        get_settings(request),
        capability=ApiCapability.SUBJECTIVE_DEBUG,
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.read_snapshot(run_id)
    except ValueError as exc:
        if str(exc) == "credit_relationships_store_corrupt":
            _LOGGER.error("credit_relationships_store_corrupt")
            raise internal(code="credit_relationships_store_corrupt") from exc
        raise not_found(code="credit_relationships_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="credit_relationships_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="credit_relationships_run_not_found")
    return snapshot


def _filters(window_index: int | None) -> dict[str, object]:
    return {} if window_index is None else {"window_index": window_index}


def _fingerprint(
    snapshot: Any, purpose: str, window_index: int | None, limit: int
) -> str:
    return credit_relationships_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=_filters(window_index),
        limit=limit,
    )


def _after_key(
    codec: CreditRelationshipsCursorCodec,
    token: str | None,
    *,
    snapshot: Any,
    purpose: str,
    window_index: int | None,
    limit: int,
) -> tuple[object, ...] | None:
    if token is None:
        return None
    try:
        payload = codec.decode(token, purpose=purpose)
    except CreditRelationshipsCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="credit_relationships_cursor_expired") from exc
        raise bad_request(code="credit_relationships_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, window_index, limit)
    ):
        raise bad_request(code="credit_relationships_cursor_invalid")
    raw = payload.get("after_key")
    if type(raw) is not str:
        return None
    try:
        decoded = json.loads(raw)
    except ValueError as exc:
        raise bad_request(code="credit_relationships_cursor_invalid") from exc
    if type(decoded) is not list:
        raise bad_request(code="credit_relationships_cursor_invalid")
    return tuple(decoded)


_ROW_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "relationships": ("window_index", "relationship_id"),
    "claims": ("window_index", "claim_id"),
    "performances": ("window_index", "performance_id"),
    "distributions": ("window_index", "distribution_id"),
    "counterparties": ("window_index", "counterparty_token"),
    "alignment": ("window_index", "alignment_id"),
}


def _row_key(row: object, purpose: str) -> str:
    return json.dumps([getattr(row, name) for name in _ROW_KEYS[purpose]])


def _dict(row: Any) -> dict[str, object]:
    values: dict[str, object] = {}
    for item in fields(row):
        value = getattr(row, item.name)
        if hasattr(value, "value"):
            value = value.value
        values[item.name] = value
    return values


def _page(
    request: Request,
    run_id: str,
    *,
    purpose: str,
    limit: int,
    cursor: str | None,
    window_index: int | None,
) -> tuple[Any, tuple[object, ...], str | None]:
    reader = _reader(request)
    _authorize(request)
    snapshot = _snapshot(reader, run_id)
    codec = _codec(request)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose=purpose,
        window_index=window_index,
        limit=limit,
    )
    page = page_credit_relationships(
        getattr(
            snapshot,
            "alignments" if purpose == "alignment" else purpose,
        ),
        purpose=purpose,
        after_key=after,
        limit=limit,
        window_index=window_index,
    )
    next_cursor = None
    if len(page) >= limit:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.digest,
            query_fingerprint=_fingerprint(snapshot, purpose, window_index, limit),
            after_key=_row_key(page[-1], purpose),
        )
    _LOGGER.info("credit_relationships_route_served purpose=%s", purpose)
    return snapshot, page, next_cursor


def _page_body(
    snapshot: Any,
    page: tuple[object, ...],
    next_cursor: str | None,
    window_index: int | None,
) -> dict[str, object]:
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "window_index": window_index,
        "rows": [_dict(row) for row in page],
        "next_cursor": next_cursor,
        "coverage": snapshot.summary.coverage,
    }


@router.get("/{run_id}/credit-relationships")
def get_credit_relationships_summary(
    run_id: str, request: Request
) -> JSONResponse:
    reader = _reader(request)
    _authorize(request)
    snapshot = _snapshot(reader, run_id)
    summary = snapshot.summary
    return JSONResponse(
        {
            "run_id": snapshot.run_id,
            "publication_id": snapshot.publication_id,
            "digest": snapshot.digest,
            "schema_version": snapshot.schema_version,
            "window_tick": summary.window_tick,
            "window_count": summary.window_count,
            "relationship_count": summary.relationship_count,
            "claim_count": summary.claim_count,
            "performance_count": summary.performance_count,
            "distribution_count": summary.distribution_count,
            "counterparty_count": summary.counterparty_count,
            "alignment_count": summary.alignment_count,
            "claim_event_count": summary.claim_event_count,
            "transfer_event_count": summary.transfer_event_count,
            "evidence_coverage": summary.evidence_coverage,
            "owner_coverage": summary.owner_coverage,
            "relationship_coverage": summary.relationship_coverage,
            "performance_coverage": summary.performance_coverage,
            "distribution_coverage": summary.distribution_coverage,
            "counterparty_coverage": summary.counterparty_coverage,
            "alignment_coverage": summary.alignment_coverage,
            "coverage": summary.coverage,
            "truncated": summary.truncated,
        }
    )


@router.get("/{run_id}/credit-relationships/relationships")
def get_credit_relationships_relationships(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="relationships",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/credit-relationships/claims")
def get_credit_relationships_claims(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="claims",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/credit-relationships/performances")
def get_credit_relationships_performances(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="performances",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/credit-relationships/distributions")
def get_credit_relationships_distributions(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="distributions",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/credit-relationships/counterparties")
def get_credit_relationships_counterparties(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="counterparties",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/credit-relationships/alignment")
def get_credit_relationships_alignment(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="alignment",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))
