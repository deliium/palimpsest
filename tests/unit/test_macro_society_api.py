"""GET-only macro-society API routes: credentials, cursors, disabled state."""

from __future__ import annotations

import ast
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.macro_society_contract import MacroSocietyLane
from analysis.macro_society_evidence import MacroSocietyEdge, MacroSocietyWindowEvidence
from api.dependencies import get_macro_society_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.macro_society_cursor import MacroSocietyCursorCodec
from api.routes.macro_society import router
from experiments.macro_society_publication import (
    MacroSocietyHarvest,
    build_macro_society_harvest_result,
)
from infrastructure.settings import Settings
from persistence.macro_society_filesystem import (
    create_macro_society_publisher,
    create_macro_society_reader,
)
from simulation.macro_society_codec import encode_macro_society_snapshot
from simulation.macro_society_ports import MacroSocietyPublication

ROOT = Path(__file__).resolve().parents[2]
PERSONS = tuple(f"person-{index}" for index in range(1, 9))
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}


def _seed(root: Path, *, generated_tick: int = 9) -> str:
    edges = tuple(
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, source, target, 0)
        for index, source in enumerate(PERSONS[:4])
        for target in PERSONS[:4][index + 1 :]
    )
    harvest = MacroSocietyHarvest(
        run_id="run-1",
        input_revision="rev-1",
        windows=(
            MacroSocietyWindowEvidence(
                window_index=0,
                tick_start=0,
                tick_end=9,
                person_ids=PERSONS,
                edges=edges,
            ),
        ),
        objective_rows=(
            {"region_id": "region-a", "tick": 0, "population_count": 8},
        ),
        generated_tick=generated_tick,
    )
    result = build_macro_society_harvest_result(harvest)
    publisher = create_macro_society_publisher(root)
    assert publisher is not None
    publisher.publish(
        MacroSocietyPublication(
            snapshot=result.snapshot,
            payload=encode_macro_society_snapshot(result.snapshot),
            created_at_utc="2026-10-30T00:00:00Z",
        )
    )
    return result.snapshot.candidates[0].macro_society_id


def _client(root: Path | None, *, clock: list[float]) -> tuple:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_macro_society_reader(root)
    app.dependency_overrides[get_macro_society_reader] = lambda: reader
    app.state.macro_society_cursor_codec = MacroSocietyCursorCodec(
        b"k" * 32, now=lambda: clock[0]
    )
    app.state.macro_society_reader = reader
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    return app, client


def _clock() -> list[float]:
    return [1000.0]


@pytest.mark.asyncio
async def test_summary_route_returns_published_metadata(tmp_path) -> None:
    _seed(tmp_path)
    _, client = _client(tmp_path, clock=_clock())
    async with client:
        response = await client.get(
            "/v1/simulations/run-1/macro-societies", headers=HEADERS
        )
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] == 1
    assert body["window_count"] == 1
    assert body["schema_version"] == "macro-society-snapshot-v1"


@pytest.mark.asyncio
async def test_candidates_and_candidate_routes(tmp_path) -> None:
    macro_id = _seed(tmp_path)
    _, client = _client(tmp_path, clock=_clock())
    async with client:
        page = await client.get(
            "/v1/simulations/run-1/macro-societies/candidates",
            headers=HEADERS,
            params={"limit": 10},
        )
        detail = await client.get(
            f"/v1/simulations/run-1/macro-societies/candidates/{macro_id}",
            headers=HEADERS,
        )
    assert page.status_code == 200
    items = page.json()["items"]
    assert len(items) == 1
    assert items[0]["macro_society_id"] == macro_id
    assert detail.status_code == 200
    assert detail.json()["member_ids"] == list(PERSONS[:4])


@pytest.mark.asyncio
async def test_lineage_route_returns_emergence(tmp_path) -> None:
    _seed(tmp_path)
    _, client = _client(tmp_path, clock=_clock())
    async with client:
        response = await client.get(
            "/v1/simulations/run-1/macro-societies/lineage", headers=HEADERS
        )
    assert response.status_code == 200
    kinds = [item["kind"] for item in response.json()["items"]]
    assert kinds == ["emerged"]


@pytest.mark.asyncio
async def test_missing_credential_is_rejected(tmp_path) -> None:
    _seed(tmp_path)
    _, client = _client(tmp_path, clock=_clock())
    async with client:
        response = await client.get("/v1/simulations/run-1/macro-societies")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_disabled_reader_returns_503() -> None:
    _, client = _client(None, clock=_clock())
    async with client:
        response = await client.get(
            "/v1/simulations/run-1/macro-societies", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.headers["x-palimpsest-error-code"] == "macro_society_disabled"


@pytest.mark.asyncio
async def test_unknown_candidate_returns_404(tmp_path) -> None:
    _seed(tmp_path)
    _, client = _client(tmp_path, clock=_clock())
    async with client:
        response = await client.get(
            "/v1/simulations/run-1/macro-societies/candidates/msoc-0000000000000000",
            headers=HEADERS,
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_and_expired_cursor_are_distinguished(tmp_path) -> None:
    _seed(tmp_path)
    clock = _clock()
    app, client = _client(tmp_path, clock=clock)
    codec = app.state.macro_society_cursor_codec
    token = codec.encode(
        purpose="candidates",
        run_id="run-1",
        publication_id="msoc-edge-0123456789abcdef",
        snapshot_digest="a" * 64,
        offset=1,
        query_fingerprint="b" * 64,
    )
    async with client:
        bad = await client.get(
            "/v1/simulations/run-1/macro-societies/candidates",
            headers=HEADERS,
            params={"cursor": "not-a-cursor"},
        )
        assert bad.status_code == 400
        clock[0] = 10_000
        expired = await client.get(
            "/v1/simulations/run-1/macro-societies/candidates",
            headers=HEADERS,
            params={"cursor": token},
        )
    assert expired.status_code == 410


@pytest.mark.asyncio
async def test_route_module_is_get_only() -> None:
    path = ROOT / "src" / "api" / "routes" / "macro_society.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    methods = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "router"
    ]
    assert methods == ["get", "get", "get", "get"]
