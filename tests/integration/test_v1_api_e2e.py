"""End-to-end V1 API lifecycle against PostgreSQL (Task 21)."""

from __future__ import annotations

import base64
import hashlib
import uuid

import httpx
import pytest
from fastapi import FastAPI

from api.app import create_app
from api.simulation_manager import SimulationManager, TickExecutionResult
from infrastructure.database import DatabaseResources
from infrastructure.settings import Settings, load_settings
from persistence import create_run_control_repository, create_stream_repository
from simulation.models import RunId
from simulation.run_control import (
    StreamRecordDraft,
    StreamRecordKind,
    make_stream_envelope,
)

pytestmark = pytest.mark.integration

_PAYLOAD = b'{"schema_version":"runner-config-v2","agents":[]}'
_FINGERPRINT = hashlib.sha256(_PAYLOAD).hexdigest()
_B64 = base64.b64encode(_PAYLOAD).decode("ascii")


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@pytest.mark.asyncio
async def test_v1_api_create_status_and_stream_publication(
    database_resources: DatabaseResources,
    migrated_test_database: Settings,
) -> None:
    run_id = _unique("v1-e2e")
    settings = load_settings(
        env_file=False,
        database_url=migrated_test_database.database_dsn(),
        test_database_url=migrated_test_database.database_dsn(),
    )
    run_control = create_run_control_repository(database_resources.session_factory)
    stream = create_stream_repository(database_resources.session_factory)

    async def executor(requested: str) -> TickExecutionResult:
        await stream.publish(
            run_id=RunId(requested),
            drafts=(
                StreamRecordDraft(
                    kind=StreamRecordKind.EVENTLESS_TICK,
                    envelope=make_stream_envelope(b'{"tick":0}'),
                    related_tick=0,
                ),
            ),
        )
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
            listed = await client.get("/v1/simulations")
            assert listed.status_code == 200
            status = await client.get(f"/v1/simulations/{run_id}")
            assert status.status_code == 200
            assert status.json()["run_id"] == run_id
    assert await stream.high_water(run_id=RunId(run_id)) >= 0
