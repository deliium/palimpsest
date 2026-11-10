# mypy: ignore-errors
"""Read-only trade-network API routes and dual-gate 503."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_settings, get_trade_networks_reader
from api.errors import ApiError, api_error_handler
from api.routes.trade_networks import TRADE_NETWORKS_ROUTE_COUNT, router
from api.trade_networks_cursor import TradeNetworksCursorCodec
from infrastructure.settings import Settings
from persistence.trade_networks_filesystem import (
    create_trade_networks_publisher,
    create_trade_networks_reader,
)
from simulation.trade_networks_codec import finalize_trade_networks_snapshot
from simulation.trade_networks_models import (
    CrossSocietyTradeRecord,
    TradeCorridorRecord,
    TradeDependenceRecord,
    TradeFlowCountRecord,
    TradeFlowRecord,
    TradeLocationRecord,
    TradeNetworkRecord,
    TradeNetworksSnapshot,
    TradeNetworksSummaryRecord,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-trade-api"

PATHS = {
    "/v1/simulations/{run_id}/trade-networks",
    "/v1/simulations/{run_id}/trade-networks/corridors",
    "/v1/simulations/{run_id}/trade-networks/flows",
    "/v1/simulations/{run_id}/trade-networks/locations",
    "/v1/simulations/{run_id}/trade-networks/dependence",
    "/v1/simulations/{run_id}/trade-networks/cross-society",
    "/v1/simulations/{run_id}/trade-networks/networks",
}


def _flows(count: int = 1):
    return (TradeFlowCountRecord(flow_class="food", count=count),)


def _summary(**kwargs):
    values = dict(
        window_tick=64,
        corridor_count=2,
        flow_count=2,
        location_count=2,
        major_location_count=1,
        trade_post_location_count=1,
        network_count=1,
        cross_society_pair_count=1,
        transfer_count=4,
        emerged_count=0,
        continued_count=1,
        transformed_count=0,
        split_count=0,
        merge_count=0,
        dissolved_count=0,
        rerouted_count=0,
        sustained_network_count=1,
        lineage_edge_count=1,
        coverage="complete",
        truncated=False,
    )
    values.update(kwargs)
    return TradeNetworksSummaryRecord(**values)


def _snapshot():
    corridors = tuple(
        TradeCorridorRecord(
            corridor_id=f"trd-cor-{index:016x}",
            window_index=window,
            from_location_id="loc-a",
            to_location_id="loc-b",
            flow_counts=_flows(),
            transfer_count=1,
            coverage="complete",
        )
        for index, window in ((1, 0), (2, 0), (3, 1), (4, 1))
    )
    return finalize_trade_networks_snapshot(
        TradeNetworksSnapshot(
            run_id=RUN,
            schema_version="trade-networks-snapshot-v1",
            policy_version="trade-networks.v1",
            summary=_summary(),
            corridors=corridors,
            flows=tuple(
                TradeFlowRecord(
                    window_index=window,
                    flow_class="food",
                    transfer_count=2,
                    cross_location_count=2,
                    imported_count=2,
                    exported_count=2,
                    local_count=0,
                    coverage="complete",
                )
                for window in (0, 1)
            ),
            locations=tuple(
                TradeLocationRecord(
                    location_id=location,
                    window_index=0,
                    inflow_count=1,
                    outflow_count=1,
                    local_count=0,
                    corridor_degree=1,
                    is_major=(location == "loc-b"),
                    trade_post_present=(location == "loc-b"),
                    flow_counts=_flows(),
                    coverage="complete",
                )
                for location in ("loc-a", "loc-b")
            ),
            dependence=(
                TradeDependenceRecord(
                    location_id="loc-b",
                    window_index=0,
                    flow_class="food",
                    imported_count=1,
                    locally_originated_count=0,
                    dependence_milli=1_000,
                    high_dependence=True,
                    coverage="complete",
                ),
            ),
            cross_society=(
                CrossSocietyTradeRecord(
                    pair_id="trd-pair-0000000000000001",
                    window_index=0,
                    society_a="msoc-aaaaaaaaaaaaaaaa",
                    society_b="msoc-bbbbbbbbbbbbbbbb",
                    society_a_location_id="loc-a",
                    society_b_location_id="loc-b",
                    overlap_member_count=0,
                    flow_counts=_flows(),
                    transfer_count=1,
                    society_a_to_b_count=1,
                    society_b_to_a_count=0,
                    coverage="complete",
                ),
            ),
            networks=(
                TradeNetworkRecord(
                    network_id="trd-net-0000000000000001",
                    window_index=0,
                    corridor_ids=("trd-cor-0000000000000001",),
                    location_ids=("loc-a", "loc-b"),
                    flow_counts=_flows(),
                    transfer_count=1,
                    status="continued",
                    previous_network_ids=("trd-net-0000000000000000",),
                    next_network_ids=(),
                    rerouted=False,
                    sustained=True,
                    coverage="complete",
                ),
            ),
        )
    )


def _seed(root: Path):
    snapshot = _snapshot()
    create_trade_networks_publisher(root / "store").publish(snapshot)
    return snapshot


def _client(root: Path | None, *, clock: list[float]) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_trade_networks_reader(root / "store")
    app.dependency_overrides[get_trade_networks_reader] = lambda: reader
    app.state.trade_networks_reader = reader
    app.state.trade_networks_cursor_codec = (
        TradeNetworksCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_route_count_is_seven_and_all_get() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert TRADE_NETWORKS_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_disabled_without_root_or_key() -> None:
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/trade-networks", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "trade_networks_disabled"


@pytest.mark.asyncio
async def test_requires_subjective_debug(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        response = await client.get(f"/v1/simulations/{RUN}/trade-networks")
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_summary_and_each_page_round_trip(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/trade-networks", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == snapshot.publication_id
        for purpose in (
            "corridors",
            "flows",
            "locations",
            "dependence",
            "cross-society",
            "networks",
        ):
            page = await client.get(
                f"/v1/simulations/{RUN}/trade-networks/{purpose}",
                headers=HEADERS,
            )
            assert page.status_code == 200, purpose
            assert len(page.json()["items"]) >= 1, purpose
        networks = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/networks", headers=HEADERS
        )
        row = networks.json()["items"][0]
        assert row["status"] == "continued"
        assert row["sustained"] is True
        assert row["previous_network_ids"] == ["trd-net-0000000000000000"]
        cross = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/cross-society",
            headers=HEADERS,
        )
        assert cross.json()["items"][0]["society_a_location_id"] == "loc-a"


@pytest.mark.asyncio
async def test_cursor_purpose_mismatch_rejected(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/corridors",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = first.json()["next_cursor"]
        assert cursor
        mismatched = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/flows",
            headers=HEADERS,
            params={"cursor": cursor, "limit": 1},
        )
    assert mismatched.status_code == 400
    assert mismatched.json()["detail"] == "trade_networks_cursor_invalid"


@pytest.mark.asyncio
async def test_window_filter_applies_to_every_paged_route(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        corridors = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/corridors",
            headers=HEADERS,
            params={"window_index": 1},
        )
        assert corridors.status_code == 200
        assert {row["window_index"] for row in corridors.json()["items"]} == {1}


@pytest.mark.asyncio
async def test_cursor_from_other_window_is_rejected(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/corridors",
            headers=HEADERS,
            params={"limit": 1, "window_index": 0},
        )
        cursor = first.json()["next_cursor"]
        assert cursor
        other = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/corridors",
            headers=HEADERS,
            params={"cursor": cursor, "limit": 1, "window_index": 1},
        )
    assert other.status_code == 400


class _CorruptReader:
    def read_snapshot(self, run_id: str) -> Any:
        raise ValueError("trade_networks_store_corrupt")


@pytest.mark.asyncio
async def test_corrupt_store_returns_safe_error() -> None:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.trade_networks_reader = _CorruptReader()
    app.state.trade_networks_cursor_codec = TradeNetworksCursorCodec(
        b"k" * 32, now=lambda: 0.0
    )
    app.dependency_overrides[get_trade_networks_reader] = lambda: (
        app.state.trade_networks_reader
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/trade-networks", headers=HEADERS
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "trade_networks_store_corrupt"


@pytest.mark.asyncio
async def test_absent_run_returns_not_found(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        response = await client.get(
            "/v1/simulations/run-absent/trade-networks", headers=HEADERS
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "trade_networks_run_not_found"
