"""Seven GET-only credit relationship routes with dual gate and cursors."""

# mypy: ignore-errors


from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.credit_relationships_analysis import (
    harvest_credit_relationships_analysis,
)
from api.credit_relationships_cursor import CreditRelationshipsCursorCodec
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.credit_relationships import (
    CREDIT_RELATIONSHIPS_ROUTE_COUNT,
    router,
)
from experiments.credit_relationships_publication import (
    compose_credit_relationships_snapshot,
)
from infrastructure.settings import Settings
from persistence.credit_relationships_filesystem import (
    create_credit_relationships_publisher,
    create_credit_relationships_reader,
)
from simulation.credit_relationships_ports import (
    credit_relationships_query_fingerprint,
)
from tests.unit.credit_relationships_analysis_helpers import frame, talked

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-credit-api"

PATHS = {
    "/v1/simulations/{run_id}/credit-relationships",
    "/v1/simulations/{run_id}/credit-relationships/relationships",
    "/v1/simulations/{run_id}/credit-relationships/claims",
    "/v1/simulations/{run_id}/credit-relationships/performances",
    "/v1/simulations/{run_id}/credit-relationships/distributions",
    "/v1/simulations/{run_id}/credit-relationships/counterparties",
    "/v1/simulations/{run_id}/credit-relationships/alignment",
}


def _snapshot():
    analysis = harvest_credit_relationships_analysis(
        committed_events=[
            talked(f"evt-{index}", frame(), tick=index) for index in range(4)
        ]
    )
    return compose_credit_relationships_snapshot(analysis, run_id=RUN)


def _seed(tmp_path: Path) -> None:
    create_credit_relationships_publisher(tmp_path / "store").publish(_snapshot())


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = (
        None
        if root is None
        else create_credit_relationships_reader(root / "store")
    )
    app.state.credit_relationships_reader = reader
    app.state.settings = settings
    app.state.credit_relationships_cursor_codec = (
        CreditRelationshipsCursorCodec(b"k" * 32) if reader is not None else None
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
    assert CREDIT_RELATIONSHIPS_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_disabled_without_reader() -> None:
    async with _client(None) as client:
        for path in PATHS:
            response = await client.get(path.format(run_id=RUN), headers=HEADERS)
            assert response.status_code == 503
            assert response.json()["detail"] == "credit_relationships_disabled"


@pytest.mark.asyncio
async def test_all_routes_serve_published_rows(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships", headers=HEADERS
        )
        assert summary.status_code == 200
        body = summary.json()
        assert body["digest"] == _snapshot().digest
        assert body["claim_count"] == 4
        assert body["relationship_count"] == 0
        for purpose in (
            "relationships",
            "claims",
            "performances",
            "distributions",
            "counterparties",
            "alignment",
        ):
            response = await client.get(
                f"/v1/simulations/{RUN}/credit-relationships/{purpose}",
                headers=HEADERS,
            )
            assert response.status_code == 200
            assert "rows" in response.json()


@pytest.mark.asyncio
async def test_missing_run_is_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(
            "/v1/simulations/absent/credit-relationships", headers=HEADERS
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_corrupt_store_is_500(tmp_path: Path) -> None:
    _seed(tmp_path)
    state = json.loads((tmp_path / "store" / RUN / "state.json").read_text())
    publication = next(iter(state["publications"]))
    (tmp_path / "store" / RUN / f"{publication}.json").write_bytes(b"bad")
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships", headers=HEADERS
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "credit_relationships_store_corrupt"


@pytest.mark.asyncio
async def test_invalid_cursor_and_window_mismatch_are_400(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        invalid = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships/claims?cursor=bad",
            headers=HEADERS,
        )
        assert invalid.status_code == 400
    snapshot = _snapshot()
    codec = CreditRelationshipsCursorCodec(b"k" * 32)
    token = codec.encode(
        purpose="claims",
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=credit_relationships_query_fingerprint(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            purpose="claims",
            filters={"window_index": 0},
            limit=100,
        ),
        after_key=json.dumps(["x"]),
    )
    async with _client(tmp_path) as client:
        mismatch = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships/claims"
            f"?cursor={token}&window_index=1",
            headers=HEADERS,
        )
    assert mismatch.status_code == 400


@pytest.mark.asyncio
async def test_limit_and_window_bounds(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        too_large = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships/claims?limit=501",
            headers=HEADERS,
        )
        too_high = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships/claims?window_index=512",
            headers=HEADERS,
        )
        maximum = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships/claims?limit=500",
            headers=HEADERS,
        )
    assert too_large.status_code == 422
    assert too_high.status_code == 422
    assert maximum.status_code == 200


@pytest.mark.asyncio
async def test_page_exposes_next_cursor_when_full(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships/claims?limit=1",
            headers=HEADERS,
        )
    body = response.json()
    assert response.status_code == 200
    assert len(body["rows"]) == 1
    assert body["next_cursor"] is not None
