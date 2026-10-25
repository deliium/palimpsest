"""GET-only objective civilization sidecar; authorize before any metadata read."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request, Response

from api.civilization_cursor import CivilizationCursorCodec
from api.civilization_schemas import CivilizationMapOut
from api.civilization_service import CivilizationApiService
from api.dependencies import get_observer_service, get_settings
from api.errors import bad_request
from api.observer_service import ObserverReadService
from api.security import ApiCapability, require_http_capability
from infrastructure.settings import Settings

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
