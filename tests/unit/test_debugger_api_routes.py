"""API contract tests for research causal debugger routes."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from api.app import DisposableEngine, create_app
from api.errors import not_found
from api.schemas import (
    CausalTraceOut,
    DebuggerAddressOut,
    DebuggerAvailabilityOut,
    DebuggerInvocationPageOut,
    DebuggerLineageOut,
)
from api.services import CausalDebuggerApiService
from api.simulation_manager import SimulationManager
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings
from simulation.memory_run_control import InMemoryRunControlRepository

pytestmark = pytest.mark.unit


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = FakeEngine()


class StubDebugger(CausalDebuggerApiService):
    async def causal_trace(
        self,
        run_id: str,
        *,
        event_id: str | None,
        tick: int | None,
        sequence: int | None,
    ) -> CausalTraceOut:
        if event_id == "missing":
            raise not_found(code="event_not_found", run_id=run_id)
        return CausalTraceOut(
            address=DebuggerAddressOut(
                run_id=run_id,
                tick=tick if tick is not None else 1,
                event_id=event_id,
                sequence=sequence,
                agent_id="alice",
            ),
            availability=DebuggerAvailabilityOut.UNAVAILABLE,
            nodes=(),
            reason_code="cognition_trace_missing",
        )

    async def list_invocations(
        self, run_id: str, agent_id: str, *, tick: int | None
    ) -> DebuggerInvocationPageOut:
        return DebuggerInvocationPageOut(
            run_id=run_id,
            agent_id=agent_id,
            tick=tick,
            items=(),
            count=0,
            availability=DebuggerAvailabilityOut.UNAVAILABLE,
        )

    async def lineage(
        self, run_id: str, *, kind: str, subject_id: str, owner_id: str
    ) -> DebuggerLineageOut:
        return DebuggerLineageOut(
            run_id=run_id,
            owner_id=owner_id,
            kind=kind,
            subject_id=subject_id,
            availability=DebuggerAvailabilityOut.UNAVAILABLE,
            reason_code="lineage_not_found",
        )


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _settings(**overrides: object) -> Settings:
    return load_settings(env_file=False, **overrides)


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or _settings()
    app = create_app(
        settings=resolved,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=resolved,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    app.state.debugger_service = StubDebugger()
    return app


async def test_debugger_requires_subjective_debug(logging_sandbox: None) -> None:
    async with running_client(_app()) as client:
        response = await client.get(
            "/v1/simulations/run-1/debugger/events/e1/causal-trace"
        )
        assert response.status_code == 403
        assert response.json()["code"] == "debug_disabled"


async def test_debugger_causal_trace_tracing_off_unavailable(
    logging_sandbox: None,
) -> None:
    secret = "d" * 32
    settings = _settings(api_debug_enabled=True, api_debug_credential=secret)
    async with running_client(_app(settings)) as client:
        response = await client.get(
            "/v1/simulations/run-1/debugger/events/e1/causal-trace",
            headers={"x-palimpsest-token": secret},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["availability"] == "unavailable"
        assert body["reason_code"] == "cognition_trace_missing"
        assert "rationale" not in body
        assert body["nodes"] == []


async def test_debugger_event_not_found_is_404(logging_sandbox: None) -> None:
    secret = "d" * 32
    settings = _settings(api_debug_enabled=True, api_debug_credential=secret)
    async with running_client(_app(settings)) as client:
        response = await client.get(
            "/v1/simulations/run-1/debugger/events/missing/causal-trace",
            headers={"x-palimpsest-token": secret},
        )
        assert response.status_code == 404
        assert response.json()["code"] == "event_not_found"


async def test_debugger_get_only_surface(logging_sandbox: None) -> None:
    secret = "d" * 32
    settings = _settings(api_debug_enabled=True, api_debug_credential=secret)
    async with running_client(_app(settings)) as client:
        response = await client.post(
            "/v1/simulations/run-1/debugger/events/e1/causal-trace",
            headers={"x-palimpsest-token": secret},
        )
        assert response.status_code == 405
