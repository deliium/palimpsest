# mypy: ignore-errors
"""In-process economic cascades: engine, events, analysis, store, API."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.models import AgentId
from api.dependencies import get_settings
from api.economic_cascades_cursor import EconomicCascadesCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.economic_cascades import router
from experiments.economic_cascades_completed_run import (
    build_completed_run_economic_cascades_analysis,
)
from experiments.economic_cascades_publication import (
    compose_economic_cascades_snapshot,
)
from infrastructure.settings import Settings
from persistence.economic_cascades_filesystem import (
    economic_cascades_store_publisher,
    economic_cascades_store_reader,
)
from simulation.bootstrap import AgentRegistration
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import Craft, Harvest, Wait
from world.environment import scarcity_scenario_dynamics
from world.identifiers import EntityId, RecipeId
from world.models import PhysicalRules
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-economic-cascades-e2e"
CATALOG = supply_chain_production_catalog(example_production_catalog())


def _engine() -> WorldEngine:
    fixture = two_location_fixture(item_on_ground=False)
    resources = tuple(
        replace(
            fixture.resources[0],
            entity_id=EntityId(f"res-food-{index}"),
            name="grain",
            quantity=1.0,
            maximum_quantity=5.0,
            regeneration_per_tick=0.0,
        )
        for index in (1, 2)
    )
    fixture = replace(fixture, resources=resources)
    boot = fixture.as_bootstrap()
    boot = replace(
        boot,
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )
    return WorldEngine(
        config=physical_config(
            11,
            rules=PhysicalRules(
                metabolism_hunger=0.0,
                metabolism_thirst=0.0,
                metabolism_fatigue=0.0,
                exposure_damage=0.0,
            ),
        ),
        bootstrap=boot,
        production_catalog=CATALOG,
        environmental_dynamics=scarcity_scenario_dynamics(),
        supply_chains_active=True,
    )


def _act(engine: WorldEngine, agent: str, command: object) -> None:
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )
    assert result.resolutions


def _wait(engine: WorldEngine, ticks: int = 4) -> None:
    for _ in range(ticks):
        _act(engine, "agent-2", Wait())


def _runner_result() -> SimpleNamespace:
    agent = SimpleNamespace(
        cognition=SimpleNamespace(production_catalog=CATALOG)
    )
    return SimpleNamespace(
        runner_config=SimpleNamespace(agents=(agent,)),
        final_infrastructure_assets=(),
    )


def _client(root: Path, *, enabled: bool = True) -> httpx.AsyncClient:
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr(TOKEN),
    )
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    app.state.economic_cascades_reader = (
        economic_cascades_store_reader(root) if enabled else None
    )
    app.state.economic_cascades_cursor_codec = (
        EconomicCascadesCursorCodec(b"k" * 32) if enabled else None
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.mark.asyncio
async def test_real_path_publishes_and_serves_seven_routes(tmp_path: Path) -> None:
    engine = _engine()
    _act(
        engine,
        "agent-1",
        Harvest(RecipeId("harvest_grain"), EntityId("res-food-1")),
    )
    _wait(engine)
    _act(engine, "agent-1", Craft(RecipeId("mill_grain")))
    _wait(engine, 30)
    for _ in range(6):
        _act(
            engine,
            "agent-1",
            Harvest(RecipeId("harvest_grain"), EntityId("res-food-2")),
        )
        _wait(engine, 1)
    _wait(engine, 2)
    events = engine.export_events().events
    assert events

    analysis = build_completed_run_economic_cascades_analysis(
        _runner_result(), committed_events=events, run_id=RUN
    )
    assert analysis.event_count >= 1
    snapshot = compose_economic_cascades_snapshot(analysis, run_id=RUN)
    assert snapshot.summary.coverage in {"complete", "partial"}
    assert (
        economic_cascades_store_publisher(tmp_path).publish(snapshot).stored
        is True
    )

    async with _client(tmp_path) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["disruption_count"] >= 2
        assert summary.json()["chain_count"] >= 1
        first_page = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades/disruptions",
            headers=HEADERS,
            params={"limit": 1},
        )
        assert first_page.status_code == 200
        windows = {row["window_index"] for row in first_page.json()["rows"]}
        cursor = first_page.json()["next_cursor"]
        assert cursor is not None
        second_page = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades/disruptions",
            headers=HEADERS,
            params={"limit": 1, "cursor": cursor},
        )
        assert second_page.status_code == 200
        windows |= {row["window_index"] for row in second_page.json()["rows"]}
        assert windows == {0, 1}
        for purpose in (
            "disruptions",
            "dependencies",
            "chains",
            "propagation",
            "windows",
            "coverage",
        ):
            response = await client.get(
                f"/v1/simulations/{RUN}/economic-cascades/{purpose}",
                headers=HEADERS,
            )
            assert response.status_code == 200, purpose


@pytest.mark.asyncio
async def test_dual_gate_and_corrupt_store(tmp_path: Path) -> None:
    engine = _engine()
    _act(
        engine,
        "agent-1",
        Harvest(RecipeId("harvest_grain"), EntityId("res-food")),
    )
    events = engine.export_events().events
    analysis = build_completed_run_economic_cascades_analysis(
        _runner_result(), committed_events=events, run_id=RUN
    )
    snapshot = compose_economic_cascades_snapshot(analysis, run_id=RUN)
    economic_cascades_store_publisher(tmp_path).publish(snapshot)
    async with _client(tmp_path, enabled=False) as client:
        response = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
    assert response.status_code == 503
    (tmp_path / RUN / "state.json").write_text("{not-json")
    async with _client(tmp_path) as client:
        corrupt = await client.get(
            f"/v1/simulations/{RUN}/economic-cascades", headers=HEADERS
        )
    assert corrupt.status_code == 500
