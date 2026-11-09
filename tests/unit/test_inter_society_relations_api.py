# mypy: ignore-errors
"""Read-only ISR API routes, schemas, and cursors."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
    harvest_inter_society_relations,
)
from analysis.inter_society_relations_evidence import InterSocietyEvidenceInputs
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id
from api.dependencies import get_inter_society_relations_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.inter_society_relations_cursor import InterSocietyRelationsCursorCodec
from api.routes.inter_society_relations import (
    INTER_SOCIETY_RELATIONS_ROUTE_COUNT,
    router,
)
from experiments.inter_society_relations_completed_run import (
    compose_inter_society_relations_snapshot,
)
from infrastructure.settings import Settings
from persistence.inter_society_relations_filesystem import (
    create_inter_society_relations_publisher,
    create_inter_society_relations_reader,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-isr-api"

PATHS = {
    "/v1/simulations/{run_id}/inter-society-relations",
    "/v1/simulations/{run_id}/inter-society-relations/pairs",
    "/v1/simulations/{run_id}/inter-society-relations/pairs/{pair_id}",
    "/v1/simulations/{run_id}/inter-society-relations/pairs/{pair_id}/series",
    "/v1/simulations/{run_id}/inter-society-relations/comparison",
    "/v1/simulations/{run_id}/inter-society-relations/windows",
}


def _msoc(label: str, *, tick: int = 0) -> str:
    members = tuple(f"{label}-p{index}" for index in range(1, 5))
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=members,
        lane_signature=(MacroSocietyLane.INTERACTION.value,),
    )


def _seed(root: Path):
    left = _msoc("alpha")
    right = _msoc("beta", tick=1)
    other_left = _msoc("gamma", tick=2)
    other_right = _msoc("delta", tick=3)
    ordered = tuple(sorted((left, right)))
    ordered_other = tuple(sorted((other_left, other_right)))
    analysis = harvest_inter_society_relations(
        [
            InterSocietyMacroCandidate(
                society_id=left,
                member_ids=("alpha-p1", "alpha-p2", "alpha-p3", "alpha-p4"),
                window_tick=32,
            ),
            InterSocietyMacroCandidate(
                society_id=right,
                member_ids=("beta-p1", "beta-p2", "beta-p3", "beta-p4"),
                window_tick=32,
            ),
            InterSocietyMacroCandidate(
                society_id=other_left,
                member_ids=("gamma-p1", "gamma-p2", "gamma-p3", "gamma-p4"),
                window_tick=32,
            ),
            InterSocietyMacroCandidate(
                society_id=other_right,
                member_ids=("delta-p1", "delta-p2", "delta-p3", "delta-p4"),
                window_tick=32,
            ),
            InterSocietyMacroCandidate(
                society_id=left,
                member_ids=("alpha-p1", "alpha-p2", "alpha-p3", "alpha-p4"),
                window_tick=64,
            ),
            InterSocietyMacroCandidate(
                society_id=right,
                member_ids=("beta-p1", "beta-p2", "beta-p3", "beta-p4"),
                window_tick=64,
            ),
        ],
        evidence_by_pair={
            ordered: InterSocietyEvidenceInputs(exchange_event_count=3),
            ordered_other: InterSocietyEvidenceInputs(cooperation_event_count=1),
        },
    )
    snapshot = compose_inter_society_relations_snapshot(analysis, run_id=RUN)
    create_inter_society_relations_publisher(root / "store").publish(snapshot)
    return snapshot


def _client(root: Path | None, *, clock: list[float]) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = (
        None if root is None else create_inter_society_relations_reader(root / "store")
    )
    app.dependency_overrides[get_inter_society_relations_reader] = lambda: reader
    app.state.inter_society_relations_reader = reader
    app.state.inter_society_relations_cursor_codec = (
        InterSocietyRelationsCursorCodec(b"k" * 32, now=lambda: clock[0])
        if reader is not None
        else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def test_exactly_six_get_routes() -> None:
    routes = [
        cast(Any, route)
        for route in router.routes
        if getattr(route, "methods", None) is not None
    ]
    assert INTER_SOCIETY_RELATIONS_ROUTE_COUNT == 6
    assert len(routes) == 6
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_all_routes_require_subjective_debug(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    pair_id = snapshot.pairs[0].pair_id
    async with _client(tmp_path, clock=[0.0]) as client:
        for path in (
            f"/v1/simulations/{RUN}/inter-society-relations",
            f"/v1/simulations/{RUN}/inter-society-relations/pairs",
            f"/v1/simulations/{RUN}/inter-society-relations/pairs/{pair_id}",
            f"/v1/simulations/{RUN}/inter-society-relations/pairs/{pair_id}/series",
            f"/v1/simulations/{RUN}/inter-society-relations/windows",
            (
                f"/v1/simulations/{RUN}/inter-society-relations/comparison"
                f"?pair_a={snapshot.pairs[0].pair_id}"
                f"&pair_b={snapshot.pairs[1].pair_id}"
            ),
        ):
            response = await client.get(path)
            assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_unconfigured_store_returns_disabled() -> None:
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/inter-society-relations", headers=HEADERS
        )
    assert response.status_code == 503
    assert response.json()["code"] == "inter_society_relations_disabled"


@pytest.mark.asyncio
async def test_summary_and_pairs(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/inter-society-relations", headers=HEADERS
        )
        pairs = await client.get(
            f"/v1/simulations/{RUN}/inter-society-relations/pairs", headers=HEADERS
        )
    assert summary.status_code == 200
    body = summary.json()
    assert body["pair_count"] == snapshot.summary.pair_count
    assert body["series_point_count"] == snapshot.summary.series_point_count
    assert "score" not in body
    assert pairs.status_code == 200
    assert len(pairs.json()["items"]) == snapshot.summary.pair_count


@pytest.mark.asyncio
async def test_comparison_operand_contract(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    pair_a = snapshot.pairs[0].pair_id
    pair_b = snapshot.pairs[1].pair_id
    # Prefer a society pair that has series coverage in both windows 32 and 64.
    multi_window_pair = next(
        pair.pair_id
        for pair in snapshot.pairs
        if pair.window_tick == 32
        and any(
            other.society_a == pair.society_a
            and other.society_b == pair.society_b
            and other.window_tick == 64
            for other in snapshot.pairs
        )
    )
    async with _client(tmp_path, clock=[0.0]) as client:
        ok = await client.get(
            f"/v1/simulations/{RUN}/inter-society-relations/comparison",
            headers=HEADERS,
            params={"pair_a": pair_a, "pair_b": pair_b},
        )
        mixed = await client.get(
            f"/v1/simulations/{RUN}/inter-society-relations/comparison",
            headers=HEADERS,
            params={
                "pair_a": pair_a,
                "pair_b": pair_b,
                "pair_id": pair_a,
                "window_a": 32,
                "window_b": 64,
            },
        )
        incomplete = await client.get(
            f"/v1/simulations/{RUN}/inter-society-relations/comparison",
            headers=HEADERS,
            params={"pair_a": pair_a},
        )
        windowed = await client.get(
            f"/v1/simulations/{RUN}/inter-society-relations/comparison",
            headers=HEADERS,
            params={
                "pair_id": multi_window_pair,
                "window_a": 32,
                "window_b": 64,
            },
        )
    assert ok.status_code == 200
    assert "domain_deltas" in ok.json()
    assert mixed.status_code == 400
    assert mixed.json()["code"] == "inter_society_relations_comparison_invalid"
    assert incomplete.status_code == 400
    assert windowed.status_code == 200
