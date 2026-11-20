"""Seven GET-only, dual-gated competing-theory read routes."""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Final

from fastapi import APIRouter, Query, Request

from api.competing_theories_cursor import (
    CompetingTheoriesCursorCodec,
    CompetingTheoriesCursorError,
)
from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.competing_theories_codec import competing_theories_digest
from simulation.competing_theories_models import section_names
from simulation.competing_theories_paging import (
    DEFAULT_THEORY_PAGE_LIMIT,
    MAX_THEORY_PAGE_LIMIT,
    page_theory_rows,
)

router = APIRouter(prefix="/v1/simulations", tags=["competing-theories"])
_LOGGER = get_logger("api.routes.competing_theories")
COMPETING_THEORIES_ROUTE_COUNT: Final[int] = 8


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "competing_theories_reader", None)
    if reader is None:
        raise service_unavailable(code="competing_theories_disabled")
    return reader


def _codec(request: Request) -> CompetingTheoriesCursorCodec:
    codec = getattr(request.app.state, "competing_theories_cursor_codec", None)
    if not isinstance(codec, CompetingTheoriesCursorCodec):
        raise service_unavailable(code="competing_theories_disabled")
    return codec


def _authorize(request: Request) -> None:
    require_http_capability(
        request,
        get_settings(request),
        capability=ApiCapability.SUBJECTIVE_DEBUG,
    )


def _snapshot(
    request: Request, run_id: str, publication_id: str | None
) -> Any:
    reader = _reader(request)
    if publication_id is None:
        publications = reader.list_publications(run_id)
        if not publications:
            raise not_found(code="competing_theories_run_not_found")
        publication_id = publications[-1]
    try:
        snapshot = reader.read(run_id, publication_id)
    except ValueError as exc:
        _LOGGER.error("competing_theories_store_corrupt")
        raise internal(code="competing_theories_store_corrupt") from exc
    if snapshot is None:
        if publication_id not in reader.list_publications(run_id):
            raise not_found(code="competing_theories_publication_not_found")
        raise not_found(code="competing_theories_run_not_found")
    return snapshot


def _fingerprint(
    *,
    digest: str,
    section: str,
    limit: int,
    window: int | None,
    theory_id: str | None,
) -> str:
    material = repr((section, limit, window, theory_id)).encode()
    return digest + ":" + hashlib.sha256(material).hexdigest()[:16]


@router.get("/{run_id}/competing-theories")
async def competing_theories_summary(
    request: Request,
    run_id: str,
    publication_id: str | None = Query(default=None),
) -> dict[str, object]:
    _authorize(request)
    reader = _reader(request)
    snapshot = _snapshot(request, run_id, publication_id)
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "snapshot_digest": competing_theories_digest(snapshot),
        "schema_version": snapshot.version,
        "counts": {
            section: len(snapshot.rows_for(section)) for section in section_names()
        },
        "summary": dict(snapshot.summary),
        "omitted_windows": snapshot.omitted_windows,
        "first_retained_window": snapshot.first_retained_window,
        "publications": list(reader.list_publications(run_id)),
    }


def _page(
    request: Request,
    run_id: str,
    *,
    section: str,
    publication_id: str | None,
    cursor: str | None,
    limit: int,
    window: int | None,
    theory_id: str | None,
) -> dict[str, object]:
    _authorize(request)
    if section not in section_names():
        raise bad_request(code="competing_theories_invalid_section")
    if not 1 <= limit <= MAX_THEORY_PAGE_LIMIT:
        raise bad_request(code="competing_theories_invalid_page_size")
    codec = _codec(request)
    purpose = f"competing-theories:{section}"
    payload: dict[str, Any] | None = None
    if cursor is not None:
        try:
            payload = codec.decode(cursor, purpose=purpose)
        except CompetingTheoriesCursorError as exc:
            if exc.reason_code == "diplomacy_cursor_expired":
                raise gone(code="competing_theories_cursor_expired") from exc
            raise bad_request(code="competing_theories_cursor_invalid") from exc
        bound = payload.get("publication_id")
        if type(bound) is not str or not bound:
            raise bad_request(code="competing_theories_cursor_invalid")
        if publication_id is not None and publication_id != bound:
            raise bad_request(code="competing_theories_cursor_invalid")
        publication_id = bound
    snapshot = _snapshot(request, run_id, publication_id)
    digest = competing_theories_digest(snapshot)
    fingerprint = _fingerprint(
        digest=digest,
        section=section,
        limit=limit,
        window=window,
        theory_id=theory_id,
    )
    position = 0
    if payload is not None:
        if (
            payload.get("run_id") != snapshot.run_id
            or payload.get("publication_id") != snapshot.publication_id
            or payload.get("snapshot_digest") != digest
            or payload.get("query_fingerprint") != fingerprint
        ):
            raise bad_request(code="competing_theories_cursor_invalid")
        raw = payload.get("after_key")
        try:
            position = 0 if raw in {None, ""} else int(str(raw))
        except ValueError as exc:
            raise bad_request(code="competing_theories_cursor_invalid") from exc
    try:
        page = page_theory_rows(
            snapshot,
            section=section,
            position=position,
            limit=limit,
            window=window,
            theory_id=theory_id,
        )
    except ValueError as exc:
        raise bad_request(code="competing_theories_filter_invalid") from exc
    next_cursor = None
    if page.next_position is not None:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=digest,
            query_fingerprint=fingerprint,
            after_key=str(page.next_position),
        )
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "snapshot_digest": digest,
        "section": section,
        "rows": [dataclasses.asdict(row) for row in page.rows],
        "next_cursor": next_cursor,
        "truncated": next_cursor is not None,
    }


def _section_route(section: str) -> Any:
    async def handler(
        request: Request,
        run_id: str,
        publication_id: str | None = Query(default=None),
        cursor: str | None = Query(default=None),
        limit: int = Query(default=DEFAULT_THEORY_PAGE_LIMIT),
        window: int | None = Query(default=None),
        theory_id: str | None = Query(default=None),
    ) -> dict[str, object]:
        return _page(
            request,
            run_id,
            section=section,
            publication_id=publication_id,
            cursor=cursor,
            limit=limit,
            window=window,
            theory_id=theory_id,
        )

    handler.__name__ = f"competing_theories_{section}"
    return handler


for _section in section_names():
    router.add_api_route(
        f"/{{run_id}}/competing-theories/{_section}",
        _section_route(_section),
        methods=["GET"],
    )
