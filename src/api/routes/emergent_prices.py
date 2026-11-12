"""Seven GET-only, dual-gated emergent-price read routes."""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any, Final

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.dependencies import get_settings
from api.emergent_prices_cursor import (
    EmergentPricesCursorCodec,
    EmergentPricesCursorError,
)
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.emergent_prices_paging import page_emergent_prices
from simulation.emergent_prices_ports import emergent_prices_query_fingerprint

router = APIRouter(prefix="/v1/simulations", tags=["emergent-prices"])
_LOGGER = get_logger("api.routes.emergent_prices")
EMERGENT_PRICES_ROUTE_COUNT: Final[int] = 7


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "emergent_prices_reader", None)
    if reader is None:
        _LOGGER.info("emergent_prices_route_disabled")
        raise service_unavailable(code="emergent_prices_disabled")
    return reader


def _codec(request: Request) -> EmergentPricesCursorCodec:
    codec = getattr(request.app.state, "emergent_prices_cursor_codec", None)
    if not isinstance(codec, EmergentPricesCursorCodec):
        _LOGGER.info("emergent_prices_route_disabled")
        raise service_unavailable(code="emergent_prices_disabled")
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
        if str(exc) == "emergent_prices_store_corrupt":
            _LOGGER.error("emergent_prices_store_corrupt")
            raise internal(code="emergent_prices_store_corrupt") from exc
        raise not_found(code="emergent_prices_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="emergent_prices_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="emergent_prices_run_not_found")
    return snapshot


def _filters(window_index: int | None) -> dict[str, object]:
    return {} if window_index is None else {"window_index": window_index}


def _fingerprint(
    snapshot: Any, purpose: str, window_index: int | None, limit: int
) -> str:
    return emergent_prices_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=_filters(window_index),
        limit=limit,
    )


def _after_key(
    codec: EmergentPricesCursorCodec,
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
    except EmergentPricesCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="emergent_prices_cursor_expired") from exc
        raise bad_request(code="emergent_prices_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, window_index, limit)
    ):
        raise bad_request(code="emergent_prices_cursor_invalid")
    raw = payload.get("after_key")
    if type(raw) is not str:
        return None
    try:
        decoded = json.loads(raw)
    except ValueError as exc:
        raise bad_request(code="emergent_prices_cursor_invalid") from exc
    if type(decoded) is not list:
        raise bad_request(code="emergent_prices_cursor_invalid")
    return tuple(decoded)


_ROW_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "units": ("unit_token", "unit_source"),
    "expectations": ("window_index", "expectation_id"),
    "quotes": ("window_index", "venue_id", "quote_id"),
    "distributions": ("window_index", "distribution_id"),
    "markets": ("window_index", "market_token"),
    "relations": ("window_index", "relation_id"),
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
    page = page_emergent_prices(
        getattr(snapshot, purpose),
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
    _LOGGER.info("emergent_prices_route_served purpose=%s", purpose)
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


@router.get("/{run_id}/emergent-prices")
def get_emergent_prices_summary(run_id: str, request: Request) -> JSONResponse:
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
            "unit_count": summary.unit_count,
            "expectation_count": summary.expectation_count,
            "quote_count": summary.quote_count,
            "distribution_count": summary.distribution_count,
            "market_count": summary.market_count,
            "relation_count": summary.relation_count,
            "exchange_count": summary.exchange_count,
            "quote_event_count": summary.quote_event_count,
            "evidence_coverage": summary.evidence_coverage,
            "expectation_coverage": summary.expectation_coverage,
            "quote_coverage": summary.quote_coverage,
            "distribution_coverage": summary.distribution_coverage,
            "market_coverage": summary.market_coverage,
            "relation_coverage": summary.relation_coverage,
            "coverage": summary.coverage,
            "truncated": summary.truncated,
        }
    )


@router.get("/{run_id}/emergent-prices/units")
def get_emergent_prices_units(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="units",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/emergent-prices/expectations")
def get_emergent_prices_expectations(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="expectations",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/emergent-prices/quotes")
def get_emergent_prices_quotes(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="quotes",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/emergent-prices/distributions")
def get_emergent_prices_distributions(
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


@router.get("/{run_id}/emergent-prices/markets")
def get_emergent_prices_markets(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="markets",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/emergent-prices/relations")
def get_emergent_prices_relations(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose="relations",
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))
