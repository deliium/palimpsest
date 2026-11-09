"""V4-17 read-only travel-network route pages and dual gate."""

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
from api.routes.infrastructure_networks import router
from infrastructure.settings import Settings
from persistence.infrastructure_filesystem import (
    create_infrastructure_networks_publisher,
    create_infrastructure_networks_reader,
)
from simulation.infrastructure_codec import finalize_infrastructure_networks_snapshot
from simulation.infrastructure_models import (
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
    InfrastructureNetworksSnapshot,
    InfrastructureNetworksSummaryRecord,
    TravelRouteRecord,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-travel-api"
ROUTES = (
    TravelRouteRecord(
        origin_location_id="loc-a",
        destination_location_id="loc-b",
        status="open",
        seasonal_availability="open",
        blockage_cause="none",
        duration_ticks=2,
        fatigue_cost=3.0,
        capacity=8,
        risk=0.1,
        infrastructure_quality=0.5,
        as_of_tick=1,
    ),
    TravelRouteRecord(
        origin_location_id="loc-b",
        destination_location_id="loc-c",
        status="closed",
        seasonal_availability="closed",
        blockage_cause="seasonal",
        duration_ticks=4,
        fatigue_cost=5.0,
        capacity=4,
        risk=0.5,
        infrastructure_quality=0.0,
        as_of_tick=2,
    ),
)


def _seed(root: Path) -> InfrastructureNetworksSnapshot:
    snapshot = finalize_infrastructure_networks_snapshot(
        InfrastructureNetworksSnapshot(
            summary=InfrastructureNetworksSummaryRecord(
                run_id=RUN,
                publication_id="",
                digest="",
                schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
                policy_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
                asset_count=0,
                node_count=0,
                edge_count=0,
                operational_count=0,
                damaged_count=0,
                destroyed_count=0,
                effects_active_count=0,
                coverage="not_applicable",
            ),
            assets=(),
            routes=ROUTES,
        )
    )
    create_infrastructure_networks_publisher(root / "store").publish(snapshot)
    return snapshot


def _client(root: Path | None, *, clock: list[float]) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = (
        None
        if root is None
        else create_infrastructure_networks_reader(root / "store")
    )
    app.dependency_overrides[get_infrastructure_networks_reader] = lambda: reader
    app.state.infrastructure_networks_reader = reader
    app.state.infrastructure_networks_cursor_codec = InfrastructureNetworksCursorCodec(
        b"k" * 32, now=lambda: clock[0]
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_routes_page_paging_and_publication(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/routes?limit=1",
            headers=HEADERS,
        )
        assert first.status_code == 200
        body = first.json()
        assert body["items"][0]["origin_location_id"] == "loc-a"
        assert body["fingerprint"] == snapshot.digest
        assert body["publication"] == snapshot.publication_id
        assert body["next_cursor"] is not None

        second = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/routes?limit=1&cursor={body['next_cursor']}",
            headers=HEADERS,
        )
        assert second.status_code == 200
        assert second.json()["items"][0]["origin_location_id"] == "loc-b"
        assert second.json()["next_cursor"] is None


@pytest.mark.asyncio
async def test_route_cursor_is_purpose_bound_and_expiring(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/routes?limit=1",
            headers=HEADERS,
        )
        cursor = first.json()["next_cursor"]
        wrong_purpose = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/assets?limit=1&cursor={cursor}",
            headers=HEADERS,
        )
        assert wrong_purpose.status_code == 400
        clock[0] = 3600.0
        expired = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/routes?limit=1&cursor={cursor}",
            headers=HEADERS,
        )
        assert expired.status_code == 410


@pytest.mark.asyncio
async def test_routes_require_dual_gate_and_auth() -> None:
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/routes",
            headers=HEADERS,
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "infrastructure_networks_disabled"


@pytest.mark.asyncio
async def test_routes_require_subjective_debug(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/routes"
        )
        assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_route_page_has_no_write_methods() -> None:
    methods = {
        frozenset(cast(Any, route).methods or ())
        for route in router.routes
        if "routes" in cast(Any, route).path
    }
    assert methods == {frozenset({"GET"})}


class _CorruptReader:
    def read_snapshot(self, run_id: str) -> Any:
        raise ValueError("infrastructure_networks_store_corrupt")


@pytest.mark.asyncio
async def test_corrupt_route_store_is_500() -> None:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_infrastructure_networks_reader] = (
        lambda: _CorruptReader()
    )
    app.state.infrastructure_networks_reader = _CorruptReader()
    app.state.infrastructure_networks_cursor_codec = InfrastructureNetworksCursorCodec(
        b"k" * 32, now=lambda: 0.0
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/infrastructure-networks/routes",
            headers=HEADERS,
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "infrastructure_networks_store_corrupt"
