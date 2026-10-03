"""Versioned research-branch create and lineage inspection endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, Request

from api.branch_api import BranchApiService
from api.dependencies import get_branch_api_service, get_settings
from api.errors import bad_request
from api.schemas import (
    BranchCreateIn,
    BranchCreateOut,
    BranchForkPointOut,
    BranchLineageOut,
    BranchListOut,
    BranchStateOut,
    BranchTimelineCompareIn,
    BranchTimelineCompareOut,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings

router = APIRouter(prefix="/v1/simulations", tags=["branches"])
_LOGGER = get_logger("api.routes.branches")


def _control(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SIMULATION_CONTROL
    )


def _inspect(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.OBJECTIVE_INSPECTION
    )


@router.post(
    "/{parent_run_id}/branches",
    response_model=BranchCreateOut,
    status_code=201,
)
async def create_branch(
    parent_run_id: str,
    body: BranchCreateIn,
    request: Request,
    _: None = Depends(_control),
    service: BranchApiService = Depends(get_branch_api_service),
) -> BranchCreateOut:
    started = time.perf_counter()
    result = await service.create_branch(parent_run_id, body)
    _LOGGER.info(
        "route_create_branch",
        route_template="POST /v1/simulations/{parent_run_id}/branches",
        status=201,
        parent_run_id=parent_run_id,
        child_run_id=result.child_run_id,
        fork_tick=body.fork_tick,
        kind=body.intervention.kind,
        idempotent_hit=result.idempotent_hit,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return result


@router.get("/{run_id}/branches", response_model=BranchListOut)
async def list_branches(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: BranchApiService = Depends(get_branch_api_service),
    settings: Settings = Depends(get_settings),
    after_child_run_id: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> BranchListOut:
    page_limit = limit if limit is not None else settings.api_max_page_size
    if page_limit > settings.api_max_page_size:
        raise bad_request(code="limit_exceeds_maximum")
    return await service.list_children(
        run_id, after_child_run_id=after_child_run_id, limit=page_limit
    )


@router.get("/{run_id}/branch", response_model=BranchLineageOut)
async def get_branch(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: BranchApiService = Depends(get_branch_api_service),
) -> BranchLineageOut:
    return await service.get_lineage(run_id)


@router.get("/{run_id}/branch/fork-point", response_model=BranchForkPointOut)
async def get_fork_point(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: BranchApiService = Depends(get_branch_api_service),
) -> BranchForkPointOut:
    return await service.fork_point(run_id)


@router.get("/{run_id}/branch/state", response_model=BranchStateOut)
async def get_branch_state(
    run_id: str,
    request: Request,
    _: None = Depends(_inspect),
    service: BranchApiService = Depends(get_branch_api_service),
) -> BranchStateOut:
    return await service.branch_state(run_id)


@router.post("/branches/compare", response_model=BranchTimelineCompareOut)
async def compare_branches(
    body: BranchTimelineCompareIn,
    request: Request,
    _: None = Depends(_inspect),
    service: BranchApiService = Depends(get_branch_api_service),
) -> BranchTimelineCompareOut:
    return await service.compare_timelines(body)
