"""Seven GET-only emergent-price routes with dual gate and cursors."""

# mypy: ignore-errors


from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.emergent_prices_analysis import harvest_emergent_prices_analysis
from api.dependencies import get_settings
from api.emergent_prices_cursor import EmergentPricesCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.emergent_prices import EMERGENT_PRICES_ROUTE_COUNT, router
from experiments.emergent_prices_publication import (
    compose_emergent_prices_snapshot,
)
from infrastructure.settings import Settings
from persistence.emergent_prices_filesystem import (
    create_emergent_prices_publisher,
    create_emergent_prices_reader,
)
from simulation.emergent_prices_ports import emergent_prices_query_fingerprint
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-price-api"

PATHS = {
    "/v1/simulations/{run_id}/emergent-prices",
    "/v1/simulations/{run_id}/emergent-prices/units",
    "/v1/simulations/{run_id}/emergent-prices/expectations",
    "/v1/simulations/{run_id}/emergent-prices/quotes",
    "/v1/simulations/{run_id}/emergent-prices/distributions",
    "/v1/simulations/{run_id}/emergent-prices/markets",
    "/v1/simulations/{run_id}/emergent-prices/relations",
}


def _snapshot():
    analysis = harvest_emergent_prices_analysis(
        committed_events=[
            completed(f"event-{index}", tick=index) for index in range(4)
        ]
    )
    return compose_emergent_prices_snapshot(analysis, run_id=RUN)


def _seed(tmp_path: Path) -> None:
    create_emergent_prices_publisher(tmp_path / "store").publish(_snapshot())


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_emergent_prices_reader(root / "store")
    app.state.emergent_prices_reader = reader
    app.state.settings = settings
    app.state.emergent_prices_cursor_codec = (
        EmergentPricesCursorCodec(b"k" * 32) if reader is not None else None
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
    assert EMERGENT_PRICES_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_disabled_without_settings() -> None:
    async with _client(None) as client:
        for path in PATHS:
            response = await client.get(path.format(run_id=RUN), headers=HEADERS)
            assert response.status_code == 503
            assert response.json()["detail"] == "emergent_prices_disabled"


@pytest.mark.asyncio
async def test_all_routes_serve_published_rows(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/emergent-prices", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["digest"] == _snapshot().digest
        for purpose in (
            "units",
            "expectations",
            "quotes",
            "distributions",
            "markets",
            "relations",
        ):
            response = await client.get(
                f"/v1/simulations/{RUN}/emergent-prices/{purpose}",
                headers=HEADERS,
            )
            assert response.status_code == 200
            assert "rows" in response.json()


@pytest.mark.asyncio
async def test_missing_run_is_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(
            "/v1/simulations/absent/emergent-prices", headers=HEADERS
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_corrupt_store_is_500(tmp_path: Path) -> None:
    _seed(tmp_path)
    state = json.loads((tmp_path / "store" / RUN / "state.json").read_text())
    publication = next(iter(state["publications"]))
    (tmp_path / "store" / RUN / f"{publication}.json").write_bytes(b"bad")
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/emergent-prices", headers=HEADERS
        )
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_invalid_cursor_and_window_mismatch_are_400(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        invalid = await client.get(
            f"/v1/simulations/{RUN}/emergent-prices/distributions?cursor=bad",
            headers=HEADERS,
        )
        assert invalid.status_code == 400
    snapshot = _snapshot()
    codec = EmergentPricesCursorCodec(b"k" * 32)
    token = codec.encode(
        purpose="distributions",
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=emergent_prices_query_fingerprint(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            purpose="distributions",
            filters={"window_index": 0},
            limit=100,
        ),
        after_key=json.dumps(["x"]),
    )
    async with _client(tmp_path) as client:
        mismatch = await client.get(
            f"/v1/simulations/{RUN}/emergent-prices/distributions"
            f"?cursor={token}&window_index=1",
            headers=HEADERS,
        )
    assert mismatch.status_code == 400


@pytest.mark.asyncio
async def test_limit_bounds(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/emergent-prices/distributions?limit=501",
            headers=HEADERS,
        )
    assert response.status_code == 422
