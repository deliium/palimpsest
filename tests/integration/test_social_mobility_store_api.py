# mypy: ignore-errors
"""Integration round-trip for the social-mobility store and API."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from tests.unit.test_social_mobility_metrics import _analysis

from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.social_mobility import router
from api.social_mobility_cursor import SocialMobilityCursorCodec
from experiments.social_mobility_publication import (
    compose_social_mobility_snapshot,
)
from infrastructure.settings import Settings
from persistence.social_mobility_filesystem import (
    create_social_mobility_publisher,
    create_social_mobility_reader,
)

pytestmark = pytest.mark.integration

TOKEN = "integration-debug-token-0123456789"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-social-mobility-integration"


def _client(root: Path, *, enabled: bool = True) -> httpx.AsyncClient:
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    app.state.social_mobility_reader = (
        create_social_mobility_reader(root) if enabled else None
    )
    app.state.social_mobility_cursor_codec = (
        SocialMobilityCursorCodec(b"k" * 32) if enabled else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_publish_then_read_through_api(tmp_path: Path) -> None:
    snapshot = compose_social_mobility_snapshot(_analysis(), run_id=RUN)
    publisher = create_social_mobility_publisher(tmp_path)
    assert publisher.publish(snapshot).stored is True
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/social-mobility", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["digest"] == snapshot.digest
        domains = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/domains", headers=HEADERS
        )
        assert domains.status_code == 200
        assert domains.json()["rows"]
        generations = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/generations", headers=HEADERS
        )
        assert generations.status_code == 200
        coverage = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/coverage", headers=HEADERS
        )
        assert coverage.status_code == 200


@pytest.mark.asyncio
async def test_dual_gate_and_cursor_mismatch(tmp_path: Path) -> None:
    snapshot = compose_social_mobility_snapshot(_analysis(), run_id=RUN)
    create_social_mobility_publisher(tmp_path).publish(snapshot)
    async with _client(tmp_path, enabled=False) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/social-mobility", headers=HEADERS
        )
        assert response.status_code == 503
        assert response.json()["code"] == "social_mobility_disabled"
    async with _client(tmp_path) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/domains",
            headers=HEADERS,
            params={"limit": 1, "window_index": 0},
        )
        cursor = first.json()["next_cursor"]
        if cursor is not None:
            mismatched = await client.get(
                f"/v1/simulations/{RUN}/social-mobility/domains",
                headers=HEADERS,
                params={"limit": 1, "window_index": 1, "cursor": cursor},
            )
            assert mismatched.status_code == 400
