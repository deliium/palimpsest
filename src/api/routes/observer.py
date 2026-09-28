"""Read-only observer HTTP routes. No mutating methods are registered."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_observer_service, get_settings
from api.errors import bad_request
from api.observer_schemas import (
    ObserverEventOut,
    ObserverEventPageOut,
    ObserverFrameOut,
    ObserverManifestOut,
    ObserverRelationshipPageOut,
    ObserverRunOut,
    ObserverTickPageOut,
)
from api.observer_service import ObserverReadService
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from observer.version import DEFAULT_LAYOUT_ID

router = APIRouter(prefix="/v1/simulations", tags=["observer"])
_LOGGER = get_logger("api.routes.observer")


def _inspect(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.OBJECTIVE_INSPECTION
    )


def _debug(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


@router.get(
    "/{run_id}/observer/manifest",
    response_model=ObserverManifestOut,
)
async def get_observer_manifest(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: ObserverReadService = Depends(get_observer_service),
    layout_id: str = Query(default=DEFAULT_LAYOUT_ID),
) -> ObserverManifestOut:
    started = time.perf_counter()
    result = await service.manifest(run_id, layout_id=layout_id)
    _LOGGER.info(
        "route_observer_manifest",
        route_template="GET /v1/simulations/{run_id}/observer/manifest",
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        count=1,
    )
    del request
    return result


@router.get("/{run_id}/observer/state", response_model=ObserverFrameOut)
async def get_observer_state(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: ObserverReadService = Depends(get_observer_service),
    settings: Settings = Depends(get_settings),
    tick: int | None = Query(default=None, ge=0),
    through_sequence: int | None = Query(default=None, ge=0),
    layout_id: str = Query(default=DEFAULT_LAYOUT_ID),
) -> ObserverFrameOut:
    del settings
    if through_sequence is not None and tick is None:
        raise bad_request(code="incomplete_event_cursor")
    _LOGGER.debug(
        "route_observer_state_cursor",
        run_id=run_id,
        tick=tick,
        through_sequence=through_sequence,
    )
    started = time.perf_counter()
    result = await service.state(
        run_id,
        tick=tick,
        through_sequence=through_sequence,
        layout_id=layout_id,
    )
    _LOGGER.info(
        "route_observer_state",
        route_template="GET /v1/simulations/{run_id}/observer/state",
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        tick=result.world.tick,
    )
    del request
    return result


@router.get("/{run_id}/observer/events", response_model=ObserverEventPageOut)
async def list_observer_events(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: ObserverReadService = Depends(get_observer_service),
    settings: Settings = Depends(get_settings),
    after_tick: int | None = Query(default=None, ge=0),
    after_sequence: int | None = Query(default=None, ge=0),
    limit: int | None = Query(default=None, ge=1, le=1000),
    layout_id: str = Query(default=DEFAULT_LAYOUT_ID),
) -> ObserverEventPageOut:
    page_limit = limit if limit is not None else settings.api_max_page_size
    if page_limit > settings.api_max_page_size:
        raise bad_request(code="limit_exceeds_maximum")
    if (after_tick is None) != (after_sequence is None):
        raise bad_request(code="incomplete_event_cursor")
    started = time.perf_counter()
    result = await service.events(
        run_id,
        after_tick=after_tick,
        after_sequence=after_sequence,
        limit=page_limit,
        layout_id=layout_id,
    )
    _LOGGER.info(
        "route_observer_events",
        route_template="GET /v1/simulations/{run_id}/observer/events",
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        count=result.count,
    )
    _LOGGER.debug(
        "route_observer_events_cursor",
        run_id=run_id,
        after_tick=after_tick,
        after_sequence=after_sequence,
    )
    del request
    return result


@router.get("/{run_id}/observer/ticks", response_model=ObserverTickPageOut)
async def list_observer_ticks(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: ObserverReadService = Depends(get_observer_service),
    from_tick: int = Query(ge=0),
    to_tick: int = Query(ge=0),
) -> ObserverTickPageOut:
    started = time.perf_counter()
    result = await service.ticks(run_id, from_tick=from_tick, to_tick=to_tick)
    _LOGGER.info(
        "route_observer_ticks",
        route_template="GET /v1/simulations/{run_id}/observer/ticks",
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        count=result.count,
    )
    del request
    return result


@router.get(
    "/{run_id}/observer/events/{event_id}",
    response_model=ObserverEventOut,
)
async def get_observer_event(
    run_id: str,
    event_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: ObserverReadService = Depends(get_observer_service),
) -> ObserverEventOut:
    started = time.perf_counter()
    result = await service.event(run_id, event_id)
    _LOGGER.info(
        "route_observer_event",
        route_template="GET /v1/simulations/{run_id}/observer/events/{event_id}",
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        count=1,
    )
    del request
    return result


@router.get("/{run_id}/observer/run", response_model=ObserverRunOut)
async def get_observer_run(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: ObserverReadService = Depends(get_observer_service),
) -> ObserverRunOut:
    started = time.perf_counter()
    result = await service.run(run_id)
    _LOGGER.info(
        "route_observer_run",
        route_template="GET /v1/simulations/{run_id}/observer/run",
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        tick=result.tick,
    )
    del request
    return result


@router.get(
    "/{run_id}/observer/agents/{agent_id}/relationships",
    response_model=ObserverRelationshipPageOut,
)
async def get_observer_relationships(
    run_id: str,
    agent_id: str,
    request: Request,
    _: None = Depends(_debug),
    service: ObserverReadService = Depends(get_observer_service),
) -> ObserverRelationshipPageOut:
    started = time.perf_counter()
    result = await service.relationships(run_id, agent_id)
    _LOGGER.info(
        "route_observer_relationships",
        route_template=(
            "GET /v1/simulations/{run_id}/observer/agents/{agent_id}/relationships"
        ),
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        count=result.count,
    )
    del request
    return result
