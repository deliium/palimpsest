# mypy: ignore-errors
"""Non-scale trade-network store and API integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_settings, get_trade_networks_reader
from api.errors import ApiError, api_error_handler
from api.routes.trade_networks import router
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
    TradeFlowCountRecord,
    TradeFlowRecord,
    TradeLocationRecord,
    TradeNetworkRecord,
    TradeNetworksSnapshot,
    TradeNetworksSummaryRecord,
)

pytestmark = pytest.mark.integration

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-trade-integration"


def _snapshot():
    flows = (TradeFlowCountRecord(flow_class="food", count=2),)
    return finalize_trade_networks_snapshot(
        TradeNetworksSnapshot(
            run_id=RUN,
            schema_version="trade-networks-snapshot-v1",
            policy_version="trade-networks.v1",
            summary=TradeNetworksSummaryRecord(
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
            ),
            corridors=tuple(
                TradeCorridorRecord(
                    corridor_id=f"trd-cor-{index:016x}",
                    window_index=window,
                    from_location_id="loc-a",
                    to_location_id="loc-b",
                    flow_counts=flows,
                    transfer_count=2,
                    coverage="complete",
                )
                for index, window in ((1, 0), (2, 0), (3, 1), (4, 1))
            ),
            flows=(
                TradeFlowRecord(
                    window_index=0,
                    flow_class="food",
                    transfer_count=2,
                    cross_location_count=2,
                    imported_count=2,
                    exported_count=2,
                    local_count=0,
                    coverage="complete",
                ),
            ),
            locations=(
                TradeLocationRecord(
                    location_id="loc-b",
                    window_index=0,
                    inflow_count=2,
                    outflow_count=0,
                    local_count=0,
                    corridor_degree=2,
                    is_major=True,
                    trade_post_present=True,
                    flow_counts=flows,
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
                    flow_counts=flows,
                    transfer_count=2,
                    society_a_to_b_count=2,
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
                    flow_counts=flows,
                    transfer_count=2,
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


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_trade_networks_reader(root)
    app.dependency_overrides[get_trade_networks_reader] = lambda: reader
    app.state.trade_networks_reader = reader
    app.state.trade_networks_cursor_codec = (
        TradeNetworksCursorCodec(b"k" * 32, now=lambda: 0.0)
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.fixture()
def published(tmp_path: Path) -> tuple[Path, Any]:
    root = tmp_path / "store"
    snapshot = _snapshot()
    create_trade_networks_publisher(root).publish(snapshot)
    return root, snapshot


@pytest.mark.asyncio
async def test_store_and_api_round_trip(
    published: tuple[Path, Any],
) -> None:
    root, snapshot = published
    assert create_trade_networks_reader(root).read_snapshot(RUN) == snapshot
    async with _client(root) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/trade-networks", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == snapshot.publication_id
        corridors = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/corridors",
            headers=HEADERS,
            params={"window_index": 1},
        )
        assert corridors.status_code == 200
        assert {row["window_index"] for row in corridors.json()["items"]} == {1}
        networks = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/networks", headers=HEADERS
        )
        row = networks.json()["items"][0]
        assert row["status"] == "continued"
        assert row["sustained"] is True
        cross = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/cross-society",
            headers=HEADERS,
        )
        assert cross.json()["items"][0]["society_b_location_id"] == "loc-b"
        locations = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/locations", headers=HEADERS
        )
        assert locations.json()["items"][0]["trade_post_present"] is True


@pytest.mark.asyncio
async def test_dual_gate_and_window_bound_cursor(
    published: tuple[Path, Any],
) -> None:
    root, _snapshot_value = published
    async with _client(None) as disabled:
        response = await disabled.get(
            f"/v1/simulations/{RUN}/trade-networks", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "trade_networks_disabled"
    async with _client(root) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/corridors",
            headers=HEADERS,
            params={"limit": 1, "window_index": 0},
        )
        cursor = first.json()["next_cursor"]
        assert cursor
        mismatched = await client.get(
            f"/v1/simulations/{RUN}/trade-networks/corridors",
            headers=HEADERS,
            params={"cursor": cursor, "limit": 1, "window_index": 1},
        )
    assert mismatched.status_code == 400
