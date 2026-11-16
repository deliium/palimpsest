"""Seven GET-only, dual-gated scientific-hypothesis read routes."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Final

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.scientific_hypotheses_cursor import (
    ScientificHypothesesCursorCodec,
    ScientificHypothesesCursorError,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.scientific_hypotheses_paging import (
    page_scientific_hypothesis_rows,
)
from simulation.scientific_hypotheses_ports import (
    scientific_hypotheses_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["scientific-hypotheses"])
_LOGGER = get_logger("api.routes.scientific_hypotheses")
SCIENTIFIC_HYPOTHESES_ROUTE_COUNT: Final[int] = 7


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "scientific_hypotheses_reader", None)
    if reader is None:
        _LOGGER.info("scientific_hypotheses_reader_disabled")
        raise service_unavailable(code="scientific_hypotheses_disabled")
    return reader


def _codec(request: Request) -> ScientificHypothesesCursorCodec:
    codec = getattr(request.app.state, "scientific_hypotheses_cursor_codec", None)
    if not isinstance(codec, ScientificHypothesesCursorCodec):
        _LOGGER.info("scientific_hypotheses_reader_disabled")
        raise service_unavailable(code="scientific_hypotheses_disabled")
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
        if code == "scientific_hypotheses_store_corrupt" or code.startswith(
            "scientific_hypotheses_snapshot_"
        ):
            _LOGGER.error("scientific_hypotheses_store_corrupt")
            raise internal(code="scientific_hypotheses_store_corrupt") from exc
        raise not_found(code="scientific_hypotheses_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="scientific_hypotheses_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="scientific_hypotheses_run_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any, purpose: str, window_index: int | None, limit: int
) -> str:
    return scientific_hypotheses_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.internal_digest,
        purpose=purpose,
        window_index=window_index,
        limit=limit,
    )


def _after_key(
    codec: ScientificHypothesesCursorCodec,
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
    except ScientificHypothesesCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="scientific_hypotheses_cursor_expired") from exc
        raise bad_request(code="scientific_hypotheses_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.internal_digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, window_index, limit)
    ):
        _LOGGER.warning("scientific_hypotheses_cursor_invalid")
        raise bad_request(code="scientific_hypotheses_cursor_invalid")
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
        if isinstance(value, tuple):
            value = [
                [pair[0], pair[1]] if isinstance(pair, tuple) else pair
                for pair in value
            ]
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
        page, next_key = page_scientific_hypothesis_rows(
            snapshot,
            purpose=purpose,
            limit=limit,
            after=after or None,
            window_index=window_index,
        )
    except ValueError as exc:
        raise bad_request(code="scientific_hypotheses_cursor_invalid") from exc
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
    _LOGGER.info("scientific_hypotheses_route_served purpose=%s", purpose)
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


@router.get("/{run_id}/scientific-hypotheses")
def get_scientific_hypotheses_summary(
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
            "owner_count": summary.owner_count,
            "hypothesis_count": summary.hypothesis_count,
            "active_count": summary.active_count,
            "supported_count": summary.supported_count,
            "contradicted_count": summary.contradicted_count,
            "inconclusive_count": summary.inconclusive_count,
            "revision_count": summary.revision_count,
            "trial_count": summary.trial_count,
            "matched_count": summary.matched_count,
            "mismatched_count": summary.mismatched_count,
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
    return JSONResponse(_page_body(snapshot, page, next_cursor, window_index))


@router.get("/{run_id}/scientific-hypotheses/hypotheses")
def get_scientific_hypotheses_hypotheses(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "hypotheses", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/scientific-hypotheses/evidence")
def get_scientific_hypotheses_evidence(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("evidence", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/scientific-hypotheses/tests")
def get_scientific_hypotheses_tests(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("tests", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/scientific-hypotheses/revisions")
def get_scientific_hypotheses_revisions(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("revisions", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/scientific-hypotheses/sources")
def get_scientific_hypotheses_sources(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("sources", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/scientific-hypotheses/coverage")
def get_scientific_hypotheses_coverage(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("coverage", run_id, request, limit, cursor, window_index)
