"""Five GET-only, dual-gated scientific-institution read routes."""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Final

from fastapi import APIRouter, Query, Request

from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.scientific_institutions_cursor import (
    ScientificInstitutionsCursorCodec,
    ScientificInstitutionsCursorError,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.scientific_institutions_codec import (
    scientific_institutions_digest,
)
from simulation.scientific_institutions_models import section_names
from simulation.scientific_institutions_paging import (
    DEFAULT_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT,
    MAX_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT,
    page_scientific_institution_rows,
)

router = APIRouter(prefix="/v1/simulations", tags=["scientific-institutions"])
_LOGGER = get_logger("api.routes.scientific_institutions")
SCIENTIFIC_INSTITUTIONS_ROUTE_COUNT: Final[int] = 5


def _reader(request: Request) -> Any:
    reader = getattr(
        request.app.state, "scientific_institutions_reader", None
    )
    if reader is None:
        raise service_unavailable(code="scientific_institutions_disabled")
    return reader


def _codec(request: Request) -> ScientificInstitutionsCursorCodec:
    codec = getattr(
        request.app.state, "scientific_institutions_cursor_codec", None
    )
    if not isinstance(codec, ScientificInstitutionsCursorCodec):
        raise service_unavailable(code="scientific_institutions_disabled")
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
        publication_id = reader.latest_publication_id(run_id)
        if publication_id is None:
            raise not_found(code="scientific_institutions_run_not_found")
    try:
        snapshot = reader.read(run_id, publication_id)
    except ValueError as exc:
        _LOGGER.error("scientific_institutions_store_corrupt")
        raise internal(code="scientific_institutions_store_corrupt") from exc
    if snapshot is None:
        if publication_id not in reader.list_publications(run_id):
            raise not_found(
                code="scientific_institutions_publication_not_found"
            )
        raise not_found(code="scientific_institutions_run_not_found")
    return snapshot


def _fingerprint(*, digest: str, section: str, limit: int) -> str:
    material = repr((section, limit)).encode()
    return digest + ":" + hashlib.sha256(material).hexdigest()[:16]


@router.get("/{run_id}/scientific-institutions")
async def scientific_institutions_summary(
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
        "snapshot_digest": scientific_institutions_digest(snapshot),
        "schema_version": snapshot.version,
        "policy_version": snapshot.policy_version,
        "input_revision": snapshot.input_revision,
        "boundary_tick": snapshot.boundary_tick,
        "counts": {
            section: len(snapshot.rows_for(section))
            for section in section_names()
        },
        "summary": dict(snapshot.summary),
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
) -> dict[str, object]:
    _authorize(request)
    if section not in section_names():
        raise bad_request(code="scientific_institutions_invalid_section")
    if not 1 <= limit <= MAX_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT:
        raise bad_request(code="scientific_institutions_invalid_page_size")
    codec = _codec(request)
    purpose = f"scientific-institutions:{section}"
    payload: dict[str, Any] | None = None
    if cursor is not None:
        try:
            payload = codec.decode(cursor, purpose=purpose)
        except ScientificInstitutionsCursorError as exc:
            if exc.reason_code == "diplomacy_cursor_expired":
                raise gone(code="scientific_institutions_cursor_expired") from exc
            raise bad_request(
                code="scientific_institutions_cursor_invalid"
            ) from exc
        bound = payload.get("publication_id")
        if type(bound) is not str or not bound:
            raise bad_request(code="scientific_institutions_cursor_invalid")
        if publication_id is not None and publication_id != bound:
            raise bad_request(code="scientific_institutions_cursor_invalid")
        publication_id = bound
    if publication_id is None:
        raise bad_request(
            code="scientific_institutions_publication_id_required"
        )
    snapshot = _snapshot(request, run_id, publication_id)
    digest = scientific_institutions_digest(snapshot)
    fingerprint = _fingerprint(digest=digest, section=section, limit=limit)
    position = 0
    if payload is not None:
        if (
            payload.get("run_id") != snapshot.run_id
            or payload.get("publication_id") != snapshot.publication_id
            or payload.get("snapshot_digest") != digest
            or payload.get("query_fingerprint") != fingerprint
        ):
            raise bad_request(code="scientific_institutions_cursor_invalid")
        raw = payload.get("after_key")
        try:
            position = 0 if raw in {None, ""} else int(str(raw))
        except ValueError as exc:
            raise bad_request(
                code="scientific_institutions_cursor_invalid"
            ) from exc
    try:
        page = page_scientific_institution_rows(
            snapshot,
            section=section,
            position=position,
            limit=limit,
        )
    except ValueError as exc:
        raise bad_request(
            code="scientific_institutions_page_invalid"
        ) from exc
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
        limit: int = Query(
            default=DEFAULT_SCIENTIFIC_INSTITUTIONS_PAGE_LIMIT
        ),
    ) -> dict[str, object]:
        return _page(
            request,
            run_id,
            section=section,
            publication_id=publication_id,
            cursor=cursor,
            limit=limit,
        )

    handler.__name__ = f"scientific_institutions_{section}"
    return handler


for _section in section_names():
    router.add_api_route(
        f"/{{run_id}}/scientific-institutions/{_section}",
        _section_route(_section),
        methods=["GET"],
    )
