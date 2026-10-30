"""Read-only organization HTTP routes."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from api.dependencies import get_organization_reader, get_settings
from api.errors import bad_request, gone, not_found, service_unavailable
from api.organization_cursor import OrganizationCursorCodec, OrganizationCursorError
from api.organization_schemas import (
    OrganizationCandidateDetailOut,
    OrganizationCandidateOut,
    OrganizationCoverageOut,
    OrganizationLineageEdgeOut,
    OrganizationMemberOut,
    OrganizationStructuralOut,
    OrganizationSummaryOut,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.organization_models import (
    MAX_PAGE_ROWS,
    MAX_RESPONSE_BYTES,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationLineageEdgeRecord,
    OrganizationStructuralKind,
)
from simulation.organization_ports import (
    OrganizationCursor,
    OrganizationReadPort,
    OrganizationReadSession,
    organization_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["organizations"])
_LOGGER = get_logger("api.routes.organization")
_PURPOSE_SUMMARY = "organization_summary"
_PURPOSE_CANDIDATES = "organization_candidates"
_PURPOSE_CANDIDATE = "organization_candidate"
_PURPOSE_LINEAGE = "organization_lineage"

_STATUS_VALUES = (
    "recognized",
    "partial",
    "disputed",
    "fragmented",
    "temporary",
    "dissolved",
)
_KIND_VALUES = (
    "continued",
    "transformed",
    "split",
    "merge",
    "dissolved",
    "emerged",
)


def _reader(reader: OrganizationReadPort | None) -> OrganizationReadPort:
    if reader is None:
        raise service_unavailable(code="organization_disabled")
    return reader


def _codec(request: Request) -> OrganizationCursorCodec:
    codec = getattr(request.app.state, "organization_cursor_codec", None)
    if not isinstance(codec, OrganizationCursorCodec):
        raise service_unavailable(code="organization_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _decode_cursor(
    codec: OrganizationCursorCodec,
    token: str,
    *,
    purpose: str,
    run_id: str,
    publication_id: str,
    fingerprint: str,
) -> OrganizationCursor:
    try:
        cursor, _ = codec.decode(token, purpose=purpose)
    except OrganizationCursorError as exc:
        if exc.reason_code == "organization_cursor_expired":
            raise gone(code=exc.reason_code) from exc
        raise bad_request(code=exc.reason_code) from exc
    if (
        cursor.run_id != run_id
        or cursor.publication_id != publication_id
        or cursor.query_fingerprint != fingerprint
    ):
        raise bad_request(code="organization_cursor_invalid")
    return cursor


def _charge(payload: object) -> None:
    session = OrganizationReadSession(max_bytes=MAX_RESPONSE_BYTES)
    try:
        session.charge(len(json.dumps(payload, default=str).encode()))
    except OrganizationArtifactError as exc:
        raise bad_request(code=exc.code) from exc


def _candidate_out(candidate: OrganizationCandidateRecord) -> OrganizationCandidateOut:
    return OrganizationCandidateOut(
        organization_id=candidate.organization_id,
        creation_tick=candidate.creation_tick,
        first_tick=candidate.first_tick,
        last_tick=candidate.last_tick,
        status=candidate.status,
        temporal_scope=candidate.temporal_scope,
        self_identified=candidate.self_identified,
        member_count=candidate.member_count,
        role_count=candidate.count(OrganizationStructuralKind.ROLE),
        goal_count=candidate.count(OrganizationStructuralKind.GOAL),
        resource_count=candidate.count(OrganizationStructuralKind.RESOURCE),
        procedure_count=candidate.count(OrganizationStructuralKind.PROCEDURE),
        record_count=candidate.count(OrganizationStructuralKind.RECORD),
        commitment_count=candidate.count(OrganizationStructuralKind.COMMITMENT),
        identity_count=candidate.count(OrganizationStructuralKind.IDENTITY),
        structural_channel_count=candidate.structural_channel_count,
        window_indexes=candidate.window_indexes,
    )


@router.get("/{run_id}/organizations")
async def organization_summary(
    run_id: str,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    reader: OrganizationReadPort | None = Depends(get_organization_reader),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    _authorize(request, settings)
    summary = _reader(reader).summary(run_id)
    if summary is None:
        raise not_found(code="organization_publication_missing")
    payload = OrganizationSummaryOut(
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        schema_version=summary.schema_version,
        generated_tick=summary.generated_tick,
        candidate_count=summary.candidate_count,
        edge_count=summary.edge_count,
        window_count=summary.window_count,
        coverage=OrganizationCoverageOut(
            observed=summary.coverage.observed,
            expected=summary.coverage.expected,
            ratio=summary.coverage.ratio,
        ),
        provenance_code=summary.provenance_code,
    ).model_dump()
    _charge(payload)
    _LOGGER.debug("organization_api_request route=summary run_id=%s", run_id)
    return payload


@router.get("/{run_id}/organizations/candidates")
async def organization_candidates(
    run_id: str,
    request: Request,
    response: Response,
    status: Literal[
        "recognized", "partial", "disputed", "fragmented", "temporary", "dissolved"
    ]
    | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
    cursor: str | None = Query(default=None),
    publication: str = Query(default=""),
    settings: Settings = Depends(get_settings),
    reader: OrganizationReadPort | None = Depends(get_organization_reader),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    _authorize(request, settings)
    codec = _codec(request)
    summary = _reader(reader).summary(run_id)
    if summary is None:
        raise not_found(code="organization_publication_missing")
    publication_id = publication or summary.publication_id
    fingerprint = organization_query_fingerprint(
        run_id, publication_id, _PURPOSE_CANDIDATES, {"status": status}
    )
    offset = 0
    if cursor:
        offset = _decode_cursor(
            codec,
            cursor,
            purpose=_PURPOSE_CANDIDATES,
            run_id=run_id,
            publication_id=publication_id,
            fingerprint=fingerprint,
        ).offset
    page = _reader(reader).candidates(
        run_id, publication_id, offset, min(limit, MAX_PAGE_ROWS), status
    )
    items = tuple(
        _candidate_out(candidate)
        for candidate in page.rows
        if isinstance(candidate, OrganizationCandidateRecord)
    )
    next_cursor = (
        codec.encode(
            purpose=_PURPOSE_CANDIDATES,
            run_id=run_id,
            publication_id=publication_id,
            snapshot_digest="",
            offset=page.next_offset,
            query_fingerprint=fingerprint,
        )
        if page.truncated
        else None
    )
    payload: dict[str, object] = {
        "publication_id": publication_id,
        "items": [item.model_dump() for item in items],
        "next_cursor": next_cursor,
        "truncated": page.truncated,
    }
    _charge(payload)
    _LOGGER.debug(
        "organization_api_request route=candidates run_id=%s rows=%s",
        run_id,
        len(items),
    )
    return payload


@router.get("/{run_id}/organizations/candidates/{organization_id}")
async def organization_candidate(
    run_id: str,
    organization_id: str,
    request: Request,
    response: Response,
    publication: str = Query(default=""),
    settings: Settings = Depends(get_settings),
    reader: OrganizationReadPort | None = Depends(get_organization_reader),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    _authorize(request, settings)
    summary = _reader(reader).summary(run_id)
    if summary is None:
        raise not_found(code="organization_publication_missing")
    publication_id = publication or summary.publication_id
    candidate = _reader(reader).candidate(run_id, publication_id, organization_id)
    if candidate is None:
        raise not_found(code="organization_unknown_candidate")
    base = _candidate_out(candidate)
    detail = OrganizationCandidateDetailOut(
        **base.model_dump(),
        members=tuple(
            OrganizationMemberOut(
                member_id=member.member_id,
                status=member.status,
                basis=member.basis,
                temporal_scope=member.temporal_scope,
                first_tick=member.first_tick,
                last_tick=member.last_tick,
                expires_tick=member.expires_tick,
                strength=member.strength,
                owner_support_count=member.owner_support_count,
            )
            for member in candidate.members
        ),
        structure=tuple(
            OrganizationStructuralOut(
                kind=item.kind,
                anchor_id=item.anchor_id,
                status=item.status,
                first_tick=item.first_tick,
                last_tick=item.last_tick,
                resolved=item.resolved,
            )
            for item in candidate.structure
        ),
    ).model_dump()
    _charge(detail)
    _LOGGER.debug("organization_api_request route=candidate run_id=%s", run_id)
    return detail


@router.get("/{run_id}/organizations/lineage")
async def organization_lineage(
    run_id: str,
    request: Request,
    response: Response,
    kind: Literal["continued", "transformed", "split", "merge", "dissolved", "emerged"]
    | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
    cursor: str | None = Query(default=None),
    publication: str = Query(default=""),
    settings: Settings = Depends(get_settings),
    reader: OrganizationReadPort | None = Depends(get_organization_reader),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    _authorize(request, settings)
    codec = _codec(request)
    summary = _reader(reader).summary(run_id)
    if summary is None:
        raise not_found(code="organization_publication_missing")
    publication_id = publication or summary.publication_id
    fingerprint = organization_query_fingerprint(
        run_id, publication_id, _PURPOSE_LINEAGE, {"kind": kind}
    )
    offset = 0
    if cursor:
        offset = _decode_cursor(
            codec,
            cursor,
            purpose=_PURPOSE_LINEAGE,
            run_id=run_id,
            publication_id=publication_id,
            fingerprint=fingerprint,
        ).offset
    page = _reader(reader).lineage(
        run_id, publication_id, offset, min(limit, MAX_PAGE_ROWS), kind
    )
    items = tuple(
        OrganizationLineageEdgeOut(
            kind=edge.kind,
            tick=edge.tick,
            from_id=edge.from_id,
            to_id=edge.to_id,
            jaccard=edge.jaccard,
            containment=edge.containment,
        )
        for edge in page.rows
        if isinstance(edge, OrganizationLineageEdgeRecord)
    )
    next_cursor = (
        codec.encode(
            purpose=_PURPOSE_LINEAGE,
            run_id=run_id,
            publication_id=publication_id,
            snapshot_digest="",
            offset=page.next_offset,
            query_fingerprint=fingerprint,
        )
        if page.truncated
        else None
    )
    payload: dict[str, object] = {
        "publication_id": publication_id,
        "items": [item.model_dump() for item in items],
        "next_cursor": next_cursor,
        "truncated": page.truncated,
    }
    _charge(payload)
    _LOGGER.debug(
        "organization_api_request route=lineage run_id=%s rows=%s",
        run_id,
        len(items),
    )
    return payload
