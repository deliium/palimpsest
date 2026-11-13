"""Seven GET-only economic-inequality routes with dual gate and cursors."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_settings
from api.economic_inequality_cursor import EconomicInequalityCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.economic_inequality import (
    ECONOMIC_INEQUALITY_ROUTE_COUNT,
    router,
)
from experiments.economic_inequality_publication import (
    compose_economic_inequality_snapshot,
)
from infrastructure.settings import Settings
from persistence.economic_inequality_filesystem import (
    create_economic_inequality_publisher,
    create_economic_inequality_reader,
)
from tests.unit.test_economic_inequality_metrics import _analysis

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-economic-inequality-api"

PATHS = {
    "/v1/simulations/{run_id}/economic-inequality",
    "/v1/simulations/{run_id}/economic-inequality/dimensions",
    "/v1/simulations/{run_id}/economic-inequality/possession",
    "/v1/simulations/{run_id}/economic-inequality/access",
    "/v1/simulations/{run_id}/economic-inequality/claims",
    "/v1/simulations/{run_id}/economic-inequality/cohorts",
    "/v1/simulations/{run_id}/economic-inequality/societies",
}


def _snapshot():
    return compose_economic_inequality_snapshot(_analysis(), run_id=RUN)


def _seed(tmp_path: Path) -> None:
    create_economic_inequality_publisher(tmp_path / "store").publish(_snapshot())


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_economic_inequality_reader(root / "store")
    app.state.economic_inequality_reader = reader
    app.state.settings = settings
    app.state.economic_inequality_cursor_codec = (
        EconomicInequalityCursorCodec(b"k" * 32) if reader is not None else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_route_count_and_all_get() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert ECONOMIC_INEQUALITY_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_dual_gate_fails_closed(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(None) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["code"] == "economic_inequality_disabled"


@pytest.mark.asyncio
async def test_summary_and_pages_serve(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality", headers=HEADERS
        )
        dimensions = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality/dimensions",
            headers=HEADERS,
        )
        possession = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality/possession",
            headers=HEADERS,
        )
        claims = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality/claims",
            headers=HEADERS,
        )
    assert summary.status_code == 200
    assert summary.json()["dimension_row_count"] > 0
    assert dimensions.status_code == 200
    assert possession.status_code == 200
    assert claims.status_code == 200
    assert all(
        row["dimension"] == "resource_possession" for row in possession.json()["rows"]
    )
    assert {row["dimension"] for row in claims.json()["rows"]} <= {
        "credit_relationship",
        "organizational_resource_control",
    }


@pytest.mark.asyncio
async def test_cursor_from_another_window_is_rejected(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality/dimensions",
            params={"limit": 1, "window_index": 0},
            headers=HEADERS,
        )
        cursor = first.json()["next_cursor"]
        assert cursor
        second = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality/dimensions",
            params={"limit": 1, "window_index": 1, "cursor": cursor},
            headers=HEADERS,
        )
    assert second.status_code == 400
    assert second.json()["code"] == "economic_inequality_cursor_invalid"


@pytest.mark.asyncio
async def test_corrupt_store_returns_500(tmp_path: Path) -> None:
    _seed(tmp_path)
    state = tmp_path / "store" / RUN / "state.json"
    state.write_text("{not-json", encoding="utf-8")
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-inequality", headers=HEADERS
        )
    assert response.status_code == 500
    assert response.json()["code"] == "economic_inequality_store_corrupt"


@pytest.mark.asyncio
async def test_subjective_debug_is_required(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(f"/v1/simulations/{RUN}/economic-inequality")
    assert response.status_code in {401, 403}
