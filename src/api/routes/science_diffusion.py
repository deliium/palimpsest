"""Six GET-only, capability-gated science-diffusion read routes."""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Final

from fastapi import APIRouter, Query, Request

from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.science_diffusion_cursor import (
    ScienceDiffusionCursorCodec,
    ScienceDiffusionCursorError,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.science_diffusion_codec import science_diffusion_digest
from simulation.science_diffusion_models import section_names
from simulation.science_diffusion_paging import (
    DEFAULT_SCIENCE_DIFFUSION_PAGE_LIMIT,
    MAX_SCIENCE_DIFFUSION_PAGE_LIMIT,
    page_science_diffusion_rows,
)

router = APIRouter(prefix="/v1/simulations", tags=["science-diffusion"])
_LOGGER = get_logger("api.routes.science_diffusion")
SCIENCE_DIFFUSION_ROUTE_COUNT: Final[int] = 6


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "science_diffusion_reader", None)
    if reader is None:
        raise service_unavailable(code="science_diffusion_disabled")
    return reader


def _codec(request: Request) -> Any:
    codec = getattr(request.app.state, "science_diffusion_cursor_codec", None)
    if not isinstance(codec, ScienceDiffusionCursorCodec):
        raise service_unavailable(code="science_diffusion_disabled")
    return codec


def _authorize(request: Request) -> None:
    require_http_capability(
        request,
        get_settings(request),
        capability=ApiCapability.SUBJECTIVE_DEBUG,
    )


def _snapshot(request: Request, run_id: str, publication_id: str | None) -> Any:
    reader = _reader(request)
    try:
        if publication_id is None:
            publication_id = reader.latest_publication_id(run_id)
            if publication_id is None:
                raise not_found(code="science_diffusion_run_not_found")
        snapshot = reader.read(run_id, publication_id)
    except ValueError as exc:
        _LOGGER.error("science_diffusion_store_corrupt")
        raise internal(code="science_diffusion_store_corrupt") from exc
    if snapshot is None:
        if publication_id not in reader.list_publications(run_id):
            raise not_found(code="science_diffusion_publication_not_found")
        raise not_found(code="science_diffusion_run_not_found")
    return snapshot


def _fingerprint(*, digest: str, section: str, limit: int) -> str:
    material = repr((section, limit)).encode()
    return digest + ":" + hashlib.sha256(material).hexdigest()[:16]


@router.get("/{run_id}/science-diffusion")
async def science_diffusion_summary(
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
        "snapshot_digest": science_diffusion_digest(snapshot),
        "schema_version": snapshot.version,
        "policy_version": snapshot.policy_version,
        "input_revision": snapshot.input_revision,
        "boundary_tick": snapshot.boundary_tick,
        "counts": {
            section: len(snapshot.rows_for(section))
            for section in section_names()
        },
        "publications": list(reader.list_publications(run_id)),
    }


def _row_key(row: object) -> str:
    key = getattr(row, "row_key", None)
    return str(key) if key is not None else ""


def _page(
    request: Request,
    run_id: str,
    *,
    section: str,
    publication_id: str | None,
    cursor: str | None,
    limit: int,
) -> dict[str, object]:
    _authorize(request)
    if section not in section_names():
        raise bad_request(code="science_diffusion_invalid_section")
    if not 1 <= limit <= MAX_SCIENCE_DIFFUSION_PAGE_LIMIT:
        raise bad_request(code="science_diffusion_invalid_page_size")
    codec = _codec(request)
    purpose = f"science-diffusion:{section}"
    payload: dict[str, Any] | None = None
    if cursor is not None:
        try:
            payload = codec.decode(cursor, purpose=purpose)
        except ScienceDiffusionCursorError as exc:
            if exc.reason_code == "diplomacy_cursor_expired":
                raise gone(code="science_diffusion_cursor_expired") from exc
            raise bad_request(code="science_diffusion_cursor_invalid") from exc
        bound = payload.get("publication_id")
        if type(bound) is not str or not bound:
            raise bad_request(code="science_diffusion_cursor_invalid")
        if publication_id is not None and publication_id != bound:
            raise bad_request(code="science_diffusion_cursor_invalid")
        publication_id = bound
    if publication_id is None:
        raise bad_request(code="science_diffusion_publication_id_required")
    snapshot = _snapshot(request, run_id, publication_id)
    digest = science_diffusion_digest(snapshot)
    fingerprint = _fingerprint(digest=digest, section=section, limit=limit)
    position = 0
    if payload is not None:
        if (
            payload.get("run_id") != snapshot.run_id
            or payload.get("publication_id") != snapshot.publication_id
            or payload.get("snapshot_digest") != digest
            or payload.get("query_fingerprint") != fingerprint
        ):
            raise bad_request(code="science_diffusion_cursor_invalid")
        after_key = payload.get("after_key")
        if type(after_key) is not str or not after_key:
            raise bad_request(code="science_diffusion_cursor_invalid")
        rows = snapshot.rows_for(section)
        keys = [_row_key(row) for row in rows]
        if after_key not in keys:
            raise bad_request(code="science_diffusion_cursor_invalid")
        position = keys.index(after_key) + 1
    try:
        page = page_science_diffusion_rows(
            snapshot, section=section, position=position, limit=limit
        )
    except ValueError as exc:
        raise bad_request(code="science_diffusion_page_invalid") from exc
    next_cursor = None
    if page.next_position is not None:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=digest,
            query_fingerprint=fingerprint,
            after_key=_row_key(page.rows[-1]),
        )
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "snapshot_digest": digest,
        "section": section,
        "rows": [
            dataclasses.asdict(row)  # type: ignore[call-overload]
            for row in page.rows
        ],
        "next_cursor": next_cursor,
        "truncated": next_cursor is not None,
    }


def _section_route(section: str) -> Any:
    async def handler(
        request: Request,
        run_id: str,
        publication_id: str | None = Query(default=None),
        cursor: str | None = Query(default=None),
        limit: int = Query(default=DEFAULT_SCIENCE_DIFFUSION_PAGE_LIMIT),
    ) -> dict[str, object]:
        return _page(
            request,
            run_id,
            section=section,
            publication_id=publication_id,
            cursor=cursor,
            limit=limit,
        )

    handler.__name__ = f"science_diffusion_{section}"
    return handler


router.add_api_route(
    "/{run_id}/science-diffusion/coverage",
    _section_route("coverage"),
    methods=["GET"],
)
router.add_api_route(
    "/{run_id}/science-diffusion/versions",
    _section_route("versions"),
    methods=["GET"],
)
router.add_api_route(
    "/{run_id}/science-diffusion/transmissions",
    _section_route("transmissions"),
    methods=["GET"],
)
router.add_api_route(
    "/{run_id}/science-diffusion/changes",
    _section_route("changes"),
    methods=["GET"],
)
router.add_api_route(
    "/{run_id}/science-diffusion/genealogy",
    _section_route("genealogy"),
    methods=["GET"],
)
