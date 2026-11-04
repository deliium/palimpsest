"""V4-08 GET-only evidence API: auth, disabled state, paging, cursors."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition import EvidenceLedger
from api.dependencies import get_evidence_testimony_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.evidence_testimony_cursor import EvidenceTestimonyCursorCodec
from api.routes.evidence_testimony import router
from experiments.evidence_testimony_harvest import (
    build_completed_run_evidence_harvest,
)
from experiments.evidence_testimony_publication import (
    build_evidence_testimony_harvest_result,
    publish_evidence_testimony_snapshot,
)
from infrastructure.settings import Settings
from persistence.evidence_testimony_filesystem import (
    create_evidence_testimony_reader,
)
from tests.unit.evidence_testimony_helpers import make_item, make_source

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-evidence-api"

EVIDENCE_PATHS = {
    "/v1/simulations/{run_id}/evidence",
    "/v1/simulations/{run_id}/evidence/candidates",
    "/v1/simulations/{run_id}/evidence/candidates/{candidate_id}",
    "/v1/simulations/{run_id}/evidence/candidates/{candidate_id}/sources",
    "/v1/simulations/{run_id}/evidence/candidates/{candidate_id}/contradictions",
    "/v1/simulations/{run_id}/evidence/lineage",
}


def _two_candidate_ledger() -> EvidenceLedger:
    first = make_source(reference_id="artifact-1", ordinal=0)
    second = make_source(reference_id="artifact-2", ordinal=1)
    first_item = make_item(source_id=first.source_id, subject="artifact-1")
    second_item = make_item(source_id=second.source_id, subject="artifact-2", ordinal=1)
    return EvidenceLedger(
        owner_id=first.owner_id,
        sources=(first, second),
        items=(first_item, second_item),
    )


class _Result:
    def __init__(self, run_id: str) -> None:
        self.evidence_ledgers = (_two_candidate_ledger(),)
        self.run_id = run_id
        self.ticks_committed = 2
        self.stop_reason = type("Stop", (), {"value": "completed"})()


def _snapshot(run_id: str = RUN) -> Any:
    harvest = build_completed_run_evidence_harvest(_Result(run_id))
    return build_evidence_testimony_harvest_result(harvest).snapshot


def _seed(root: Path, *, run_id: str = RUN) -> Any:
    result = build_evidence_testimony_harvest_result(
        build_completed_run_evidence_harvest(_Result(run_id))
    )
    publisher_root = root / "store"
    from persistence.evidence_testimony_filesystem import (
        FilesystemEvidenceTestimonyPublisher,
    )

    publish_evidence_testimony_snapshot(
        result, FilesystemEvidenceTestimonyPublisher(publisher_root)
    )
    return result.snapshot


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
    reader = create_evidence_testimony_reader(None if root is None else root / "store")
    app.dependency_overrides[get_evidence_testimony_reader] = lambda: reader
    app.state.evidence_testimony_cursor_codec = (
        EvidenceTestimonyCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    app.state.evidence_testimony_reader = reader
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_exactly_six_get_routes() -> None:
    routes: list[Any] = []
    for route in router.routes:
        if getattr(route, "methods", None) is not None:
            routes.append(cast(Any, route))
    assert len(routes) == 6
    assert {route.path for route in routes} == EVIDENCE_PATHS
    assert all(route.methods == {"GET"} for route in routes)


def test_route_module_does_not_import_analysis() -> None:
    path = ROOT / "src" / "api" / "routes" / "evidence_testimony.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(module.startswith("analysis") for module in imported)


@pytest.mark.asyncio
async def test_disabled_reader_returns_503() -> None:
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(f"/v1/simulations/{RUN}/evidence", headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["code"] == "evidence_testimony_disabled"


@pytest.mark.asyncio
async def test_requires_subjective_debug(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        response = await client.get(f"/v1/simulations/{RUN}/evidence")
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_summary_and_pages(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        summary = await client.get(f"/v1/simulations/{RUN}/evidence", headers=HEADERS)
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["source_count"] == snapshot.counts.source_count
        assert payload["schema_version"] == "evidence-testimony-snapshot-v1"

        candidates = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates",
            headers=HEADERS,
        )
        assert candidates.status_code == 200
        candidate_id = candidates.json()["items"][0]["candidate_id"]

        detail = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates/{candidate_id}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        assert detail.json()["candidate"]["candidate_id"] == candidate_id

        sources = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates/{candidate_id}/sources",
            headers=HEADERS,
        )
        assert sources.status_code == 200
        contradictions = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates/{candidate_id}/contradictions",
            headers=HEADERS,
        )
        assert contradictions.status_code == 200
        lineage = await client.get(
            f"/v1/simulations/{RUN}/evidence/lineage", headers=HEADERS
        )
        assert lineage.status_code == 200


@pytest.mark.asyncio
async def test_cursor_round_trip_and_mismatch(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates?limit=1",
            headers=HEADERS,
        )
        assert first.status_code == 200
        cursor = first.json()["next_cursor"]
        assert cursor
        second = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates?limit=1&cursor={cursor}",
            headers=HEADERS,
        )
        assert second.status_code == 200

        other = await client.get(
            f"/v1/simulations/run-other/evidence/candidates?limit=1&cursor={cursor}",
            headers=HEADERS,
        )
        assert other.status_code in {400, 404}


@pytest.mark.asyncio
async def test_expired_cursor_returns_410(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates?limit=1",
            headers=HEADERS,
        )
        cursor = first.json()["next_cursor"]
        clock[0] = 10_000.0
        expired = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates?limit=1&cursor={cursor}",
            headers=HEADERS,
        )
    assert expired.status_code == 410
    assert expired.json()["code"] == "evidence_testimony_cursor_expired"


@pytest.mark.asyncio
async def test_unknown_candidate_returns_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/evidence/candidates/evid-{'0' * 16}",
            headers=HEADERS,
        )
    assert response.status_code == 404


def test_fixture_snapshot_is_canonical() -> None:
    snapshot = _snapshot()
    assert snapshot.counts.source_count == 2
    assert snapshot.publication_id.startswith("evid-pub-")
