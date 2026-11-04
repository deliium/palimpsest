"""Read-only evidence-testimony HTTP routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_evidence_testimony_reader, get_settings
from api.errors import bad_request, gone, not_found, service_unavailable
from api.evidence_testimony_cursor import (
    EvidenceTestimonyCursorCodec,
    EvidenceTestimonyCursorError,
)
from api.evidence_testimony_schemas import (
    MAX_PAGE_LIMIT,
    EvidenceCandidateDetailOut,
    EvidenceCandidateOut,
    EvidenceCandidatePageOut,
    EvidenceContradictionOut,
    EvidenceContradictionPageOut,
    EvidenceLineageEdgeOut,
    EvidenceLineagePageOut,
    EvidenceSourceOut,
    EvidenceSourcePageOut,
    EvidenceSummaryOut,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.evidence_testimony_models import (
    EVIDENCE_TESTIMONY_PAGE_MAX_BYTES,
    EvidenceTestimonyArtifactError,
)
from simulation.evidence_testimony_ports import (
    EvidenceTestimonyPortError,
    EvidenceTestimonyReadPort,
    EvidenceTestimonySummary,
    evidence_testimony_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["evidence"])
_LOGGER = get_logger("api.routes.evidence_testimony")

_PURPOSE_SUMMARY = "summary"
_PURPOSE_CANDIDATES = "candidates"
_PURPOSE_CANDIDATE = "candidate"
_PURPOSE_SOURCES = "sources"
_PURPOSE_CONTRADICTIONS = "contradictions"
_PURPOSE_LINEAGE = "lineage"


def _reader(reader: EvidenceTestimonyReadPort | None) -> EvidenceTestimonyReadPort:
    if reader is None:
        raise service_unavailable(code="evidence_testimony_disabled")
    return reader


def _codec(request: Request) -> EvidenceTestimonyCursorCodec:
    codec = getattr(request.app.state, "evidence_testimony_cursor_codec", None)
    if not isinstance(codec, EvidenceTestimonyCursorCodec):
        raise service_unavailable(code="evidence_testimony_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _read(func: Any, *args: object, **kwargs: object) -> Any:
    try:
        return func(*args, **kwargs)
    except EvidenceTestimonyPortError as exc:
        if exc.code == "evidence_testimony_not_found":
            raise not_found(code=exc.code) from exc
        raise bad_request(code=exc.code) from exc
    except EvidenceTestimonyArtifactError as exc:
        if exc.code == "evidence_testimony_size_limit":
            raise bad_request(code=exc.code) from exc
        raise not_found(code="evidence_testimony_not_found") from exc


def _decode_cursor(
    codec: EvidenceTestimonyCursorCodec,
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
    except EvidenceTestimonyCursorError as exc:
        if exc.reason_code == "evidence_testimony_cursor_expired":
            raise gone(code=exc.reason_code) from exc
        raise bad_request(code=exc.reason_code) from exc
    if (
        cursor.run_id != run_id
        or cursor.publication_id != publication_id
        or cursor.snapshot_digest != snapshot_digest
        or cursor.query_fingerprint != fingerprint
    ):
        raise bad_request(code="evidence_testimony_cursor_invalid")
    return cursor.offset


def _page_cursor(
    *,
    codec: EvidenceTestimonyCursorCodec,
    purpose: str,
    run_id: str,
    summary: EvidenceTestimonySummary,
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
    if (
        len(json.dumps(payload, default=str).encode())
        > EVIDENCE_TESTIMONY_PAGE_MAX_BYTES
    ):
        raise bad_request(code="evidence_testimony_size_limit")


def _summary_out(summary: EvidenceTestimonySummary) -> EvidenceSummaryOut:
    return EvidenceSummaryOut(
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        generated_tick=summary.generated_tick,
        candidate_count=summary.candidate_count,
        source_count=summary.source_count,
        testimony_count=summary.testimony_count,
        item_count=summary.item_count,
        custody_link_count=summary.custody_link_count,
        contradiction_count=summary.contradiction_count,
        evaluation_count=summary.evaluation_count,
        edge_count=summary.edge_count,
        coverage=summary.coverage,
        schema_version=summary.schema_version,
        window_count=summary.window_count,
        provenance_code=summary.provenance_code,
    )


def _candidate_out(candidate: Any) -> EvidenceCandidateOut:
    return EvidenceCandidateOut(
        candidate_id=candidate.candidate_id,
        subject_token=candidate.subject_token,
        source_kind_family=candidate.source_kind_family,
        owner_count=len(getattr(candidate, "owner_tokens", ())),
        item_count=candidate.item_count,
        source_count=candidate.source_count,
        testimony_count=candidate.testimony_count,
        contradiction_count=candidate.contradiction_count,
        status=candidate.status,
        coverage=candidate.coverage,
        first_tick=candidate.first_tick,
        last_tick=candidate.last_tick,
    )


def _source_out(row: Any) -> EvidenceSourceOut:
    return EvidenceSourceOut(
        owner_token=row.owner_token,
        local_id=row.local_id,
        source_kind=row.source_kind,
        reference_kind=row.reference_kind,
        provenance=row.provenance,
        confidence_band=row.confidence_band,
        tick=row.tick,
        subject_token=row.subject_token,
        custody_status=row.custody_status,
        root_ref=getattr(row, "root_ref", None),
        correlation_token=getattr(row, "correlation_token", None),
    )


def _contradiction_out(row: Any) -> EvidenceContradictionOut:
    return EvidenceContradictionOut(
        owner_token=row.owner_token,
        local_id=row.local_id,
        candidate_id=row.candidate_id,
        first_ref=row.first_ref,
        second_ref=row.second_ref,
        kind=row.kind,
        status=row.status,
        tick=row.tick,
    )


def _edge_out(row: Any) -> EvidenceLineageEdgeOut:
    return EvidenceLineageEdgeOut(
        edge_id=row.edge_id,
        kind=row.kind,
        source_ids=tuple(getattr(row, "source_ids", ())),
        target_ids=tuple(getattr(row, "target_ids", ())),
        window_index=row.window_index,
    )


@router.get("/{run_id}/evidence", response_model=EvidenceSummaryOut)
async def evidence_summary(
    request: Request,
    run_id: str,
    reader: EvidenceTestimonyReadPort | None = Depends(get_evidence_testimony_reader),
    settings: Settings = Depends(get_settings),
) -> EvidenceSummaryOut:
    _authorize(request, settings)
    summary = _read(_reader(reader).summary, run_id=run_id)
    payload = _summary_out(summary)
    _charge(payload.model_dump())
    _LOGGER.info("evidence_testimony_read route=summary")
    return payload


@router.get("/{run_id}/evidence/candidates", response_model=EvidenceCandidatePageOut)
async def evidence_candidates(
    request: Request,
    run_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
    reader: EvidenceTestimonyReadPort | None = Depends(get_evidence_testimony_reader),
    settings: Settings = Depends(get_settings),
) -> EvidenceCandidatePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id=run_id)
    fingerprint = evidence_testimony_query_fingerprint(
        purpose=_PURPOSE_CANDIDATES,
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
            purpose=_PURPOSE_CANDIDATES,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        )
    )
    selection = _read(port.candidates, run_id=run_id, offset=offset, limit=limit)
    payload = EvidenceCandidatePageOut(
        items=[_candidate_out(row) for row in selection.rows],
        next_cursor=_page_cursor(
            codec=_codec(request),
            purpose=_PURPOSE_CANDIDATES,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info("evidence_testimony_read route=candidates")
    return payload


@router.get(
    "/{run_id}/evidence/candidates/{candidate_id}",
    response_model=EvidenceCandidateDetailOut,
)
async def evidence_candidate(
    request: Request,
    run_id: str,
    candidate_id: str,
    reader: EvidenceTestimonyReadPort | None = Depends(get_evidence_testimony_reader),
    settings: Settings = Depends(get_settings),
) -> EvidenceCandidateDetailOut:
    _authorize(request, settings)
    detail = _read(_reader(reader).candidate, run_id=run_id, candidate_id=candidate_id)
    candidate = type(
        "CandidateView",
        (),
        {
            "candidate_id": detail.candidate_id,
            "subject_token": detail.subject_token,
            "source_kind_family": detail.source_kind_family,
            "owner_tokens": ("0" * 16,) * detail.owner_count,
            "item_count": detail.item_count,
            "source_count": detail.source_count,
            "testimony_count": detail.testimony_count,
            "contradiction_count": detail.contradiction_count,
            "status": detail.status,
            "coverage": detail.coverage,
            "first_tick": detail.first_tick,
            "last_tick": detail.last_tick,
        },
    )()
    payload = EvidenceCandidateDetailOut(
        candidate=_candidate_out(candidate),
        sources=[_source_out(row) for row in detail.sources],
        contradictions=[_contradiction_out(row) for row in detail.contradictions],
        custody_complete_count=detail.custody_complete_count,
        custody_incomplete_count=detail.custody_incomplete_count,
        custody_conflicting_count=detail.custody_conflicting_count,
        sources_truncated=detail.sources_truncated,
        contradictions_truncated=detail.contradictions_truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info("evidence_testimony_read route=candidate")
    return payload


@router.get(
    "/{run_id}/evidence/candidates/{candidate_id}/sources",
    response_model=EvidenceSourcePageOut,
)
async def evidence_sources(
    request: Request,
    run_id: str,
    candidate_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
    reader: EvidenceTestimonyReadPort | None = Depends(get_evidence_testimony_reader),
    settings: Settings = Depends(get_settings),
) -> EvidenceSourcePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id=run_id)
    detail = _read(port.candidate, run_id=run_id, candidate_id=candidate_id)
    fingerprint = evidence_testimony_query_fingerprint(
        purpose=_PURPOSE_SOURCES,
        run_id=run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        filters=(("candidate_id", candidate_id),),
    )
    offset = (
        0
        if cursor is None
        else _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_SOURCES,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        )
    )
    selection = _read(port.sources, run_id=run_id, offset=0, limit=MAX_PAGE_LIMIT)
    filtered = tuple(
        row
        for row in selection.rows
        if getattr(row, "subject_token", None) == detail.subject_token
    )
    rows = filtered[offset : offset + limit]
    payload = EvidenceSourcePageOut(
        items=[_source_out(row) for row in rows],
        next_cursor=_page_cursor(
            codec=_codec(request),
            purpose=_PURPOSE_SOURCES,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=(offset + limit if offset + limit < len(filtered) else None),
        ),
        truncated=offset + limit < len(filtered),
    )
    _charge(payload.model_dump())
    _LOGGER.info("evidence_testimony_read route=sources")
    return payload


@router.get(
    "/{run_id}/evidence/candidates/{candidate_id}/contradictions",
    response_model=EvidenceContradictionPageOut,
)
async def evidence_contradictions(
    request: Request,
    run_id: str,
    candidate_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
    reader: EvidenceTestimonyReadPort | None = Depends(get_evidence_testimony_reader),
    settings: Settings = Depends(get_settings),
) -> EvidenceContradictionPageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id=run_id)
    fingerprint = evidence_testimony_query_fingerprint(
        purpose=_PURPOSE_CONTRADICTIONS,
        run_id=run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        filters=(("candidate_id", candidate_id),),
    )
    offset = (
        0
        if cursor is None
        else _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_CONTRADICTIONS,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        )
    )
    selection = _read(
        port.contradictions, run_id=run_id, offset=0, limit=MAX_PAGE_LIMIT
    )
    filtered = tuple(
        row
        for row in selection.rows
        if getattr(row, "candidate_id", None) == candidate_id
    )
    rows = filtered[offset : offset + limit]
    payload = EvidenceContradictionPageOut(
        items=[_contradiction_out(row) for row in rows],
        next_cursor=_page_cursor(
            codec=_codec(request),
            purpose=_PURPOSE_CONTRADICTIONS,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=(offset + limit if offset + limit < len(filtered) else None),
        ),
        truncated=offset + limit < len(filtered),
    )
    _charge(payload.model_dump())
    _LOGGER.info("evidence_testimony_read route=contradictions")
    return payload


@router.get("/{run_id}/evidence/lineage", response_model=EvidenceLineagePageOut)
async def evidence_lineage(
    request: Request,
    run_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cursor: str | None = None,
    reader: EvidenceTestimonyReadPort | None = Depends(get_evidence_testimony_reader),
    settings: Settings = Depends(get_settings),
) -> EvidenceLineagePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id=run_id)
    fingerprint = evidence_testimony_query_fingerprint(
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
    payload = EvidenceLineagePageOut(
        items=[_edge_out(row) for row in selection.rows],
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
    _LOGGER.info("evidence_testimony_read route=lineage")
    return payload
