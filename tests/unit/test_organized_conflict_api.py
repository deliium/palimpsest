# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_organized_conflict_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.organized_conflict_cursor import OrganizedConflictCursorCodec
from api.routes.organized_conflict import router
from infrastructure.settings import Settings
from persistence.organized_conflict_filesystem import (
    create_organized_conflict_publisher,
    create_organized_conflict_reader,
)
from simulation.organized_conflict_codec import finalize_organized_conflict_snapshot
from simulation.organized_conflict_models import (
    ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
    OrganizedConflictEpisodeRow,
    OrganizedConflictInterpretationRow,
    OrganizedConflictPlanRow,
    OrganizedConflictSnapshot,
    OrganizedConflictSummaryRow,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-conflict-api"
HEX = "a" * 16
PATHS = {
    "/v1/simulations/{run_id}/organized-conflict",
    "/v1/simulations/{run_id}/organized-conflict/episodes",
    "/v1/simulations/{run_id}/organized-conflict/episodes/{episode_id}",
    "/v1/simulations/{run_id}/organized-conflict/plans",
    "/v1/simulations/{run_id}/organized-conflict/plans/{plan_id}",
    "/v1/simulations/{run_id}/organized-conflict/interpretations",
}


def _snapshot() -> OrganizedConflictSnapshot:
    return finalize_organized_conflict_snapshot(
        OrganizedConflictSnapshot(
            schema_version=ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
            policy_version="organized-conflict-snapshot.v1",
            run_id=RUN,
            publication_id="oc-pub-" + "0" * 16,
            digest="0" * 64,
            summary=OrganizedConflictSummaryRow(episode_count=1, plan_count=1),
            episodes=(
                OrganizedConflictEpisodeRow(
                    episode_id="oc-" + HEX,
                    classification="coordinated_conflict",
                    start_tick=1,
                    end_tick=5,
                    participant_tokens=(HEX,),
                ),
            ),
            plans=(
                OrganizedConflictPlanRow(
                    plan_id="ocp-" + HEX,
                    owner_token=HEX,
                    operation="coordinated_attack",
                    target_kind="agent",
                    status="active",
                    participant_count=1,
                    tick=1,
                ),
            ),
            interpretations=(
                OrganizedConflictInterpretationRow(
                    interpretation_id="oci-" + HEX,
                    owner_token=HEX,
                    episode_id="oc-" + HEX,
                    kind="coordinated_conflict",
                    alignment="consistent",
                    tick=1,
                ),
            ),
        )
    )


def _seed(root: Path) -> OrganizedConflictSnapshot:
    snapshot = _snapshot()
    create_organized_conflict_publisher(root / "store").publish(snapshot)
    return snapshot


def _client(root: Path | None, *, clock: list[float]) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_organized_conflict_reader(root / "store")
    app.dependency_overrides[get_organized_conflict_reader] = lambda: reader
    app.state.organized_conflict_reader = reader
    app.state.organized_conflict_cursor_codec = (
        OrganizedConflictCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_six_get_routes_are_registered() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert len(routes) == 6
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_subjective_debug_is_required_and_disabled_is_explicit(
    tmp_path: Path,
) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        assert (
            await client.get(f"/v1/simulations/{RUN}/organized-conflict")
        ).status_code in {401, 403}
        assert (
            await client.get(
                f"/v1/simulations/{RUN}/organized-conflict", headers=HEADERS
            )
        ).status_code == 200
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict", headers=HEADERS
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "organized_conflict_disabled"


@pytest.mark.asyncio
async def test_summary_pages_and_details(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == snapshot.publication_id
        episodes = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/episodes", headers=HEADERS
        )
        assert episodes.status_code == 200
        assert episodes.json()["items"][0]["classification"] == "coordinated_conflict"
        detail = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/episodes/oc-{HEX}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        plans = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/plans", headers=HEADERS
        )
        assert plans.status_code == 200
        plan_detail = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/plans/ocp-{HEX}",
            headers=HEADERS,
        )
        assert plan_detail.status_code == 200
        interpretations = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/interpretations",
            headers=HEADERS,
        )
        assert interpretations.status_code == 200
        assert interpretations.json()["items"][0]["alignment"] == "consistent"


@pytest.mark.asyncio
async def test_unknown_episode_and_plan_return_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        episode = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/episodes/oc-{'f' * 16}",
            headers=HEADERS,
        )
        assert episode.status_code == 404
        assert episode.json()["detail"] == "organized_conflict_unknown_episode"
        plan = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/plans/ocp-{'f' * 16}",
            headers=HEADERS,
        )
        assert plan.status_code == 404
        assert plan.json()["detail"] == "organized_conflict_unknown_plan"


@pytest.mark.asyncio
async def test_cursor_binding_and_expiry(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        page = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/episodes",
            headers=HEADERS,
            params={"limit": 1},
        )
        assert page.status_code == 200
        assert page.json()["next_cursor"] is None
        # Build a cursor for a different run binding and reject it.
        codec = OrganizedConflictCursorCodec(b"k" * 32, now=lambda: clock[0])
        token = codec.encode(
            purpose="episodes",
            run_id="other-run",
            publication_id="oc-pub-" + "0" * 16,
            snapshot_digest="0" * 64,
            query_fingerprint="fingerprint",
            after_key=None,
        )
        mismatch = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/episodes",
            headers=HEADERS,
            params={"cursor": token},
        )
        assert mismatch.status_code == 400
        assert mismatch.json()["detail"] == "organized_conflict_cursor_invalid"
        clock[0] = 10_000.0
        expired = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/episodes",
            headers=HEADERS,
            params={"cursor": token},
        )
        assert expired.status_code in {400, 410}


@pytest.mark.asyncio
async def test_same_binding_cursor_reuse_serves_next_page(tmp_path: Path) -> None:
    base = _snapshot()
    second = OrganizedConflictEpisodeRow(
        episode_id="oc-" + "b" * 16,
        classification="individual_violence",
        start_tick=2,
        end_tick=2,
        participant_tokens=("b" * 16,),
    )
    snapshot = finalize_organized_conflict_snapshot(
        replace(base, episodes=tuple(sorted((*base.episodes, second), key=lambda row: row.episode_id)))
    )
    create_organized_conflict_publisher(tmp_path / "store").publish(snapshot)
    async with _client(tmp_path, clock=[0.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/episodes",
            headers=HEADERS,
            params={"limit": 1},
        )
        assert first.status_code == 200
        cursor = first.json()["next_cursor"]
        assert cursor
        second_page = await client.get(
            f"/v1/simulations/{RUN}/organized-conflict/episodes",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert second_page.status_code == 200
        assert second_page.json()["items"]


def test_no_v2_routes() -> None:
    assert all("/v2/" not in route.path for route in router.routes)
