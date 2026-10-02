"""Versioned inspection, debug, and metric read endpoints."""

from __future__ import annotations

import base64
import time

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import (
    get_inspection_service,
    get_metric_read_service,
    get_settings,
)
from api.errors import bad_request
from api.schemas import (
    AgentVisibleOut,
    AvailabilityOut,
    EventCursorIn,
    EventPageOut,
    EventSummaryOut,
    ExperimentalStateOut,
    MetricCatalogItemOut,
    MetricCatalogOut,
    MetricDocumentOut,
    ObjectiveWorldOut,
    SubjectiveClaimsOut,
    SubjectivePageOut,
    TerritorialClaimHeadOut,
)
from api.security import ApiCapability, require_http_capability
from api.services import InspectionService, MetricReadService
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.inspection import subjective_claims_document
from simulation.run_control import AgentRuntimeCheckpoint

router = APIRouter(prefix="/v1/simulations", tags=["inspection"])
_LOGGER = get_logger("api.routes.inspection")


def _inspect(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.OBJECTIVE_INSPECTION
    )


def _agent_visible(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.AGENT_VISIBLE
    )


def _debug(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


@router.get("/{run_id}/world", response_model=ObjectiveWorldOut)
async def get_objective_world(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: InspectionService = Depends(get_inspection_service),
) -> ObjectiveWorldOut:
    started = time.perf_counter()
    result = await service.objective_world(run_id)
    _LOGGER.info(
        "route_objective_world",
        route_template="GET /v1/simulations/{run_id}/world",
        status=200,
        run_id=run_id,
        availability=result.availability.value,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return result


@router.get("/{run_id}/events", response_model=EventPageOut)
async def list_events(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: InspectionService = Depends(get_inspection_service),
    settings: Settings = Depends(get_settings),
    after_tick: int | None = Query(default=None, ge=0),
    after_sequence: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> EventPageOut:
    page_limit = limit if limit is not None else settings.api_max_page_size
    if page_limit > settings.api_max_page_size:
        raise bad_request(code="limit_exceeds_maximum")
    after: EventCursorIn | None = None
    if after_tick is not None or after_sequence is not None:
        if after_tick is None or after_sequence is None:
            raise bad_request(code="incomplete_event_cursor")
        after = EventCursorIn(tick=after_tick, sequence=after_sequence)
    result = await service.events_page(run_id, after=after, limit=page_limit)
    _LOGGER.info(
        "route_events",
        route_template="GET /v1/simulations/{run_id}/events",
        status=200,
        run_id=run_id,
        count=result.count,
        availability=result.availability.value,
    )
    return result


@router.get("/{run_id}/agents/{agent_id}/observation", response_model=AgentVisibleOut)
async def get_agent_observation(
    run_id: str,
    agent_id: str,
    request: Request,
    _: None = Depends(_agent_visible),
    service: InspectionService = Depends(get_inspection_service),
) -> AgentVisibleOut:
    result = await service.agent_visible(run_id, agent_id)
    _LOGGER.info(
        "route_agent_visible",
        route_template="GET /v1/simulations/{run_id}/agents/{agent_id}/observation",
        status=200,
        run_id=run_id,
        availability=result.availability.value,
    )
    return result


@router.get("/{run_id}/experimental", response_model=ExperimentalStateOut)
async def get_experimental_state(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: InspectionService = Depends(get_inspection_service),
) -> ExperimentalStateOut:
    result = await service.experimental_state(run_id)
    _LOGGER.info(
        "route_experimental",
        route_template="GET /v1/simulations/{run_id}/experimental",
        status=200,
        run_id=run_id,
        availability=result.availability.value,
    )
    return result


@router.get(
    "/{run_id}/owners/{owner_id}/memories",
    response_model=SubjectivePageOut,
)
async def list_owner_memories(
    run_id: str,
    owner_id: str,
    request: Request,
    _: None = Depends(_debug),
    service: InspectionService = Depends(get_inspection_service),
    settings: Settings = Depends(get_settings),
    after: str | None = Query(default=None, max_length=256),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> SubjectivePageOut:
    page_limit = limit if limit is not None else settings.api_max_page_size
    result = await service.subjective_page(
        run_id, owner_id, kind="memories", after=after, limit=page_limit
    )
    _LOGGER.info(
        "route_debug_memories",
        route_template="GET /v1/simulations/{run_id}/owners/{owner_id}/memories",
        status=200,
        run_id=run_id,
        count=result.item_count,
    )
    return result


@router.get(
    "/{run_id}/owners/{owner_id}/beliefs",
    response_model=SubjectivePageOut,
)
async def list_owner_beliefs(
    run_id: str,
    owner_id: str,
    request: Request,
    _: None = Depends(_debug),
    service: InspectionService = Depends(get_inspection_service),
    settings: Settings = Depends(get_settings),
    after: str | None = Query(default=None, max_length=256),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> SubjectivePageOut:
    page_limit = limit if limit is not None else settings.api_max_page_size
    result = await service.subjective_page(
        run_id, owner_id, kind="beliefs", after=after, limit=page_limit
    )
    _LOGGER.info(
        "route_debug_beliefs",
        route_template="GET /v1/simulations/{run_id}/owners/{owner_id}/beliefs",
        status=200,
        run_id=run_id,
        count=result.item_count,
    )
    return result


@router.get(
    "/{run_id}/owners/{owner_id}/relationships",
    response_model=SubjectivePageOut,
)
async def list_owner_relationships(
    run_id: str,
    owner_id: str,
    request: Request,
    _: None = Depends(_debug),
    service: InspectionService = Depends(get_inspection_service),
    settings: Settings = Depends(get_settings),
    after: str | None = Query(default=None, max_length=256),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> SubjectivePageOut:
    page_limit = limit if limit is not None else settings.api_max_page_size
    result = await service.subjective_page(
        run_id, owner_id, kind="relationships", after=after, limit=page_limit
    )
    _LOGGER.info(
        "route_debug_relationships",
        route_template="GET /v1/simulations/{run_id}/owners/{owner_id}/relationships",
        status=200,
        run_id=run_id,
        count=result.item_count,
    )
    return result


@router.get(
    "/{run_id}/owners/{owner_id}/territorial-claims",
    response_model=SubjectiveClaimsOut,
)
async def list_territorial_claims(
    run_id: str,
    owner_id: str,
    request: Request,
    _: None = Depends(_debug),
) -> SubjectiveClaimsOut:
    manager = getattr(request.app.state, "simulation_manager", None)
    checkpoint = None
    if manager is not None and hasattr(manager, "owner_runtime_checkpoint"):
        checkpoint = manager.owner_runtime_checkpoint(run_id, owner_id)
    typed = checkpoint if type(checkpoint) is AgentRuntimeCheckpoint else None
    document = subjective_claims_document(owner_id, typed)
    _LOGGER.info(
        "route_territorial_claims",
        route_template=(
            "GET /v1/simulations/{run_id}/owners/{owner_id}/territorial-claims"
        ),
        status=200,
        run_id=run_id,
        heads=len(document.heads),
    )
    return SubjectiveClaimsOut(
        owner_id=document.owner_id,
        heads=tuple(
            TerritorialClaimHeadOut(
                owner_id=head.owner_id,
                target_kind=head.target_kind,
                target_entity_id=head.target_entity_id,
                strength=head.strength,
            )
            for head in document.heads
        ),
    )


@router.get("/{run_id}/metrics", response_model=MetricCatalogOut)
async def metric_catalog(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: MetricReadService = Depends(get_metric_read_service),
) -> MetricCatalogOut:
    result = await service.catalog(run_id)
    _LOGGER.info(
        "route_metric_catalog",
        route_template="GET /v1/simulations/{run_id}/metrics",
        status=200,
        run_id=run_id,
        count=result.count,
    )
    return result


@router.get(
    "/{run_id}/metrics/{metric_set_id}/{metric_family}",
    response_model=MetricDocumentOut,
)
async def metric_document(
    run_id: str,
    metric_set_id: str,
    metric_family: str,
    request: Request,
    _: None = Depends(_inspect),
    service: MetricReadService = Depends(get_metric_read_service),
) -> MetricDocumentOut:
    result = await service.document(run_id, metric_set_id, metric_family)
    _LOGGER.info(
        "route_metric_document",
        route_template=(
            "GET /v1/simulations/{run_id}/metrics/{metric_set_id}/{metric_family}"
        ),
        status=200,
        run_id=run_id,
    )
    return result


# Re-export helpers for composition wiring without importing analysis.
def encode_metric_payload_b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def metric_catalog_item(
    *,
    metric_set_id: str,
    metric_family: str,
    evidence_manifest_hash: str,
    schema_version: str,
    content_hash: str,
) -> MetricCatalogItemOut:
    return MetricCatalogItemOut(
        metric_set_id=metric_set_id,
        metric_family=metric_family,
        evidence_manifest_hash=evidence_manifest_hash,
        schema_version=schema_version,
        content_hash_prefix=content_hash[:12],
    )


def empty_event_page(*, run_id: str, limit: int) -> EventPageOut:
    return EventPageOut(
        run_id=run_id,
        limit=limit,
        count=0,
        next_cursor=None,
        availability=AvailabilityOut.UNAVAILABLE,
        events=(),
    )


def event_summaries_from_world_events(
    events: tuple[object, ...],
) -> tuple[EventSummaryOut, ...]:
    """Extract tick/sequence/kind only from WorldEvent-like objects."""
    summaries: list[EventSummaryOut] = []
    for event in events:
        tick = int(getattr(event, "tick", 0))
        sequence = int(getattr(event, "sequence", 0))
        kind_obj = getattr(event, "kind", None)
        kind = getattr(kind_obj, "value", None) or str(kind_obj or "unknown")
        summaries.append(EventSummaryOut(tick=tick, sequence=sequence, kind=str(kind)))
    return tuple(summaries)
