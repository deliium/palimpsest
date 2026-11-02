"""Sixth GET route: collective-agency pages, counts, and cursors."""

from __future__ import annotations

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
    OrganizationCollectiveDecisionRecord,
    OrganizationCoverage,
    OrganizationImplementationRecord,
    OrganizationLineageEdgeRecord,
    OrganizationOperationRecord,
    OrganizationSnapshot,
)
from simulation.organization_ports import OrganizationPublication

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-agency-api"
ORG = f"org-{'a' * 16}"
DECISION = f"orgcpd-{'b' * 16}"
IMPLEMENTATION = f"orgcpi-{'c' * 16}"


def _decision(
    *,
    decision_id: str = DECISION,
    recognition: str = "recognized",
    implementation_id: str = IMPLEMENTATION,
    actor_ref: str = "f" * 16,
) -> OrganizationCollectiveDecisionRecord:
    return OrganizationCollectiveDecisionRecord(
        decision_id=decision_id,
        organization_id=ORG,
        proposal_ref="d" * 16,
        revision=1,
        procedure_ref="e" * 16,
        recognition=recognition,
        authority_basis="procedure_belief",
        support_count=1,
        oppose_count=0,
        abstain_count=0,
        contest_count=0,
        implementation_mode="physical",
        effect="give",
        target_kind="none",
        target_ref=None,
        decided_tick=6,
        window_end_tick=20,
        implementation_status="implemented",
        provenance_code="observed_effect",
        resolved=True,
        implementations=(
            OrganizationImplementationRecord(
                implementation_id=implementation_id,
                decision_id=decision_id,
                actor_ref=actor_ref,
                status="implemented",
                effect="give",
                observed_tick=7,
                provenance_code="observed_effect",
                resolved=True,
            ),
        ),
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
                organization_id=ORG,
                creation_tick=0,
                first_tick=0,
                last_tick=9,
                status="partial",
                temporal_scope="ongoing",
                self_identified=False,
                collective_decisions=(
                    _decision(),
                    _decision(
                        decision_id=f"orgcpd-{'d' * 16}",
                        recognition="contested",
                        implementation_id=f"orgcpi-{'9' * 16}",
                        actor_ref="8" * 16,
                    ),
                ),
                collective_proposal_count=1,
                collective_support_count=1,
                collective_decision_count=2,
                collective_implementation_count=2,
                contested_decision_count=1,
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
async def test_routes_are_six_get_only() -> None:
    routes = [
        route
        for route in router.routes
        if getattr(route, "path", "").startswith("/v1/simulations")
    ]
    assert len(routes) == 6
    assert all("GET" in getattr(route, "methods", set()) for route in routes)


@pytest.mark.asyncio
async def test_agency_route_returns_decisions_and_implementations(
    tmp_path: Path,
) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
        )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["decision_id"] == DECISION
    assert body["items"][0]["implementations"][0]["actor_ref"] == "f" * 16
    assert "agent-1" not in response.text


@pytest.mark.asyncio
async def test_agency_route_filters_and_summary_counts(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/organizations", headers=HEADERS
        )
        matched = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
            params={"recognition": "recognized"},
        )
        missed = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
            params={"recognition": "contested"},
        )
    assert summary.json()["collective_decision_count"] == 2
    assert summary.json()["snapshot_digest"]
    assert len(matched.json()["items"]) == 1
    assert len(missed.json()["items"]) == 1


@pytest.mark.asyncio
async def test_cursor_reuse_and_changed_filter_fails(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = first.json()["next_cursor"]
        reused = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        changed = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor, "recognition": "contested"},
        )
    assert reused.status_code == 200
    assert changed.status_code == 400
    assert changed.json()["code"] == "organization_cursor_invalid"


@pytest.mark.asyncio
async def test_candidate_detail_includes_decisions(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/organizations/candidates/{ORG}",
            headers=HEADERS,
        )
    body = response.json()
    assert body["collective_decision_count"] == 2
    assert len(body["collective_decisions"]) == 2


@pytest.mark.asyncio
async def test_disabled_reader_returns_503(tmp_path: Path) -> None:
    async with _client(None, clock=[1000.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
        )
    assert response.status_code == 503
    assert response.json()["code"] == "organization_disabled"


@pytest.mark.asyncio
async def test_requires_subjective_debug(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[1000.0], enable_debug=False) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
        )
    assert response.status_code in (401, 403)


def _paged_snapshot() -> OrganizationSnapshot:
    operations = tuple(
        OrganizationOperationRecord(
            operation_id=f"orgop-{index:016x}",
            domain="resource_control",
            act="authorize_control",
            stance="recognized",
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
            contest_count=0,
            resolved=True,
        )
        for index in range(2)
    )
    edges = tuple(
        OrganizationLineageEdgeRecord(
            kind="continued",
            tick=1,
            from_id=ORG,
            to_id=ORG,
            jaccard=1.0,
            containment=1.0,
        )
        for _ in range(2)
    )
    second = ORG.replace("a", "c")
    return OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        policy_version="organization-analysis.v1",
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        publication_id="",
        coverage=OrganizationCoverage(observed=2, expected=2, ratio=1.0),
        candidates=(
            OrganizationCandidateRecord(
                organization_id=ORG,
                creation_tick=0,
                first_tick=0,
                last_tick=9,
                status="partial",
                temporal_scope="ongoing",
                self_identified=False,
                operations=operations,
                collective_decisions=(
                    _decision(),
                    _decision(
                        decision_id=f"orgcpd-{'d' * 16}",
                        recognition="contested",
                        implementation_id=f"orgcpi-{'9' * 16}",
                        actor_ref="8" * 16,
                    ),
                ),
                collective_proposal_count=1,
                collective_support_count=1,
                collective_decision_count=2,
                collective_implementation_count=2,
                contested_decision_count=1,
            ),
            OrganizationCandidateRecord(
                organization_id=second,
                creation_tick=0,
                first_tick=0,
                last_tick=9,
                status="partial",
                temporal_scope="ongoing",
                self_identified=False,
            ),
        ),
        edges=edges,
    )


def _seed_snapshot(root: Path, snapshot: OrganizationSnapshot) -> str:
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


@pytest.mark.asyncio
async def test_every_paged_route_reuses_its_cursor(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path, _paged_snapshot())
    paths = (
        "candidates",
        "lineage",
        "operations",
        "collective-agency",
    )
    async with _client(tmp_path, clock=[1000.0]) as client:
        for path in paths:
            first = await client.get(
                f"/v1/simulations/{RUN}/organizations/{path}",
                headers=HEADERS,
                params={"limit": 1},
            )
            assert first.status_code == 200
            cursor = first.json()["next_cursor"]
            assert cursor is not None, path
            reused = await client.get(
                f"/v1/simulations/{RUN}/organizations/{path}",
                headers=HEADERS,
                params={"limit": 1, "cursor": cursor},
            )
            assert reused.status_code == 200, path


@pytest.mark.asyncio
async def test_cursor_expiry_returns_410(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [1000.0]
    async with _client(tmp_path, clock=clock) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = first.json()["next_cursor"]
        assert cursor is not None
        clock[0] += 901
        expired = await client.get(
            f"/v1/simulations/{RUN}/organizations/collective-agency",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
    assert expired.status_code == 410
    assert expired.json()["code"] == "organization_cursor_expired"
