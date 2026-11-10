# mypy: ignore-errors
"""DB-free supply-chain store to API round trip."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.unit.supply_chain_api_helpers import HEADERS, RUN, client, snapshot

from persistence.supply_chain_filesystem import create_supply_chain_publisher

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_publish_then_read_summary(tmp_path: Path) -> None:
    expected = snapshot()
    create_supply_chain_publisher(tmp_path / "store").publish(expected)
    async with client(tmp_path) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains", headers=HEADERS
        )
    assert response.status_code == 200
    assert response.json()["stage_count"] == 2
    assert response.json()["publication_id"] == expected.publication_id


@pytest.mark.asyncio
async def test_publish_then_page_stages(tmp_path: Path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages",
            headers=HEADERS,
            params={"limit": 1},
        )
    assert response.status_code == 200
    assert response.json()["next_cursor"]


@pytest.mark.asyncio
async def test_window_filter_round_trip(tmp_path: Path) -> None:
    create_supply_chain_publisher(tmp_path / "store").publish(snapshot())
    async with client(tmp_path) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages",
            headers=HEADERS,
            params={"window_index": 1},
        )
    assert response.status_code == 200
    assert {row["window_index"] for row in response.json()["items"]} == {1}


@pytest.mark.asyncio
async def test_disabled_gate_returns_503() -> None:
    async with client(None) as api:
        response = await api.get(
            f"/v1/simulations/{RUN}/supply-chains/stages", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "supply_chains_disabled"
