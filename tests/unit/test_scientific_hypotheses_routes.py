# mypy: ignore-errors
"""Seven GET-only scientific-hypothesis routes with dual gate and cursors."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisConditionSlot,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_rows import (
    HypothesisConditionFact,
    HypothesisFact,
    HypothesisTrialFact,
)
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.scientific_hypotheses import (
    SCIENTIFIC_HYPOTHESES_ROUTE_COUNT,
    router,
)
from api.scientific_hypotheses_cursor import ScientificHypothesesCursorCodec
from experiments.scientific_hypotheses_publication import (
    compose_scientific_hypotheses_snapshot,
)
from infrastructure.settings import Settings
from persistence.scientific_hypotheses_filesystem import (
    scientific_hypotheses_store_publisher,
    scientific_hypotheses_store_reader,
)
from world.experimentation import DiscoveryMode, ExperimentOutcomeClass

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-scientific-hypotheses-api"

PATHS = {
    "/v1/simulations/{run_id}/scientific-hypotheses",
    "/v1/simulations/{run_id}/scientific-hypotheses/hypotheses",
    "/v1/simulations/{run_id}/scientific-hypotheses/evidence",
    "/v1/simulations/{run_id}/scientific-hypotheses/tests",
    "/v1/simulations/{run_id}/scientific-hypotheses/revisions",
    "/v1/simulations/{run_id}/scientific-hypotheses/sources",
    "/v1/simulations/{run_id}/scientific-hypotheses/coverage",
}


def _analysis():
    facts = tuple(
        HypothesisFact(
            owner_token=f"owner-{index}",
            hypothesis_token=f"schyp-{index}",
            claim_token=f"claim-{index}",
            causal_hypothesis_token=NONE_TOKEN,
            status=ScientificHypothesisStatus.PROVISIONAL,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
            confidence_milli=500,
            created_tick=index,
            active=True,
            source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
            source_token="self",
            conditions=(
                HypothesisConditionFact(
                    slot=ScientificHypothesisConditionSlot.LOCATION,
                    value_token="loc-1",
                ),
            ),
            revisions=(),
            trials=(
                HypothesisTrialFact(
                    tick=index,
                    event_token=f"evt:{index}",
                    outcome_class=ExperimentOutcomeClass.SUCCESS,
                    discovery_mode=DiscoveryMode.DELIBERATE,
                    predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
                    matched=True,
                ),
            ),
        )
        for index in range(3)
    )
    return harvest_scientific_hypotheses_analysis(events=(), facts=facts)


def _snapshot():
    return compose_scientific_hypotheses_snapshot(_analysis(), run_id=RUN)


def _seed(tmp_path: Path) -> None:
    scientific_hypotheses_store_publisher(tmp_path / "store").publish(_snapshot())


def _client(root: Path | None) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN)
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = (
        None
        if root is None
        else scientific_hypotheses_store_reader(root / "store")
    )
    app.state.scientific_hypotheses_reader = reader
    app.state.settings = settings
    app.state.scientific_hypotheses_cursor_codec = (
        ScientificHypothesesCursorCodec(b"k" * 32) if reader is not None else None
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
    assert SCIENTIFIC_HYPOTHESES_ROUTE_COUNT == 7
    assert len(routes) == 7
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_dual_gate_fails_closed(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(None) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/scientific-hypotheses", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["code"] == "scientific_hypotheses_disabled"


@pytest.mark.asyncio
async def test_summary_and_all_pages_serve(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        for path in PATHS:
            response = await client.get(
                path.format(run_id=RUN), headers=HEADERS
            )
            assert response.status_code == 200, path
        summary = (
            await client.get(
                f"/v1/simulations/{RUN}/scientific-hypotheses", headers=HEADERS
            )
        ).json()
        assert summary["hypothesis_count"] == 3
        assert summary["snapshot_version"] == "scientific-hypotheses-snapshot-v1"


@pytest.mark.asyncio
async def test_window_filter_and_cross_window_cursor(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        first = await client.get(
            f"/v1/simulations/{RUN}/scientific-hypotheses/hypotheses",
            headers=HEADERS,
            params={"limit": 1, "window_index": 0},
        )
        assert first.status_code == 200
        body = first.json()
        assert len(body["rows"]) == 1
        assert body["next_cursor"]
        cross = await client.get(
            f"/v1/simulations/{RUN}/scientific-hypotheses/hypotheses",
            headers=HEADERS,
            params={"cursor": body["next_cursor"], "window_index": 1},
        )
        assert cross.status_code == 400
        assert cross.json()["code"] == "scientific_hypotheses_cursor_invalid"


@pytest.mark.asyncio
async def test_missing_run_and_corrupt_store(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        missing = await client.get(
            "/v1/simulations/run-missing/scientific-hypotheses", headers=HEADERS
        )
        assert missing.status_code == 404
    state = tmp_path / "store" / RUN / "state.json"
    state.write_text("{bad", encoding="utf-8")
    async with _client(tmp_path) as client:
        corrupt = await client.get(
            f"/v1/simulations/{RUN}/scientific-hypotheses", headers=HEADERS
        )
    assert corrupt.status_code == 500
    assert corrupt.json()["code"] == "scientific_hypotheses_store_corrupt"


@pytest.mark.asyncio
async def test_summary_ignores_paging_parameters(tmp_path: Path) -> None:
    _seed(tmp_path)
    async with _client(tmp_path) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/scientific-hypotheses",
            headers=HEADERS,
            params={"limit": 1},
        )
    assert response.status_code == 200
