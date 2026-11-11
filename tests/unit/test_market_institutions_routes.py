"""Seven GET-only market-institution routes with dual-gate and cursors."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.market_institutions_analysis import harvest_market_institutions_analysis
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.market_institutions_cursor import MarketInstitutionsCursorCodec
from api.routes.market_institutions import (
    MARKET_INSTITUTIONS_ROUTE_COUNT,
    router,
)
from experiments.market_institutions_publication import (
    compose_market_institutions_snapshot,
)
from infrastructure.settings import Settings
from persistence.market_institutions_filesystem import (
    create_market_institutions_publisher,
    create_market_institutions_reader,
)
from tests.unit.test_market_institutions_analysis import _events

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-market-api"

PATHS = {
    "/v1/simulations/{run_id}/market-institutions",
    "/v1/simulations/{run_id}/market-institutions/venues",
    "/v1/simulations/{run_id}/market-institutions/gatherings",
    "/v1/simulations/{run_id}/market-institutions/expectations",
    "/v1/simulations/{run_id}/market-institutions/roles",
    "/v1/simulations/{run_id}/market-institutions/records",
    "/v1/simulations/{run_id}/market-institutions/markets",
}


def _seed(tmp_path: Path) -> None:
    analysis = harvest_market_institutions_analysis(committed_events=_events())
    snapshot = compose_market_institutions_snapshot(analysis, run_id=RUN)
    create_market_institutions_publisher(tmp_path / "store").publish(snapshot)


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_market_institutions_reader(root / "store")
    app.state.market_institutions_reader = reader
    app.state.settings = settings
    app.state.market_institutions_cursor_codec = (
        MarketInstitutionsCursorCodec(b"k" * 32) if reader is not None else None
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
    assert MARKET_INSTITUTIONS_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_disabled_without_settings() -> None:
    async with _client(None) as client:
        for path in PATHS:
            response = await client.get(path.format(run_id=RUN), headers=HEADERS)
            assert response.status_code == 503
            assert response.json()["detail"] == "market_institutions_disabled"


@pytest.mark.asyncio
async def test_requires_subjective_debug(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(f"/v1/simulations/{RUN}/market-institutions")
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_summary_and_page(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/market-institutions", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["venue_count"] >= 1
        venues = await client.get(
            f"/v1/simulations/{RUN}/market-institutions/venues",
            headers=HEADERS,
        )
        assert venues.status_code == 200
        assert venues.json()["rows"]


@pytest.mark.asyncio
async def test_cursor_is_bound_to_window(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/market-institutions/venues",
            headers=HEADERS,
            params={"window_index": 0, "limit": 1},
        )
        assert first.status_code == 200
        cursor = first.json()["next_cursor"]
        assert cursor
        cross = await client.get(
            f"/v1/simulations/{RUN}/market-institutions/venues",
            headers=HEADERS,
            params={"window_index": 1, "limit": 1, "cursor": cursor},
        )
        assert cross.status_code == 400


@pytest.mark.asyncio
async def test_missing_run_is_not_found(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(
            "/v1/simulations/run-missing/market-institutions", headers=HEADERS
        )
    assert response.status_code == 404
