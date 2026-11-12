"""Seven GET-only accounting routes with dual gate and cursors."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.accounting_ledgers_analysis import (
    harvest_accounting_ledgers_analysis,
)
from api.accounting_ledgers_cursor import AccountingLedgersCursorCodec
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.accounting_ledgers import (
    ACCOUNTING_LEDGERS_ROUTE_COUNT,
    router,
)
from experiments.accounting_ledgers_publication import (
    compose_accounting_ledgers_snapshot,
)
from infrastructure.settings import Settings
from persistence.accounting_ledgers_filesystem import (
    create_accounting_ledgers_publisher,
    create_accounting_ledgers_reader,
)
from tests.unit.test_accounting_ledgers_events import _talked

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-accounting-api"

PATHS = {
    "/v1/simulations/{run_id}/accounting-ledgers",
    "/v1/simulations/{run_id}/accounting-ledgers/entries",
    "/v1/simulations/{run_id}/accounting-ledgers/records",
    "/v1/simulations/{run_id}/accounting-ledgers/conditions",
    "/v1/simulations/{run_id}/accounting-ledgers/flows",
    "/v1/simulations/{run_id}/accounting-ledgers/counterparties",
    "/v1/simulations/{run_id}/accounting-ledgers/alignment",
}


def _snapshot():
    analysis = harvest_accounting_ledgers_analysis(
        run_id=RUN,
        events=tuple(
            _talked(f"ev-{index}", tick=index, sequence=index)
            for index in range(4)
        ),
    )
    return compose_accounting_ledgers_snapshot(analysis, run_id=RUN)


def _seed(tmp_path: Path) -> None:
    create_accounting_ledgers_publisher(tmp_path / "store").publish(_snapshot())


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = (
        None
        if root is None
        else create_accounting_ledgers_reader(root / "store")
    )
    app.state.accounting_ledgers_reader = reader
    app.state.settings = settings
    app.state.accounting_ledgers_cursor_codec = (
        AccountingLedgersCursorCodec(b"k" * 32) if reader is not None else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_route_count_and_all_get() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert ACCOUNTING_LEDGERS_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_disabled_without_reader() -> None:
    async with _client(None) as client:
        for path in PATHS:
            response = await client.get(path.format(run_id=RUN), headers=HEADERS)
            assert response.status_code == 503
            assert response.json()["detail"] == "accounting_ledgers_disabled"


@pytest.mark.asyncio
async def test_all_routes_serve_published_rows(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/accounting-ledgers", headers=HEADERS
        )
        assert summary.status_code == 200
        body = summary.json()
        assert body["run_id"] == RUN
        assert body["entry_count"] >= 1
        for path in PATHS:
            response = await client.get(path.format(run_id=RUN), headers=HEADERS)
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_cursor_binds_purpose_and_window(tmp_path: Path) -> None:
    _seed(tmp_path)
    snapshot = _snapshot()
    codec = AccountingLedgersCursorCodec(b"k" * 32)
    from simulation.accounting_ledgers_ports import (
        accounting_ledgers_query_fingerprint,
    )

    cursor = codec.encode(
        purpose="entries",
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=accounting_ledgers_query_fingerprint(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            purpose="entries",
            limit=100,
            window_index=None,
        ),
        after_key="acce-0000000000000000",
    )
    async with _client(tmp_path) as client:
        cross_purpose = await client.get(
            f"/v1/simulations/{RUN}/accounting-ledgers/records",
            params={"cursor": cursor},
            headers=HEADERS,
        )
        assert cross_purpose.status_code == 400
        assert cross_purpose.json()["detail"] == "accounting_ledgers_cursor_invalid"
        cross_window = await client.get(
            f"/v1/simulations/{RUN}/accounting-ledgers/entries",
            params={"cursor": cursor, "window_index": 1},
            headers=HEADERS,
        )
        assert cross_window.status_code == 400


@pytest.mark.asyncio
async def test_missing_run_and_corrupt_store(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        missing = await client.get(
            "/v1/simulations/unknown/accounting-ledgers", headers=HEADERS
        )
        assert missing.status_code == 404
        assert missing.json()["detail"] == "accounting_ledgers_run_not_found"
    (tmp_path / "store" / RUN / "state.json").write_text("{bad", encoding="utf-8")
    async with _client(tmp_path) as client:
        corrupt = await client.get(
            f"/v1/simulations/{RUN}/accounting-ledgers", headers=HEADERS
        )
        assert corrupt.status_code == 500
        assert corrupt.json()["detail"] == "accounting_ledgers_store_corrupt"


@pytest.mark.asyncio
async def test_limit_and_window_bounds(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        for params in ({"limit": 0}, {"limit": 501}, {"window_index": 512}):
            response = await client.get(
                f"/v1/simulations/{RUN}/accounting-ledgers/entries",
                params=params,
                headers=HEADERS,
            )
            assert response.status_code == 422
