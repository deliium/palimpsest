"""Seven GET-only, dual-gated economic-inequality read routes."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Final

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.dependencies import get_settings
from api.economic_inequality_cursor import (
    EconomicInequalityCursorCodec,
    EconomicInequalityCursorError,
)
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.economic_inequality_paging import page_economic_inequality
from simulation.economic_inequality_ports import (
    economic_inequality_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["economic-inequality"])
_LOGGER = get_logger("api.routes.economic_inequality")
ECONOMIC_INEQUALITY_ROUTE_COUNT: Final[int] = 7


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "economic_inequality_reader", None)
    if reader is None:
        _LOGGER.info("economic_inequality_reader_disabled")
        raise service_unavailable(code="economic_inequality_disabled")
    return reader


def _codec(request: Request) -> EconomicInequalityCursorCodec:
    codec = getattr(
        request.app.state, "economic_inequality_cursor_codec", None
    )
    if not isinstance(codec, EconomicInequalityCursorCodec):
        _LOGGER.info("economic_inequality_reader_disabled")
        raise service_unavailable(code="economic_inequality_disabled")
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
        if "corrupt" in str(exc):
            _LOGGER.error("economic_inequality_store_corrupt")
            raise internal(code="economic_inequality_store_corrupt") from exc
        raise not_found(code="economic_inequality_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="economic_inequality_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="economic_inequality_run_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any, purpose: str, window_index: int | None, limit: int
) -> str:
    return economic_inequality_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        limit=limit,
        window_index=window_index,
    )


def _after_key(
    codec: EconomicInequalityCursorCodec,
    token: str | None,
    *,
    snapshot: Any,
    purpose: str,
    window_index: int | None,
    limit: int,
) -> str:
    if token is None:
        return ""
    try:
        payload = codec.decode(token, purpose=purpose)
    except EconomicInequalityCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="economic_inequality_cursor_expired") from exc
        raise bad_request(code="economic_inequality_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, window_index, limit)
    ):
        raise bad_request(code="economic_inequality_cursor_invalid")
    raw = payload.get("after_key")
    return "" if type(raw) is not str else raw


def _dict(row: Any) -> dict[str, object]:
    values: dict[str, object] = {}
    for item in fields(row):
        value = getattr(row, item.name)
        if hasattr(value, "value"):
            value = value.value
        values[item.name] = value
    return values


def _rows(snapshot: Any, purpose: str) -> tuple[object, ...]:
    if purpose == "cohorts":
        return tuple(snapshot.cohorts)
    if purpose == "societies":
        return tuple(snapshot.societies)
    return tuple(snapshot.dimensions)


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
    page, next_key = page_economic_inequality(
        _rows(snapshot, purpose),
        purpose=purpose,
        limit=limit,
        after_key=after,
        window_index=window_index,
    )
    next_cursor = None
    if next_key:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.digest,
            query_fingerprint=_fingerprint(
                snapshot, purpose, window_index, limit
            ),
            after_key=next_key,
        )
    _LOGGER.info("economic_inequality_route_served purpose=%s", purpose)
    return snapshot, page, next_cursor


def _page_body(
    snapshot: Any,
    page: tuple[object, ...],
    next_cursor: str | None,
    window_index: int | None,
    purpose: str,
) -> dict[str, object]:
    coverage = {
        "cohorts": snapshot.summary.comparison_coverage,
        "societies": snapshot.summary.comparison_coverage,
    }.get(purpose, snapshot.summary.dimension_coverage)
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "window_index": window_index,
        "rows": [_dict(row) for row in page],
        "next_cursor": next_cursor,
        "coverage": coverage,
    }


@router.get("/{run_id}/economic-inequality")
def get_economic_inequality_summary(
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
            "dimension_row_count": summary.dimension_row_count,
            "cohort_row_count": summary.cohort_row_count,
            "society_row_count": summary.society_row_count,
            "window_count": summary.window_count,
            "owner_count": summary.owner_count,
            "observed_owner_count": summary.observed_owner_count,
            "overlap_member_count": summary.overlap_member_count,
            "coverage": summary.coverage,
            "evidence_coverage": summary.evidence_coverage,
            "dimension_coverage": summary.dimension_coverage,
            "comparison_coverage": summary.comparison_coverage,
            "truncated": summary.truncated,
        }
    )


def _page_handler(
    purpose: str,
    run_id: str,
    request: Request,
    limit: int,
    cursor: str | None,
    window_index: int | None,
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose=purpose,
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(
        _page_body(snapshot, page, next_cursor, window_index, purpose)
    )


@router.get("/{run_id}/economic-inequality/dimensions")
def get_economic_inequality_dimensions(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "dimensions", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/economic-inequality/possession")
def get_economic_inequality_possession(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "possession", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/economic-inequality/access")
def get_economic_inequality_access(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("access", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/economic-inequality/claims")
def get_economic_inequality_claims(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "claims", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/economic-inequality/cohorts")
def get_economic_inequality_cohorts(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "cohorts", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/economic-inequality/societies")
def get_economic_inequality_societies(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "societies", run_id, request, limit, cursor, window_index
    )
