"""Detached replay-to-tick inspection endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request

from api.dependencies import get_replay_api_service, get_settings
from api.errors import gone, unprocessable
from api.schemas import AvailabilityOut, ReplayRequest, ReplayResultOut
from api.security import ApiCapability, require_http_capability
from api.services import ReplayApiService
from infrastructure.logging import get_logger
from infrastructure.settings import Settings

router = APIRouter(prefix="/v1/simulations", tags=["replay"])
_LOGGER = get_logger("api.routes.replay")


def _inspect(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.OBJECTIVE_INSPECTION
    )


@router.post("/{run_id}/replay", response_model=ReplayResultOut)
async def replay_to_tick(
    run_id: str,
    body: ReplayRequest,
    request: Request,
    _: None = Depends(_inspect),
    service: ReplayApiService = Depends(get_replay_api_service),
) -> ReplayResultOut:
    if body.agent_id is not None:
        require_http_capability(
            request,
            request.app.state.settings,
            capability=ApiCapability.AGENT_VISIBLE,
        )
    started = time.perf_counter()
    try:
        result = await service.replay_to_tick(run_id, body)
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code == "corruption":
            raise unprocessable(code="replay_corruption", run_id=run_id) from exc
        if code == "unavailable":
            raise gone(code="replay_unavailable", run_id=run_id) from exc
        raise
    _LOGGER.info(
        "route_replay",
        route_template="POST /v1/simulations/{run_id}/replay",
        status=200,
        run_id=run_id,
        availability=result.availability.value,
        ticks_replayed=result.ticks_replayed,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return result


def unavailable_replay(*, run_id: str, reason_code: str) -> ReplayResultOut:
    return ReplayResultOut(
        run_id=run_id,
        status="unavailable",
        availability=AvailabilityOut.UNAVAILABLE,
        ticks_replayed=0,
        reason_code=reason_code,
    )
