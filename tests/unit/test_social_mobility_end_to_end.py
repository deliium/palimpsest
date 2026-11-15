# mypy: ignore-errors
"""In-process social mobility: engine, analysis, snapshot, store, API."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.models import AgentId
from analysis.social_mobility_contract import (
    SocialMobilityAvailability,
    SocialMobilityDomain,
)
from analysis.social_mobility_policy import SocialMobilityAnalysisPolicy
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.social_mobility import router
from api.social_mobility_cursor import SocialMobilityCursorCodec
from experiments.social_mobility_completed_run import (
    build_completed_run_social_mobility_analysis,
)
from experiments.social_mobility_publication import (
    compose_social_mobility_snapshot,
)
from infrastructure.settings import Settings
from persistence.social_mobility_filesystem import (
    create_social_mobility_publisher,
    create_social_mobility_reader,
)
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.runner_models import KinshipSpec
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_item
from world.actions import Craft
from world.identifiers import EntityId, RecipeId
from world.production import (
    HeldItemNameInput,
    ItemLoad,
    ItemProduct,
    ProductionAction,
    ProductionCatalog,
    ProductionRecipe,
    ToolRole,
)
from world.values import ItemKind

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-social-mobility-e2e"


def _catalog() -> ProductionCatalog:
    return ProductionCatalog(
        (
            ProductionRecipe(
                recipe_id=RecipeId("craft_tool"),
                action=ProductionAction.CRAFT,
                duration_ticks=1,
                success_probability=1.0,
                inputs=(
                    HeldItemNameInput("wood"),
                    HeldItemNameInput("stone"),
                ),
                output=ItemProduct(
                    ItemKind.TOOL, "tool", ItemLoad(1), tool_role=ToolRole.STRIKE
                ),
                tool_role=ToolRole.STRIKE,
            ),
        )
    )


def _engine():
    base = two_location_fixture(item_on_ground=False)
    items = (
        tuple(
            make_item(
                f"item-wood-{index}",
                name="wood",
                location_id=None,
                holder_id="body-1",
            )
            for index in range(4)
        )
        + tuple(
            make_item(
                f"item-stone-{index}",
                name="stone",
                location_id=None,
                holder_id="body-1",
            )
            for index in range(4)
        )
        + (
            make_item(
                "item-wood-99", name="wood", location_id=None, holder_id="body-2"
            ),
            make_item(
                "item-stone-99", name="stone", location_id=None, holder_id="body-2"
            ),
        )
    )
    bodies = (
        alive_body(
            "body-1",
            location_id="loc-1",
            inventory=tuple(
                EntityId(f"item-{name}-{index}")
                for index in range(4)
                for name in ("wood", "stone")
            ),
        ),
        alive_body(
            "body-2",
            location_id="loc-1",
            inventory=(EntityId("item-wood-99"), EntityId("item-stone-99")),
        ),
    )
    fixture = replace(base, items=items, bodies=bodies)
    from simulation.bootstrap import AgentRegistration
    from simulation.engine import WorldEngine

    boot = fixture.as_bootstrap()
    boot = replace(
        boot,
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )
    return WorldEngine(
        config=physical_config(11),
        bootstrap=boot,
        production_catalog=_catalog(),
        kinship_spec=KinshipSpec(),
    )


def _act(engine, agent: str, command: object):
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )
    assert any(
        item.status is ActionResolutionStatus.APPLIED for item in result.resolutions
    ), command
    return result


def _agent_created_event() -> object:
    from world.effects import ActionCause
    from world.events import (
        AgentCreated,
        OccurrenceContext,
        WorldEvent,
        target_id_for_details,
    )
    from world.identifiers import EventId, RequestId, WorldId, WorldRevision

    details = AgentCreated(
        body_id=EntityId("body-2"),
        agent_id="agent-2",
        generation_index=1,
        cohort_id="cohort-1",
        provenance="demographic_policy",
    )
    return WorldEvent(
        event_id=EventId("evt-generation-agent-2"),
        run_id=RUN,
        world_id=WorldId("world-social-mobility-e2e"),
        tick=0,
        sequence=99,
        request_id=RequestId("req-generation-agent-2"),
        resulting_revision=WorldRevision(99),
        schema_version=22,
        details=details,
        actor_id=EntityId("body-2"),
        target_id=target_id_for_details(details),
        cause=ActionCause(RequestId("req-generation-agent-2"), EntityId("body-2")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _config():
    return SimpleNamespace(
        agents=(
            SimpleNamespace(
                agent_id=AgentId("agent-1"),
                entity_id=EntityId("body-1"),
                cognition=SimpleNamespace(production_catalog=_catalog()),
            ),
            SimpleNamespace(
                agent_id=AgentId("agent-2"),
                entity_id=EntityId("body-2"),
                cognition=SimpleNamespace(production_catalog=_catalog()),
            ),
        )
    )


def _analysis(engine, *, window_end: int = 2):
    return build_completed_run_social_mobility_analysis(
        SimpleNamespace(
            practical_knowledge_audits=(),
            teaching_audits=(),
            organization_operation_ledgers=(),
        ),
        runner_config=_config(),
        committed_events=(
            *engine.export_events().events,
            _agent_created_event(),
        ),
        run_id=RUN,
        policy=SocialMobilityAnalysisPolicy(window_ticks=1),
        window_end=window_end,
    )


def _app(tmp_path: Path, *, enabled: bool = True) -> FastAPI:
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    if enabled:
        app.state.social_mobility_reader = create_social_mobility_reader(
            tmp_path / "store"
        )
        app.state.social_mobility_cursor_codec = SocialMobilityCursorCodec(b"k" * 32)
    else:
        app.state.social_mobility_reader = None
        app.state.social_mobility_cursor_codec = None
    return app


def _get(app: FastAPI, path: str, **params):
    async def read():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path, headers=HEADERS, params=params)

    import asyncio

    return asyncio.run(read())


def test_engine_analysis_snapshot_store_and_api(tmp_path: Path) -> None:
    engine = _engine()
    for _ in range(3):
        _act(engine, "agent-1", Craft(RecipeId("craft_tool")))
    _act(engine, "agent-2", Craft(RecipeId("craft_tool")))
    engine.establish_kinship_edge(
        parent_agent_id=AgentId("agent-1"),
        child_agent_id=AgentId("agent-2"),
        established_tick=0,
    )

    analysis = _analysis(engine)
    assert analysis.genealogy_edge_count >= 1
    assert analysis.owner_count == 2
    assert analysis.generation_count == 2
    assert analysis.pair_rows
    assert analysis.generation_rows
    assert analysis.coverage_row is not None
    resources = [
        row
        for row in analysis.domain_rows
        if row.domain is SocialMobilityDomain.RESOURCES
    ]
    assert resources
    assert any(
        row.availability is SocialMobilityAvailability.AVAILABLE for row in resources
    ) or any(
        row.availability is SocialMobilityAvailability.INSUFFICIENT_SAMPLES
        for row in resources
    )
    assert any(
        row.availability is SocialMobilityAvailability.INSUFFICIENT_SAMPLES
        for row in analysis.domain_rows
    )

    publisher = create_social_mobility_publisher(tmp_path / "store")
    snapshot = compose_social_mobility_snapshot(_analysis(engine), run_id=RUN)
    assert publisher.publish(snapshot).stored is True
    import json

    state = json.loads((tmp_path / "store" / RUN / "state.json").read_text())
    entries = list(state["publications"].values())
    assert len(entries) == 1
    assert entries[0]["bytes"] > 0
    app = _app(tmp_path)
    summary = _get(app, f"/v1/simulations/{RUN}/social-mobility")
    assert summary.status_code == 200
    assert summary.json()["pair_count"] > 0
    domains = _get(app, f"/v1/simulations/{RUN}/social-mobility/domains", limit=1)
    assert domains.status_code == 200
    cursor = domains.json()["next_cursor"]
    if cursor is not None:
        mismatched = _get(
            app,
            f"/v1/simulations/{RUN}/social-mobility/domains",
            limit=1,
            window_index=1,
            cursor=cursor,
        )
        assert mismatched.status_code == 400
    disabled = _get(
        _app(tmp_path, enabled=False), f"/v1/simulations/{RUN}/social-mobility"
    )
    assert disabled.status_code == 503


def test_cumulative_publication_bytes_and_corrupt_store(tmp_path: Path) -> None:
    engine = _engine()
    _act(engine, "agent-1", Craft(RecipeId("craft_tool")))
    _act(engine, "agent-2", Craft(RecipeId("craft_tool")))
    engine.establish_kinship_edge(
        parent_agent_id=AgentId("agent-1"),
        child_agent_id=AgentId("agent-2"),
        established_tick=0,
    )

    analyses = [
        _analysis(engine, window_end=window) for window in (0, 1, 2)
    ]
    snapshots = [
        compose_social_mobility_snapshot(analysis, run_id=RUN) for analysis in analyses
    ]
    publisher = create_social_mobility_publisher(tmp_path / "store")
    receipts = [publisher.publish(snapshot) for snapshot in snapshots]
    assert len(receipts) == 3
    assert receipts[0].stored is True
    assert all(receipt.reason_code == "published" for receipt in receipts)
    records = list((tmp_path / "store" / RUN / "state.json").read_text().split())
    assert records
    app = _app(tmp_path)
    for window in (0, 1, 2):
        page = _get(
            app,
            f"/v1/simulations/{RUN}/social-mobility/domains",
            window_index=window,
        )
        assert page.status_code == 200
    coverage = _get(app, f"/v1/simulations/{RUN}/social-mobility/coverage")
    assert coverage.status_code == 200

    (tmp_path / "store" / RUN / "state.json").write_text("{bad", encoding="utf-8")
    corrupt = _get(app, f"/v1/simulations/{RUN}/social-mobility")
    assert corrupt.status_code == 500
