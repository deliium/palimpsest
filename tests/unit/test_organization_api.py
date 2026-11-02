"""GET-only organization API routes: credentials, cursors, disabled state."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_organization_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.organization_cursor import OrganizationCursorCodec
from api.routes.organization import router
from infrastructure.settings import Settings
from persistence.organization_filesystem import (
    create_organization_publisher,
    create_organization_reader,
)
from simulation.organization_codec import (
    compute_organization_publication_id,
    encode_organization_snapshot,
)
from simulation.organization_ports import OrganizationPublication
from tests.unit.organization_artifact_helpers import FIRST, example_snapshot

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}


def _seed(root: Path) -> str:
    snapshot = example_snapshot()
    publication_id = compute_organization_publication_id(snapshot)
    published = replace(snapshot, publication_id=publication_id)
    payload = encode_organization_snapshot(published)
    import hashlib

    publisher = create_organization_publisher(root)
    assert publisher is not None
    publisher.publish(
        OrganizationPublication(
            run_id=published.run_id,
            publication_id=publication_id,
            snapshot_digest=hashlib.sha256(payload).hexdigest(),
            payload=payload,
            generated_tick=published.generated_tick,
        )
    )
    return publication_id


def _client(
    root: Path | None, *, clock: list[float], enable_debug: bool = True
) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=enable_debug,
        api_debug_credential=SecretStr(TOKEN) if enable_debug else None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_organization_reader(root)
    app.dependency_overrides[get_organization_reader] = lambda: reader
    app.state.organization_cursor_codec = OrganizationCursorCodec(
        b"k" * 32, now=lambda: clock[0]
    )
    app.state.organization_reader = reader
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_summary_route_returns_published_metadata(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            "/v1/simulations/run-organization-1/organizations", headers=HEADERS
        )
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] == 2
    assert body["schema_version"] == "organization-snapshot-v3"
    assert body["coverage"]["observed"] == 4


@pytest.mark.asyncio
async def test_candidate_routes(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        page = await client.get(
            "/v1/simulations/run-organization-1/organizations/candidates",
            headers=HEADERS,
            params={"limit": 10},
        )
        detail = await client.get(
            f"/v1/simulations/run-organization-1/organizations/candidates/{FIRST}",
            headers=HEADERS,
        )
        missing = await client.get(
            "/v1/simulations/run-organization-1/organizations/candidates/"
            "org-aaaaaaaaaaaaaaaa",
            headers=HEADERS,
        )
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert detail.status_code == 200
    assert detail.json()["members"][0]["member_id"] == "body-ada"
    assert len(detail.json()["structure"]) == 2
    assert missing.status_code == 404
    assert missing.json()["code"] == "organization_unknown_candidate"


@pytest.mark.asyncio
async def test_lineage_route(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            "/v1/simulations/run-organization-1/organizations/lineage",
            headers=HEADERS,
        )
    assert response.status_code == 200
    assert [item["kind"] for item in response.json()["items"]] == ["emerged"]


@pytest.mark.asyncio
async def test_missing_credential_is_unauthorized(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get("/v1/simulations/run-organization-1/organizations")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_disabled_state_is_explicit() -> None:
    async with _client(None, clock=[1000.0]) as client:
        response = await client.get(
            "/v1/simulations/run-organization-1/organizations", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["code"] == "organization_disabled"


@pytest.mark.asyncio
async def test_invalid_and_expired_cursors(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [1000.0]
    async with _client(tmp_path, clock=clock) as client:
        invalid = await client.get(
            "/v1/simulations/run-organization-1/organizations/candidates",
            headers=HEADERS,
            params={"cursor": "not-a-cursor"},
        )
        assert invalid.status_code == 400
        assert invalid.json()["code"] == "organization_cursor_invalid"

        page = await client.get(
            "/v1/simulations/run-organization-1/organizations/candidates",
            headers=HEADERS,
            params={"limit": 1},
        )
        token = page.json()["next_cursor"]
        assert token
        clock[0] += 901
        expired = await client.get(
            "/v1/simulations/run-organization-1/organizations/candidates",
            headers=HEADERS,
            params={"cursor": token},
        )
    assert expired.status_code == 410


@pytest.mark.asyncio
async def test_cursor_reused_with_a_changed_filter_is_rejected(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        page = await client.get(
            "/v1/simulations/run-organization-1/organizations/candidates",
            headers=HEADERS,
            params={"limit": 1},
        )
        token = page.json()["next_cursor"]
        reused = await client.get(
            "/v1/simulations/run-organization-1/organizations/candidates",
            headers=HEADERS,
            params={"cursor": token, "status": "partial"},
        )
    assert reused.status_code == 400
    assert reused.json()["code"] == "organization_cursor_invalid"


def test_route_module_declares_only_get() -> None:
    tree = ast.parse((ROOT / "src/api/routes/organization.py").read_text())
    methods = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in {"get", "post", "put", "patch", "delete"}
    }
    assert methods == {"get"}


def test_api_modules_do_not_import_analysis_or_cognition() -> None:
    for path in (
        ROOT / "src/api/routes/organization.py",
        ROOT / "src/api/organization_schemas.py",
        ROOT / "src/api/organization_cursor.py",
    ):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith(
                    ("analysis", "experiments", "agents.cognition")
                )
