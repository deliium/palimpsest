"""Eight GET-only, dual-gated scientific-model read routes."""

from __future__ import annotations

import hashlib
from typing import Any, Final

from fastapi import APIRouter, Query, Request

from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.scientific_models_cursor import (
    ScientificModelsCursorCodec,
    ScientificModelsCursorError,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.scientific_models_codec import scientific_models_snapshot_digest
from simulation.scientific_models_paging import page_scientific_models_rows

router = APIRouter(prefix="/v1/simulations", tags=["scientific-models"])
_LOGGER = get_logger("api.routes.scientific_models")
SCIENTIFIC_MODELS_ROUTE_COUNT: Final[int] = 8
_DEFAULT_PAGE: Final[int] = 100
_MAX_PAGE: Final[int] = 500

_SECTIONS: Final[tuple[str, ...]] = (
    "models",
    "predictions",
    "outcomes",
    "calibration",
    "revisions",
    "comparisons",
    "coverage",
)


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "scientific_models_reader", None)
    if reader is None:
        raise service_unavailable(code="scientific_models_disabled")
    return reader


def _codec(request: Request) -> ScientificModelsCursorCodec:
    codec = getattr(request.app.state, "scientific_models_cursor_codec", None)
    if not isinstance(codec, ScientificModelsCursorCodec):
        raise service_unavailable(code="scientific_models_disabled")
    return codec


def _authorize(request: Request) -> None:
    require_http_capability(
        request,
        get_settings(request),
        capability=ApiCapability.SUBJECTIVE_DEBUG,
    )


def _snapshot(reader: Any, run_id: str, publication_id: str | None) -> Any:
    from persistence.scientific_models_filesystem import ScientificModelsStoreError

    if publication_id is None:
        try:
            publications = reader.list_publications(run_id)
        except ScientificModelsStoreError as exc:
            if exc.code == "scientific_models_store_run_missing":
                raise not_found(code="scientific_models_run_not_found") from exc
            raise internal(code="scientific_models_store_corrupt") from exc
        if not publications:
            raise not_found(code="scientific_models_run_not_found")
        publication_id = publications[-1]
    try:
        return reader.read_snapshot(run_id, publication_id)
    except ScientificModelsStoreError as exc:
        if exc.code == "scientific_models_store_run_missing":
            raise not_found(code="scientific_models_run_not_found") from exc
        if exc.code == "scientific_models_store_publication_missing":
            raise not_found(code="scientific_models_publication_not_found") from exc
        _LOGGER.error("scientific_models_store_corrupt")
        raise internal(code="scientific_models_store_corrupt") from exc
    except Exception as exc:
        raise not_found(code="scientific_models_run_not_found") from exc


def _fingerprint(
    *,
    digest: str,
    section: str,
    limit: int,
    model_token: str | None,
    target_kind: str | None,
    status: str | None,
    issued_from_tick: int | None,
    issued_through_tick: int | None,
) -> str:
    material = repr(
        (
            section,
            limit,
            model_token,
            target_kind,
            status,
            issued_from_tick,
            issued_through_tick,
        )
    ).encode()
    return digest + ":" + hashlib.sha256(material).hexdigest()[:16]


def _page(
    request: Request,
    run_id: str,
    *,
    section: str,
    publication_id: str | None,
    cursor: str | None,
    limit: int,
    model_token: str | None = None,
    target_kind: str | None = None,
    status: str | None = None,
    issued_from_tick: int | None = None,
    issued_through_tick: int | None = None,
) -> dict[str, object]:
    _authorize(request)
    reader = _reader(request)
    codec = _codec(request)
    if not 1 <= limit <= _MAX_PAGE:
        raise bad_request(code="scientific_models_invalid_page_size")
    purpose = f"scientific-models:{section}"
    payload: dict[str, object] | None = None
    if cursor is not None:
        try:
            payload = codec.decode(cursor, purpose=purpose)
        except ScientificModelsCursorError as exc:
            if exc.reason_code == "diplomacy_cursor_expired":
                raise gone(code="scientific_models_cursor_expired") from exc
            raise bad_request(code="scientific_models_cursor_invalid") from exc
        bound = payload.get("publication_id")
        if type(bound) is not str or not bound:
            raise bad_request(code="scientific_models_cursor_invalid")
        if publication_id is not None and publication_id != bound:
            raise bad_request(code="scientific_models_cursor_invalid")
        publication_id = bound
    snapshot = _snapshot(reader, run_id, publication_id)
    digest = scientific_models_snapshot_digest(snapshot)
    fingerprint = _fingerprint(
        digest=digest,
        section=section,
        limit=limit,
        model_token=model_token,
        target_kind=target_kind,
        status=status,
        issued_from_tick=issued_from_tick,
        issued_through_tick=issued_through_tick,
    )
    offset = 0
    if payload is not None:
        if (
            payload.get("run_id") != snapshot.run_token
            or payload.get("publication_id") != snapshot.publication_id
            or payload.get("snapshot_digest") != digest
            or payload.get("query_fingerprint") != fingerprint
        ):
            raise bad_request(code="scientific_models_cursor_invalid")
        raw = payload.get("after_key")
        try:
            offset = 0 if raw in {None, ""} else int(str(raw))
        except ValueError as exc:
            raise bad_request(code="scientific_models_cursor_invalid") from exc
    page = page_scientific_models_rows(
        snapshot,
        section=section,
        page_size=limit,
        offset=offset,
        model_token=model_token,
        target_kind=target_kind,
        status=status,
        issued_from_tick=issued_from_tick,
        issued_through_tick=issued_through_tick,
    )
    next_cursor = None
    if page.next_offset is not None:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_token,
            publication_id=snapshot.publication_id,
            snapshot_digest=digest,
            query_fingerprint=fingerprint,
            after_key=str(page.next_offset),
        )
    return {
        "run_id": snapshot.run_token,
        "publication_id": snapshot.publication_id,
        "snapshot_digest": digest,
        "section": section,
        "rows": page.rows,
        "next_cursor": next_cursor,
        "truncated": next_cursor is not None,
    }


@router.get("/{run_id}/scientific-models")
async def scientific_models_summary(
    request: Request,
    run_id: str,
    publication_id: str | None = Query(default=None),
) -> dict[str, object]:
    _authorize(request)
    reader = _reader(request)
    codec = _codec(request)
    del codec
    snapshot = _snapshot(reader, run_id, publication_id)
    return {
        "run_id": snapshot.run_token,
        "publication_id": snapshot.publication_id,
        "snapshot_digest": scientific_models_snapshot_digest(snapshot),
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "finalized_through_tick": snapshot.finalized_through_tick,
        "coverage_status": snapshot.coverage_status,
        "counts": {
            section: len(getattr(snapshot, section)) for section in _SECTIONS
        },
        "publications": list(reader.list_publications(run_id)),
    }


def _section_route(section: str) -> Any:
    async def handler(
        request: Request,
        run_id: str,
        publication_id: str | None = Query(default=None),
        cursor: str | None = Query(default=None),
        limit: int = Query(default=_DEFAULT_PAGE),
        model_token: str | None = Query(default=None),
        target_kind: str | None = Query(default=None),
        status: str | None = Query(default=None),
        issued_from_tick: int | None = Query(default=None),
        issued_through_tick: int | None = Query(default=None),
    ) -> dict[str, object]:
        return _page(
            request,
            run_id,
            section=section,
            publication_id=publication_id,
            cursor=cursor,
            limit=limit,
            model_token=model_token,
            target_kind=target_kind,
            status=status,
            issued_from_tick=issued_from_tick,
            issued_through_tick=issued_through_tick,
        )

    handler.__name__ = f"scientific_models_{section}"
    return handler


for _section in _SECTIONS:
    router.add_api_route(
        f"/{{run_id}}/scientific-models/{_section}",
        _section_route(_section),
        methods=["GET"],
        name=f"scientific_models_{_section}",
    )
