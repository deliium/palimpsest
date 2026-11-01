"""Fifth GET route: operation pages, counts, cursors, and read-only policy."""

from __future__ import annotations

import ast
import hashlib
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
from simulation.organization_models import (
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationOperationRecord,
    OrganizationSnapshot,
)
from simulation.organization_ports import OrganizationPublication

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-operations"
ORG_A = f"org-{'a' * 16}"
ORG_B = f"org-{'b' * 16}"


def _operation(
    index: int, *, domain: str = "resource_control", contest: int = 0
) -> OrganizationOperationRecord:
    return OrganizationOperationRecord(
        operation_id=f"orgop-{index:016x}",
        domain=domain,
        act="authorize_control",
        stance="disputed" if contest else "recognized",
        authority_basis="role_belief",
        provenance_code="role_authorized",
        outcome="observed",
        command_kind="give",
        target_kind="anchor",
        anchor_kind="item",
        anchor_id=f"item-{index}",
        tick=3,
        first_tick=1,
        last_tick=9,
        support_count=1,
        contest_count=contest,
        resolved=True,
    )


def _snapshot() -> OrganizationSnapshot:
    return OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        policy_version="organization-analysis.v1",
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        publication_id="",
        coverage=OrganizationCoverage(observed=1, expected=1, ratio=1.0),
        candidates=(
            OrganizationCandidateRecord(
                organization_id=ORG_A,
                creation_tick=0,
                first_tick=0,
                last_tick=9,
                status="partial",
                temporal_scope="ongoing",
                self_identified=False,
                operations=(
                    _operation(1),
                    _operation(2, domain="storage"),
                    _operation(3, contest=2),
                ),
            ),
            OrganizationCandidateRecord(
                organization_id=ORG_B,
                creation_tick=0,
                first_tick=0,
                last_tick=9,
                status="partial",
                temporal_scope="ongoing",
                self_identified=False,
                operations=(_operation(4),),
            ),
        ),
    )


def _seed(root: Path) -> str:
    snapshot = _snapshot()
    publication_id = compute_organization_publication_id(snapshot)
    published = replace(snapshot, publication_id=publication_id)
    payload = encode_organization_snapshot(published)
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
async def test_summary_and_detail_include_operation_counts(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/organizations", headers=HEADERS
        )
        detail = await client.get(
            f"/v1/simulations/{RUN}/organizations/candidates/{ORG_A}",
            headers=HEADERS,
        )
    assert summary.status_code == 200
    assert summary.json()["operation_count"] == 4
    body = detail.json()
    assert body["operation_count"] == 3
    assert body["contested_operation_count"] == 1
    assert len(body["operations"]) == 3
    assert body["operations"][0]["operation_id"].startswith("orgop-")


@pytest.mark.asyncio
async def test_operations_route_pages_and_filters(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        page = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations",
            headers=HEADERS,
            params={"limit": 2},
        )
        domain = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations",
            headers=HEADERS,
            params={"domain": "storage"},
        )
        owned = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations",
            headers=HEADERS,
            params={"organization_id": ORG_B},
        )
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert page.json()["next_cursor"]
    assert [item["domain"] for item in domain.json()["items"]] == ["storage"]
    assert [item["operation_id"] for item in owned.json()["items"]] == [
        "orgop-0000000000000004"
    ]


@pytest.mark.asyncio
async def test_operations_route_requires_debug_capability(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        missing = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations"
        )
    assert missing.status_code == 401


@pytest.mark.asyncio
async def test_disabled_and_missing_publication_states() -> None:
    async with _client(None, clock=[1000.0]) as client:
        disabled = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations", headers=HEADERS
        )
    assert disabled.status_code == 503
    assert disabled.json()["code"] == "organization_disabled"


@pytest.mark.asyncio
async def test_missing_publication_returns_404(tmp_path: Path) -> None:
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations", headers=HEADERS
        )
    assert response.status_code == 404
    assert response.json()["code"] == "organization_publication_missing"


@pytest.mark.asyncio
async def test_cursor_filter_binding_and_expiry(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [1000.0]
    async with _client(tmp_path, clock=clock) as client:
        page = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations",
            headers=HEADERS,
            params={"limit": 1},
        )
        token = page.json()["next_cursor"]
        assert token
        reused = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations",
            headers=HEADERS,
            params={"cursor": token, "domain": "storage"},
        )
        assert reused.status_code == 400
        assert reused.json()["code"] == "organization_cursor_invalid"
        clock[0] += 901
        expired = await client.get(
            f"/v1/simulations/{RUN}/organizations/operations",
            headers=HEADERS,
            params={"cursor": token},
        )
    assert expired.status_code == 410
    assert expired.json()["code"] == "organization_cursor_expired"


def test_router_is_get_only() -> None:
    tree = ast.parse((ROOT / "src/api/routes/organization.py").read_text())
    methods = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in {"get", "post", "put", "patch", "delete"}
    }
    assert methods == {"get"}
    source = (ROOT / "src/api/routes/organization.py").read_text()
    assert "/organizations/operations" in source
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in source
