"""In-process emergent-price end-to-end over real engine admission."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.models import AgentId
from analysis.emergent_prices_analysis import (
    emergent_prices_analysis_digest,
    harvest_emergent_prices_analysis,
)
from analysis.emergent_prices_contract import PriceCoverage
from analysis.emergent_prices_rows import PriceMarketMembershipInput
from analysis.market_institutions_contract import market_venue_token
from api.dependencies import get_settings
from api.emergent_prices_cursor import EmergentPricesCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.emergent_prices import router
from experiments.emergent_prices_publication import (
    compose_emergent_prices_snapshot,
    publish_emergent_prices_snapshot,
)
from infrastructure.settings import Settings
from persistence.emergent_prices_filesystem import (
    create_emergent_prices_publisher,
    create_emergent_prices_reader,
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

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-price-e2e"
MARKET_A = "mktc-aaaaaaaaaaaaaaaa"
MARKET_B = "mktc-bbbbbbbbbbbbbbbb"


def _engine() -> WorldEngine:
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-price-e2e"),
        revision=WorldRevision(0),
        locations=(
            make_location("loc-a", adjacent=("loc-b",)),
            make_location("loc-b", adjacent=("loc-a",)),
        ),
        items=(
            make_item(
                "a-food", kind=ItemKind.FOOD, location_id=None, holder_id="body-1"
            ),
            make_item(
                "a-material",
                kind=ItemKind.MATERIAL,
                location_id=None,
                holder_id="body-2",
            ),
            make_item(
                "b-food", kind=ItemKind.FOOD, location_id=None, holder_id="body-3"
            ),
            make_item(
                "b-material",
                kind=ItemKind.MATERIAL,
                location_id=None,
                holder_id="body-4",
            ),
        ),
        bodies=(
            alive_body("body-1", location_id="loc-a", inventory=(EntityId("a-food"),)),
            alive_body(
                "body-2", location_id="loc-a", inventory=(EntityId("a-material"),)
            ),
            alive_body("body-3", location_id="loc-b", inventory=(EntityId("b-food"),)),
            alive_body(
                "body-4", location_id="loc-b", inventory=(EntityId("b-material"),)
            ),
        ),
        weather=(make_weather("loc-a"), make_weather("loc-b")),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
            AgentRegistration(AgentId("agent-3"), EntityId("body-3")),
            AgentRegistration(AgentId("agent-4"), EntityId("body-4")),
        ),
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=41, physical_rules=non_lethal_physical_rules()
        ),
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
            for index in (1, 2, 3, 4)
        )
    )


def _exchange(
    engine: WorldEngine, *, first: int, second: int, one: str, other: str
) -> None:
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId(f"agent-{first}"),
                NegotiateExchange(
                    EntityId(f"body-{second}"),
                    "offer",
                    (EntityId(one),),
                    (EntityId(other),),
                ),
            ),
            ActionSubmission(
                batch.token,
                AgentId(f"agent-{second}"),
                NegotiateExchange(
                    EntityId(f"body-{first}"),
                    "accept",
                    (EntityId(other),),
                    (EntityId(one),),
                ),
            ),
        )
    )
    applied = [
        item
        for item in result.resolutions
        if item.status is ActionResolutionStatus.APPLIED
    ]
    assert applied


@pytest.mark.asyncio
async def test_real_engine_price_snapshot_and_seven_routes(tmp_path: Path) -> None:
    engine = _engine()
    for index in range(4):
        a_one, a_other = (
            ("a-food", "a-material")
            if index % 2 == 0
            else ("a-material", "a-food")
        )
        b_one, b_other = (
            ("b-food", "b-material")
            if index % 2 == 0
            else ("b-material", "b-food")
        )
        _exchange(engine, first=1, second=2, one=a_one, other=a_other)
        _wait(engine)
        _exchange(engine, first=3, second=4, one=b_one, other=b_other)
        _wait(engine)
        if index == 1:
            while engine.observe().tick.value % 32 != 0:
                _wait(engine)

    events = engine.export_events().events
    memberships = (
        PriceMarketMembershipInput(
            market_token=MARKET_A,
            venue_id=market_venue_token("loc-a"),
            window_index=0,
            coverage=PriceCoverage.COMPLETE,
        ),
        PriceMarketMembershipInput(
            market_token=MARKET_B,
            venue_id=market_venue_token("loc-b"),
            window_index=0,
            coverage=PriceCoverage.COMPLETE,
        ),
    )
    analysis = harvest_emergent_prices_analysis(
        committed_events=events, membership_inputs=memberships
    )
    assert analysis.distributions
    assert analysis.markets
    assert analysis.relations
    assert all(
        sum(row.bin_shares_milli) == 1_000
        for row in analysis.distributions
        if row.status.value == "available"
    )
    assert "price" not in {
        name
        for row in analysis.distributions
        for name in type(row).__dataclass_fields__
    }
    assert emergent_prices_analysis_digest(analysis) == (
        emergent_prices_analysis_digest(
            harvest_emergent_prices_analysis(
                committed_events=events, membership_inputs=memberships
            )
        )
    )

    snapshot = compose_emergent_prices_snapshot(analysis, run_id=RUN)
    publisher = create_emergent_prices_publisher(tmp_path / "store")
    receipt = publish_emergent_prices_snapshot(snapshot, publisher)
    assert receipt.stored is True

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.emergent_prices_reader = create_emergent_prices_reader(
        tmp_path / "store"
    )
    app.state.emergent_prices_cursor_codec = EmergentPricesCursorCodec(b"k" * 32)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/emergent-prices", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["digest"] == snapshot.digest
        for purpose in (
            "units",
            "expectations",
            "quotes",
            "distributions",
            "markets",
            "relations",
        ):
            response = await client.get(
                f"/v1/simulations/{RUN}/emergent-prices/{purpose}",
                headers=HEADERS,
            )
            assert response.status_code == 200
