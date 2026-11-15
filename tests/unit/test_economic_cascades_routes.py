# mypy: ignore-errors
"""Seven GET-only economic-cascade routes with dual gate and cursors."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.economic_cascades_analysis import harvest_economic_cascades_analysis
from api.app import create_app
from api.dependencies import get_settings
from api.economic_cascades_cursor import EconomicCascadesCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.economic_cascades import (
    ECONOMIC_CASCADES_ROUTE_COUNT,
    router,
)
from experiments.economic_cascades_publication import (
    compose_economic_cascades_snapshot,
)
from infrastructure.settings import Settings
from persistence.economic_cascades_filesystem import (
    economic_cascades_store_publisher,
    economic_cascades_store_reader,
)
from simulation.economic_cascades_ports import (
    economic_cascades_query_fingerprint,
)
from tests.unit.test_economic_cascades_analysis import (
    _harvest_events,
    _recipes,
    _stage,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-economic-cascades-api"

PATHS = {
    "/v1/simulations/{run_id}/economic-cascades",
    "/v1/simulations/{run_id}/economic-cascades/disruptions",
    "/v1/simulations/{run_id}/economic-cascades/dependencies",
    "/v1/simulations/{run_id}/economic-cascades/chains",
    "/v1/simulations/{run_id}/economic-cascades/propagation",
    "/v1/simulations/{run_id}/economic-cascades/windows",
    "/v1/simulations/{run_id}/economic-cascades/coverage",
}


def _snapshot():
    analysis = harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
    )
    return compose_economic_cascades_snapshot(analysis, run_id=RUN)


def _seed(tmp_path: Path) -> None:
    economic_cascades_store_publisher(tmp_path / "store").publish(_snapshot())


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = (
        None
        if root is None
        else economic_cascades_store_reader(root / "store")
    )
    app.state.economic_cascades_reader = reader
    app.state.settings = settings
    app.state.economic_cascades_cursor_codec = (
        EconomicCascadesCursorCodec(b"k" * 32) if reader is not None else None
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
    assert ECONOMIC_CASCADES_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_dual_gate_fails_closed(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(None) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["code"] == "economic_cascades_disabled"


@pytest.mark.asyncio
async def test_summary_and_all_pages_serve(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        for path in PATHS:
            response = await client.get(
                path.format(run_id=RUN), headers=HEADERS
            )
            assert response.status_code == 200, path
        summary = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
    body = summary.json()
    assert body["chain_count"] >= 1
    assert body["snapshot_version"] == "economic-cascades-snapshot-v1"


@pytest.mark.asyncio
async def test_missing_run_is_not_found(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(
            "/v1/simulations/missing/economic-cascades", headers=HEADERS
        )
    assert response.status_code == 404
    assert response.json()["code"] == "economic_cascades_run_not_found"


@pytest.mark.asyncio
async def test_bad_cursor_is_rejected(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades/chains",
            params={"cursor": "not-a-cursor"},
            headers=HEADERS,
        )
    assert response.status_code == 400
    assert response.json()["code"] == "economic_cascades_cursor_invalid"


@pytest.mark.asyncio
async def test_cursor_from_another_window_is_rejected(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades/chains",
            params={"limit": 1, "window_index": 0},
            headers=HEADERS,
        )
        cursor = first.json()["next_cursor"]
        if cursor is None:
            pytest.skip("snapshot has a single chain row")
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades/chains",
            params={"limit": 1, "window_index": 1, "cursor": cursor},
            headers=HEADERS,
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_corrupt_store_is_internal_error(tmp_path: Path) -> None:
    _seed(tmp_path)
    state = tmp_path / "store" / RUN / "state.json"
    state.write_text("{not-json")
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
    assert response.status_code == 500
    assert response.json()["code"] == "economic_cascades_store_corrupt"


@pytest.mark.asyncio
async def test_expired_cursor_is_gone(tmp_path: Path) -> None:
    _seed(tmp_path)
    snapshot = _snapshot()
    fingerprint = economic_cascades_query_fingerprint(
        run_id=RUN,
        publication_id=snapshot.publication_id,
        digest=snapshot.internal_digest,
        purpose="chains",
        window_index=0,
        limit=1,
    )
    expired = EconomicCascadesCursorCodec(b"k" * 32, now=lambda: 0).encode(
        purpose="chains",
        run_id=RUN,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.internal_digest,
        query_fingerprint=fingerprint,
        after_key="0001|casc-1",
    )
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades/chains",
            params={"limit": 1, "window_index": 0, "cursor": expired},
            headers=HEADERS,
        )
    assert response.status_code == 410
    assert response.json()["code"] == "economic_cascades_cursor_expired"


@pytest.mark.asyncio
async def test_app_factory_attaches_the_dual_gated_reader(tmp_path: Path) -> None:
    _seed(tmp_path)
    root = tmp_path / "store"
    enabled = create_app(
        Settings(
            api_debug_enabled=True,
            api_debug_credential=SecretStr(TOKEN),
            economic_cascades_root=root,
            economic_cascades_cursor_key=SecretStr("k" * 32),
        ),
        attach_default_manager=False,
    )
    assert enabled.state.economic_cascades_reader is not None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=enabled), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
    assert response.status_code == 200

    disabled = create_app(
        Settings(
            api_debug_enabled=True,
            api_debug_credential=SecretStr(TOKEN),
            economic_cascades_root=root,
        ),
        attach_default_manager=False,
    )
    assert disabled.state.economic_cascades_reader is None
    assert disabled.state.economic_cascades_cursor_codec is None
