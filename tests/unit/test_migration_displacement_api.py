# mypy: ignore-errors
"""Read-only migration-displacement API routes, schemas, and cursors."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from api.dependencies import get_migration_displacement_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.migration_displacement_cursor import MigrationDisplacementCursorCodec
from api.migration_displacement_schemas import (
    MigrationCauseOut,
    MigrationDisplacementSummaryOut,
    MigrationOutcomeOut,
    MigrationRouteOut,
    MigrationWaveDetailOut,
    MigrationWaveOut,
)
from api.routes.migration_displacement import (
    MIGRATION_DISPLACEMENT_ROUTE_COUNT,
    router,
)
from infrastructure.settings import Settings
from persistence.migration_displacement_filesystem import (
    create_migration_displacement_publisher,
    create_migration_displacement_reader,
)
from simulation.migration_displacement_codec import (
    finalize_migration_displacement_snapshot,
)
from simulation.migration_displacement_models import (
    MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
    MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
    MigrationCauseSnapshotRow,
    MigrationDisplacementSnapshot,
    MigrationDisplacementSummaryRow,
    MigrationOutcomeSnapshotRow,
    MigrationRouteSnapshotRow,
    MigrationWaveSnapshotRow,
    empty_migration_displacement_snapshot,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-migration-api"
TOK = "a" * 16

PATHS = {
    "/v1/simulations/{run_id}/migration",
    "/v1/simulations/{run_id}/migration/waves",
    "/v1/simulations/{run_id}/migration/waves/{wave_id}",
    "/v1/simulations/{run_id}/migration/routes",
    "/v1/simulations/{run_id}/migration/causes",
    "/v1/simulations/{run_id}/migration/outcomes",
}

FORBIDDEN_FIELD_NAMES = {
    "refugee",
    "asylum",
    "forced",
    "wellbeing",
    "assimilation",
    "score",
    "composite",
}


def _wave(token: str, *, start: int = 0, classification: str = "unknown") -> MigrationWaveSnapshotRow:
    return MigrationWaveSnapshotRow(
        wave_token=f"mig-{token}",
        origin_token="mdl-origin",
        destination_token="mdl-dest",
        participant_tokens=("mdo-1", "mdo-2"),
        route_tokens=("mdl-origin", "mdl-dest"),
        start_tick=start,
        end_tick=start + 2,
        cause_support_counts=(("conflict", 1),) if classification == "displacement_like" else (),
        displacement_classification=classification,
        displacement_bases=("conflict",) if classification == "displacement_like" else (),
        independent_cause_count=1 if classification == "displacement_like" else 0,
        cluster_tokens=("mdc-1",),
        coverage="complete",
    )


def _route(token: str, *, tick: int = 0) -> MigrationRouteSnapshotRow:
    return MigrationRouteSnapshotRow(
        owner_token=f"mown-{token}",
        route_token=f"mdr-{token}",
        origin_token="mdl-origin",
        destination_token="mdl-dest",
        route_tokens=("mdl-origin", "mdl-dest"),
        observed_duration_ticks=2,
        fatigue_cost=1.0,
        basis="own_journey",
        status="open",
        first_tick=tick,
        last_tick=tick + 2,
    )


def _cause(token: str, *, tick: int = 0, kind: str = "conflict") -> MigrationCauseSnapshotRow:
    return MigrationCauseSnapshotRow(
        owner_token=f"mown-{token}",
        cause_token=f"mdcse-{token}",
        cause_kind=kind,
        source_kind="direct_observation",
        anchor_token="",
        confidence=0.5,
        tick=tick,
        status="active",
    )


def _outcome(token: str, *, classification: str = "settled") -> MigrationOutcomeSnapshotRow:
    return MigrationOutcomeSnapshotRow(
        outcome_token=f"mdo-{token}",
        participant_token=f"mdp-{token}",
        destination_token="mdl-dest",
        residence_ticks=3,
        access_evidence_count=1,
        participation_evidence_count=0,
        relationship_evidence_count=0,
        conflict_evidence_count=0,
        classification=classification,
        coverage="complete",
        censored=False,
    )


def _snapshot() -> MigrationDisplacementSnapshot:
    waves = (
        _wave("waveaaaaaaaaaaaa", start=0, classification="displacement_like"),
        _wave("wavebbbbbbbbbbbb", start=1, classification="unknown"),
    )
    routes = (_route("routeaaaaaaaaaaa", tick=0), _route("routebbbbbbbbbbb", tick=1))
    causes = (
        _cause("causeaaaaaaaaaaa", tick=0, kind="conflict"),
        _cause("causebbbbbbbbbbb", tick=1, kind="opportunity"),
    )
    outcomes = (
        _outcome("outcomeaaaaaaaa", classification="settled"),
        _outcome("outcomebbbbbbbb", classification="returned"),
    )
    base = empty_migration_displacement_snapshot(
        RUN, digest="", publication_id=""
    )
    summary = replace(
        base.summary,
        wave_count=2,
        cause_count=2,
        outcome_count=2,
        movement_count=0,
        cluster_count=0,
        candidate_count=0,
        displacement_like_count=1,
        unknown_count=1,
        integration_settled_count=1,
        integration_returned_count=1,
        coverage="complete",
    )
    return finalize_migration_displacement_snapshot(
        MigrationDisplacementSnapshot(
            summary=summary,
            waves=waves,
            routes=routes,
            causes=causes,
            outcomes=outcomes,
            digest="",
            publication_id="",
            schema_version=MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
            policy_version=MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
        )
    )


def _seed(root: Path) -> MigrationDisplacementSnapshot:
    snapshot = _snapshot()
    create_migration_displacement_publisher(root / "store").publish(snapshot)
    return snapshot


def _client(root: Path | None, *, clock: list[float]) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_migration_displacement_reader(root / "store")
    app.dependency_overrides[get_migration_displacement_reader] = lambda: reader
    app.state.migration_displacement_reader = reader
    app.state.migration_displacement_cursor_codec = (
        MigrationDisplacementCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_six_get_routes_exist() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert MIGRATION_DISPLACEMENT_ROUTE_COUNT == 6
    assert len(routes) == 6
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_subjective_debug_is_required(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        for path in (
            f"/v1/simulations/{RUN}/migration",
            f"/v1/simulations/{RUN}/migration/waves",
            f"/v1/simulations/{RUN}/migration/routes",
            f"/v1/simulations/{RUN}/migration/causes",
            f"/v1/simulations/{RUN}/migration/outcomes",
        ):
            response = await client.get(path)
            assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_unset_reader_is_503_disabled() -> None:
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/migration", headers=HEADERS
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "migration_displacement_disabled"


class _CorruptReader:
    def read_snapshot(self, run_id: str) -> Any:
        raise ValueError("migration_displacement_store_corrupt")


@pytest.mark.asyncio
async def test_corrupt_store_is_500_not_404() -> None:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.migration_displacement_reader = _CorruptReader()
    app.state.migration_displacement_cursor_codec = MigrationDisplacementCursorCodec(
        b"k" * 32, now=lambda: 0.0
    )
    app.dependency_overrides[get_migration_displacement_reader] = (
        lambda: app.state.migration_displacement_reader
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/migration", headers=HEADERS
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "migration_displacement_store_corrupt"


@pytest.mark.asyncio
async def test_summary_and_pages_return_tokens_only(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/migration", headers=HEADERS
        )
        assert summary.status_code == 200
        body = summary.json()
        assert body["publication_id"] == snapshot.publication_id
        assert body["wave_count"] == 2
        assert "refugee" not in body
        waves = await client.get(
            f"/v1/simulations/{RUN}/migration/waves", headers=HEADERS
        )
        assert waves.status_code == 200
        wave_item = waves.json()["items"][0]
        assert "wave_token" in wave_item
        assert "participant_tokens" in wave_item
        detail = await client.get(
            f"/v1/simulations/{RUN}/migration/waves/{wave_item['wave_token']}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        assert "lineage_tokens" in detail.json()
        routes = await client.get(
            f"/v1/simulations/{RUN}/migration/routes", headers=HEADERS
        )
        assert routes.status_code == 200
        assert routes.json()["items"][0]["route_token"].startswith("mdr-")
        causes = await client.get(
            f"/v1/simulations/{RUN}/migration/causes", headers=HEADERS
        )
        assert causes.status_code == 200
        assert causes.json()["items"][0]["cause_kind"] in {
            "conflict",
            "opportunity",
        }
        outcomes = await client.get(
            f"/v1/simulations/{RUN}/migration/outcomes", headers=HEADERS
        )
        assert outcomes.status_code == 200
        assert outcomes.json()["items"][0]["classification"] in {
            "settled",
            "returned",
        }


@pytest.mark.asyncio
async def test_unknown_run_or_wave_is_404(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        missing_run = await client.get(
            "/v1/simulations/missing/migration", headers=HEADERS
        )
        assert missing_run.status_code == 404
        assert missing_run.json()["detail"] == "migration_displacement_not_found"
        missing_wave = await client.get(
            f"/v1/simulations/{RUN}/migration/waves/mig-missing",
            headers=HEADERS,
        )
        assert missing_wave.status_code == 404
        assert missing_wave.json()["detail"] == "migration_displacement_not_found"


@pytest.mark.asyncio
async def test_cursor_reuse_succeeds_for_same_binding(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?limit=1", headers=HEADERS
        )
        assert first.status_code == 200
        cursor = first.json()["next_cursor"]
        assert cursor is not None
        second = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?limit=1&cursor={cursor}",
            headers=HEADERS,
        )
        assert second.status_code == 200
        assert len(second.json()["items"]) == 1
        assert (
            second.json()["items"][0]["wave_token"]
            != first.json()["items"][0]["wave_token"]
        )


@pytest.mark.asyncio
async def test_cursor_mismatch_is_400_and_expiry_is_410(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?limit=1", headers=HEADERS
        )
        cursor = first.json()["next_cursor"]
        assert cursor is not None
        bad = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?cursor=invalid",
            headers=HEADERS,
        )
        assert bad.status_code == 400
        assert bad.json()["detail"] == "migration_displacement_cursor_invalid"
        changed = await client.get(
            f"/v1/simulations/{RUN}/migration/causes?cursor={cursor}",
            headers=HEADERS,
        )
        assert changed.status_code == 400
        assert changed.json()["detail"] == "migration_displacement_cursor_invalid"
        clock[0] = 10_000.0
        expired = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?limit=1&cursor={cursor}",
            headers=HEADERS,
        )
        assert expired.status_code == 410
        assert expired.json()["detail"] == "migration_displacement_cursor_expired"


@pytest.mark.asyncio
async def test_limit_and_filter_validation(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        bad_limit = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?limit=0", headers=HEADERS
        )
        assert bad_limit.status_code == 422
        too_large = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?limit=501", headers=HEADERS
        )
        assert too_large.status_code == 422
        bad_class = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?classification=refugee",
            headers=HEADERS,
        )
        assert bad_class.status_code == 422
        ok = await client.get(
            f"/v1/simulations/{RUN}/migration/waves?classification=displacement_like",
            headers=HEADERS,
        )
        assert ok.status_code == 200
        assert all(
            item["displacement_classification"] == "displacement_like"
            for item in ok.json()["items"]
        )
        causes = await client.get(
            f"/v1/simulations/{RUN}/migration/causes?cause_kind=conflict",
            headers=HEADERS,
        )
        assert causes.status_code == 200
        assert all(item["cause_kind"] == "conflict" for item in causes.json()["items"])


def test_no_refugee_or_score_field_in_schemas() -> None:
    models = (
        MigrationDisplacementSummaryOut,
        MigrationWaveOut,
        MigrationWaveDetailOut,
        MigrationRouteOut,
        MigrationCauseOut,
        MigrationOutcomeOut,
    )
    for model in models:
        names = set(model.model_fields)
        assert names.isdisjoint(FORBIDDEN_FIELD_NAMES)
