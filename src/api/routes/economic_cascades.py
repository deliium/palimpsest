"""Seven GET-only, dual-gated economic-cascade read routes."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Final

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.dependencies import get_settings
from api.economic_cascades_cursor import (
    EconomicCascadesCursorCodec,
    EconomicCascadesCursorError,
)
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.economic_cascades_paging import page_economic_cascades_rows
from simulation.economic_cascades_ports import (
    economic_cascades_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["economic-cascades"])
_LOGGER = get_logger("api.routes.economic_cascades")
ECONOMIC_CASCADES_ROUTE_COUNT: Final[int] = 7


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "economic_cascades_reader", None)
    if reader is None:
        _LOGGER.info("economic_cascades_reader_disabled")
        raise service_unavailable(code="economic_cascades_disabled")
    return reader


def _codec(request: Request) -> EconomicCascadesCursorCodec:
    codec = getattr(request.app.state, "economic_cascades_cursor_codec", None)
    if not isinstance(codec, EconomicCascadesCursorCodec):
        _LOGGER.info("economic_cascades_reader_disabled")
        raise service_unavailable(code="economic_cascades_disabled")
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
        code = str(exc)
        if code == "economic_cascades_store_corrupt" or code.startswith(
            "economic_cascades_snapshot_"
        ):
            _LOGGER.error("economic_cascades_store_corrupt")
            raise internal(code="economic_cascades_store_corrupt") from exc
        raise not_found(code="economic_cascades_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="economic_cascades_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="economic_cascades_run_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any, purpose: str, window_index: int | None, limit: int
) -> str:
    return economic_cascades_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.internal_digest,
        purpose=purpose,
        window_index=window_index,
        limit=limit,
    )


def _after_key(
    codec: EconomicCascadesCursorCodec,
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
    except EconomicCascadesCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="economic_cascades_cursor_expired") from exc
        raise bad_request(code="economic_cascades_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.internal_digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, window_index, limit)
    ):
        _LOGGER.warning("economic_cascades_cursor_mismatch")
        raise bad_request(code="economic_cascades_cursor_invalid")
    raw = payload.get("after_key")
    return "" if type(raw) is not str else raw


def _dict(row: Any) -> dict[str, object]:
    if isinstance(row, tuple):
        return {"window_index": row[0], "window_tick": row[1]}
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
    try:
        page, next_key = page_economic_cascades_rows(
            snapshot,
            purpose=purpose,
            limit=limit,
            after=after or None,
            window_index=window_index,
        )
    except ValueError as exc:
        raise bad_request(code="economic_cascades_cursor_invalid") from exc
    next_cursor = None
    if next_key:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.internal_digest,
            query_fingerprint=_fingerprint(
                snapshot, purpose, window_index, limit
            ),
            after_key=next_key,
        )
    _LOGGER.info("economic_cascades_route_served purpose=%s", purpose)
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


@router.get("/{run_id}/economic-cascades")
def get_economic_cascades_summary(
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
            "digest": snapshot.internal_digest,
            "snapshot_version": snapshot.snapshot_version,
            "policy_version": snapshot.policy_version,
            "generated_from_tick": snapshot.generated_from_tick,
            "window_tick": summary.window_tick,
            "window_count": summary.window_count,
            "coverage": summary.coverage,
            "availability": summary.availability,
            "event_count": summary.event_count,
            "disruption_count": summary.disruption_count,
            "stage_count": summary.stage_count,
            "dependency_edge_count": summary.dependency_edge_count,
            "chain_count": summary.chain_count,
            "linked_chain_count": summary.linked_chain_count,
            "disruption_kind_count": summary.disruption_kind_count,
            "max_depth": summary.max_depth,
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
        _page_body(snapshot, page, next_cursor, window_index)
    )


@router.get("/{run_id}/economic-cascades/disruptions")
def get_economic_cascades_disruptions(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "disruptions", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/economic-cascades/dependencies")
def get_economic_cascades_dependencies(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "dependencies", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/economic-cascades/chains")
def get_economic_cascades_chains(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("chains", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/economic-cascades/propagation")
def get_economic_cascades_propagation(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "propagation", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/economic-cascades/windows")
def get_economic_cascades_windows(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("windows", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/economic-cascades/coverage")
def get_economic_cascades_coverage(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("coverage", run_id, request, limit, cursor, window_index)
