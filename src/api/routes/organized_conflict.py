# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Read-only organized-conflict HTTP routes."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_organized_conflict_reader, get_settings
from api.errors import bad_request, gone, not_found, service_unavailable
from api.organized_conflict_cursor import (
    OrganizedConflictCursorCodec,
    OrganizedConflictCursorError,
)
from api.organized_conflict_schemas import (
    MAX_PAGE_LIMIT,
    OrganizedConflictEpisodeDetailOut,
    OrganizedConflictEpisodePageOut,
    OrganizedConflictEpisodeResponse,
    OrganizedConflictInterpretationPageOut,
    OrganizedConflictInterpretationResponse,
    OrganizedConflictLineageResponse,
    OrganizedConflictParticipantResponse,
    OrganizedConflictPlanDetailOut,
    OrganizedConflictPlanPageOut,
    OrganizedConflictPlanResponse,
    OrganizedConflictSummaryResponse,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.organized_conflict_ports import (
    organized_conflict_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["organized-conflict"])
_LOGGER = get_logger("api.routes.organized_conflict")
ORGANIZED_CONFLICT_ROUTE_COUNT: Final[int] = 6


def _reader(reader: object | None) -> Any:
    if reader is None:
        raise service_unavailable(code="organized_conflict_disabled")
    return reader


def _codec(request: Request) -> OrganizedConflictCursorCodec:
    codec = getattr(request.app.state, "organized_conflict_cursor_codec", None)
    if not isinstance(codec, OrganizedConflictCursorCodec):
        raise service_unavailable(code="organized_conflict_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.snapshot(run_id)
    except Exception as exc:
        raise not_found(code="organized_conflict_not_found") from exc
    if snapshot is None:
        raise not_found(code="organized_conflict_not_found")
    return snapshot


def _fingerprint(snapshot: Any, purpose: str) -> str:
    return organized_conflict_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters={},
    )


def _after_key(
    codec: OrganizedConflictCursorCodec,
    token: str | None,
    *,
    snapshot: Any,
    purpose: str,
) -> str | None:
    if token is None:
        return None
    try:
        payload = codec.decode(token, purpose=purpose)
    except OrganizedConflictCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="organized_conflict_cursor_expired") from exc
        raise bad_request(code="organized_conflict_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint") != _fingerprint(snapshot, purpose)
    ):
        raise bad_request(code="organized_conflict_cursor_invalid")
    after = payload.get("after_key")
    return after if type(after) is str else None


def _next_cursor(
    codec: OrganizedConflictCursorCodec,
    *,
    snapshot: Any,
    purpose: str,
    next_key: str | None,
) -> str | None:
    if next_key is None:
        return None
    return codec.encode(
        purpose=purpose,
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=_fingerprint(snapshot, purpose),
        after_key=next_key,
    )


def _episode(row: Any) -> OrganizedConflictEpisodeResponse:
    return OrganizedConflictEpisodeResponse(
        episode_id=row.episode_id,
        classification=row.classification,
        start_tick=row.start_tick,
        end_tick=row.end_tick,
        participant_tokens=tuple(row.participant_tokens),
        opponent_tokens=tuple(row.opponent_tokens),
        side_count=row.side_count,
        hostile_event_count=row.hostile_event_count,
        active_window_count=row.active_window_count,
        sustained=row.sustained,
        org_ids=tuple(row.org_ids),
        msoc_ids=tuple(row.macro_society_ids),
    )


def _plan(row: Any) -> OrganizedConflictPlanResponse:
    return OrganizedConflictPlanResponse(
        plan_id=row.plan_id,
        owner_token=row.owner_token,
        operation=row.operation,
        target_kind=row.target_kind,
        status=row.status,
        participant_count=row.participant_count,
        tick=row.tick,
    )


def _interpretation(row: Any) -> OrganizedConflictInterpretationResponse:
    return OrganizedConflictInterpretationResponse(
        interpretation_id=row.interpretation_id,
        owner_token=row.owner_token,
        episode_id=row.episode_id,
        kind=row.kind,
        alignment=row.alignment,
        tick=row.tick,
    )


def _page(
    rows: tuple[Any, ...], *, key: str, after: str | None, limit: int
) -> tuple[tuple[Any, ...], str | None]:
    ordered = sorted(rows, key=lambda row: getattr(row, key))
    if after is not None:
        ordered = [row for row in ordered if getattr(row, key) > after]
    clamped = max(1, min(limit, MAX_PAGE_LIMIT))
    page = tuple(ordered[:clamped])
    next_key = getattr(page[-1], key) if len(ordered) > len(page) else None
    return page, next_key


@router.get(
    "/{run_id}/organized-conflict", response_model=OrganizedConflictSummaryResponse
)
def get_organized_conflict_summary(
    run_id: str,
    request: Request,
    reader: object | None = Depends(get_organized_conflict_reader),
    settings: Settings = Depends(get_settings),
) -> OrganizedConflictSummaryResponse:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    summary = snapshot.summary
    return OrganizedConflictSummaryResponse(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        episode_count=summary.episode_count,
        individual_episode_count=summary.individual_episode_count,
        coordinated_episode_count=summary.coordinated_episode_count,
        persistent_inter_group_episode_count=(
            summary.persistent_inter_group_episode_count
        ),
        participant_count=summary.participant_count,
        plan_count=summary.plan_count,
        interpretation_count=summary.interpretation_count,
        outcome_count=summary.outcome_count,
        contradiction_count=summary.contradiction_count,
        termination_count=summary.termination_count,
        sustained_episode_count=summary.sustained_episode_count,
        coverage=summary.coverage,
    )


@router.get(
    "/{run_id}/organized-conflict/episodes",
    response_model=OrganizedConflictEpisodePageOut,
)
def get_organized_conflict_episodes(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_organized_conflict_reader),
    settings: Settings = Depends(get_settings),
) -> OrganizedConflictEpisodePageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    after = _after_key(codec, cursor, snapshot=snapshot, purpose="episodes")
    rows, next_key = _page(
        snapshot.episodes, key="episode_id", after=after, limit=limit
    )
    return OrganizedConflictEpisodePageOut(
        items=tuple(_episode(row) for row in rows),
        next_cursor=_next_cursor(
            codec, snapshot=snapshot, purpose="episodes", next_key=next_key
        ),
    )


@router.get(
    "/{run_id}/organized-conflict/episodes/{episode_id}",
    response_model=OrganizedConflictEpisodeDetailOut,
)
def get_organized_conflict_episode(
    run_id: str,
    episode_id: str,
    request: Request,
    reader: object | None = Depends(get_organized_conflict_reader),
    settings: Settings = Depends(get_settings),
) -> OrganizedConflictEpisodeDetailOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    matching = [row for row in snapshot.episodes if row.episode_id == episode_id]
    if not matching:
        raise not_found(code="organized_conflict_unknown_episode")
    participants = tuple(
        OrganizedConflictParticipantResponse(
            episode_id=row.episode_id,
            participant_token=row.participant_token,
            role=row.role,
            tick=row.tick,
        )
        for row in snapshot.participants
        if row.episode_id == episode_id
    )
    lineage = tuple(
        OrganizedConflictLineageResponse(
            edge_id=row.edge_id,
            from_id=row.from_id,
            to_id=row.to_id,
            kind=row.kind,
            tick=row.tick,
        )
        for row in snapshot.lineage
        if row.from_id == episode_id or row.to_id == episode_id
    )
    return OrganizedConflictEpisodeDetailOut(
        episode=_episode(matching[0]),
        participants=participants[:MAX_PAGE_LIMIT],
        lineage=lineage[:MAX_PAGE_LIMIT],
        truncated=len(participants) > MAX_PAGE_LIMIT,
    )


@router.get(
    "/{run_id}/organized-conflict/plans",
    response_model=OrganizedConflictPlanPageOut,
)
def get_organized_conflict_plans(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_organized_conflict_reader),
    settings: Settings = Depends(get_settings),
) -> OrganizedConflictPlanPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    after = _after_key(codec, cursor, snapshot=snapshot, purpose="plans")
    rows, next_key = _page(snapshot.plans, key="plan_id", after=after, limit=limit)
    return OrganizedConflictPlanPageOut(
        items=tuple(_plan(row) for row in rows),
        next_cursor=_next_cursor(
            codec, snapshot=snapshot, purpose="plans", next_key=next_key
        ),
    )


@router.get(
    "/{run_id}/organized-conflict/plans/{plan_id}",
    response_model=OrganizedConflictPlanDetailOut,
)
def get_organized_conflict_plan(
    run_id: str,
    plan_id: str,
    request: Request,
    reader: object | None = Depends(get_organized_conflict_reader),
    settings: Settings = Depends(get_settings),
) -> OrganizedConflictPlanDetailOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    matching = [row for row in snapshot.plans if row.plan_id == plan_id]
    if not matching:
        raise not_found(code="organized_conflict_unknown_plan")
    outcomes = tuple(
        {
            "outcome_id": row.outcome_id,
            "kind": row.kind,
            "target_token": row.target_token,
            "tick": row.tick,
        }
        for row in snapshot.outcomes
        if row.plan_id == plan_id
    )
    terminations = tuple(
        {
            "termination_id": row.termination_id,
            "kind": row.kind,
            "tick": row.tick,
        }
        for row in snapshot.terminations
        if row.plan_id == plan_id
    )
    combined = len(outcomes) + len(terminations)
    return OrganizedConflictPlanDetailOut(
        plan=_plan(matching[0]),
        outcomes=outcomes[:MAX_PAGE_LIMIT],
        terminations=terminations[:MAX_PAGE_LIMIT],
        truncated=combined > MAX_PAGE_LIMIT,
    )


@router.get(
    "/{run_id}/organized-conflict/interpretations",
    response_model=OrganizedConflictInterpretationPageOut,
)
def get_organized_conflict_interpretations(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_organized_conflict_reader),
    settings: Settings = Depends(get_settings),
) -> OrganizedConflictInterpretationPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    after = _after_key(codec, cursor, snapshot=snapshot, purpose="interpretations")
    rows, next_key = _page(
        snapshot.interpretations, key="interpretation_id", after=after, limit=limit
    )
    return OrganizedConflictInterpretationPageOut(
        items=tuple(_interpretation(row) for row in rows),
        next_cursor=_next_cursor(
            codec, snapshot=snapshot, purpose="interpretations", next_key=next_key
        ),
    )
