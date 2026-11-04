"""Read-only delegation-representation HTTP routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from api.delegation_representation_cursor import (
    DelegationRepresentationCursorCodec,
    DelegationRepresentationCursorError,
)
from api.delegation_representation_schemas import (
    MAX_PAGE_LIMIT,
    RepresentationLineageOut,
    RepresentationLineagePageOut,
    RepresentationMandateOut,
    RepresentationMandatePageOut,
    RepresentationPositionOut,
    RepresentationPositionPageOut,
    RepresentationRevocationOut,
    RepresentationRevocationPageOut,
    RepresentationSummaryOut,
)
from api.dependencies import get_delegation_representation_reader, get_settings
from api.errors import bad_request, gone, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.delegation_representation_models import (
    MAX_SNAPSHOT_BYTES,
    DelegationRepresentationArtifactError,
)
from simulation.delegation_representation_ports import (
    DelegationRepresentationPortError,
    DelegationRepresentationReadPort,
    DelegationRepresentationSummary,
    delegation_representation_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["representation"])
_LOGGER = get_logger("api.routes.delegation_representation")

_PURPOSE_SUMMARY = "summary"
_PURPOSE_MANDATES = "mandates"
_PURPOSE_MANDATE = "mandate"
_PURPOSE_POSITIONS = "positions"
_PURPOSE_REVOCATIONS = "revocations"
_PURPOSE_LINEAGE = "lineage"


def _reader(
    reader: DelegationRepresentationReadPort | None,
) -> DelegationRepresentationReadPort:
    if reader is None:
        raise service_unavailable(code="representation_disabled")
    return reader


def _codec(request: Request) -> DelegationRepresentationCursorCodec:
    codec = getattr(request.app.state, "representation_cursor_codec", None)
    if not isinstance(codec, DelegationRepresentationCursorCodec):
        raise service_unavailable(code="representation_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _read(func: Any, *args: object, **kwargs: object) -> Any:
    try:
        return func(*args, **kwargs)
    except DelegationRepresentationPortError as exc:
        if exc.code == "delegation_representation_not_found":
            raise not_found(code=exc.code) from exc
        if exc.code == "delegation_representation_cursor_expired":
            raise gone(code=exc.code) from exc
        raise bad_request(code=exc.code) from exc
    except DelegationRepresentationArtifactError as exc:
        if exc.code == "delegation_representation_size_limit":
            raise bad_request(code=exc.code) from exc
        raise not_found(code="delegation_representation_not_found") from exc


def _decode_cursor(
    codec: DelegationRepresentationCursorCodec,
    token: str,
    *,
    purpose: str,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    fingerprint: str,
) -> int:
    try:
        cursor, _ = codec.decode(token, purpose=purpose)
    except DelegationRepresentationCursorError as exc:
        if exc.reason_code == "representation_cursor_expired":
            raise gone(code=exc.reason_code) from exc
        raise bad_request(code=exc.reason_code) from exc
    if (
        cursor.run_id != run_id
        or cursor.publication_id != publication_id
        or cursor.snapshot_digest != snapshot_digest
        or cursor.query_fingerprint != fingerprint
    ):
        raise bad_request(code="representation_cursor_invalid")
    return cursor.offset


def _page_cursor(
    *,
    codec: DelegationRepresentationCursorCodec,
    purpose: str,
    run_id: str,
    summary: DelegationRepresentationSummary,
    fingerprint: str,
    next_offset: int | None,
) -> str | None:
    if next_offset is None:
        return None
    return codec.encode(
        purpose=purpose,
        run_id=run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        offset=next_offset,
        query_fingerprint=fingerprint,
    )


def _charge(payload: object) -> None:
    if len(json.dumps(payload, default=str).encode()) > MAX_SNAPSHOT_BYTES:
        raise bad_request(code="representation_size_limit")


def _summary_out(summary: DelegationRepresentationSummary) -> RepresentationSummaryOut:
    return RepresentationSummaryOut(
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        generated_tick=summary.generated_tick,
        mandate_count=summary.mandate_count,
        position_count=summary.position_count,
        revocation_count=summary.revocation_count,
        conflict_count=summary.conflict_count,
        candidate_count=summary.candidate_count,
        lineage_edge_count=summary.lineage_edge_count,
        owner_count=summary.owner_count,
        coverage=summary.coverage,
        schema_version=summary.schema_version,
    )


def _mandate_out(row: Any) -> RepresentationMandateOut:
    return RepresentationMandateOut(
        mandate_id=row.mandate_id,
        owner_token=row.owner_token,
        principal_kind=row.principal_kind,
        principal_token=row.principal_token,
        representative_token=row.representative_token,
        scope_kind=row.scope_kind,
        scope_subject_token=row.scope_subject_token,
        duration_kind=row.duration_kind,
        start_tick=row.start_tick,
        end_tick=row.end_tick,
        provenance=row.provenance,
        status=row.status,
        recognition_basis=row.recognition_basis,
        support_roots=row.support_roots,
        opposition_roots=row.opposition_roots,
        confidence_band=row.confidence_band,
        coverage=row.coverage,
    )


def _position_out(row: Any) -> RepresentationPositionOut:
    return RepresentationPositionOut(
        position_id=row.position_id,
        mandate_id=row.mandate_id,
        owner_token=row.owner_token,
        actor_token=row.actor_token,
        stance=row.stance,
        provenance=row.provenance,
        tick=row.tick,
        active=row.active,
    )


def _revocation_out(row: Any) -> RepresentationRevocationOut:
    return RepresentationRevocationOut(
        revocation_id=row.revocation_id,
        mandate_id=row.mandate_id,
        owner_token=row.owner_token,
        actor_token=row.actor_token,
        kind=row.kind,
        provenance=row.provenance,
        tick=row.tick,
        contested=row.contested,
    )


def _lineage_out(row: Any) -> RepresentationLineageOut:
    return RepresentationLineageOut(
        edge_id=row.edge_id,
        from_candidate_id=row.from_candidate_id,
        to_candidate_id=row.to_candidate_id,
        kind=row.kind,
        tick=row.tick,
    )


@router.get("/{run_id}/representation", response_model=RepresentationSummaryOut)
async def representation_summary(
    request: Request,
    run_id: str,
    reader: DelegationRepresentationReadPort | None = Depends(
        get_delegation_representation_reader
    ),
    settings: Settings = Depends(get_settings),
) -> RepresentationSummaryOut:
    _authorize(request, settings)
    summary = _read(_reader(reader).summary, run_id=run_id)
    payload = _summary_out(summary)
    _charge(payload.model_dump())
    _LOGGER.info("representation_read route=summary")
    return payload


@router.get(
    "/{run_id}/representation/mandates",
    response_model=RepresentationMandatePageOut,
)
async def representation_mandates(
    request: Request,
    run_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
    candidate_id: str | None = None,
    reader: DelegationRepresentationReadPort | None = Depends(
        get_delegation_representation_reader
    ),
    settings: Settings = Depends(get_settings),
) -> RepresentationMandatePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id=run_id)
    filters = () if candidate_id is None else (("candidate_id", candidate_id),)
    fingerprint = delegation_representation_query_fingerprint(
        purpose=_PURPOSE_MANDATES,
        run_id=run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        filters=filters,
    )
    offset = (
        0
        if cursor is None
        else _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_MANDATES,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        )
    )
    selection = _read(
        port.mandates,
        run_id=run_id,
        offset=offset,
        limit=limit,
        candidate_id=candidate_id,
    )
    payload = RepresentationMandatePageOut(
        items=[_mandate_out(row) for row in selection.rows],
        next_cursor=_page_cursor(
            codec=_codec(request),
            purpose=_PURPOSE_MANDATES,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info("representation_read route=mandates")
    return payload


@router.get(
    "/{run_id}/representation/mandates/{mandate_id}",
    response_model=RepresentationMandateOut,
)
async def representation_mandate(
    request: Request,
    run_id: str,
    mandate_id: str,
    reader: DelegationRepresentationReadPort | None = Depends(
        get_delegation_representation_reader
    ),
    settings: Settings = Depends(get_settings),
) -> RepresentationMandateOut:
    _authorize(request, settings)
    row = _read(_reader(reader).mandate, run_id=run_id, mandate_id=mandate_id)
    payload = _mandate_out(row)
    _charge(payload.model_dump())
    _LOGGER.info("representation_read route=mandate")
    return payload


@router.get(
    "/{run_id}/representation/mandates/{mandate_id}/positions",
    response_model=RepresentationPositionPageOut,
)
async def representation_positions(
    request: Request,
    run_id: str,
    mandate_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
    reader: DelegationRepresentationReadPort | None = Depends(
        get_delegation_representation_reader
    ),
    settings: Settings = Depends(get_settings),
) -> RepresentationPositionPageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id=run_id)
    fingerprint = delegation_representation_query_fingerprint(
        purpose=_PURPOSE_POSITIONS,
        run_id=run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        filters=(("mandate_id", mandate_id),),
    )
    offset = (
        0
        if cursor is None
        else _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_POSITIONS,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        )
    )
    selection = _read(
        port.positions,
        run_id=run_id,
        mandate_id=mandate_id,
        offset=offset,
        limit=limit,
    )
    payload = RepresentationPositionPageOut(
        items=[_position_out(row) for row in selection.rows],
        next_cursor=_page_cursor(
            codec=_codec(request),
            purpose=_PURPOSE_POSITIONS,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info("representation_read route=positions")
    return payload


@router.get(
    "/{run_id}/representation/mandates/{mandate_id}/revocations",
    response_model=RepresentationRevocationPageOut,
)
async def representation_revocations(
    request: Request,
    run_id: str,
    mandate_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
    reader: DelegationRepresentationReadPort | None = Depends(
        get_delegation_representation_reader
    ),
    settings: Settings = Depends(get_settings),
) -> RepresentationRevocationPageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id=run_id)
    fingerprint = delegation_representation_query_fingerprint(
        purpose=_PURPOSE_REVOCATIONS,
        run_id=run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        filters=(("mandate_id", mandate_id),),
    )
    offset = (
        0
        if cursor is None
        else _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_REVOCATIONS,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        )
    )
    selection = _read(
        port.revocations,
        run_id=run_id,
        mandate_id=mandate_id,
        offset=offset,
        limit=limit,
    )
    payload = RepresentationRevocationPageOut(
        items=[_revocation_out(row) for row in selection.rows],
        next_cursor=_page_cursor(
            codec=_codec(request),
            purpose=_PURPOSE_REVOCATIONS,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info("representation_read route=revocations")
    return payload


@router.get(
    "/{run_id}/representation/lineage",
    response_model=RepresentationLineagePageOut,
)
async def representation_lineage(
    request: Request,
    run_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
    reader: DelegationRepresentationReadPort | None = Depends(
        get_delegation_representation_reader
    ),
    settings: Settings = Depends(get_settings),
) -> RepresentationLineagePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id=run_id)
    fingerprint = delegation_representation_query_fingerprint(
        purpose=_PURPOSE_LINEAGE,
        run_id=run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
    )
    offset = (
        0
        if cursor is None
        else _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_LINEAGE,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        )
    )
    selection = _read(port.lineage, run_id=run_id, offset=offset, limit=limit)
    payload = RepresentationLineagePageOut(
        items=[_lineage_out(row) for row in selection.rows],
        next_cursor=_page_cursor(
            codec=_codec(request),
            purpose=_PURPOSE_LINEAGE,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info("representation_read route=lineage")
    return payload
