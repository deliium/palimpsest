"""Read-only observer HTTP routes. No mutating methods are registered."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_observer_service, get_settings
from api.errors import bad_request, not_found
from api.observer_schemas import (
    NarrativeHopOverlayOut,
    NarrativeHopVariantOut,
    ObserverEventOut,
    ObserverEventPageOut,
    ObserverFrameOut,
    ObserverLabelOverlayOut,
    ObserverLabelReadingOut,
    ObserverManifestOut,
    ObserverRelationshipPageOut,
    ObserverRunOut,
    ObserverTickPageOut,
    StrategyAuditEntryOut,
    StrategyAuditOverlayOut,
)
from api.observer_service import ObserverReadService
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from observer.labels import project_subjective_label_overlay
from observer.narrative_hops import project_narrative_hop_overlay
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
    settings: Settings = Depends(get_settings),
    from_tick: int = Query(ge=0),
    to_tick: int = Query(ge=0),
) -> ObserverTickPageOut:
    if to_tick < from_tick:
        raise bad_request(code="invalid_tick_range", run_id=run_id)
    span = to_tick - from_tick + 1
    if span > settings.api_max_page_size:
        raise bad_request(code="tick_range_exceeds_maximum", run_id=run_id)
    started = time.perf_counter()
    result = await service.ticks(
        run_id,
        from_tick=from_tick,
        to_tick=to_tick,
        limit=settings.api_max_page_size,
    )
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
    "/{run_id}/observer/communication-strategy-audit",
    response_model=StrategyAuditOverlayOut,
)
async def get_communication_strategy_audit(
    run_id: str,
    request: Request,
    _: None = Depends(_debug),
    service: ObserverReadService = Depends(get_observer_service),
) -> StrategyAuditOverlayOut:
    """ANALYTICAL research/debug mapping of event_id → strategy category.

    Ordinary speech presentation must not consume this payload.
    """
    started = time.perf_counter()
    manager = getattr(request.app.state, "simulation_manager", None)
    audits: tuple[object, ...] = ()
    if manager is not None and hasattr(manager, "export_communication_intent_audits"):
        audits = manager.export_communication_intent_audits(run_id)
    agent_entity_ids: dict[str, str] = {}
    try:
        frame = await service.state(run_id, tick=None, layout_id=DEFAULT_LAYOUT_ID)
        for agent in frame.world.agents:
            if agent.agent_id:
                agent_entity_ids[agent.agent_id] = agent.entity_id
    except Exception:
        agent_entity_ids = {}
    overlay = await service.strategy_audit_overlay(
        run_id,
        audits=tuple(audits),
        agent_entity_ids=agent_entity_ids,
    )
    _LOGGER.info(
        "route_observer_strategy_audit",
        route_template=(
            "GET /v1/simulations/{run_id}/observer/communication-strategy-audit"
        ),
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        count=overlay.count,
    )
    _LOGGER.debug("strategy_audit_projected count=%s", overlay.count)
    del request
    return StrategyAuditOverlayOut(
        run_id=run_id,
        layer=overlay.layer,  # type: ignore[arg-type]
        evidence_class=overlay.evidence_class,  # type: ignore[arg-type]
        protocol_version=overlay.protocol_version,
        count=overlay.count,
        entries=tuple(
            StrategyAuditEntryOut(
                event_id=entry.event_id,
                category=entry.category,
                evidence_class=entry.evidence_class,  # type: ignore[arg-type]
            )
            for entry in overlay.entries
        ),
    )


@router.get(
    "/{run_id}/observer/agents/{agent_id}/narrative-hops",
    response_model=NarrativeHopOverlayOut,
)
async def get_observer_narrative_hops(
    run_id: str,
    agent_id: str,
    request: Request,
    _: None = Depends(_debug),
) -> NarrativeHopOverlayOut:
    """SUBJECTIVE owner narrative-ledger hops. No content tokens on the wire."""
    started = time.perf_counter()
    manager = getattr(request.app.state, "simulation_manager", None)
    checkpoint = None
    if manager is not None and hasattr(manager, "owner_runtime_checkpoint"):
        checkpoint = manager.owner_runtime_checkpoint(run_id, agent_id)
    ledger = (
        None if checkpoint is None else getattr(checkpoint, "cultural_narratives", None)
    )
    overlay = project_narrative_hop_overlay(agent_id, ledger)
    _LOGGER.info(
        "route_observer_narrative_hops",
        route_template=(
            "GET /v1/simulations/{run_id}/observer/agents/{agent_id}/narrative-hops"
        ),
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        count=overlay.count,
    )
    del request
    return NarrativeHopOverlayOut(
        run_id=run_id,
        owner_id=overlay.owner_id,
        layer=overlay.layer,  # type: ignore[arg-type]
        evidence_class=overlay.evidence_class,  # type: ignore[arg-type]
        protocol_version=overlay.protocol_version,
        count=overlay.count,
        variants=tuple(
            NarrativeHopVariantOut(
                variant_id=item.variant_id,
                status=item.status,
                origin=item.origin,
                carrier_agent_ids=item.carrier_agent_ids,
                location_ids=item.location_ids,
                parent_variant_ids=item.parent_variant_ids,
                merged_into_id=item.merged_into_id,
                transmission_root_id=item.transmission_root_id,
                source_event_id=item.source_event_id,
                last_communication_id=item.last_communication_id,
                strength_band=item.strength_band,  # type: ignore[arg-type]
            )
            for item in overlay.variants
        ),
    )


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


@router.get(
    "/{run_id}/observer/agents/{agent_id}/labels",
    response_model=ObserverLabelOverlayOut,
)
async def get_observer_labels(
    run_id: str,
    agent_id: str,
    request: Request,
    _: None = Depends(_debug),
    service: ObserverReadService = Depends(get_observer_service),
    tick: int | None = Query(default=None, ge=0),
) -> ObserverLabelOverlayOut:
    started = time.perf_counter()
    manager = getattr(request.app.state, "simulation_manager", None)
    checkpoint = None
    if manager is not None and hasattr(manager, "owner_runtime_checkpoint"):
        checkpoint = manager.owner_runtime_checkpoint(run_id, agent_id)
    if tick is not None:
        key = (
            None
            if checkpoint is None
            else getattr(checkpoint, "last_observation_key", None)
        )
        live_tick = None if not isinstance(key, tuple) or not key else key[0]
        if live_tick != tick:
            _LOGGER.warning(
                "labels_unavailable_at_tick run_id=%s agent_id=%s tick=%s",
                run_id,
                agent_id,
                tick,
            )
            raise not_found(code="labels_unavailable_at_tick", run_id=run_id)
    display_index: dict[str, str] = {}
    try:
        frame = await service.state(run_id, tick=None, layout_id=DEFAULT_LAYOUT_ID)
        world = frame.world
        for location in world.locations:
            display_index[location.location_id] = location.display_name
        for agent in world.agents:
            if agent.agent_id:
                display_index[agent.agent_id] = agent.agent_id
            display_index[agent.entity_id] = (
                agent.agent_id if agent.agent_id else agent.entity_id
            )
    except Exception:
        display_index = {}
    ledger = (
        None
        if checkpoint is None
        else getattr(checkpoint, "semantic_naming", None)
    )
    rows = () if ledger is None else getattr(ledger, "bindings", ()) or ()
    overlay = project_subjective_label_overlay(agent_id, rows, display_index)
    _LOGGER.info(
        "route_observer_labels",
        route_template=(
            "GET /v1/simulations/{run_id}/observer/agents/{agent_id}/labels"
        ),
        status=200,
        run_id=run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        count=len(overlay.readings),
    )
    _LOGGER.debug(
        "subjective_labels_served agent_id=%s row_count=%s",
        agent_id,
        len(overlay.readings),
    )
    return ObserverLabelOverlayOut(
        run_id=run_id,
        agent_id=overlay.agent_id,
        layer=overlay.layer,
        protocol_version=overlay.protocol_version,
        count=len(overlay.readings),
        readings=tuple(
            ObserverLabelReadingOut(
                objective_id=reading.objective_id,
                objective_display_name=reading.objective_display_name,
                referent_kind=reading.referent_kind,
                label_token=reading.label_token,
                label_display=reading.label_display,
                sense_revision=reading.sense_revision,
                strength_band=reading.strength_band,  # type: ignore[arg-type]
                label_source=reading.label_source,
            )
            for reading in overlay.readings
        ),
    )
