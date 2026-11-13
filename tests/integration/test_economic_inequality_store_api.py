"""Integration round-trip for the economic-inequality store and API."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from tests.unit.test_economic_inequality_metrics import _analysis

from api.dependencies import get_settings
from api.economic_inequality_cursor import EconomicInequalityCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.economic_inequality import router
from experiments.economic_inequality_publication import (
    compose_economic_inequality_snapshot,
)
from infrastructure.settings import Settings
from persistence.economic_inequality_filesystem import (
    create_economic_inequality_publisher,
    create_economic_inequality_reader,
)

pytestmark = pytest.mark.integration

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-economic-inequality-integration"


@pytest.mark.asyncio
async def test_store_api_round_trip_and_dual_gate(tmp_path: Path) -> None:
    snapshot = compose_economic_inequality_snapshot(_analysis(), run_id=RUN)
    create_economic_inequality_publisher(tmp_path / "store").publish(snapshot)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    app.state.economic_inequality_reader = create_economic_inequality_reader(
        tmp_path / "store"
    )
    app.state.economic_inequality_cursor_codec = EconomicInequalityCursorCodec(
        b"k" * 32
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality", headers=HEADERS
        )
    assert summary.status_code == 200
    assert summary.json()["publication_id"] == snapshot.publication_id

    app.state.economic_inequality_reader = None
    app.state.economic_inequality_cursor_codec = None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        disabled = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality", headers=HEADERS
        )
    assert disabled.status_code == 503
    assert disabled.json()["code"] == "economic_inequality_disabled"
