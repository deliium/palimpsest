"""PostgreSQL debug-scope proofs (Task 21)."""

from __future__ import annotations

import base64
import hashlib
import logging
import uuid

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.app import create_app
from api.simulation_manager import SimulationManager, TickExecutionResult
from infrastructure.database import DatabaseResources
from infrastructure.settings import Settings, load_settings
from persistence import create_run_control_repository

pytestmark = pytest.mark.integration

_PAYLOAD = b'{"schema_version":"runner-config-v2","agents":[]}'
_FINGERPRINT = hashlib.sha256(_PAYLOAD).hexdigest()
_B64 = base64.b64encode(_PAYLOAD).decode("ascii")


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@pytest.mark.asyncio
async def test_api_debug_routes_disabled_by_default(
    database_resources: DatabaseResources,
    migrated_test_database: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_id = _unique("api-debug")
    settings = load_settings(
        env_file=False,
        database_url=migrated_test_database.database_dsn(),
        test_database_url=migrated_test_database.database_dsn(),
        api_debug_enabled=False,
    )
    run_control = create_run_control_repository(database_resources.session_factory)

    async def executor(requested: str) -> TickExecutionResult:
        del requested
        return TickExecutionResult(ticks_committed=0)

    manager = SimulationManager(
        settings=settings,
        run_control=run_control,
        tick_executor=executor,
    )
    app: FastAPI = create_app(
        settings=settings,
        database_factory=lambda _s: database_resources,
        simulation_manager=manager,
        attach_default_manager=False,
    )
    with caplog.at_level(logging.WARNING, logger="api"):
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                await client.post(
                    "/v1/simulations",
                    json={
                        "run_id": run_id,
                        "config_fingerprint": _FINGERPRINT,
                        "config_payload_b64": _B64,
                    },
                )
                denied = await client.get(
                    f"/v1/simulations/{run_id}/owners/agent-1/memories"
                )
                assert denied.status_code == 403
                assert denied.json().get("code") == "debug_disabled"
    for record in caplog.records:
        if record.name.startswith("api"):
            assert "research-debug-secret" not in record.getMessage()


@pytest.mark.asyncio
async def test_api_debug_routes_require_explicit_credential(
    database_resources: DatabaseResources,
    migrated_test_database: Settings,
) -> None:
    run_id = _unique("api-debug-on")
    settings = load_settings(
        env_file=False,
        database_url=migrated_test_database.database_dsn(),
        test_database_url=migrated_test_database.database_dsn(),
        api_debug_enabled=True,
        api_debug_credential=SecretStr("research-debug-secret-value"),
    )
    run_control = create_run_control_repository(database_resources.session_factory)

    async def executor(requested: str) -> TickExecutionResult:
        del requested
        return TickExecutionResult(ticks_committed=0)

    manager = SimulationManager(
        settings=settings,
        run_control=run_control,
        tick_executor=executor,
    )
    app: FastAPI = create_app(
        settings=settings,
        database_factory=lambda _s: database_resources,
        simulation_manager=manager,
        attach_default_manager=False,
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            await client.post(
                "/v1/simulations",
                json={
                    "run_id": run_id,
                    "config_fingerprint": _FINGERPRINT,
                    "config_payload_b64": _B64,
                },
            )
            missing = await client.get(
                f"/v1/simulations/{run_id}/owners/agent-1/memories"
            )
            assert missing.status_code == 401
            query = await client.get(
                f"/v1/simulations/{run_id}/owners/agent-1/memories"
                "?debug_secret=research-debug-secret-value"
            )
            assert query.status_code == 401
