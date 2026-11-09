"""Read-only infrastructure-networks API routes and dual-gate 503."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_infrastructure_networks_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.infrastructure_networks_cursor import InfrastructureNetworksCursorCodec
from api.routes.infrastructure_networks import (
    INFRASTRUCTURE_NETWORKS_ROUTE_COUNT,
    router,
)
from infrastructure.settings import Settings
from persistence.infrastructure_filesystem import (
    create_infrastructure_networks_publisher,
    create_infrastructure_networks_reader,
)
from simulation.infrastructure_codec import finalize_infrastructure_networks_snapshot
from simulation.infrastructure_models import (
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
    InfrastructureAssetRecord,
    InfrastructureNetworksSnapshot,
    InfrastructureNetworksSummaryRecord,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-infra-api"
_ASSET = "infra-" + ("c" * 32)

PATHS = {
    "/v1/simulations/{run_id}/infrastructure-networks",
    "/v1/simulations/{run_id}/infrastructure-networks/assets",
    "/v1/simulations/{run_id}/infrastructure-networks/edges",
    "/v1/simulations/{run_id}/infrastructure-networks/condition",
    "/v1/simulations/{run_id}/infrastructure-networks/effects",
    "/v1/simulations/{run_id}/infrastructure-networks/maintenance",
}


def _asset(**overrides: object) -> InfrastructureAssetRecord:
    values: dict[str, object] = {
        "asset_id": _ASSET,
        "kind": "bridge",
        "topology": "node",
        "status": "operational",
        "integrity": 1.0,
        "location_id": "loc-a",
        "endpoint_location_id": None,
        "effects_active": True,
        "created_tick": 1,
        "last_maintained_tick": 1,
        "ticks_since_maintained": 0,
        "linked_project_id": "proj-1",
        "linked_structure_id": "struct-1",
    }
    values.update(overrides)
    return InfrastructureAssetRecord(**values)  # type: ignore[arg-type]


def _seed(root: Path) -> Any:
    road = _asset(
        asset_id="infra-" + ("d" * 32),
        kind="road",
        topology="edge",
        endpoint_location_id="loc-b",
    )
    snapshot = finalize_infrastructure_networks_snapshot(
        InfrastructureNetworksSnapshot(
            summary=InfrastructureNetworksSummaryRecord(
                run_id=RUN,
                publication_id="",
                digest="",
                schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
                policy_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
                asset_count=2,
                node_count=1,
                edge_count=1,
                operational_count=2,
                damaged_count=0,
                destroyed_count=0,
                effects_active_count=2,
                coverage="complete",
            ),
            assets=(_asset(), road),
        )
    )
    store = root / "store"
    create_infrastructure_networks_publisher(store).publish(snapshot)
    return snapshot


def _client(root: Path | None, *, clock: list[float]) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_infrastructure_networks_reader(root / "store")
    app.dependency_overrides[get_infrastructure_networks_reader] = lambda: reader
    app.state.infrastructure_networks_reader = reader
    app.state.infrastructure_networks_cursor_codec = (
        InfrastructureNetworksCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_six_get_routes_exist() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert INFRASTRUCTURE_NETWORKS_ROUTE_COUNT == 6
    assert len(routes) == 6
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_unset_reader_is_503_disabled() -> None:
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks", headers=HEADERS
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "infrastructure_networks_disabled"


@pytest.mark.asyncio
async def test_summary_and_pages(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks", headers=HEADERS
        )
        assert summary.status_code == 200
        body = summary.json()
        assert body["publication_id"] == snapshot.publication_id
        assert body["asset_count"] == 2
        assert body["edge_count"] == 1
        assert "score" not in body
        assert "civilization_score" not in body
        assets = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/assets",
            headers=HEADERS,
        )
        assert assets.status_code == 200
        assert len(assets.json()["items"]) == 2
        edges = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/edges",
            headers=HEADERS,
        )
        assert edges.status_code == 200
        assert len(edges.json()["items"]) == 1
        for purpose in ("condition", "effects", "maintenance"):
            page = await client.get(
                f"/v1/simulations/{RUN}/infrastructure-networks/{purpose}",
                headers=HEADERS,
            )
            assert page.status_code == 200
            assert len(page.json()["items"]) == 2


@pytest.mark.asyncio
async def test_subjective_debug_is_required(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks"
        )
        assert response.status_code in {401, 403}


class _CorruptReader:
    def read_snapshot(self, run_id: str) -> Any:
        raise ValueError("infrastructure_networks_store_corrupt")


@pytest.mark.asyncio
async def test_corrupt_store_is_500() -> None:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.infrastructure_networks_reader = _CorruptReader()
    app.state.infrastructure_networks_cursor_codec = InfrastructureNetworksCursorCodec(
        b"k" * 32, now=lambda: 0.0
    )
    app.dependency_overrides[get_infrastructure_networks_reader] = (
        lambda: app.state.infrastructure_networks_reader
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks", headers=HEADERS
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "infrastructure_networks_store_corrupt"
