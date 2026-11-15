# mypy: ignore-errors
"""Integration round-trip for the economic-cascade store and API."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from tests.unit.test_economic_cascades_analysis import (
    _harvest_events,
    _recipes,
    _stage,
)

from analysis.economic_cascades_analysis import harvest_economic_cascades_analysis
from api.dependencies import get_settings
from api.economic_cascades_cursor import EconomicCascadesCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.economic_cascades import router
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

pytestmark = pytest.mark.integration

TOKEN = "integration-debug-token-0123456789"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-economic-cascades-integration"


def _snapshot():
    analysis = harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
    )
    return compose_economic_cascades_snapshot(analysis, run_id=RUN)


def _client(root: Path, *, enabled: bool = True) -> httpx.AsyncClient:
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    app.state.economic_cascades_reader = (
        economic_cascades_store_reader(root) if enabled else None
    )
    app.state.economic_cascades_cursor_codec = (
        EconomicCascadesCursorCodec(b"k" * 32) if enabled else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_publish_then_read_all_seven_routes(tmp_path: Path) -> None:
    snapshot = _snapshot()
    assert (
        economic_cascades_store_publisher(tmp_path).publish(snapshot).stored
        is True
    )
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["digest"] == snapshot.internal_digest
        for purpose in (
            "disruptions",
            "dependencies",
            "chains",
            "propagation",
            "windows",
            "coverage",
        ):
            response = await client.get(
                f"/v1/simulations/{RUN}/economic-cascades/{purpose}",
                headers=HEADERS,
            )
            assert response.status_code == 200, purpose
        filtered = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades/chains",
            headers=HEADERS,
            params={"window_index": 0},
        )
        assert filtered.status_code == 200


@pytest.mark.asyncio
async def test_dual_gate_fails_closed(tmp_path: Path) -> None:
    economic_cascades_store_publisher(tmp_path).publish(_snapshot())
    async with _client(tmp_path, enabled=False) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["code"] == "economic_cascades_disabled"


@pytest.mark.asyncio
async def test_corrupt_store_and_cursor_mismatch(tmp_path: Path) -> None:
    snapshot = _snapshot()
    economic_cascades_store_publisher(tmp_path).publish(snapshot)
    async with _client(tmp_path) as client:
        codec = EconomicCascadesCursorCodec(b"k" * 32)
        fingerprint = economic_cascades_query_fingerprint(
            run_id=RUN,
            publication_id=snapshot.publication_id,
            digest=snapshot.internal_digest,
            purpose="chains",
            window_index=1,
            limit=1,
        )
        cursor = codec.encode(
            purpose="chains",
            run_id=RUN,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.internal_digest,
            query_fingerprint=fingerprint,
            after_key="0001|casc-1",
        )
        mismatched = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades/chains",
            headers=HEADERS,
            params={"limit": 1, "window_index": 0, "cursor": cursor},
        )
        assert mismatched.status_code == 400

    (tmp_path / RUN / "state.json").write_text("{not-json")
    async with _client(tmp_path) as client:
        corrupt = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
    assert corrupt.status_code == 500
    assert corrupt.json()["code"] == "economic_cascades_store_corrupt"
