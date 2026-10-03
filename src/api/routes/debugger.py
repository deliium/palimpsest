"""Read-only research causal debugger HTTP routes (subjective_debug)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_debugger_service, get_settings
from api.errors import bad_request
from api.schemas import (
    CausalTraceOut,
    DebuggerInvocationPageOut,
    DebuggerLineageOut,
)
from api.security import ApiCapability, require_http_capability
from api.services import CausalDebuggerApiService
from infrastructure.logging import get_logger
from infrastructure.settings import Settings

router = APIRouter(prefix="/v1/simulations", tags=["debugger"])
_LOGGER = get_logger("api.routes.debugger")


def _subjective_debug(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


@router.get(
    "/{run_id}/debugger/events/{event_id}/causal-trace",
    response_model=CausalTraceOut,
    summary="Causal trace by opaque event id (observational, non-mutating)",
)
async def causal_trace_by_event_id(
    run_id: str,
    event_id: str,
    request: Request,
    _: None = Depends(_subjective_debug),
    service: CausalDebuggerApiService = Depends(get_debugger_service),
) -> CausalTraceOut:
    started = time.perf_counter()
    result = await service.causal_trace(
        run_id, event_id=event_id, tick=None, sequence=None
    )
    _LOGGER.info(
        "route_debugger_causal_trace",
        route_template=(
            "GET /v1/simulations/{run_id}/debugger/events/{event_id}/causal-trace"
        ),
        status=200,
        run_id=run_id,
        availability=result.availability.value,
        node_count=len(result.nodes),
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return result


@router.get(
    "/{run_id}/debugger/causal-trace",
    response_model=CausalTraceOut,
    summary="Causal trace by tick+sequence (observational, non-mutating)",
)
async def causal_trace_by_cursor(
    run_id: str,
    request: Request,
    _: None = Depends(_subjective_debug),
    service: CausalDebuggerApiService = Depends(get_debugger_service),
    tick: int = Query(..., ge=0),
    sequence: int = Query(..., ge=0),
) -> CausalTraceOut:
    started = time.perf_counter()
    _LOGGER.debug(
        "debugger_address",
        run_id=run_id,
        tick=tick,
        sequence=sequence,
    )
    result = await service.causal_trace(
        run_id, event_id=None, tick=tick, sequence=sequence
    )
    _LOGGER.info(
        "route_debugger_causal_trace",
        route_template="GET /v1/simulations/{run_id}/debugger/causal-trace",
        status=200,
        run_id=run_id,
        availability=result.availability.value,
        node_count=len(result.nodes),
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return result


@router.get(
    "/{run_id}/debugger/agents/{agent_id}/invocations",
    response_model=DebuggerInvocationPageOut,
    summary="List cognition-trace invocations for an agent (observational)",
)
async def list_debugger_invocations(
    run_id: str,
    agent_id: str,
    request: Request,
    _: None = Depends(_subjective_debug),
    service: CausalDebuggerApiService = Depends(get_debugger_service),
    tick: int | None = Query(default=None, ge=0),
) -> DebuggerInvocationPageOut:
    started = time.perf_counter()
    result = await service.list_invocations(run_id, agent_id, tick=tick)
    _LOGGER.info(
        "route_debugger_invocations",
        route_template=(
            "GET /v1/simulations/{run_id}/debugger/agents/{agent_id}/invocations"
        ),
        status=200,
        run_id=run_id,
        count=result.count,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return result


@router.get(
    "/{run_id}/debugger/lineage/{kind}/{subject_id}",
    response_model=DebuggerLineageOut,
    summary="Lineage drill-down (closed kind enum, observational)",
)
async def debugger_lineage(
    run_id: str,
    kind: str,
    subject_id: str,
    request: Request,
    _: None = Depends(_subjective_debug),
    service: CausalDebuggerApiService = Depends(get_debugger_service),
    owner_id: str = Query(..., min_length=1, max_length=128),
) -> DebuggerLineageOut:
    started = time.perf_counter()
    allowed = {
        "belief_evidence",
        "memory_derivation",
        "communication",
        "narrative",
        "goal_ancestry",
        "prediction",
    }
    if kind not in allowed:
        raise bad_request(code="invalid_kind")
    result = await service.lineage(
        run_id, kind=kind, subject_id=subject_id, owner_id=owner_id
    )
    _LOGGER.info(
        "route_debugger_lineage",
        route_template="GET /v1/simulations/{run_id}/debugger/lineage/{kind}/{id}",
        status=200,
        run_id=run_id,
        kind=kind,
        entry_count=len(result.entries),
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    return result
