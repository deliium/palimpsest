"""PostgreSQL API lifecycle proofs (Task 21)."""

from __future__ import annotations

import base64
import hashlib
import logging
import uuid

import httpx
import pytest
from fastapi import FastAPI

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


def _settings(database: Settings) -> Settings:
    return load_settings(
        env_file=False,
        database_url=database.database_dsn(),
        test_database_url=database.database_dsn(),
    )


@pytest.mark.asyncio
async def test_api_simulation_lifecycle_against_postgres(
    database_resources: DatabaseResources,
    migrated_test_database: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_id = _unique("api-life")
    settings = _settings(migrated_test_database)
    run_control = create_run_control_repository(database_resources.session_factory)

    async def executor(requested: str) -> TickExecutionResult:
        del requested
        return TickExecutionResult(ticks_committed=1)

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
    with caplog.at_level(logging.INFO, logger="api"):
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                created = await client.post(
                    "/v1/simulations",
                    json={
                        "run_id": run_id,
                        "config_fingerprint": _FINGERPRINT,
                        "config_payload_b64": _B64,
                    },
                )
                assert created.status_code in {200, 201}
                started = await client.post(f"/v1/simulations/{run_id}/start")
                assert started.status_code in {200, 202, 409}
                status = await client.get(f"/v1/simulations/{run_id}")
                assert status.status_code == 200
                body = status.json()
                assert body["run_id"] == run_id
                assert "lifecycle" in body or "status" in body
    for record in caplog.records:
        if record.name.startswith("api"):
            text = record.getMessage()
            assert "postgres://" not in text
            assert _B64 not in text
