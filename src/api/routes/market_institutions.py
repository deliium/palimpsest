"""Seven GET-only, dual-gated market-institution read routes."""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any, Final

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.market_institutions_cursor import (
    MarketInstitutionsCursorCodec,
    MarketInstitutionsCursorError,
)
from api.market_institutions_schemas import (
    MarketExpectationsPageOut,
    MarketGatheringsPageOut,
    MarketMarketsPageOut,
    MarketRecordsPageOut,
    MarketRolesPageOut,
    MarketVenuesPageOut,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.market_institutions_paging import page_market_institutions

router = APIRouter(prefix="/v1/simulations", tags=["market-institutions"])
_LOGGER = get_logger("api.routes.market_institutions")
MARKET_INSTITUTIONS_ROUTE_COUNT: Final[int] = 7


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "market_institutions_reader", None)
    if reader is None:
        _LOGGER.info("market_institutions_route_disabled")
        raise service_unavailable(code="market_institutions_disabled")
    return reader


def _codec(request: Request) -> MarketInstitutionsCursorCodec:
    codec = getattr(request.app.state, "market_institutions_cursor_codec", None)
    if not isinstance(codec, MarketInstitutionsCursorCodec):
        _LOGGER.info("market_institutions_route_disabled")
        raise service_unavailable(code="market_institutions_disabled")
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
        if str(exc) == "market_institutions_store_corrupt":
            _LOGGER.error("market_institutions_store_corrupt")
            raise internal(code="market_institutions_store_corrupt") from exc
        raise not_found(code="market_institutions_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="market_institutions_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="market_institutions_run_not_found")
    return snapshot


def _filters(window_index: int | None) -> dict[str, object]:
    return {} if window_index is None else {"window_index": window_index}


def _fingerprint(
    snapshot: Any,
    purpose: str,
    window_index: int | None,
    limit: int,
) -> str:
    from simulation.market_institutions_ports import (
        market_institutions_query_fingerprint,
    )

    return market_institutions_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=_filters(window_index),
        limit=limit,
    )


def _after_key(
    codec: MarketInstitutionsCursorCodec,
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
    except MarketInstitutionsCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            _LOGGER.warning("market_institutions_cursor_invalid reason=expired")
            raise gone(code="market_institutions_cursor_expired") from exc
        _LOGGER.warning("market_institutions_cursor_invalid")
        raise bad_request(code="market_institutions_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, window_index, limit)
    ):
        raise bad_request(code="market_institutions_cursor_invalid")
    raw = payload.get("after_key")
    if type(raw) is not str:
        return None
    try:
        decoded = json.loads(raw)
    except ValueError as exc:
        raise bad_request(code="market_institutions_cursor_invalid") from exc
    if type(decoded) is not list:
        raise bad_request(code="market_institutions_cursor_invalid")
    return tuple(decoded)


def _row_key(row: object, purpose: str) -> str:
    names = {
        "venues": ("window_index", "venue_id"),
        "gatherings": ("window_index", "venue_id"),
        "expectations": ("window_index", "venue_id", "owner_token"),
        "roles": ("window_index", "venue_id", "actor_token"),
        "records": ("window_index", "venue_id", "anchor_token"),
        "markets": ("window_index", "market_id"),
    }[purpose]
    return json.dumps([getattr(row, name) for name in names])


def _next_cursor(
    codec: MarketInstitutionsCursorCodec,
    *,
    snapshot: Any,
    purpose: str,
    window_index: int | None,
    limit: int,
    page: tuple[object, ...],
) -> str | None:
    if len(page) < limit:
        return None
    return codec.encode(
        purpose=purpose,
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=_fingerprint(snapshot, purpose, window_index, limit),
        after_key=_row_key(page[-1], purpose),
    )


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
    rows = getattr(snapshot, purpose)
    page = page_market_institutions(
        rows,
        purpose=purpose,
        after_key=after,
        limit=limit,
        window_index=window_index,
    )
    return (
        snapshot,
        page,
        _next_cursor(
            codec,
            snapshot=snapshot,
            purpose=purpose,
            window_index=window_index,
            limit=limit,
            page=page,
        ),
    )


@router.get("/{run_id}/market-institutions")
def get_market_institutions_summary(
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
            "venue_count": summary.venue_count,
            "gathering_count": summary.gathering_count,
            "market_like_venue_count": summary.market_like_venue_count,
            "recurring_venue_count": summary.recurring_venue_count,
            "expected_venue_count": summary.expected_venue_count,
            "market_count": summary.market_count,
            "expectation_row_count": summary.expectation_row_count,
            "role_row_count": summary.role_row_count,
            "record_anchor_count": summary.record_anchor_count,
            "emerged_count": summary.emerged_count,
            "continued_count": summary.continued_count,
            "transformed_count": summary.transformed_count,
            "split_count": summary.split_count,
            "merge_count": summary.merge_count,
            "dissolved_count": summary.dissolved_count,
            "sustained_market_count": summary.sustained_market_count,
            "lineage_edge_count": summary.lineage_edge_count,
            "coverage": summary.coverage,
            "truncated": summary.truncated,
        }
    )


def _page_response(
    request: Request,
    run_id: str,
    *,
    purpose: str,
    limit: int,
    cursor: str | None,
    window_index: int | None,
) -> tuple[Any, list[Any], str | None]:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose=purpose,
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return snapshot, [_dict(row) for row in page], next_cursor


@router.get(
    "/{run_id}/market-institutions/venues",
    response_model=MarketVenuesPageOut,
)
def get_market_institutions_venues(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> MarketVenuesPageOut:
    snapshot, rows, next_cursor = _page_response(
        request,
        run_id,
        purpose="venues",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return MarketVenuesPageOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        window_index=window_index,
        rows=rows,
        next_cursor=next_cursor,
        coverage=snapshot.summary.coverage,
    )


@router.get(
    "/{run_id}/market-institutions/gatherings",
    response_model=MarketGatheringsPageOut,
)
def get_market_institutions_gatherings(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> MarketGatheringsPageOut:
    snapshot, rows, next_cursor = _page_response(
        request,
        run_id,
        purpose="gatherings",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return MarketGatheringsPageOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        window_index=window_index,
        rows=rows,
        next_cursor=next_cursor,
        coverage=snapshot.summary.coverage,
    )


@router.get(
    "/{run_id}/market-institutions/expectations",
    response_model=MarketExpectationsPageOut,
)
def get_market_institutions_expectations(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> MarketExpectationsPageOut:
    snapshot, rows, next_cursor = _page_response(
        request,
        run_id,
        purpose="expectations",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return MarketExpectationsPageOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        window_index=window_index,
        rows=rows,
        next_cursor=next_cursor,
        coverage=snapshot.summary.coverage,
    )


@router.get(
    "/{run_id}/market-institutions/roles",
    response_model=MarketRolesPageOut,
)
def get_market_institutions_roles(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> MarketRolesPageOut:
    snapshot, rows, next_cursor = _page_response(
        request,
        run_id,
        purpose="roles",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return MarketRolesPageOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        window_index=window_index,
        rows=rows,
        next_cursor=next_cursor,
        coverage=snapshot.summary.coverage,
    )


@router.get(
    "/{run_id}/market-institutions/records",
    response_model=MarketRecordsPageOut,
)
def get_market_institutions_records(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> MarketRecordsPageOut:
    snapshot, rows, next_cursor = _page_response(
        request,
        run_id,
        purpose="records",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return MarketRecordsPageOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        window_index=window_index,
        rows=rows,
        next_cursor=next_cursor,
        coverage=snapshot.summary.coverage,
    )


@router.get(
    "/{run_id}/market-institutions/markets",
    response_model=MarketMarketsPageOut,
)
def get_market_institutions_markets(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> MarketMarketsPageOut:
    snapshot, rows, next_cursor = _page_response(
        request,
        run_id,
        purpose="markets",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    lineage_rows: list[Any] = [
        _dict(row)
        for row in snapshot.lineage
        if window_index is None or row.window_index == window_index
    ]
    return MarketMarketsPageOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        window_index=window_index,
        rows=rows,
        lineage=lineage_rows,
        next_cursor=next_cursor,
        coverage=snapshot.summary.coverage,
    )
