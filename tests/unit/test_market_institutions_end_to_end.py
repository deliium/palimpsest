"""In-process market-institution end-to-end over real engine admission."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.models import AgentId
from analysis.market_institutions_analysis import harvest_market_institutions_analysis
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.market_institutions_cursor import MarketInstitutionsCursorCodec
from api.routes.market_institutions import router
from experiments.market_institutions_publication import (
    compose_market_institutions_snapshot,
)
from infrastructure.settings import Settings
from persistence.market_institutions_filesystem import (
    create_market_institutions_publisher,
    create_market_institutions_reader,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
)
from world.actions import NegotiateExchange, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.values import ItemKind

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
FOOD = EntityId("item-food")
MATERIAL = EntityId("item-material")
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-market-e2e"


def _engine() -> WorldEngine:
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-market-e2e"),
        revision=WorldRevision(0),
        locations=(make_location("loc-a"),),
        items=(
            make_item(
                "item-food",
                kind=ItemKind.FOOD,
                location_id=None,
                holder_id="body-1",
            ),
            make_item(
                "item-material",
                kind=ItemKind.MATERIAL,
                location_id=None,
                holder_id="body-2",
            ),
        ),
        bodies=(
            alive_body("body-1", location_id="loc-a", inventory=(FOOD,)),
            alive_body("body-2", location_id="loc-a", inventory=(MATERIAL,)),
        ),
        weather=(make_weather("loc-a"),),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=31, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        run_id=RunId(RUN),
        subjective_valuation_active=True,
        resource_exchange_profile_active=True,
    )


def _wait(engine: WorldEngine) -> None:
    batch = engine.observe()
    engine.resolve_tick(
        tuple(
            ActionSubmission(batch.token, AgentId(f"agent-{index}"), Wait())
            for index in (1, 2)
        )
    )


def _exchange(engine: WorldEngine, *, first_side: str) -> None:
    if first_side == "food":
        give_a, take_a = (FOOD,), (MATERIAL,)
        give_b, take_b = (MATERIAL,), (FOOD,)
    else:
        give_a, take_a = (MATERIAL,), (FOOD,)
        give_b, take_b = (FOOD,), (MATERIAL,)
    batch = engine.observe()
    submissions = (
        ActionSubmission(
            batch.token,
            AgentId("agent-1"),
            NegotiateExchange(EntityId("body-2"), "offer", give_a, take_a),
        ),
        ActionSubmission(
            batch.token,
            AgentId("agent-2"),
            NegotiateExchange(EntityId("body-1"), "accept", give_b, take_b),
        ),
    )
    result = engine.resolve_tick(submissions)
    assert all(
        item.status is ActionResolutionStatus.APPLIED for item in result.resolutions
    )


@pytest.mark.asyncio
async def test_real_engine_market_persistence_snapshot_and_api(
    tmp_path: Path,
) -> None:
    engine = _engine()
    sides = ["food", "material", "food", "material", "food", "material"]
    for index, side in enumerate(sides):
        if index == 2 or index == 4:
            while engine.observe().tick.value % 32 != 0:
                _wait(engine)
        _exchange(engine, first_side=side)
        _wait(engine)
    while engine.observe().tick.value < 66:
        _wait(engine)

    events = engine.export_events().events
    completions = [
        event
        for event in events
        if getattr(event.details, "kind", None) == "exchange_completed"
    ]
    assert len(completions) >= 6
    origins = {
        event.occurrence.origin_location_id.value
        for event in completions
        if event.occurrence is not None
        and event.occurrence.origin_location_id is not None
    }
    assert len(origins) == 1

    analysis = harvest_market_institutions_analysis(committed_events=events)
    assert analysis.venues
    assert any(row.status.value == "market_like_persistent" for row in analysis.venues)
    assert analysis.coverage.value != "missing"

    snapshot = compose_market_institutions_snapshot(analysis, run_id=RUN)
    create_market_institutions_publisher(tmp_path / "store").publish(snapshot)

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.market_institutions_reader = create_market_institutions_reader(
        tmp_path / "store"
    )
    app.state.market_institutions_cursor_codec = MarketInstitutionsCursorCodec(
        b"k" * 32
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/market-institutions", headers=HEADERS
        )
        venues = await client.get(
            f"/v1/simulations/{RUN}/market-institutions/venues",
            headers=HEADERS,
        )
    assert summary.status_code == 200
    assert summary.json()["venue_count"] >= 1
    assert venues.status_code == 200
    assert venues.json()["rows"]
    assert venues.json()["rows"][0]["venue_id"] == snapshot.venues[0].venue_id
