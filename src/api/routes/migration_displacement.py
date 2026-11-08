"""Read-only migration-displacement HTTP routes."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_migration_displacement_reader, get_settings
from api.errors import (
    bad_request,
    gone,
    internal,
    not_found,
    service_unavailable,
    unprocessable,
)
from api.migration_displacement_cursor import (
    MigrationDisplacementCursorCodec,
    MigrationDisplacementCursorError,
)
from api.migration_displacement_schemas import (
    MAX_PAGE_LIMIT,
    MigrationCauseOut,
    MigrationCausePageOut,
    MigrationDisplacementSummaryOut,
    MigrationOutcomeOut,
    MigrationOutcomePageOut,
    MigrationRouteOut,
    MigrationRoutePageOut,
    MigrationWaveDetailOut,
    MigrationWaveOut,
    MigrationWavePageOut,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.migration_displacement_ports import (
    migration_displacement_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["migration-displacement"])
_LOGGER = get_logger("api.routes.migration_displacement")
MIGRATION_DISPLACEMENT_ROUTE_COUNT: Final[int] = 6

_DISPLACEMENT_CLASSES: Final[frozenset[str]] = frozenset(
    {"not_displacement_like", "displacement_like", "mixed", "unknown"}
)
_CAUSE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "resource_scarcity",
        "environmental_hazard",
        "conflict",
        "opportunity",
        "social_network",
        "institution",
        "unknown",
    }
)
_OUTCOME_CLASSES: Final[frozenset[str]] = frozenset(
    {"settled", "transient", "returned", "onward", "unknown"}
)


def _reader(reader: object | None) -> Any:
    if reader is None:
        _LOGGER.info("migration_displacement_api_disabled")
        raise service_unavailable(code="migration_displacement_disabled")
    return reader


def _codec(request: Request) -> MigrationDisplacementCursorCodec:
    codec = getattr(request.app.state, "migration_displacement_cursor_codec", None)
    if not isinstance(codec, MigrationDisplacementCursorCodec):
        _LOGGER.info("migration_displacement_api_disabled")
        raise service_unavailable(code="migration_displacement_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.read_snapshot(run_id)
    except ValueError as exc:
        if str(exc) == "migration_displacement_store_corrupt":
            _LOGGER.error("migration_displacement_store_corrupt")
            raise internal(code="migration_displacement_store_corrupt") from exc
        raise not_found(code="migration_displacement_not_found") from exc
    except Exception as exc:
        raise not_found(code="migration_displacement_not_found") from exc
    if snapshot is None:
        raise not_found(code="migration_displacement_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    *,
    limit: int,
) -> str:
    return migration_displacement_query_fingerprint(
        run_id=snapshot.summary.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=filters,
        after_key=None,
        limit=limit,
    )


def _after_key(
    codec: MigrationDisplacementCursorCodec,
    token: str | None,
    *,
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    limit: int,
) -> str | None:
    if token is None:
        return None
    try:
        payload = codec.decode(token, purpose=purpose)
    except MigrationDisplacementCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            _LOGGER.warning("migration_displacement_cursor_expired")
            raise gone(code="migration_displacement_cursor_expired") from exc
        _LOGGER.warning("migration_displacement_cursor_invalid")
        raise bad_request(code="migration_displacement_cursor_invalid") from exc
    expected = _fingerprint(snapshot, purpose, filters, limit=limit)
    if (
        payload.get("run_id") != snapshot.summary.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint") != expected
    ):
        _LOGGER.warning("migration_displacement_cursor_invalid")
        raise bad_request(code="migration_displacement_cursor_invalid")
    after = payload.get("after_key")
    return after if type(after) is str else None


def _next_cursor(
    codec: MigrationDisplacementCursorCodec,
    *,
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    limit: int,
    next_key: str | None,
) -> str | None:
    if next_key is None:
        return None
    return codec.encode(
        purpose=purpose,
        run_id=snapshot.summary.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=_fingerprint(snapshot, purpose, filters, limit=limit),
        after_key=next_key,
    )


def _wave_key(row: Any) -> str:
    return f"{row.start_tick:020d}|{row.wave_token}"


def _route_key(row: Any) -> str:
    return f"{row.owner_token}|{row.first_tick:020d}|{row.route_token}"


def _cause_key(row: Any) -> str:
    return f"{row.owner_token}|{row.tick:020d}|{row.cause_token}"


def _outcome_key(row: Any) -> str:
    return f"{row.participant_token}|{row.destination_token}|{row.outcome_token}"


def _wave(row: Any) -> MigrationWaveOut:
    return MigrationWaveOut(
        wave_token=row.wave_token,
        origin_token=row.origin_token,
        destination_token=row.destination_token,
        participant_tokens=tuple(row.participant_tokens),
        route_tokens=tuple(row.route_tokens),
        start_tick=row.start_tick,
        end_tick=row.end_tick,
        cause_support_counts=tuple(
            (str(kind), int(count)) for kind, count in row.cause_support_counts
        ),
        displacement_classification=row.displacement_classification,
        displacement_bases=tuple(row.displacement_bases),
        independent_cause_count=row.independent_cause_count,
        cluster_tokens=tuple(row.cluster_tokens),
        coverage=row.coverage,
    )


def _wave_detail(snapshot: Any, row: Any) -> MigrationWaveDetailOut:
    base = _wave(row)
    lineage = tuple(
        sorted(
            {
                link.previous_token
                for link in snapshot.lineage
                if link.candidate_token == row.wave_token
                and link.previous_token
                and link.previous_token != "none"
            }
        )
    )
    alignment = tuple(
        sorted(
            {
                f"{item.owner_token}|{item.alignment}"
                for item in snapshot.alignment
                if item.candidate_token == row.wave_token
            }
        )
    )
    return MigrationWaveDetailOut(
        **base.model_dump(),
        lineage_tokens=lineage,
        alignment_tokens=alignment,
    )


def _route(row: Any) -> MigrationRouteOut:
    return MigrationRouteOut(
        route_token=row.route_token,
        owner_token=row.owner_token,
        origin_token=row.origin_token,
        destination_token=row.destination_token,
        route_tokens=tuple(row.route_tokens),
        observed_duration_ticks=row.observed_duration_ticks,
        fatigue_cost=row.fatigue_cost,
        basis=row.basis,
        status=row.status,
        first_tick=row.first_tick,
        last_tick=row.last_tick,
    )


def _cause(row: Any) -> MigrationCauseOut:
    return MigrationCauseOut(
        cause_token=row.cause_token,
        owner_token=row.owner_token,
        cause_kind=row.cause_kind,
        source_kind=row.source_kind,
        anchor_token=row.anchor_token,
        confidence=row.confidence,
        tick=row.tick,
        status=row.status,
    )


def _outcome(row: Any) -> MigrationOutcomeOut:
    return MigrationOutcomeOut(
        outcome_token=row.outcome_token,
        participant_token=row.participant_token,
        destination_token=row.destination_token,
        residence_ticks=row.residence_ticks,
        access_evidence_count=row.access_evidence_count,
        participation_evidence_count=row.participation_evidence_count,
        relationship_evidence_count=row.relationship_evidence_count,
        conflict_evidence_count=row.conflict_evidence_count,
        classification=row.classification,
        coverage=row.coverage,
        censored=row.censored,
    )


def _require_closed(name: str, value: str | None, allowed: frozenset[str]) -> str | None:
    if value is None:
        return None
    if value not in allowed:
        raise unprocessable(code=f"migration_displacement_filter_{name}")
    return value


@router.get("/{run_id}/migration", response_model=MigrationDisplacementSummaryOut)
def get_migration_summary(
    run_id: str,
    request: Request,
    reader: object | None = Depends(get_migration_displacement_reader),
    settings: Settings = Depends(get_settings),
) -> MigrationDisplacementSummaryOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    summary = snapshot.summary
    return MigrationDisplacementSummaryOut(
        run_id=summary.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        candidate_count=summary.candidate_count,
        wave_count=summary.wave_count,
        cluster_count=summary.cluster_count,
        outcome_count=summary.outcome_count,
        movement_count=summary.movement_count,
        cause_count=summary.cause_count,
        displacement_like_count=summary.displacement_like_count,
        mixed_count=summary.mixed_count,
        not_displacement_like_count=summary.not_displacement_like_count,
        unknown_count=summary.unknown_count,
        coverage=summary.coverage,
    )


@router.get("/{run_id}/migration/waves", response_model=MigrationWavePageOut)
def get_migration_waves(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    classification: str | None = Query(default=None),
    origin_token: str | None = Query(default=None),
    destination_token: str | None = Query(default=None),
    cluster_token: str | None = Query(default=None),
    reader: object | None = Depends(get_migration_displacement_reader),
    settings: Settings = Depends(get_settings),
) -> MigrationWavePageOut:
    _authorize(request, settings)
    classification = _require_closed(
        "classification", classification, _DISPLACEMENT_CLASSES
    )
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    if classification is not None:
        filters["classification"] = classification
    if origin_token is not None:
        filters["origin_token"] = origin_token
    if destination_token is not None:
        filters["destination_token"] = destination_token
    if cluster_token is not None:
        filters["cluster_token"] = cluster_token
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="waves",
        filters=filters,
        limit=limit,
    )
    ordered = sorted(snapshot.waves, key=_wave_key)
    if classification is not None:
        ordered = [
            row
            for row in ordered
            if row.displacement_classification == classification
        ]
    if origin_token is not None:
        ordered = [row for row in ordered if row.origin_token == origin_token]
    if destination_token is not None:
        ordered = [
            row for row in ordered if row.destination_token == destination_token
        ]
    if cluster_token is not None:
        ordered = [
            row for row in ordered if cluster_token in row.cluster_tokens
        ]
    if after is not None:
        ordered = [row for row in ordered if _wave_key(row) > after]
    page = ordered[: max(1, min(limit, MAX_PAGE_LIMIT))]
    next_key = _wave_key(page[-1]) if len(ordered) > len(page) else None
    return MigrationWavePageOut(
        items=tuple(_wave(row) for row in page),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="waves",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get(
    "/{run_id}/migration/waves/{wave_id}",
    response_model=MigrationWaveDetailOut,
)
def get_migration_wave(
    run_id: str,
    wave_id: str,
    request: Request,
    reader: object | None = Depends(get_migration_displacement_reader),
    settings: Settings = Depends(get_settings),
) -> MigrationWaveDetailOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    for row in snapshot.waves:
        if row.wave_token == wave_id:
            return _wave_detail(snapshot, row)
    raise not_found(code="migration_displacement_not_found")


@router.get("/{run_id}/migration/routes", response_model=MigrationRoutePageOut)
def get_migration_routes(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    origin_token: str | None = Query(default=None),
    destination_token: str | None = Query(default=None),
    reader: object | None = Depends(get_migration_displacement_reader),
    settings: Settings = Depends(get_settings),
) -> MigrationRoutePageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    if origin_token is not None:
        filters["origin_token"] = origin_token
    if destination_token is not None:
        filters["destination_token"] = destination_token
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="routes",
        filters=filters,
        limit=limit,
    )
    ordered = sorted(snapshot.routes, key=_route_key)
    if origin_token is not None:
        ordered = [row for row in ordered if row.origin_token == origin_token]
    if destination_token is not None:
        ordered = [
            row for row in ordered if row.destination_token == destination_token
        ]
    if after is not None:
        ordered = [row for row in ordered if _route_key(row) > after]
    page = ordered[: max(1, min(limit, MAX_PAGE_LIMIT))]
    next_key = _route_key(page[-1]) if len(ordered) > len(page) else None
    return MigrationRoutePageOut(
        items=tuple(_route(row) for row in page),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="routes",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get("/{run_id}/migration/causes", response_model=MigrationCausePageOut)
def get_migration_causes(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    cause_kind: str | None = Query(default=None),
    reader: object | None = Depends(get_migration_displacement_reader),
    settings: Settings = Depends(get_settings),
) -> MigrationCausePageOut:
    _authorize(request, settings)
    cause_kind = _require_closed("cause_kind", cause_kind, _CAUSE_KINDS)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    if cause_kind is not None:
        filters["cause_kind"] = cause_kind
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="causes",
        filters=filters,
        limit=limit,
    )
    ordered = sorted(snapshot.causes, key=_cause_key)
    if cause_kind is not None:
        ordered = [row for row in ordered if row.cause_kind == cause_kind]
    if after is not None:
        ordered = [row for row in ordered if _cause_key(row) > after]
    page = ordered[: max(1, min(limit, MAX_PAGE_LIMIT))]
    next_key = _cause_key(page[-1]) if len(ordered) > len(page) else None
    return MigrationCausePageOut(
        items=tuple(_cause(row) for row in page),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="causes",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get("/{run_id}/migration/outcomes", response_model=MigrationOutcomePageOut)
def get_migration_outcomes(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    outcome: str | None = Query(default=None),
    destination_token: str | None = Query(default=None),
    reader: object | None = Depends(get_migration_displacement_reader),
    settings: Settings = Depends(get_settings),
) -> MigrationOutcomePageOut:
    _authorize(request, settings)
    outcome = _require_closed("outcome", outcome, _OUTCOME_CLASSES)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    if outcome is not None:
        filters["outcome"] = outcome
    if destination_token is not None:
        filters["destination_token"] = destination_token
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="outcomes",
        filters=filters,
        limit=limit,
    )
    ordered = sorted(snapshot.outcomes, key=_outcome_key)
    if outcome is not None:
        ordered = [row for row in ordered if row.classification == outcome]
    if destination_token is not None:
        ordered = [
            row for row in ordered if row.destination_token == destination_token
        ]
    if after is not None:
        ordered = [row for row in ordered if _outcome_key(row) > after]
    page = ordered[: max(1, min(limit, MAX_PAGE_LIMIT))]
    next_key = _outcome_key(page[-1]) if len(ordered) > len(page) else None
    return MigrationOutcomePageOut(
        items=tuple(_outcome(row) for row in page),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="outcomes",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )
