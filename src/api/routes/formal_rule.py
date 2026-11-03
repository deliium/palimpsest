"""Read-only formal-rule HTTP routes."""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Query, Request, Response

from api.dependencies import get_formal_rule_reader, get_settings
from api.errors import bad_request, gone, not_found, service_unavailable
from api.formal_rule_cursor import FormalRuleCursorCodec, FormalRuleCursorError
from api.formal_rule_schemas import (
    FormalRuleCandidateDetailOut,
    FormalRuleCandidateOut,
    FormalRuleCandidatePageOut,
    FormalRuleCoverageOut,
    FormalRuleLineageEdgeOut,
    FormalRuleLineagePageOut,
    FormalRuleOut,
    FormalRulePageOut,
    FormalRuleSummaryOut,
    FormalRuleVersionOut,
    FormalRuleVersionPageOut,
    FormalRuleWrittenRepresentationOut,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.formal_rule_models import (
    MAX_PAGE_ROWS,
    MAX_RESPONSE_BYTES,
    FormalRuleArtifactError,
    FormalRuleCoverage,
)
from simulation.formal_rule_ports import (
    FormalRuleCursor,
    FormalRuleReadPort,
    FormalRuleSummary,
    formal_rule_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["formal-rules"])
_LOGGER = get_logger("api.routes.formal_rule")

_PURPOSE_SUMMARY = "formal_rule_summary"
_PURPOSE_CANDIDATES = "formal_rule_candidates"
_PURPOSE_CANDIDATE = "formal_rule_candidate"
_PURPOSE_RULES = "formal_rule_rules"
_PURPOSE_VERSIONS = "formal_rule_versions"
_PURPOSE_LINEAGE = "formal_rule_lineage"
_PURPOSE_BY_API = {
    _PURPOSE_SUMMARY: "summary",
    _PURPOSE_CANDIDATES: "candidates",
    _PURPOSE_CANDIDATE: "candidate",
    _PURPOSE_RULES: "rules",
    _PURPOSE_VERSIONS: "versions",
    _PURPOSE_LINEAGE: "lineage",
}
_STATUS_VALUES = (
    "recognized",
    "partial",
    "contested",
    "fragmented",
    "temporary",
    "dissolved",
)
_STAGE_VALUES = (
    "habit",
    "expectation",
    "norm",
    "documented",
    "recognized_enforcement",
)
_KIND_VALUES = ("continued", "transformed", "split", "merge", "dissolved", "emerged")


def _reader(reader: FormalRuleReadPort | None) -> FormalRuleReadPort:
    if reader is None:
        raise service_unavailable(code="formal_rule_disabled")
    return reader


def _codec(request: Request) -> FormalRuleCursorCodec:
    codec = getattr(request.app.state, "formal_rule_cursor_codec", None)
    if not isinstance(codec, FormalRuleCursorCodec):
        raise service_unavailable(code="formal_rule_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _decode_cursor(
    codec: FormalRuleCursorCodec,
    token: str,
    *,
    api_purpose: str,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    fingerprint: str,
) -> FormalRuleCursor:
    purpose = _PURPOSE_BY_API[api_purpose]
    try:
        cursor, _ = codec.decode(token, purpose=purpose)
    except FormalRuleCursorError as exc:
        if exc.reason_code == "formal_rule_cursor_expired":
            raise gone(code=exc.reason_code) from exc
        raise bad_request(code=exc.reason_code) from exc
    if (
        cursor.run_id != run_id
        or cursor.publication_id != publication_id
        or cursor.query_fingerprint != fingerprint
        or cursor.snapshot_digest != snapshot_digest
    ):
        raise bad_request(code="formal_rule_cursor_invalid")
    return cursor


def _charge(payload: object) -> None:
    if len(json.dumps(payload, default=str).encode()) > MAX_RESPONSE_BYTES:
        raise bad_request(code="formal_rule_size_limit")


def _coverage_out(coverage: FormalRuleCoverage) -> FormalRuleCoverageOut:
    return FormalRuleCoverageOut(
        observed=coverage.observed,
        expected=coverage.expected,
        partial=coverage.partial,
    )


def _summary_out(summary: FormalRuleSummary) -> FormalRuleSummaryOut:
    return FormalRuleSummaryOut(
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        schema_version=summary.schema_version,
        generated_tick=summary.generated_tick,
        candidate_count=summary.candidate_count,
        rule_count=summary.rule_count,
        version_count=summary.version_count,
        window_count=summary.window_count,
        coverage=_coverage_out(summary.coverage),
        provenance_code=summary.provenance_code,
        snapshot_digest=summary.snapshot_digest,
    )


def _candidate_out(candidate: object) -> FormalRuleCandidateOut:
    item = cast(Any, candidate)
    return FormalRuleCandidateOut(
        candidate_id=item.candidate_id,
        status=item.status,
        scope_kind=item.scope_kind,
        stage=item.stage,
        action_token=item.action_token,
        constraint_kinds=item.constraint_kinds,
        authority_kinds=item.authority_kinds,
        system_count=item.system_count,
        rule_count=item.rule_count,
        version_count=item.version_count,
        competing_candidate_ids=item.competing_candidate_ids,
        first_tick=item.first_tick,
        last_tick=item.last_tick,
    )


def _written_out(record: object) -> FormalRuleWrittenRepresentationOut:
    item = cast(Any, record)
    return FormalRuleWrittenRepresentationOut(
        status=item.status,
        artifact_present=item.artifact_present,
        artifact_revision=item.artifact_revision,
        repository_present=item.repository_present,
    )


def _rule_out(rule: object) -> FormalRuleOut:
    item = cast(Any, rule)
    return FormalRuleOut(
        rule_id=item.rule_id,
        candidate_id=item.candidate_id,
        stage=item.stage,
        constraint_kind=item.constraint_kind,
        scope_kind=item.scope_kind,
        action_token=item.action_token,
        authority_kind=item.authority_kind,
        recognition=item.recognition,
        written_representation=_written_out(item.written_representation),
        sanction_kinds=item.sanction_kinds,
        exception_count=item.exception_count,
        version_count=item.version_count,
        latest_version=item.latest_version,
        proponent_count=item.proponent_count,
        response_counts=item.response_counts,
    )


def _version_out(version: object) -> FormalRuleVersionOut:
    item = cast(Any, version)
    return FormalRuleVersionOut(
        version_id=item.version_id,
        rule_id=item.rule_id,
        version_number=item.version_number,
        stage=item.stage,
        constraint_kind=item.constraint_kind,
        scope_kind=item.scope_kind,
        scope_digest=item.scope_digest,
        action_token=item.action_token,
        authority_kind=item.authority_kind,
        recognition=item.recognition,
        written_representation=_written_out(item.written_representation),
        sanction_kinds=item.sanction_kinds,
        exception_count=item.exception_count,
        tick=item.tick,
        revision_kind=item.revision_kind,
        supersedes_version_id=item.supersedes_version_id,
    )


def _edge_out(edge: object) -> FormalRuleLineageEdgeOut:
    item = cast(Any, edge)
    return FormalRuleLineageEdgeOut(
        edge_id=item.edge_id,
        source_candidate_id=item.source_candidate_id,
        target_candidate_id=item.target_candidate_id,
        kind=item.kind,
        tick=item.tick,
        jaccard=item.jaccard,
        containment=item.containment,
    )


@router.get("/{run_id}/formal-rules", response_model=FormalRuleSummaryOut)
async def formal_rule_summary(
    request: Request,
    response: Response,
    run_id: str,
    reader: FormalRuleReadPort | None = Depends(get_formal_rule_reader),
    settings: Settings = Depends(get_settings),
) -> FormalRuleSummaryOut:
    _authorize(request, settings)
    _ = response
    summary = _reader(reader).summary(run_id)
    payload = _summary_out(summary)
    _charge(payload.model_dump())
    _LOGGER.info("formal_rule_read route=summary run_id=%s rows=1", run_id)
    return payload


@router.get(
    "/{run_id}/formal-rules/candidates",
    response_model=FormalRuleCandidatePageOut,
)
async def formal_rule_candidates(
    request: Request,
    run_id: str,
    status: Literal[
        "recognized",
        "partial",
        "contested",
        "fragmented",
        "temporary",
        "dissolved",
    ]
    | None = None,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_ROWS),
    cursor: str | None = None,
    reader: FormalRuleReadPort | None = Depends(get_formal_rule_reader),
    settings: Settings = Depends(get_settings),
) -> FormalRuleCandidatePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = port.summary(run_id)
    fingerprint = formal_rule_query_fingerprint(
        "candidates",
        run_id=run_id,
        publication_id=summary.publication_id,
        filters=(() if status is None else (("status", status),)),
    )
    offset = 0
    if cursor is not None:
        offset = _decode_cursor(
            _codec(request),
            cursor,
            api_purpose=_PURPOSE_CANDIDATES,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        ).offset
    selection = port.candidates(
        run_id, status=status, offset=offset, limit=limit
    )
    next_cursor = None
    if selection.next_offset is not None:
        next_cursor = _codec(request).encode(
            purpose="candidates",
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            offset=selection.next_offset,
            query_fingerprint=fingerprint,
        )
    payload = FormalRuleCandidatePageOut(
        items=[_candidate_out(item) for item in selection.rows],
        next_cursor=next_cursor,
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    _LOGGER.info(
        "formal_rule_read route=candidates run_id=%s rows=%s",
        run_id,
        len(payload.items),
    )
    return payload


@router.get(
    "/{run_id}/formal-rules/candidates/{candidate_id}",
    response_model=FormalRuleCandidateDetailOut,
)
async def formal_rule_candidate(
    request: Request,
    run_id: str,
    candidate_id: str,
    reader: FormalRuleReadPort | None = Depends(get_formal_rule_reader),
    settings: Settings = Depends(get_settings),
) -> FormalRuleCandidateDetailOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = port.summary(run_id)
    try:
        candidate = port.candidate(run_id, candidate_id)
    except FormalRuleArtifactError as exc:
        raise not_found(code=exc.code) from exc
    payload = FormalRuleCandidateDetailOut(
        candidate=_candidate_out(cast(Any, candidate)),
        coverage=_coverage_out(cast(Any, candidate).coverage),
    )
    _charge(payload.model_dump())
    _ = summary
    return payload


def _page_cursor(
    *,
    purpose: str,
    run_id: str,
    summary: FormalRuleSummary,
    fingerprint: str,
    next_offset: int | None,
    codec: FormalRuleCursorCodec,
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


@router.get(
    "/{run_id}/formal-rules/candidates/{candidate_id}/rules",
    response_model=FormalRulePageOut,
)
async def formal_rule_rules(
    request: Request,
    run_id: str,
    candidate_id: str,
    stage: Literal[
        "habit",
        "expectation",
        "norm",
        "documented",
        "recognized_enforcement",
    ]
    | None = None,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_ROWS),
    cursor: str | None = None,
    reader: FormalRuleReadPort | None = Depends(get_formal_rule_reader),
    settings: Settings = Depends(get_settings),
) -> FormalRulePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = port.summary(run_id)
    fingerprint = formal_rule_query_fingerprint(
        "rules",
        run_id=run_id,
        publication_id=summary.publication_id,
        candidate_id=candidate_id,
        filters=(() if stage is None else (("stage", stage),)),
    )
    offset = 0
    if cursor is not None:
        offset = _decode_cursor(
            _codec(request),
            cursor,
            api_purpose=_PURPOSE_RULES,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        ).offset
    selection = port.rules(
        run_id,
        candidate_id=candidate_id,
        stage=stage,
        offset=offset,
        limit=limit,
    )
    payload = FormalRulePageOut(
        items=[_rule_out(item) for item in selection.rows],
        next_cursor=_page_cursor(
            purpose="rules",
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
            codec=_codec(request),
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    return payload


@router.get(
    "/{run_id}/formal-rules/candidates/{candidate_id}/versions",
    response_model=FormalRuleVersionPageOut,
)
async def formal_rule_versions(
    request: Request,
    run_id: str,
    candidate_id: str,
    rule_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_ROWS),
    cursor: str | None = None,
    reader: FormalRuleReadPort | None = Depends(get_formal_rule_reader),
    settings: Settings = Depends(get_settings),
) -> FormalRuleVersionPageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = port.summary(run_id)
    fingerprint = formal_rule_query_fingerprint(
        "versions",
        run_id=run_id,
        publication_id=summary.publication_id,
        candidate_id=candidate_id,
        filters=(() if rule_id is None else (("rule_id", rule_id),)),
    )
    offset = 0
    if cursor is not None:
        offset = _decode_cursor(
            _codec(request),
            cursor,
            api_purpose=_PURPOSE_VERSIONS,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        ).offset
    selection = port.versions(
        run_id,
        candidate_id=candidate_id,
        rule_id=rule_id,
        offset=offset,
        limit=limit,
    )
    payload = FormalRuleVersionPageOut(
        items=[_version_out(item) for item in selection.rows],
        next_cursor=_page_cursor(
            purpose="versions",
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
            codec=_codec(request),
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    return payload


@router.get(
    "/{run_id}/formal-rules/lineage",
    response_model=FormalRuleLineagePageOut,
)
async def formal_rule_lineage(
    request: Request,
    run_id: str,
    kind: Literal[
        "continued", "transformed", "split", "merge", "dissolved", "emerged"
    ]
    | None = None,
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_ROWS),
    cursor: str | None = None,
    reader: FormalRuleReadPort | None = Depends(get_formal_rule_reader),
    settings: Settings = Depends(get_settings),
) -> FormalRuleLineagePageOut:
    _authorize(request, settings)
    port = _reader(reader)
    summary = port.summary(run_id)
    fingerprint = formal_rule_query_fingerprint(
        "lineage",
        run_id=run_id,
        publication_id=summary.publication_id,
        filters=(() if kind is None else (("kind", kind),)),
    )
    offset = 0
    if cursor is not None:
        offset = _decode_cursor(
            _codec(request),
            cursor,
            api_purpose=_PURPOSE_LINEAGE,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            fingerprint=fingerprint,
        ).offset
    selection = port.lineage(run_id, kind=kind, offset=offset, limit=limit)
    payload = FormalRuleLineagePageOut(
        items=[_edge_out(item) for item in selection.rows],
        next_cursor=_page_cursor(
            purpose="lineage",
            run_id=run_id,
            summary=summary,
            fingerprint=fingerprint,
            next_offset=selection.next_offset,
            codec=_codec(request),
        ),
        truncated=selection.truncated,
    )
    _charge(payload.model_dump())
    return payload
