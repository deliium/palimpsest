# mypy: ignore-errors
"""Opt-in filesystem-store to replication HTTP integration."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_rows import ReplicationFacts
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.replication_cursor import ReplicationCursorCodec
from api.routes.replication import router
from experiments.replication_publication import compose_replication_snapshot
from infrastructure.settings import Settings
from persistence.replication_filesystem import replication_store_publisher
from simulation.replication_ports import ReplicationPublicationOptions

pytestmark = pytest.mark.integration

TOKEN = "integration-replication-token-" + "x" * 32
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-replication-integration"


@pytest.mark.asyncio
async def test_real_store_reads_all_eight_routes(tmp_path: Path) -> None:
    snapshot = compose_replication_snapshot(
        harvest_replication_analysis(ReplicationFacts()),
        run_id=RUN,
        generated_from_tick=0,
    )
    options = ReplicationPublicationOptions(enabled=True)
    store = replication_store_publisher(tmp_path, options=options)
    assert store.publish(snapshot).stored is True

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    app.state.scientific_replication_reader = store
    app.state.scientific_replication_cursor_codec = (
        ReplicationCursorCodec.from_secret(b"k" * 32)
    )
    base = f"/v1/simulations/{RUN}/scientific-replication"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(base, headers=HEADERS)
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == snapshot.publication_id
        calls = [
            await client.get(f"{base}/{section}", headers=HEADERS)
            for section in (
                "designs",
                "attempts",
                "results",
                "comparisons",
                "interpretations",
                "collaborations",
                "coverage",
            )
        ]
        assert all(response.status_code == 200 for response in calls)
