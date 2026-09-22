"""Versioned `/v1/simulations` control endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Header, Query, Request

from api.dependencies import get_settings, get_simulation_manager
from api.errors import bad_request
from api.schemas import (
    ConfigureSimulationRequest,
    CreateSimulationRequest,
    RunControlStatusOut,
    RunListOut,
    TickResultOut,
)
from api.security import ApiCapability, require_http_capability
from api.simulation_manager import SimulationManager, decode_config_payload_b64
from infrastructure.logging import get_logger
from infrastructure.settings import Settings

router = APIRouter(prefix="/v1/simulations", tags=["simulations"])
_LOGGER = get_logger("api.routes.simulations")


def _control(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SIMULATION_CONTROL
    )


@router.post("", response_model=RunControlStatusOut, status_code=201)
async def create_simulation(
    body: CreateSimulationRequest,
    request: Request,
    _: None = Depends(_control),
    manager: SimulationManager = Depends(get_simulation_manager),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunControlStatusOut:
    started = time.perf_counter()
    payload = decode_config_payload_b64(body.config_payload_b64)
    status = await manager.create(
        run_id=body.run_id,
        config_schema_version=body.config_schema_version,
        config_fingerprint=body.config_fingerprint,
        config_payload=payload,
        idempotency_key=idempotency_key,
    )
    _LOGGER.info(
        "route_create",
        route_template="POST /v1/simulations",
        status=201,
        run_id=status.run_id,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return status


@router.post("/{run_id}/configure", response_model=RunControlStatusOut)
async def configure_simulation(
    run_id: str,
    body: ConfigureSimulationRequest,
    request: Request,
    _: None = Depends(_control),
    manager: SimulationManager = Depends(get_simulation_manager),
) -> RunControlStatusOut:
    payload = decode_config_payload_b64(body.config_payload_b64)
    status = await manager.configure(
        run_id=run_id,
        expected_version=body.expected_version,
        config_schema_version=body.config_schema_version,
        config_fingerprint=body.config_fingerprint,
        config_payload=payload,
    )
    _LOGGER.info(
        "route_configure",
        route_template="POST /v1/simulations/{run_id}/configure",
        status=200,
        run_id=run_id,
    )
    return status


@router.post("/{run_id}/start", response_model=RunControlStatusOut)
async def start_simulation(
    run_id: str,
    request: Request,
    _: None = Depends(_control),
    manager: SimulationManager = Depends(get_simulation_manager),
) -> RunControlStatusOut:
    status = await manager.start(run_id=run_id)
    _LOGGER.info(
        "route_start",
        route_template="POST /v1/simulations/{run_id}/start",
        status=200,
        run_id=run_id,
        lifecycle_code=status.lifecycle_state.value,
    )
    return status


@router.post("/{run_id}/tick", response_model=TickResultOut)
async def tick_simulation(
    run_id: str,
    request: Request,
    _: None = Depends(_control),
    manager: SimulationManager = Depends(get_simulation_manager),
) -> TickResultOut:
    result = await manager.tick(run_id=run_id)
    _LOGGER.info(
        "route_tick",
        route_template="POST /v1/simulations/{run_id}/tick",
        status=200,
        run_id=run_id,
        ticks_committed=result.ticks_committed,
    )
    return result


@router.post("/{run_id}/run", response_model=RunControlStatusOut)
async def run_simulation(
    run_id: str,
    request: Request,
    _: None = Depends(_control),
    manager: SimulationManager = Depends(get_simulation_manager),
) -> RunControlStatusOut:
    status = await manager.run(run_id=run_id)
    _LOGGER.info(
        "route_run",
        route_template="POST /v1/simulations/{run_id}/run",
        status=200,
        run_id=run_id,
        lifecycle_code=status.lifecycle_state.value,
    )
    return status


@router.post("/{run_id}/stop", response_model=RunControlStatusOut)
async def stop_simulation(
    run_id: str,
    request: Request,
    _: None = Depends(_control),
    manager: SimulationManager = Depends(get_simulation_manager),
) -> RunControlStatusOut:
    status = await manager.stop(run_id=run_id)
    _LOGGER.info(
        "route_stop",
        route_template="POST /v1/simulations/{run_id}/stop",
        status=200,
        run_id=run_id,
        lifecycle_code=status.lifecycle_state.value,
    )
    return status


@router.get("", response_model=RunListOut)
async def list_simulations(
    request: Request,
    _: None = Depends(_control),
    manager: SimulationManager = Depends(get_simulation_manager),
    settings: Settings = Depends(get_settings),
    after: str | None = Query(default=None, max_length=128),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> RunListOut:
    page_limit = limit if limit is not None else settings.api_max_page_size
    if page_limit > settings.api_max_page_size:
        raise bad_request(code="limit_exceeds_maximum")
    result = await manager.list_runs(after_run_id=after, limit=page_limit)
    _LOGGER.info(
        "route_list",
        route_template="GET /v1/simulations",
        status=200,
        count=result.count,
    )
    return result


@router.get("/{run_id}", response_model=RunControlStatusOut)
async def simulation_status(
    run_id: str,
    request: Request,
    _: None = Depends(_control),
    manager: SimulationManager = Depends(get_simulation_manager),
) -> RunControlStatusOut:
    status = await manager.status(run_id=run_id)
    _LOGGER.info(
        "route_status",
        route_template="GET /v1/simulations/{run_id}",
        status=200,
        run_id=run_id,
        lifecycle_code=status.lifecycle_state.value,
    )
    return status
