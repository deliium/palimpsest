"""Read-only dispute HTTP routes."""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_dispute_reader, get_settings
from api.dispute_cursor import DisputeCursorCodec, DisputeCursorError
from api.dispute_schemas import (
    DisputeAuthorityReferenceOut,
    DisputeCandidateDetailOut,
    DisputeCandidateOut,
    DisputeCandidatePageOut,
    DisputeClaimOut,
    DisputeClaimPageOut,
    DisputeCoverageOut,
    DisputeEvidenceOut,
    DisputeLineageEdgeOut,
    DisputeLineagePageOut,
    DisputeMediationReferenceOut,
    DisputeResolutionOut,
    DisputeResolutionPageOut,
    DisputeResolutionResponseOut,
    DisputeRuleReferenceOut,
    DisputeSummaryOut,
    DisputeTestimonyOut,
)
from api.errors import bad_request, gone, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.dispute_models import (
    MAX_PAGE_ROWS,
    MAX_RESPONSE_BYTES,
    DisputeArtifactError,
    DisputeCoverage,
    DisputePortError,
)
from simulation.dispute_ports import (
    DisputeCandidateDetail,
    DisputeCursor,
    DisputeReadPort,
    DisputeSummary,
    dispute_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["disputes"])
_LOGGER = get_logger("api.routes.dispute")

_PURPOSE_SUMMARY = "summary"
_PURPOSE_CANDIDATES = "candidates"
_PURPOSE_CANDIDATE = "candidate"
_PURPOSE_CLAIMS = "claims"
_PURPOSE_RESOLUTIONS = "resolutions"
_PURPOSE_LINEAGE = "lineage"

_CandidateStatus = Literal[
    "emerging",
    "active",
    "contested",
    "fragmented",
    "apparently_resolved",
    "dissolved",
    "unknown",
]
_ClaimRole = Literal["claim", "counterclaim", "supplementary"]
_ResolutionStatus = Literal[
    "proposed",
    "partially_accepted",
    "apparently_accepted",
    "contested",
    "withdrawn",
    "expired",
    "superseded",
]
_LineageKind = Literal[
    "continued", "transformed", "split", "merge", "dissolved", "emerged"
]


def _reader(reader: DisputeReadPort | None) -> DisputeReadPort:
    if reader is None:
        raise service_unavailable(code="dispute_disabled")
    return reader


def _codec(request: Request) -> DisputeCursorCodec:
    codec = getattr(request.app.state, "dispute_cursor_codec", None)
    if not isinstance(codec, DisputeCursorCodec):
        raise service_unavailable(code="dispute_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _read(func: Any, *args: object, **kwargs: object) -> Any:
    """Call one read-port method and map stable failures to HTTP errors."""
    try:
        return func(*args, **kwargs)
    except DisputePortError as exc:
        if exc.code == "dispute_not_found":
            raise not_found(code=exc.code) from exc
        raise bad_request(code=exc.code) from exc
    except DisputeArtifactError as exc:
        if exc.code == "dispute_size_limit":
            raise bad_request(code=exc.code) from exc
        raise not_found(code="dispute_not_found") from exc


def _decode_cursor(
    codec: DisputeCursorCodec,
    token: str,
    *,
    purpose: str,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    fingerprint: str,
) -> DisputeCursor:
    try:
        cursor, _ = codec.decode(token, purpose=purpose)
    except DisputeCursorError as exc:
        if exc.reason_code == "dispute_cursor_expired":
            raise gone(code=exc.reason_code) from exc
        raise bad_request(code=exc.reason_code) from exc
    if (
        cursor.run_id != run_id
        or cursor.publication_id != publication_id
        or cursor.query_fingerprint != fingerprint
        or cursor.snapshot_digest != snapshot_digest
    ):
        raise bad_request(code="dispute_cursor_invalid")
    return cursor


def _charge(payload: object) -> None:
    if len(json.dumps(payload, default=str).encode()) > MAX_RESPONSE_BYTES:
        raise bad_request(code="dispute_size_limit")


def _coverage_out(coverage: DisputeCoverage) -> DisputeCoverageOut:
    return DisputeCoverageOut(
        observed=coverage.observed,
        expected=coverage.expected,
        ratio=coverage.ratio,
        note=coverage.note,
    )


def _summary_out(summary: DisputeSummary) -> DisputeSummaryOut:
    return DisputeSummaryOut(
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        schema_version=summary.schema_version,
        generated_tick=summary.generated_tick,
        candidate_count=summary.candidate_count,
        case_count=summary.case_count,
        claim_count=summary.claim_count,
        counterclaim_count=summary.counterclaim_count,
        testimony_count=summary.testimony_count,
        evidence_count=summary.evidence_count,
        resolution_count=summary.resolution_count,
        accepted_count=summary.accepted_count,
        rejected_count=summary.rejected_count,
        edge_count=summary.edge_count,
        window_count=summary.window_count,
        coverage=_coverage_out(summary.coverage),
        provenance_code=summary.provenance_code,
        snapshot_digest=summary.snapshot_digest,
    )


def _candidate_out(candidate: object) -> DisputeCandidateOut:
    item = cast(Any, candidate)
    return DisputeCandidateOut(
        candidate_id=item.candidate_id,
        kind=item.kind,
        subject_token=item.subject_token,
        party_count=item.party_count,
        owner_count=item.owner_count,
        case_count=item.case_count,
        claim_count=item.claim_count,
        counterclaim_count=item.counterclaim_count,
        testimony_count=item.testimony_count,
        evidence_count=item.evidence_count,
        resolution_count=item.resolution_count,
        disagreement_count=item.disagreement_count,
        status=item.status,
        first_tick=item.first_tick,
        last_tick=item.last_tick,
        coverage=_coverage_out(cast(Any, item).coverage),
    )


def _testimony_out(item: object) -> DisputeTestimonyOut:
    row = cast(Any, item)
    return DisputeTestimonyOut(
        testimony_id=row.testimony_id,
        case_ref=row.case_ref,
        claim_id=row.claim_id,
        speaker_id=row.speaker_id,
        channel=row.channel,
        root_token=row.root_token,
        independently_evidenced=row.independently_evidenced,
        tick=row.tick,
    )


def _evidence_out(item: object) -> DisputeEvidenceOut:
    row = cast(Any, item)
    return DisputeEvidenceOut(
        evidence_id=row.evidence_id,
        case_ref=row.case_ref,
        claim_id=row.claim_id,
        channel=row.channel,
        reference_kind=row.reference_kind,
        reference_token=row.reference_token,
        tick=row.tick,
        independently_evidenced=row.independently_evidenced,
    )


def _rule_reference_out(item: object) -> DisputeRuleReferenceOut:
    row = cast(Any, item)
    return DisputeRuleReferenceOut(
        rule_reference_id=row.rule_reference_id,
        case_ref=row.case_ref,
        claim_ref=row.claim_ref,
        system_token=row.system_token,
        rule_token=row.rule_token,
        version_number=row.version_number,
        applicability=row.applicability,
        interpretation=row.interpretation,
        status=row.status,
    )


def _authority_reference_out(item: object) -> DisputeAuthorityReferenceOut:
    row = cast(Any, item)
    return DisputeAuthorityReferenceOut(
        authority_reference_id=row.authority_reference_id,
        case_ref=row.case_ref,
        authority_kind=row.authority_kind,
        reference_token=row.reference_token,
        strength=row.strength,
        uncertainty=row.uncertainty,
        dissenting=row.dissenting,
    )


def _mediation_reference_out(item: object) -> DisputeMediationReferenceOut:
    row = cast(Any, item)
    return DisputeMediationReferenceOut(
        mediation_reference_id=row.mediation_reference_id,
        case_ref=row.case_ref,
        mediation_case_token=row.mediation_case_token,
        recommendation_token=row.recommendation_token,
        response_token=row.response_token,
        outcome_token=row.outcome_token,
        link_status=row.link_status,
    )


def _response_out(item: object) -> DisputeResolutionResponseOut:
    row = cast(Any, item)
    return DisputeResolutionResponseOut(
        response_id=row.response_id,
        resolution_ref=row.resolution_ref,
        party_id=row.party_id,
        kind=row.kind,
        tick=row.tick,
        terms_digest=row.terms_digest,
        active=row.active,
    )


def _candidate_detail_out(detail: DisputeCandidateDetail) -> DisputeCandidateDetailOut:
    return DisputeCandidateDetailOut(
        candidate=_candidate_out(detail.candidate),
        coverage=_coverage_out(detail.coverage),
        testimony=[_testimony_out(row) for row in detail.testimony],
        evidence=[_evidence_out(row) for row in detail.evidence],
        rule_references=[_rule_reference_out(row) for row in detail.rule_references],
        authority_references=[
            _authority_reference_out(row) for row in detail.authority_references
        ],
        mediation_references=[
            _mediation_reference_out(row) for row in detail.mediation_references
        ],
        responses=[_response_out(row) for row in detail.responses],
        truncated=detail.truncated,
    )


def _claim_out(claim: object) -> DisputeClaimOut:
    item = cast(Any, claim)
    return DisputeClaimOut(
        claim_id=item.claim_id,
        case_ref=item.case_ref,
        claimant_id=item.claimant_id,
        respondent_id=item.respondent_id,
        role=item.role,
        claim_kind=item.claim_kind,
        polarity=item.polarity,
        subject_token=item.subject_token,
        counters_claim_ref=item.counters_claim_ref,
        evidence_count=item.evidence_count,
        first_tick=item.first_tick,
        last_tick=item.last_tick,
        candidate_id=item.candidate_id,
    )


def _resolution_out(resolution: object) -> DisputeResolutionOut:
    item = cast(Any, resolution)
    return DisputeResolutionOut(
        resolution_id=item.resolution_id,
        resolution_ref=item.resolution_ref,
        case_ref=item.case_ref,
        proposer_id=item.proposer_id,
        source=item.source,
        terms_digest=item.terms_digest,
        status=item.status,
        first_tick=item.first_tick,
        last_tick=item.last_tick,
        expires_tick=item.expires_tick,
        accepted_party_count=item.accepted_party_count,
        rejected_party_count=item.rejected_party_count,
        candidate_id=item.candidate_id,
    )


def _edge_out(edge: object) -> DisputeLineageEdgeOut:
    item = cast(Any, edge)
    return DisputeLineageEdgeOut(
        edge_id=item.edge_id,
        source=item.source,
        target=item.target,
        kind=item.kind,
        tick=item.tick,
    )


def _page_cursor(
    *,
    purpose: str,
    run_id: str,
    summary: DisputeSummary,
    fingerprint: str,
    next_offset: int | None,
    codec: DisputeCursorCodec,
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


@router.get("/{run_id}/disputes", response_model=DisputeSummaryOut)
async def dispute_summary(
    request: Request,
    run_id: str,
    reader: DisputeReadPort | None = Depends(get_dispute_reader),
    settings: Settings = Depends(get_settings),
) -> DisputeSummaryOut:
    _authorize(request, settings)
    summary = _read(_reader(reader).summary, run_id)
    payload = _summary_out(summary)
    _charge(payload.model_dump())
    _LOGGER.info("dispute_read route=summary run_id=%s rows=1", run_id)
    return payload


@router.get(
    "/{run_id}/disputes/candidates",
    response_model=DisputeCandidatePageOut,
)
async def dispute_candidates(
    request: Request,
    run_id: str,
    status: _CandidateStatus | None = None,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_ROWS),
    cursor: str | None = None,
    reader: DisputeReadPort | None = Depends(get_dispute_reader),
    settings: Settings = Depends(get_settings),
) -> DisputeCandidatePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id)
    fingerprint = dispute_query_fingerprint(
        _PURPOSE_CANDIDATES,
        run_id=run_id,
        publication_id=summary.publication_id,
        filters=(() if status is None else (("status", status),)),
    )
    offset = 0
    if cursor is not None:
        offset = _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_CANDIDATES,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        ).offset
    selection = _read(
        port.candidates, run_id, status=status, offset=offset, limit=limit
    )
    payload = DisputeCandidatePageOut(
        items=[_candidate_out(item) for item in selection.items],
        next_cursor=_page_cursor(
            purpose=_PURPOSE_CANDIDATES,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
            codec=_codec(request),
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info(
        "dispute_read route=candidates run_id=%s rows=%s",
        run_id,
        len(payload.items),
    )
    return payload


@router.get(
    "/{run_id}/disputes/candidates/{candidate_id}",
    response_model=DisputeCandidateDetailOut,
)
async def dispute_candidate(
    request: Request,
    run_id: str,
    candidate_id: str,
    reader: DisputeReadPort | None = Depends(get_dispute_reader),
    settings: Settings = Depends(get_settings),
) -> DisputeCandidateDetailOut:
    _authorize(request, settings)
    detail = _read(_reader(reader).detail, run_id, candidate_id)
    payload = _candidate_detail_out(detail)
    _charge(payload.model_dump())
    _LOGGER.info("dispute_read route=candidate run_id=%s rows=1", run_id)
    return payload


@router.get(
    "/{run_id}/disputes/candidates/{candidate_id}/claims",
    response_model=DisputeClaimPageOut,
)
async def dispute_claims(
    request: Request,
    run_id: str,
    candidate_id: str,
    role: _ClaimRole | None = None,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_ROWS),
    cursor: str | None = None,
    reader: DisputeReadPort | None = Depends(get_dispute_reader),
    settings: Settings = Depends(get_settings),
) -> DisputeClaimPageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id)
    filters: tuple[tuple[str, str], ...] = (("candidate_id", candidate_id),)
    if role is not None:
        filters = (*filters, ("role", role))
    fingerprint = dispute_query_fingerprint(
        _PURPOSE_CLAIMS,
        run_id=run_id,
        publication_id=summary.publication_id,
        filters=filters,
    )
    offset = 0
    if cursor is not None:
        offset = _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_CLAIMS,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        ).offset
    selection = _read(
        port.claims,
        run_id,
        candidate_id=candidate_id,
        role=role,
        offset=offset,
        limit=limit,
    )
    payload = DisputeClaimPageOut(
        items=[_claim_out(item) for item in selection.items],
        next_cursor=_page_cursor(
            purpose=_PURPOSE_CLAIMS,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
            codec=_codec(request),
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info(
        "dispute_read route=claims run_id=%s rows=%s",
        run_id,
        len(payload.items),
    )
    return payload


@router.get(
    "/{run_id}/disputes/candidates/{candidate_id}/resolutions",
    response_model=DisputeResolutionPageOut,
)
async def dispute_resolutions(
    request: Request,
    run_id: str,
    candidate_id: str,
    status: _ResolutionStatus | None = None,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_ROWS),
    cursor: str | None = None,
    reader: DisputeReadPort | None = Depends(get_dispute_reader),
    settings: Settings = Depends(get_settings),
) -> DisputeResolutionPageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id)
    filters: tuple[tuple[str, str], ...] = (("candidate_id", candidate_id),)
    if status is not None:
        filters = (*filters, ("status", status))
    fingerprint = dispute_query_fingerprint(
        _PURPOSE_RESOLUTIONS,
        run_id=run_id,
        publication_id=summary.publication_id,
        filters=filters,
    )
    offset = 0
    if cursor is not None:
        offset = _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_RESOLUTIONS,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        ).offset
    selection = _read(
        port.resolutions,
        run_id,
        candidate_id=candidate_id,
        status=status,
        offset=offset,
        limit=limit,
    )
    payload = DisputeResolutionPageOut(
        items=[_resolution_out(item) for item in selection.items],
        next_cursor=_page_cursor(
            purpose=_PURPOSE_RESOLUTIONS,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
            codec=_codec(request),
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info(
        "dispute_read route=resolutions run_id=%s rows=%s",
        run_id,
        len(payload.items),
    )
    return payload


@router.get(
    "/{run_id}/disputes/lineage",
    response_model=DisputeLineagePageOut,
)
async def dispute_lineage(
    request: Request,
    run_id: str,
    kind: _LineageKind | None = None,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_ROWS),
    cursor: str | None = None,
    reader: DisputeReadPort | None = Depends(get_dispute_reader),
    settings: Settings = Depends(get_settings),
) -> DisputeLineagePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = _read(port.summary, run_id)
    fingerprint = dispute_query_fingerprint(
        _PURPOSE_LINEAGE,
        run_id=run_id,
        publication_id=summary.publication_id,
        filters=(() if kind is None else (("kind", kind),)),
    )
    offset = 0
    if cursor is not None:
        offset = _decode_cursor(
            _codec(request),
            cursor,
            purpose=_PURPOSE_LINEAGE,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        ).offset
    selection = _read(port.lineage, run_id, kind=kind, offset=offset, limit=limit)
    payload = DisputeLineagePageOut(
        items=[_edge_out(item) for item in selection.items],
        next_cursor=_page_cursor(
            purpose=_PURPOSE_LINEAGE,
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
            codec=_codec(request),
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info(
        "dispute_read route=lineage run_id=%s rows=%s",
        run_id,
        len(payload.items),
    )
    return payload
