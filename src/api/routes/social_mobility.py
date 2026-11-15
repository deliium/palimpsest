"""Seven GET-only, dual-gated social-mobility read routes."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Final

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from api.social_mobility_cursor import (
    SocialMobilityCursorCodec,
    SocialMobilityCursorError,
)
from infrastructure.logging import get_logger
from simulation.social_mobility_paging import page_social_mobility
from simulation.social_mobility_ports import social_mobility_query_fingerprint

router = APIRouter(prefix="/v1/simulations", tags=["social-mobility"])
_LOGGER = get_logger("api.routes.social_mobility")
SOCIAL_MOBILITY_ROUTE_COUNT: Final[int] = 7


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "social_mobility_reader", None)
    if reader is None:
        _LOGGER.info("social_mobility_reader_disabled")
        raise service_unavailable(code="social_mobility_disabled")
    return reader


def _codec(request: Request) -> SocialMobilityCursorCodec:
    codec = getattr(request.app.state, "social_mobility_cursor_codec", None)
    if not isinstance(codec, SocialMobilityCursorCodec):
        _LOGGER.info("social_mobility_reader_disabled")
        raise service_unavailable(code="social_mobility_disabled")
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
        if code == "social_mobility_store_corrupt" or code.startswith(
            "social_mobility_snapshot_"
        ):
            _LOGGER.error("social_mobility_store_corrupt")
            raise internal(code="social_mobility_store_corrupt") from exc
        raise not_found(code="social_mobility_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="social_mobility_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="social_mobility_run_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any, purpose: str, window_index: int | None, limit: int
) -> str:
    return social_mobility_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        limit=limit,
        window_index=window_index,
    )


def _after_key(
    codec: SocialMobilityCursorCodec,
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
    except SocialMobilityCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="social_mobility_cursor_expired") from exc
        raise bad_request(code="social_mobility_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, window_index, limit)
    ):
        _LOGGER.warning("social_mobility_cursor_mismatch")
        raise bad_request(code="social_mobility_cursor_invalid")
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
        page, next_key = page_social_mobility(
            domains=snapshot.domains,
            generations=snapshot.generations,
            lags=snapshot.lags,
            coverage=snapshot.coverage,
            purpose=purpose,
            limit=limit,
            after_key=after,
            window_index=window_index,
        )
    except ValueError as exc:
        raise bad_request(code="social_mobility_cursor_invalid") from exc
    next_cursor = None
    if next_key:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.digest,
            query_fingerprint=_fingerprint(snapshot, purpose, window_index, limit),
            after_key=next_key,
        )
    _LOGGER.info("social_mobility_route_served purpose=%s", purpose)
    return snapshot, page, next_cursor


def _page_body(
    snapshot: Any,
    page: tuple[object, ...],
    next_cursor: str | None,
    window_index: int | None,
    purpose: str,
) -> dict[str, object]:
    coverage = {
        "generations": snapshot.summary.generation_coverage,
        "coverage": snapshot.summary.coverage,
    }.get(purpose, snapshot.summary.domain_coverage)
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "window_index": window_index,
        "rows": [_dict(row) for row in page],
        "next_cursor": next_cursor,
        "coverage": coverage,
    }


@router.get("/{run_id}/social-mobility")
def get_social_mobility_summary(run_id: str, request: Request) -> JSONResponse:
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
            "domain_row_count": summary.domain_row_count,
            "generation_row_count": summary.generation_row_count,
            "lag_row_count": summary.lag_row_count,
            "window_count": summary.window_count,
            "owner_count": summary.owner_count,
            "generation_count": summary.generation_count,
            "genealogy_edge_count": summary.genealogy_edge_count,
            "pair_count": summary.pair_count,
            "resolved_pair_count": summary.resolved_pair_count,
            "unresolved_pair_count": summary.unresolved_pair_count,
            "domain_available_count": summary.domain_available_count,
            "coverage": summary.coverage,
            "evidence_coverage": summary.evidence_coverage,
            "domain_coverage": summary.domain_coverage,
            "generation_coverage": summary.generation_coverage,
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
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index, purpose))


@router.get("/{run_id}/social-mobility/domains")
def get_social_mobility_domains(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("domains", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/social-mobility/economy")
def get_social_mobility_economy(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("economy", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/social-mobility/human-capital")
def get_social_mobility_human_capital(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("human_capital", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/social-mobility/standing")
def get_social_mobility_standing(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("standing", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/social-mobility/generations")
def get_social_mobility_generations(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("generations", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/social-mobility/coverage")
def get_social_mobility_coverage(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("coverage", run_id, request, limit, cursor, window_index)
