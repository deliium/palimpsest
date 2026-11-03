"""V4-06 GET-only formal-rule API: auth, disabled state, paging, cursors."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_formal_rule_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.formal_rule_cursor import FormalRuleCursorCodec
from api.routes.formal_rule import router
from experiments.formal_rule_harvest import build_completed_run_formal_rule_harvest
from experiments.formal_rule_publication import (
    build_formal_rule_harvest_result,
    publish_formal_rule_snapshot,
)
from infrastructure.settings import Settings
from persistence.formal_rule_filesystem import create_formal_rule_reader
from tests.unit.formal_rule_helpers import make_ledger

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-formal-rule-api"


def _built() -> Any:
    result = SimpleNamespace(
        formal_rule_ledgers=(make_ledger(ticks=(0, 100)),),
        stop_reason="max_ticks",
        ticks_committed=100,
    )
    harvest = build_completed_run_formal_rule_harvest(
        result,
        run_id=RUN,
        input_revision="revision-1",
        generated_tick=100,
    )
    return build_formal_rule_harvest_result(harvest)


def _seed(root: Path) -> Any:
    built = _built()
    from persistence.formal_rule_filesystem import create_formal_rule_publisher

    publisher = create_formal_rule_publisher(root)
    assert publisher is not None
    publish_formal_rule_snapshot(built, publisher)
    return built


def _client(
    root: Path | None, *, clock: list[float], enable_debug: bool = True
) -> Any:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=enable_debug,
        api_debug_credential=SecretStr(TOKEN) if enable_debug else None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_formal_rule_reader(root)
    app.dependency_overrides[get_formal_rule_reader] = lambda: reader
    app.state.formal_rule_cursor_codec = (
        FormalRuleCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    app.state.formal_rule_reader = reader
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_six_get_only_routes_exist() -> None:
    routes = [
        route
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert len(routes) == 6
    assert {cast(Any, route).path for route in routes} == {
        "/v1/simulations/{run_id}/formal-rules",
        "/v1/simulations/{run_id}/formal-rules/candidates",
        "/v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}",
        "/v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/rules",
        "/v1/simulations/{run_id}/formal-rules/candidates/{candidate_id}/versions",
        "/v1/simulations/{run_id}/formal-rules/lineage",
    }
    assert all(
        getattr(route, "methods", None) == {"GET"} for route in routes
    )


def test_router_is_registered_exactly_once() -> None:
    paths = [cast(Any, route).path for route in router.routes]
    assert len(paths) == len(set(paths))


@pytest.mark.asyncio
async def test_every_route_requires_subjective_debug(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(
        tmp_path, clock=[1000.0], enable_debug=False
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/formal-rules"
        )
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_unset_root_returns_503_formal_rule_disabled() -> None:
    async with _client(None, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/formal-rules", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["code"] == "formal_rule_disabled"


@pytest.mark.asyncio
async def test_response_bytes_are_charged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import api.routes.formal_rule as route_module

    _seed(tmp_path)
    monkeypatch.setattr(route_module, "MAX_RESPONSE_BYTES", 32)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/formal-rules", headers=HEADERS
        )
    assert response.status_code == 400
    assert response.json()["code"] == "formal_rule_size_limit"


def test_unset_secret_clears_reader_and_cursor_codec() -> None:
    from api.app import _attach_formal_rule_reader

    app = FastAPI()
    app.state.settings = Settings(formal_rule_root=Path("/tmp/formal"))
    _attach_formal_rule_reader(app)
    assert app.state.formal_rule_reader is None
    assert app.state.formal_rule_cursor_codec is None


@pytest.mark.asyncio
async def test_summary_and_candidate_pages_are_bounded(tmp_path: Path) -> None:
    built = _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/formal-rules", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == built.publication_id

        page = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates",
            headers=HEADERS,
            params={"limit": 1},
        )
        assert page.status_code == 200
        assert len(page.json()["items"]) == 1


@pytest.mark.asyncio
async def test_candidate_rules_versions_and_lineage_filters(
    tmp_path: Path,
) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        page = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates",
            headers=HEADERS,
        )
        candidate_id = page.json()["items"][0]["candidate_id"]
        detail = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates/{candidate_id}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        rules = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates/{candidate_id}/rules",
            headers=HEADERS,
        )
        assert rules.status_code == 200
        rule_id = rules.json()["items"][0]["rule_id"]
        versions = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates/{candidate_id}/versions",
            headers=HEADERS,
            params={"rule_id": rule_id},
        )
        assert versions.status_code == 200
        assert len(versions.json()["items"]) == 2
        lineage = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/lineage", headers=HEADERS
        )
        assert lineage.status_code == 200


@pytest.mark.asyncio
async def test_unknown_candidate_returns_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/formal-rules/candidates/"
            "frule-ffffffffffffffff",
            headers=HEADERS,
        )
    assert response.status_code == 404


def test_api_does_not_import_analysis_or_experiments() -> None:
    for name in (
        "formal_rule_schemas.py",
        "formal_rule_cursor.py",
        "routes/formal_rule.py",
    ):
        path = ROOT / "src" / "api" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        assert not imported & {"analysis", "experiments"}
