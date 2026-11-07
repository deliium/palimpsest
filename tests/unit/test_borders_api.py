# mypy: ignore-errors
"""Read-only border API routes, schemas, and cursors."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.borders_cursor import BordersCursorCodec
from api.dependencies import get_borders_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.routes.borders import BORDERS_ROUTE_COUNT, router
from infrastructure.settings import Settings
from persistence.borders_filesystem import (
    create_borders_publisher,
    create_borders_reader,
)
from simulation.borders_codec import finalize_borders_snapshot
from simulation.borders_models import (
    BORDERS_SNAPSHOT_POLICY,
    BORDERS_SNAPSHOT_SCHEMA,
    BordersAgreementRow,
    BordersClaimRow,
    BordersPatternRow,
    BordersPhysicalRow,
    BordersSnapshot,
    BordersSummaryRow,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-borders-api"
TOK = "a" * 16

PATHS = {
    "/v1/simulations/{run_id}/borders",
    "/v1/simulations/{run_id}/borders/claims",
    "/v1/simulations/{run_id}/borders/claims/{claim_id}",
    "/v1/simulations/{run_id}/borders/agreements",
    "/v1/simulations/{run_id}/borders/agreements/{agreement_id}",
    "/v1/simulations/{run_id}/borders/control",
}


def _snapshot() -> BordersSnapshot:
    claim = BordersClaimRow(
        "bdc-" + TOK, "bown-" + TOK, "bdc-" + TOK, ("bloc-" + TOK,), (), "claimed", 0.8
    )
    agreement = BordersAgreementRow(
        "bda-" + TOK,
        "bdc-" + TOK,
        "bcp-" + TOK,
        ("passage",),
        "apparent_acceptance",
        "recognized",
    )
    physical = BordersPhysicalRow(
        "bloc-" + TOK, 0, 5, 1, 2, 0, 0, 2, "repeated_use"
    )
    pattern = BordersPatternRow(
        "bpat-" + TOK, "bdc-" + TOK, ("bloc-" + TOK,), "claim_aligned", 2, 1, 0, 0
    )
    return finalize_borders_snapshot(
        BordersSnapshot(
            schema_version=BORDERS_SNAPSHOT_SCHEMA,
            policy_version=BORDERS_SNAPSHOT_POLICY,
            catalog_version="metric-catalog-v1",
            run_id=RUN,
            publication_id="bd-pub-pending",
            digest="0" * 64,
            summary=BordersSummaryRow(
                run_id=RUN,
                publication_id="bd-pub-pending",
                digest="0" * 64,
                schema_version=BORDERS_SNAPSHOT_SCHEMA,
                policy_version=BORDERS_SNAPSHOT_POLICY,
                catalog_version="metric-catalog-v1",
                claim_count=1,
                agreement_count=1,
                physical_row_count=1,
                pattern_count=1,
            ),
            claims=(claim,),
            agreements=(agreement,),
            physical=(physical,),
            patterns=(pattern,),
        )
    )


def _seed(root: Path) -> BordersSnapshot:
    snapshot = _snapshot()
    create_borders_publisher(root / "store").publish(snapshot)
    return snapshot


def _client(root: Path | None, *, clock: list[float]) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_borders_reader(root / "store")
    app.dependency_overrides[get_borders_reader] = lambda: reader
    app.state.borders_reader = reader
    app.state.borders_cursor_codec = (
        BordersCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_exactly_six_get_routes() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert BORDERS_ROUTE_COUNT == 6
    assert len(routes) == 6
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_all_routes_require_subjective_debug(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        for path in (
            f"/v1/simulations/{RUN}/borders",
            f"/v1/simulations/{RUN}/borders/claims",
            f"/v1/simulations/{RUN}/borders/agreements",
            f"/v1/simulations/{RUN}/borders/control",
        ):
            response = await client.get(path)
            assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_unconfigured_store_returns_borders_disabled() -> None:
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/borders", headers=HEADERS
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "borders_disabled"


class _CorruptReader:
    def snapshot(self, run_id: str) -> Any:
        raise ValueError("borders_store_corrupt")


@pytest.mark.asyncio
async def test_corrupt_store_returns_stable_error() -> None:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.borders_reader = _CorruptReader()
    app.state.borders_cursor_codec = None
    app.dependency_overrides[get_borders_reader] = lambda: app.state.borders_reader
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/borders", headers=HEADERS
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "borders_store_corrupt"


@pytest.mark.asyncio
async def test_summary_pages_details_and_control_layers(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/borders", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == snapshot.publication_id
        claims = await client.get(
            f"/v1/simulations/{RUN}/borders/claims", headers=HEADERS
        )
        assert claims.status_code == 200
        assert claims.json()["items"][0]["status"] == "claimed"
        detail = await client.get(
            f"/v1/simulations/{RUN}/borders/claims/bdc-{TOK}", headers=HEADERS
        )
        assert detail.status_code == 200
        agreements = await client.get(
            f"/v1/simulations/{RUN}/borders/agreements", headers=HEADERS
        )
        assert agreements.status_code == 200
        agreement = await client.get(
            f"/v1/simulations/{RUN}/borders/agreements/bda-{TOK}",
            headers=HEADERS,
        )
        assert agreement.status_code == 200
        physical = await client.get(
            f"/v1/simulations/{RUN}/borders/control?layer=physical",
            headers=HEADERS,
        )
        assert physical.status_code == 200
        assert all(item["layer"] == "physical" for item in physical.json()["items"])
        all_rows = await client.get(
            f"/v1/simulations/{RUN}/borders/control?layer=all", headers=HEADERS
        )
        assert all_rows.status_code == 200
        assert {item["layer"] for item in all_rows.json()["items"]} == {
            "physical",
            "analytical",
        }


@pytest.mark.asyncio
async def test_unknown_publication_and_record_return_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        assert (
            await client.get("/v1/simulations/missing/borders", headers=HEADERS)
        ).status_code == 404
        assert (
            await client.get(
                f"/v1/simulations/{RUN}/borders/claims/bdc-missing",
                headers=HEADERS,
            )
        ).status_code == 404
        assert (
            await client.get(
                f"/v1/simulations/{RUN}/borders/agreements/missing",
                headers=HEADERS,
            )
        ).status_code == 404


@pytest.mark.asyncio
async def test_cursor_round_trip_and_changed_binding_400(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/borders/claims?limit=1", headers=HEADERS
        )
        cursor = first.json()["next_cursor"]
        assert cursor is None
        changed = await client.get(
            f"/v1/simulations/{RUN}/borders/claims?cursor=invalid", headers=HEADERS
        )
        assert changed.status_code == 400
        assert changed.json()["detail"] == "borders_cursor_invalid"


@pytest.mark.asyncio
async def test_no_write_method_and_no_v2_route(tmp_path: Path) -> None:
    paths = {getattr(route, "path", "") for route in router.routes}
    assert not any(path.startswith("/v2") for path in paths)
    assert all(
        getattr(route, "methods", set()) == {"GET"} for route in router.routes
    )
