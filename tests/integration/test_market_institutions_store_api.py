"""DB-free integration: published market snapshot served by the real API app."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from tests.unit.test_market_institutions_analysis import _events

from analysis.market_institutions_analysis import (
    harvest_market_institutions_analysis,
)
from api.app import create_app
from experiments.market_institutions_publication import (
    compose_market_institutions_snapshot,
)
from infrastructure.settings import Settings
from persistence.market_institutions_filesystem import (
    create_market_institutions_publisher,
    create_market_institutions_reader,
)
from simulation.market_institutions_codec import (
    encode_market_institutions_snapshot,
)

pytestmark = pytest.mark.integration

RUN = "run-market-integration"
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}


def _settings(root: Path) -> Settings:
    return Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
        market_institutions_root=root,
        market_institutions_cursor_key=SecretStr("k" * 32),
    )


@pytest.mark.asyncio
async def test_published_snapshot_is_read_twice_and_served_read_only(
    tmp_path: Path,
) -> None:
    root = tmp_path / "market"
    analysis = harvest_market_institutions_analysis(committed_events=_events())
    snapshot = compose_market_institutions_snapshot(analysis, run_id=RUN)
    create_market_institutions_publisher(root).publish(snapshot)

    reader = create_market_institutions_reader(root)
    first = reader.read_snapshot(RUN)
    second = reader.read_snapshot(RUN)
    assert first is not None
    assert second is not None
    assert first.publication_id == second.publication_id
    assert encode_market_institutions_snapshot(first) == (
        encode_market_institutions_snapshot(second)
    )

    app = create_app(_settings(root), attach_default_manager=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/market-institutions", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["venue_count"] >= 1

        venues = await client.get(
            f"/v1/simulations/{RUN}/market-institutions/venues", headers=HEADERS
        )
        assert venues.status_code == 200
        rows = venues.json()["rows"]
        assert rows
        assert rows[0]["venue_id"] == snapshot.venues[0].venue_id

        post = await client.post(
            f"/v1/simulations/{RUN}/market-institutions", headers=HEADERS
        )
        assert post.status_code == 405
