"""V4-10 GET-only diplomacy API: auth, disabled state, paging, cursors."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition import (
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    apply_diplomacy_update,
)
from api.dependencies import get_diplomacy_reader, get_settings
from api.diplomacy_cursor import DiplomacyCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.diplomacy import router
from experiments.diplomacy_harvest import build_completed_run_diplomacy_harvest
from experiments.diplomacy_publication import (
    build_diplomacy_harvest_result,
    publish_diplomacy_snapshot,
)
from infrastructure.settings import Settings
from persistence.diplomacy_filesystem import (
    FilesystemDiplomacyPublisher,
    create_diplomacy_reader,
)

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-diplomacy-api"
PATHS = {
    "/v1/simulations/{run_id}/diplomacy",
    "/v1/simulations/{run_id}/diplomacy/relations",
    "/v1/simulations/{run_id}/diplomacy/relations/{relation_id}",
    "/v1/simulations/{run_id}/diplomacy/instruments",
    "/v1/simulations/{run_id}/diplomacy/instruments/{instrument_id}",
    "/v1/simulations/{run_id}/diplomacy/lineage",
}


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(),
        communications=(),
        regional_context=None,
        self_body=None,
        exits=(),
    )


def _ledger(tick: int, counterparty: str) -> object:
    return apply_diplomacy_update(
        owner_id="agent-a",
        tick=tick,
        observation=_observation(),
        prior=None,
        frames=(
            DiplomacyFrame(
                act=DiplomaticAct.PROPOSE,
                envoy_ref="agent-a",
                actor_ref="agent-a",
                party_kind=DiplomaticPartyKind.AGENT,
                party_ref=counterparty,
                topic_subject="trade",
                term_kind=DiplomaticTermKind.MATERIAL_EXCHANGE,
                revision=0,
            ),
        ),
    )


def _result(run_id: str = RUN) -> object:
    return SimpleNamespace(
        run_id=SimpleNamespace(value=run_id),
        ticks_committed=2,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(
            _ledger(1, "agent-b"),
            _ledger(2, "agent-c"),
        ),
    )


def _seed(root: Path, *, run_id: str = RUN):
    harvest = build_completed_run_diplomacy_harvest(_result(run_id))
    result = build_diplomacy_harvest_result(
        harvest, run_id=run_id, revision="rev-1", window_end=2
    )
    publish_diplomacy_snapshot(result, FilesystemDiplomacyPublisher(root / "store"))
    return result.snapshot


def _client(root: Path | None, *, clock: list[float]) -> httpx.AsyncClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = None if root is None else create_diplomacy_reader(root / "store")
    app.dependency_overrides[get_diplomacy_reader] = lambda: reader
    app.state.diplomacy_reader = reader
    app.state.diplomacy_cursor_codec = (
        DiplomacyCursorCodec(b"k" * 32, now=lambda: clock[0])
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
    assert len(routes) == 6
    assert {route.path for route in routes} == PATHS
    assert all(route.methods == {"GET"} for route in routes)


@pytest.mark.asyncio
async def test_capability_is_required_and_disabled_is_explicit(
    tmp_path: Path,
) -> None:
    _seed(tmp_path)
    async with _client(tmp_path, clock=[0.0]) as client:
        assert (await client.get(f"/v1/simulations/{RUN}/diplomacy")).status_code in {
            401,
            403,
        }
        assert (
            await client.get(f"/v1/simulations/{RUN}/diplomacy", headers=HEADERS)
        ).status_code == 200
    async with _client(None, clock=[0.0]) as client:
        response = await client.get(f"/v1/simulations/{RUN}/diplomacy", headers=HEADERS)
        assert response.status_code == 503
        assert response.json()["detail"] == "diplomacy_disabled"


@pytest.mark.asyncio
async def test_summary_pages_details_and_cursors(tmp_path: Path) -> None:
    snapshot = _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        summary = await client.get(f"/v1/simulations/{RUN}/diplomacy", headers=HEADERS)
        assert summary.status_code == 200
        assert summary.json()["publication_id"] == snapshot.publication_id

        page = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/relations",
            headers=HEADERS,
            params={"limit": 1},
        )
        assert page.status_code == 200
        payload = page.json()
        assert len(payload["items"]) == 1
        assert "agent-b" not in str(payload)
        cursor = payload["next_cursor"]
        assert cursor

        second = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/relations",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert second.status_code == 200
        assert (
            second.json()["items"][0]["relation_id"]
            != payload["items"][0]["relation_id"]
        )

        changed = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/instruments",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert changed.status_code == 400

        relation_id = payload["items"][0]["relation_id"]
        detail = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/relations/{relation_id}",
            headers=HEADERS,
        )
        assert detail.status_code == 200
        assert detail.json()["relation"]["relation_id"] == relation_id
        assert "parties" in detail.json()

        instrument_id = snapshot.instruments[0].instrument_id
        instrument = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/instruments/{instrument_id}",
            headers=HEADERS,
        )
        assert instrument.status_code == 200
        assert instrument.json()["instrument"]["instrument_id"] == instrument_id


@pytest.mark.asyncio
async def test_unknown_ids_and_expired_cursor(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/relations/dpl-0000000000000000",
            headers=HEADERS,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "diplomacy_unknown_relation"

        page = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/relations",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = page.json()["next_cursor"]
        clock[0] = 10_000.0
        expired = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/relations",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert expired.status_code == 410
        assert expired.json()["detail"] == "diplomacy_cursor_expired"


@pytest.mark.asyncio
async def test_changed_run_invalidates_a_cursor(tmp_path: Path) -> None:
    _seed(tmp_path)
    clock = [0.0]
    async with _client(tmp_path, clock=clock) as client:
        page = await client.get(
            f"/v1/simulations/{RUN}/diplomacy/relations",
            headers=HEADERS,
            params={"limit": 1},
        )
        cursor = page.json()["next_cursor"]
        changed = await client.get(
            "/v1/simulations/run-other/diplomacy/relations",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert changed.status_code in {400, 404}
