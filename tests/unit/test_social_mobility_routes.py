# mypy: ignore-errors
"""Seven GET-only social-mobility routes with dual gate and cursors."""

# mypy: ignore-errors

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.social_mobility import SOCIAL_MOBILITY_ROUTE_COUNT, router
from api.social_mobility_cursor import SocialMobilityCursorCodec
from experiments.social_mobility_publication import (
    compose_social_mobility_snapshot,
)
from infrastructure.settings import Settings
from persistence.social_mobility_filesystem import (
    create_social_mobility_publisher,
    create_social_mobility_reader,
)
from tests.unit.test_social_mobility_metrics import _analysis

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-social-mobility-api"

PATHS = {
    "/v1/simulations/{run_id}/social-mobility",
    "/v1/simulations/{run_id}/social-mobility/domains",
    "/v1/simulations/{run_id}/social-mobility/economy",
    "/v1/simulations/{run_id}/social-mobility/human-capital",
    "/v1/simulations/{run_id}/social-mobility/standing",
    "/v1/simulations/{run_id}/social-mobility/generations",
    "/v1/simulations/{run_id}/social-mobility/coverage",
}


def _snapshot():
    return compose_social_mobility_snapshot(_analysis(), run_id=RUN)


def _seed(tmp_path: Path) -> None:
    create_social_mobility_publisher(tmp_path / "store").publish(_snapshot())


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_social_mobility_reader(root / "store")
    app.state.social_mobility_reader = reader
    app.state.settings = settings
    app.state.social_mobility_cursor_codec = (
        SocialMobilityCursorCodec(b"k" * 32) if reader is not None else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_route_count_paths_and_all_get() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert SOCIAL_MOBILITY_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_unset_gate_returns_503_everywhere(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(None) as client:
        for path in PATHS:
            response = await client.get(path.format(run_id=RUN), headers=HEADERS)
            assert response.status_code == 503
            assert response.json()["code"] == "social_mobility_disabled"


@pytest.mark.asyncio
async def test_summary_and_domain_filters(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/social-mobility", headers=HEADERS
        )
        assert summary.status_code == 200
        body = summary.json()
        assert body["run_id"] == RUN
        assert "owner_count" in body
        assert "pair_count" in body

        domains = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/domains", headers=HEADERS
        )
        assert {row["domain"] for row in domains.json()["rows"]} == {
            "resources",
            "skills",
            "social_influence",
            "organization_roles",
            "educational_access",
            "productive_assets",
        }
        economy = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/economy", headers=HEADERS
        )
        assert {row["domain"] for row in economy.json()["rows"]} <= {
            "resources",
            "productive_assets",
        }
        human = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/human-capital", headers=HEADERS
        )
        assert {row["domain"] for row in human.json()["rows"]} <= {
            "skills",
            "educational_access",
        }
        standing = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/standing", headers=HEADERS
        )
        assert {row["domain"] for row in standing.json()["rows"]} <= {
            "social_influence",
            "organization_roles",
        }


@pytest.mark.asyncio
async def test_generations_and_coverage_routes(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        generations = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/generations", headers=HEADERS
        )
        assert generations.status_code == 200
        rows = generations.json()["rows"]
        assert any("generation_index" in row for row in rows)
        assert any("generation_lag" in row for row in rows)
        coverage = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/coverage", headers=HEADERS
        )
        assert coverage.status_code == 200
        assert coverage.json()["rows"][0]["genealogy_edge_count"] == 8


@pytest.mark.asyncio
async def test_cursor_bound_to_window_rejects_another_window(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/domains",
            headers=HEADERS,
            params={"limit": 1, "window_index": 0},
        )
        cursor = first.json()["next_cursor"]
        if cursor is None:
            pytest.skip("fixture has a single domain row window")
        mismatched = await client.get(
            f"/v1/simulations/{RUN}/social-mobility/domains",
            headers=HEADERS,
            params={"limit": 1, "window_index": 1, "cursor": cursor},
        )
        assert mismatched.status_code == 400
        assert mismatched.json()["code"] == "social_mobility_cursor_invalid"


@pytest.mark.asyncio
async def test_corrupt_store_returns_500(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "store" / RUN / "state.json").write_text("{not json", encoding="utf-8")
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/social-mobility", headers=HEADERS
        )
        assert response.status_code == 500
        assert response.json()["code"] == "social_mobility_store_corrupt"


@pytest.mark.asyncio
async def test_corrupt_snapshot_payload_returns_500(tmp_path: Path) -> None:
    _seed(tmp_path)
    state = json.loads((tmp_path / "store" / RUN / "state.json").read_text())
    publication_id = next(iter(state["publications"]))
    (tmp_path / "store" / RUN / f"{publication_id}.json").write_text(
        "{not a snapshot", encoding="utf-8"
    )
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/social-mobility", headers=HEADERS
        )
        assert response.status_code == 500
        assert response.json()["code"] == "social_mobility_store_corrupt"
