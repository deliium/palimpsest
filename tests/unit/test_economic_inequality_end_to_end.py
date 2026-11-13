# mypy: ignore-errors
"""In-process economic inequality: engine, analysis, snapshot, store, API."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.models import AgentId
from analysis.organization_operations import (
    OrganizationControlRow,
    OrganizationOperationHarvestRows,
    OrganizationOperationOwnerRow,
)
from api.dependencies import get_settings
from api.economic_inequality_cursor import EconomicInequalityCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.economic_inequality import router
from experiments.economic_inequality_completed_run import (
    build_completed_run_economic_inequality_analysis,
)
from experiments.economic_inequality_publication import (
    build_economic_inequality_harvest_result,
)
from infrastructure.settings import Settings
from persistence.economic_inequality_filesystem import (
    create_economic_inequality_publisher,
    create_economic_inequality_reader,
)
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import alive_body, make_item
from world.actions import Build, Craft, Give, Move, Tell
from world.communications import origin_utterance
from world.credit_relationships import (
    CreditClaimFrame,
    CreditFrameAct,
    CreditFrameDirection,
    credit_claim_relation,
)
from world.events import Told
from world.identifiers import EntityId, RecipeId
from world.production import (
    HeldItemKindInput,
    HeldItemNameInput,
    ItemLoad,
    ItemProduct,
    ProductionAction,
    ProductionCatalog,
    ProductionRecipe,
    ShelterProduct,
    StructureKind,
    ToolRole,
)
from world.values import ItemKind

pytestmark = pytest.mark.unit

TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-economic-inequality-e2e"


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
            ProductionRecipe(
                recipe_id=RecipeId("build_shelter"),
                action=ProductionAction.BUILD,
                duration_ticks=1,
                success_probability=1.0,
                inputs=(HeldItemKindInput(ItemKind.MATERIAL),),
                output=ShelterProduct(StructureKind.SHELTER),
            ),
        )
    )


def _engine():
    base = two_location_fixture(item_on_ground=False)
    items = (
        make_item("item-wood", name="wood", location_id=None, holder_id="body-1"),
        make_item("item-stone", name="stone", location_id=None, holder_id="body-1"),
        make_item(
            "item-material",
            name="material",
            kind=ItemKind.MATERIAL,
            location_id=None,
            holder_id="body-1",
        ),
        make_item("item-mat-2", name="mat2", location_id=None, holder_id="body-2"),
        make_item("item-mat-3", name="mat3", location_id=None, holder_id="body-3"),
        make_item("item-mat-4", name="mat4", location_id=None, holder_id="body-4"),
    )
    bodies = (
        alive_body(
            "body-1",
            location_id="loc-1",
            inventory=(
                EntityId("item-wood"),
                EntityId("item-stone"),
                EntityId("item-material"),
            ),
        ),
        alive_body("body-2", location_id="loc-1", inventory=(EntityId("item-mat-2"),)),
        alive_body("body-3", location_id="loc-1", inventory=(EntityId("item-mat-3"),)),
        alive_body("body-4", location_id="loc-1", inventory=(EntityId("item-mat-4"),)),
    )
    fixture = replace(base, items=items, bodies=bodies)
    from simulation.bootstrap import AgentRegistration
    from simulation.engine import WorldEngine

    boot = fixture.as_bootstrap()
    boot = replace(
        boot,
        registrations=tuple(
            AgentRegistration(AgentId(f"agent-{index}"), EntityId(f"body-{index}"))
            for index in range(1, 5)
        ),
    )
    return WorldEngine(
        config=physical_config(11),
        bootstrap=boot,
        production_catalog=_catalog(),
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


def _credit_tell(engine) -> None:
    relation = credit_claim_relation(
        CreditClaimFrame(
            act=CreditFrameAct.PROPOSE,
            direction=CreditFrameDirection.OWNER_DEBTOR,
            anchor="crd-0123456789abcdef",
            principal_kind_token="food",
            principal_quantity=2,
            repayment_kind_token="water",
            repayment_quantity=3,
            paid_quantity=0,
            opened_tick=0,
            due_tick=10,
            condition="by_deadline",
            collateral_kind="none",
            collateral_item_token=None,
            collateral_quantity=0,
            confidence_milli=500,
        )
    )
    utterance = origin_utterance(
        text="credit",
        speaker_id=EntityId("body-1"),
        relations=(relation,),
    )
    _act(engine, "agent-1", Tell(recipient_id=EntityId("body-2"), utterance=utterance))


def _control_rows() -> tuple[OrganizationOperationHarvestRows, ...]:
    owner = OrganizationOperationOwnerRow(
        owner_id="body-1",
        concept_count=1,
        notices=(),
        policy_version="organization-operations.v1",
        control_count=1,
    )
    return (
        OrganizationOperationHarvestRows(
            owner=owner,
            controls=(
                OrganizationControlRow(
                    organization_id="org-1",
                    domain="resource_control",
                    last_tick=1,
                    contest_count=0,
                ),
            ),
        ),
    )


def test_engine_analysis_snapshot_store_and_api(tmp_path: Path) -> None:
    engine = _engine()
    _act(engine, "agent-1", Craft(RecipeId("craft_tool")))
    _act(engine, "agent-1", Build(RecipeId("build_shelter")))
    crafted = [
        event.details
        for event in engine.export_events().events
        if type(event.details).__name__ == "ItemCrafted"
    ]
    tool_id = crafted[-1].created_item_id
    _act(engine, "agent-1", Give(recipient_id=EntityId("body-2"), item_id=tool_id))
    _credit_tell(engine)
    for index in (2, 3, 4):
        _act(engine, f"agent-{index}", Move(EntityId("loc-2")))

    events = engine.export_events().events
    assert any(type(event.details) is Told for event in events)
    analysis = build_completed_run_economic_inequality_analysis(
        object(),
        runner_config=SimpleNamespace(
            agents=(
                SimpleNamespace(
                    cognition=SimpleNamespace(production_catalog=_catalog())
                ),
            )
        ),
        committed_events=events,
        run_id=RUN,
        organization_operation_rows=_control_rows(),
        macro_society_analysis=SimpleNamespace(
            records=(
                SimpleNamespace(
                    macro_society_id="msoc-0123456789abcdef",
                    member_ids=("body-1", "body-2", "body-3", "body-4"),
                    window_indexes=(0,),
                ),
            )
        ),
    )
    assert analysis.dimension_rows
    assert analysis.credit_claim_count >= 1
    assert analysis.control_claim_count == 1
    assert analysis.society_rows
    publisher = create_economic_inequality_publisher(tmp_path / "store")
    harvest = build_economic_inequality_harvest_result(
        analysis, run_id=RUN, publisher=publisher
    )
    assert harvest.receipt.stored is True
    assert harvest.snapshot.summary.dimension_row_count > 0

    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.settings = settings
    app.state.economic_inequality_reader = create_economic_inequality_reader(
        tmp_path / "store"
    )
    app.state.economic_inequality_cursor_codec = EconomicInequalityCursorCodec(
        b"k" * 32
    )
    import asyncio

    async def read() -> tuple[int, dict, int]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            summary = await client.get(
                f"/v1/simulations/{RUN}/economic-inequality", headers=HEADERS
            )
            possession = await client.get(
                f"/v1/simulations/{RUN}/economic-inequality/possession",
                headers=HEADERS,
            )
        return summary.status_code, summary.json(), possession.status_code

    summary_status, body, possession_status = asyncio.run(read())
    assert summary_status == 200
    assert body["digest"] == harvest.snapshot.digest
    assert possession_status == 200

    app.state.economic_inequality_reader = None
    app.state.economic_inequality_cursor_codec = None

    async def disabled() -> int:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/v1/simulations/{RUN}/economic-inequality", headers=HEADERS
            )
        return response.status_code

    assert asyncio.run(disabled()) == 503
