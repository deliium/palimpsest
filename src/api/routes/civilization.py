"""GET-only objective civilization sidecar; authorize before any metadata read."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request, Response

from api.civilization_cursor import CivilizationCursorCodec
from api.civilization_schemas import (
    CivilizationCatalogueOut,
    CivilizationMapOut,
    CivilizationMarkersOut,
    CivilizationOverlayOut,
)
from api.civilization_service import (
    ArtifactCivilizationApiService,
    CivilizationApiService,
)
from api.dependencies import get_observer_service, get_settings
from api.errors import bad_request, service_unavailable
from api.observer_service import ObserverReadService
from api.security import ApiCapability, require_http_capability
from infrastructure.settings import Settings
from simulation.civilization_models import CivilizationEvidenceClass

router = APIRouter(prefix="/v1/simulations", tags=["civilization"])


def _inspect(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.OBJECTIVE_INSPECTION
    )


def _integer(raw: str | None, default: int | None = None) -> int | None:
    if raw is None:
        return default
    if not raw or len(raw) > 20 or any(c not in "0123456789" for c in raw):
        raise bad_request(code="invalid_civilization_query")
    return int(raw)


@router.get("/{run_id}/observer/civilization/map", response_model=CivilizationMapOut)
async def civilization_map(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    observer: ObserverReadService = Depends(get_observer_service),
    settings: Settings = Depends(get_settings),
) -> Response:
    allowed = {"section", "tick", "through_sequence", "entity_id", "limit", "cursor"}
    pairs = request.query_params.multi_items()
    if any(key not in allowed for key, _ in pairs) or len(
        {key for key, _ in pairs}
    ) != len(pairs):
        raise bad_request(code="invalid_civilization_query")
    query = request.query_params
    limit = _integer(query.get("limit"), 100)
    if limit is None or not 1 <= limit <= min(200, settings.api_max_page_size):
        raise bad_request(code="invalid_civilization_query")
    service = CivilizationApiService(
        observer,
        cast(CivilizationCursorCodec, request.app.state.civilization_cursor_codec),
    )
    result = await service.map(
        run_id,
        section=query.get("section", "locations"),
        tick=_integer(query.get("tick")),
        through_sequence=_integer(query.get("through_sequence")),
        entity_id=query.get("entity_id"),
        limit=limit,
        cursor=query.get("cursor"),
    )
    return Response(
        content=result.model_dump_json().encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


def _reject_unknown(request: Request, allowed: set[str]) -> None:
    pairs = request.query_params.multi_items()
    if any(key not in allowed for key, _ in pairs) or len(
        {key for key, _ in pairs}
    ) != len(pairs):
        raise bad_request(code="invalid_civilization_query")


def _required_integer(raw: str | None) -> int:
    value = _integer(raw)
    if value is None:
        raise bad_request(code="invalid_civilization_query")
    return value


def _authorize_evidence(
    request: Request, settings: Settings, raw: str | None
) -> CivilizationEvidenceClass:
    if raw is None:
        raise bad_request(code="invalid_civilization_query")
    try:
        evidence = CivilizationEvidenceClass(raw)
    except ValueError:
        raise bad_request(code="invalid_civilization_scope") from None
    capability = (
        ApiCapability.OBJECTIVE_INSPECTION
        if evidence is CivilizationEvidenceClass.OBJECTIVE
        else ApiCapability.SUBJECTIVE_DEBUG
    )
    require_http_capability(request, settings, capability=capability)
    return evidence


def _artifact_service(
    request: Request, settings: Settings
) -> ArtifactCivilizationApiService:
    service = getattr(request.app.state, "civilization_service", None)
    if service is not None:
        return cast(ArtifactCivilizationApiService, service)
    if settings.civilization_root is not None:
        raise service_unavailable(code="civilization_storage_unavailable")
    raise service_unavailable(code="civilization_disabled")


@router.get(
    "/{run_id}/observer/civilization/catalogue",
    response_model=CivilizationCatalogueOut,
)
async def civilization_catalogue(
    run_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    _reject_unknown(request, {"evidence_class", "owner_id", "layer", "limit", "cursor"})
    query = request.query_params
    _authorize_evidence(request, settings, query.get("evidence_class"))
    limit = _integer(query.get("limit"), 100)
    if limit is None or not 1 <= limit <= min(200, settings.api_max_page_size):
        raise bad_request(code="invalid_civilization_query")
    result = await _artifact_service(request, settings).catalogue(
        run_id,
        evidence_class=cast(str, query.get("evidence_class")),
        owner_id=query.get("owner_id"),
        layer=query.get("layer"),
        limit=limit,
        cursor=query.get("cursor"),
    )
    return Response(
        content=result.model_dump_json().encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/{run_id}/observer/civilization/overlays",
    response_model=CivilizationOverlayOut,
)
async def civilization_overlays(
    run_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    _reject_unknown(
        request,
        {
            "tick",
            "layer",
            "evidence_class",
            "owner_id",
            "location_id",
            "region_id",
            "entity_id",
            "limit",
            "cursor",
            "publication_id",
        },
    )
    query = request.query_params
    _authorize_evidence(request, settings, query.get("evidence_class"))
    tick = _required_integer(query.get("tick"))
    limit = _integer(query.get("limit"), 100)
    if limit is None or not 1 <= limit <= min(200, settings.api_max_page_size):
        raise bad_request(code="invalid_civilization_query")
    location_id = query.get("location_id")
    region_id = query.get("region_id")
    if location_id is not None and region_id is not None:
        raise bad_request(code="invalid_civilization_query")
    layer = query.get("layer")
    if layer is None:
        raise bad_request(code="invalid_civilization_query")
    result = await _artifact_service(request, settings).overlays(
        run_id,
        tick=tick,
        layer=layer,
        evidence_class=cast(str, query.get("evidence_class")),
        owner_id=query.get("owner_id"),
        location_id=location_id,
        region_id=region_id,
        entity_id=query.get("entity_id"),
        limit=limit,
        cursor=query.get("cursor"),
        publication_id=query.get("publication_id"),
    )
    return Response(
        content=result.model_dump_json().encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/{run_id}/observer/civilization/markers",
    response_model=CivilizationMarkersOut,
)
async def civilization_markers(
    run_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    _reject_unknown(
        request,
        {
            "evidence_class",
            "from_tick",
            "to_tick",
            "layer",
            "owner_id",
            "publication_id",
            "limit",
            "cursor",
        },
    )
    query = request.query_params
    _authorize_evidence(request, settings, query.get("evidence_class"))
    from_tick = _required_integer(query.get("from_tick"))
    to_tick = _required_integer(query.get("to_tick"))
    limit = _integer(query.get("limit"), 100)
    if limit is None or not 1 <= limit <= min(200, settings.api_max_page_size):
        raise bad_request(code="invalid_civilization_query")
    result = await _artifact_service(request, settings).markers(
        run_id,
        evidence_class=cast(str, query.get("evidence_class")),
        owner_id=query.get("owner_id"),
        layer=query.get("layer"),
        from_tick=from_tick,
        to_tick=to_tick,
        limit=limit,
        cursor=query.get("cursor"),
        publication_id=query.get("publication_id"),
    )
    return Response(
        content=result.model_dump_json().encode("utf-8"),
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )
