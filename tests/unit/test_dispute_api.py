"""V4-07 GET-only dispute API: auth, disabled state, paging, cursors, size."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.app import _attach_dispute_reader
from api.dependencies import get_dispute_reader, get_settings
from api.dispute_cursor import DisputeCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.dispute import router
from api.routes.formal_rule import router as formal_rule_router
from api.routes.organization import router as organization_router
from infrastructure.settings import Settings
from persistence.dispute_filesystem import (
    create_dispute_publisher,
    create_dispute_reader,
)
from simulation import (
    DisputePublication,
    DisputeSnapshot,
    compute_dispute_publication_id,
    encode_dispute_snapshot,
    finalize_dispute_snapshot,
)
from tests.unit.test_dispute_snapshot import _snapshot as _base_snapshot

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-dispute-api"
OTHER_RUN = "run-dispute-api-other"
CANDIDATE = "disp-0123456789abcdef"
OTHER_CANDIDATE = "disp-fedcba9876543210"

DISPUTE_PATHS = {
    "/v1/simulations/{run_id}/disputes",
    "/v1/simulations/{run_id}/disputes/candidates",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}/claims",
    "/v1/simulations/{run_id}/disputes/candidates/{candidate_id}/resolutions",
    "/v1/simulations/{run_id}/disputes/lineage",
}


def _fixture_snapshot(run_id: str = RUN) -> DisputeSnapshot:
    base = _base_snapshot()
    renamed = replace(base, ref=replace(base.ref, run_id=run_id))
    publication_id = compute_dispute_publication_id(renamed)
    with_publication = replace(
        renamed, ref=replace(renamed.ref, publication_id=publication_id)
    )
    return finalize_dispute_snapshot(with_publication)


def _seed(root: Path, *, run_id: str = RUN) -> DisputeSnapshot:
    snapshot = _fixture_snapshot(run_id)
    publisher = create_dispute_publisher(root)
    assert publisher is not None
    publisher.publish(
        DisputePublication(
            run_id=snapshot.ref.run_id,
            publication_id=snapshot.ref.publication_id,
            snapshot_digest=snapshot.ref.snapshot_digest,
            payload=encode_dispute_snapshot(snapshot),
            generated_tick=snapshot.ref.generated_tick,
        )
    )
    return snapshot


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
    reader = create_dispute_reader(root)
    app.dependency_overrides[get_dispute_reader] = lambda: reader
    app.state.dispute_cursor_codec = (
        DisputeCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    app.state.dispute_reader = reader
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_six_get_routes_exist_and_no_write_methods() -> None:
    routes = [
        route for route in router.routes if getattr(route, "methods", None) is not None
    ]
    assert len(routes) == 6
    assert {cast(Any, route).path for route in routes} == DISPUTE_PATHS
    assert all(getattr(route, "methods", None) == {"GET"} for route in routes)


def test_existing_route_paths_are_unchanged() -> None:
    formal_rule_paths = {
        cast(Any, route).path
        for route in formal_rule_router.routes
        if getattr(route, "methods", None) is not None
    }
    organization_paths = {
        cast(Any, route).path
        for route in organization_router.routes
        if getattr(route, "methods", None) is not None
    }
    assert len(formal_rule_paths) == 6
    assert len(organization_paths) == 6
    assert not formal_rule_paths & DISPUTE_PATHS
    assert not organization_paths & DISPUTE_PATHS


@pytest.mark.asyncio
async def test_subjective_debug_is_required(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        missing = await client.get(f"/v1/simulations/{RUN}/disputes")
    assert missing.status_code == 401

    async with _client(tmp_path, clock=[1000.0], enable_debug=False) as client:
        denied = await client.get(f"/v1/simulations/{RUN}/disputes", headers=HEADERS)
    assert denied.status_code == 403
    assert denied.json()["code"] == "debug_disabled"


@pytest.mark.asyncio
async def test_query_string_credentials_are_rejected(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/disputes",
            params={"token": TOKEN},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "query_string_secret"


@pytest.mark.asyncio
async def test_unconfigured_reader_returns_dispute_disabled() -> None:
    async with _client(None, clock=[1000.0]) as client:
        response = await client.get(f"/v1/simulations/{RUN}/disputes", headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["code"] == "dispute_disabled"


@pytest.mark.asyncio
async def test_summary_and_paged_payloads(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        summary = await client.get(f"/v1/simulations/{RUN}/disputes", headers=HEADERS)
        assert summary.status_code == 200
        body = summary.json()
        assert body["candidate_count"] == 2
        assert body["claim_count"] == 2
        assert body["counterclaim_count"] == 1
        assert body["resolution_count"] == 1
        assert body["edge_count"] == 1
        assert body["coverage"]["observed"] == 1
        assert body["snapshot_digest"]

        candidates = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates", headers=HEADERS
        )
        assert candidates.status_code == 200
        assert [item["candidate_id"] for item in candidates.json()["items"]] == [
            CANDIDATE,
            OTHER_CANDIDATE,
        ]

        detail = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates/{CANDIDATE}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        detail_body = detail.json()
        assert detail_body["candidate"]["candidate_id"] == CANDIDATE
        assert detail_body["candidate"]["claim_count"] == 2
        assert detail_body["coverage"]["expected"] == 1
        assert detail_body["candidate"]["coverage"]["expected"] == 1
        assert [row["speaker_id"] for row in detail_body["testimony"]] == ["agent-1"]
        assert [row["reference_kind"] for row in detail_body["evidence"]] == [
            "observed_occurrence"
        ]
        assert [row["status"] for row in detail_body["rule_references"]] == ["resolved"]
        assert [
            row["authority_kind"] for row in detail_body["authority_references"]
        ] == ["office"]
        assert [row["link_status"] for row in detail_body["mediation_references"]] == [
            "linked"
        ]
        assert [row["kind"] for row in detail_body["responses"]] == ["accept"]
        assert detail_body["truncated"] is False

        claims = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates/{CANDIDATE}/claims",
            headers=HEADERS,
            params={"role": "counterclaim"},
        )
        assert claims.status_code == 200
        assert len(claims.json()["items"]) == 1
        assert claims.json()["items"][0]["role"] == "counterclaim"
        assert claims.json()["items"][0]["candidate_id"] == CANDIDATE

        resolutions = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates/{CANDIDATE}/resolutions",
            headers=HEADERS,
            params={"status": "partially_accepted"},
        )
        assert resolutions.status_code == 200
        assert len(resolutions.json()["items"]) == 1
        assert resolutions.json()["items"][0]["accepted_party_count"] == 1

        empty = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates/{CANDIDATE}/resolutions",
            headers=HEADERS,
            params={"status": "proposed"},
        )
        assert empty.status_code == 200
        assert empty.json()["items"] == []
        assert empty.json()["next_cursor"] is None
        assert empty.json()["truncated"] is False

        lineage = await client.get(
            f"/v1/simulations/{RUN}/disputes/lineage", headers=HEADERS
        )
        assert lineage.status_code == 200
        assert len(lineage.json()["items"]) == 1
        assert lineage.json()["items"][0]["kind"] == "emerged"


@pytest.mark.asyncio
async def test_unknown_candidate_returns_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates/disp-ffffffffffffffff",
            headers=HEADERS,
        )
    assert response.status_code == 404
    assert response.json()["code"] == "dispute_not_found"


@pytest.mark.asyncio
async def test_unknown_run_returns_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            "/v1/simulations/run-missing/disputes", headers=HEADERS
        )
    assert response.status_code == 404
    assert response.json()["code"] == "dispute_not_found"


@pytest.mark.asyncio
async def test_cursor_round_trip_and_changed_filter_invalidates(
    tmp_path: Path,
) -> None:
    _seed(tmp_path)
    _seed(tmp_path, run_id=OTHER_RUN)
    async with _client(tmp_path, clock=[1000.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates",
            headers=HEADERS,
            params={"limit": 1},
        )
        assert first.status_code == 200
        assert len(first.json()["items"]) == 1
        cursor = first.json()["next_cursor"]
        assert cursor is not None

        second = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert second.status_code == 200
        assert [item["candidate_id"] for item in second.json()["items"]] == [
            OTHER_CANDIDATE
        ]

        replay = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert replay.status_code == 200
        assert replay.json() == second.json()

        changed_filter = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor, "status": "active"},
        )
        assert changed_filter.status_code == 400
        assert changed_filter.json()["code"] == "dispute_cursor_invalid"

        changed_run = await client.get(
            f"/v1/simulations/{OTHER_RUN}/disputes/candidates",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert changed_run.status_code == 400
        assert changed_run.json()["code"] == "dispute_cursor_invalid"

        claims_first = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates/{CANDIDATE}/claims",
            headers=HEADERS,
            params={"limit": 1},
        )
        claims_cursor = claims_first.json()["next_cursor"]
        assert claims_cursor is not None
        changed_candidate = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates/{OTHER_CANDIDATE}/claims",
            headers=HEADERS,
            params={"limit": 1, "cursor": claims_cursor},
        )
        assert changed_candidate.status_code == 400
        assert changed_candidate.json()["code"] == "dispute_cursor_invalid"


@pytest.mark.asyncio
async def test_expired_cursor_returns_410(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [1000.0]
    async with _client(tmp_path, clock=clock) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = first.json()["next_cursor"]
        assert cursor is not None
        clock[0] += 901
        response = await client.get(
            f"/v1/simulations/{RUN}/disputes/candidates",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
    assert response.status_code == 410
    assert response.json()["code"] == "dispute_cursor_expired"


@pytest.mark.asyncio
async def test_malformed_cursor_returns_400(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/disputes/lineage",
            headers=HEADERS,
            params={"cursor": "not-a-cursor"},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "dispute_cursor_invalid"


@pytest.mark.asyncio
async def test_oversized_response_returns_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import api.routes.dispute as route_module

    _seed(tmp_path)
    monkeypatch.setattr(route_module, "MAX_RESPONSE_BYTES", 32)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(f"/v1/simulations/{RUN}/disputes", headers=HEADERS)
    assert response.status_code == 400
    assert response.json()["code"] == "dispute_size_limit"


def test_api_does_not_import_analysis_or_experiments_producer() -> None:
    forbidden = {"analysis", "experiments", "research_runner"}
    for name in (
        "dispute_schemas.py",
        "dispute_cursor.py",
        "routes/dispute.py",
    ):
        path = ROOT / "src" / "api" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        assert not imported & forbidden, (name, sorted(imported & forbidden))


def test_bare_app_attachment_without_settings_is_optional() -> None:
    bare = FastAPI()
    _attach_dispute_reader(bare)
    assert bare.state.dispute_reader is None
    assert bare.state.dispute_cursor_codec is None

    partial = FastAPI()
    partial.state.settings = Settings(dispute_root=Path("/tmp/disputes"))
    _attach_dispute_reader(partial)
    assert partial.state.dispute_reader is None
    assert partial.state.dispute_cursor_codec is None


def test_configured_app_attachment_builds_reader(tmp_path: Path) -> None:
    app = FastAPI()
    app.state.settings = Settings(
        dispute_root=tmp_path,
        dispute_cursor_key=SecretStr("s" * 32),
    )
    _attach_dispute_reader(app)
    assert app.state.dispute_reader is not None
    assert isinstance(app.state.dispute_cursor_codec, DisputeCursorCodec)
