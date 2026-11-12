"""In-process credit relationship end-to-end over real engine admission."""

# mypy: ignore-errors


from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition.credit_relationships import (
    CreditAct,
    CreditClaim,
    CreditClaimSource,
    CreditCollateralKind,
    CreditCondition,
    CreditDirection,
    CreditRepaymentObservation,
    CreditTerms,
    apply_credit_relationship_update,
)
from agents.models import AgentId
from api.credit_relationships_cursor import CreditRelationshipsCursorCodec
from api.dependencies import get_settings
from api.errors import ApiError, api_error_handler
from api.routes.credit_relationships import router
from experiments.credit_relationships_publication import (
    build_credit_relationships_harvest_result,
)
from infrastructure.settings import Settings
from persistence.credit_relationships_filesystem import (
    create_credit_relationships_publisher,
    create_credit_relationships_reader,
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
from world.actions import Give, Talk, Wait
from world.communications import origin_utterance
from world.credit_relationships import (
    CreditClaimFrame,
    CreditFrameAct,
    CreditFrameDirection,
    credit_claim_relation,
    parse_credit_claim_relation,
)
from world.events import Given, Talked, Told
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.values import ItemKind

pytestmark = pytest.mark.unit
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-credit-e2e"
ANCHOR = "crd-0123456789abcdef"


def _engine() -> WorldEngine:
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-credit-e2e"),
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
                "b-water", kind=ItemKind.WATER, location_id=None, holder_id="body-2"
            ),
        ),
        bodies=(
            alive_body("body-1", location_id="loc-a", inventory=(EntityId("a-food"),)),
            alive_body(
                "body-2", location_id="loc-a", inventory=(EntityId("b-water"),)
            ),
        ),
        weather=(make_weather("loc-a"), make_weather("loc-b")),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=41, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId(RUN),
        structured_commitments_active=True,
        subjective_valuation_active=True,
    )


def _frame(act: CreditFrameAct) -> CreditClaimFrame:
    return CreditClaimFrame(
        act=act,
        direction=CreditFrameDirection.OWNER_DEBTOR,
        anchor=ANCHOR,
        principal_kind_token="food",
        principal_quantity=1,
        repayment_kind_token="water",
        repayment_quantity=1,
        paid_quantity=1 if act is CreditFrameAct.REPAY else 0,
        opened_tick=0,
        due_tick=10,
        condition="by_deadline",
        collateral_kind="none",
        collateral_item_token=None,
        collateral_quantity=0,
        confidence_milli=500,
    )


def _talk(
    engine: WorldEngine, *, speaker: int, listener: int, act: CreditFrameAct
) -> None:
    batch = engine.observe()
    utterance = origin_utterance(
        text="credit",
        speaker_id=EntityId(f"body-{speaker}"),
        relations=(credit_claim_relation(_frame(act)),),
    )
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId(f"agent-{speaker}"),
                Talk(recipient_id=EntityId(f"body-{listener}"), utterance=utterance),
            ),
            ActionSubmission(
                batch.token,
                AgentId(f"agent-{listener}"),
                Wait(),
            ),
        )
    )
    assert any(
        item.status is ActionResolutionStatus.APPLIED for item in result.resolutions
    )


def _give(engine: WorldEngine) -> None:
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Give(recipient_id=EntityId("body-2"), item_id=EntityId("a-food")),
            ),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
        )
    )
    assert any(
        item.status is ActionResolutionStatus.APPLIED for item in result.resolutions
    )


def _owner_ledger(events):
    claims: list[CreditClaim] = []
    repayments: list[CreditRepaymentObservation] = []
    tick = 0
    for event in events:
        tick = max(tick, event.tick)
        if type(event.details) in {Talked, Told}:
            details = event.details
            actor = event.actor_id
            if actor is None:
                continue
            for relation in details.utterance.content.relations:
                frame = parse_credit_claim_relation(relation)
                if frame is None:
                    continue
                self_authored = actor.value == "agent-1"
                claims.append(
                    CreditClaim(
                        act=CreditAct(frame.act.value),
                        direction=CreditDirection(frame.direction.value),
                        anchor=frame.anchor,
                        terms=CreditTerms(
                            principal_kind=ItemKind(frame.principal_kind_token),
                            principal_quantity=frame.principal_quantity,
                            repayment_kind=ItemKind(frame.repayment_kind_token),
                            repayment_quantity=frame.repayment_quantity,
                            due_tick=frame.due_tick,
                            condition=CreditCondition(frame.condition),
                            collateral_kind=CreditCollateralKind(
                                frame.collateral_kind
                            ),
                            collateral_item_kind=None,
                            collateral_quantity=frame.collateral_quantity,
                        ),
                        paid_quantity=frame.paid_quantity,
                        opened_tick=frame.opened_tick,
                        confidence_milli=frame.confidence_milli,
                        counterparty_id=EntityId(
                            details.recipient_id.value
                            if self_authored
                            else actor.value
                        ),
                        source=(
                            CreditClaimSource.SELF_AUTHORED
                            if self_authored
                            else CreditClaimSource.COMMUNICATED
                        ),
                        source_tick=event.tick,
                    )
                )
        elif type(event.details) is Given:
            if event.actor_id is not None and event.actor_id.value == "agent-1":
                repayments.append(
                    CreditRepaymentObservation(
                        counterparty_id=EntityId(event.details.recipient_id.value),
                        item_kind=ItemKind.FOOD,
                        quantity=1,
                        tick=event.tick,
                    )
                )
    return apply_credit_relationship_update(
        owner_id=AgentId("agent-1"),
        tick=tick,
        claims=tuple(claims),
        repayments=tuple(repayments),
    )


@pytest.mark.asyncio
async def test_real_engine_credit_snapshot_and_seven_routes(tmp_path: Path) -> None:
    engine = _engine()
    _talk(engine, speaker=1, listener=2, act=CreditFrameAct.PROPOSE)
    _talk(engine, speaker=2, listener=1, act=CreditFrameAct.ACCEPT)
    _give(engine)
    events = engine.export_events().events
    assert any(type(event.details) is Talked for event in events)
    assert any(type(event.details) is Given for event in events)

    ledger = _owner_ledger(events)
    assert ledger.rows
    runner_result = SimpleNamespace(credit_relationship_ledgers=(ledger,))
    publisher = create_credit_relationships_publisher(tmp_path / "store")
    harvest = build_credit_relationships_harvest_result(
        runner_result,
        committed_events=events,
        run_id=RUN,
        publisher=publisher,
    )
    assert harvest.receipt.stored is True
    assert harvest.analysis.claims
    assert harvest.analysis.performances
    assert harvest.snapshot.digest.startswith("sha256:")

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.credit_relationships_reader = create_credit_relationships_reader(
        tmp_path / "store"
    )
    app.state.credit_relationships_cursor_codec = CreditRelationshipsCursorCodec(
        b"k" * 32
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        summary = await client.get(
            f"/v1/simulations/{RUN}/credit-relationships", headers=HEADERS
        )
        assert summary.status_code == 200
        assert summary.json()["digest"] == harvest.snapshot.digest
        for purpose in (
            "relationships",
            "claims",
            "performances",
            "distributions",
            "counterparties",
            "alignment",
        ):
            response = await client.get(
                f"/v1/simulations/{RUN}/credit-relationships/{purpose}",
                headers=HEADERS,
            )
            assert response.status_code == 200


def test_real_runner_activates_and_exports_credit_ledgers() -> None:
    from simulation.runner import SimulationRunner
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V56,
        STRUCTURED_COMMITMENTS_POLICY_ID,
        SUBJECTIVE_VALUATION_POLICY_ID,
        RunnerStopPolicy,
        StructuredCommitmentsSpec,
        SubjectiveValuationSpec,
    )
    from tests.unit.test_credit_relationships_experiment import _base

    base = _base()
    configured = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=replace(
            base.v4_capability_flags, markets_credit=True
        ),
        structured_commitments=StructuredCommitmentsSpec(
            policy_id=STRUCTURED_COMMITMENTS_POLICY_ID,
            horizon_ticks=16,
            max_open_interpretations=8,
        ),
        subjective_valuation=SubjectiveValuationSpec(
            policy_id=SUBJECTIVE_VALUATION_POLICY_ID,
            horizon_ticks=16,
            max_bundle=8,
        ),
        stop_policy=RunnerStopPolicy(max_ticks=2),
    )

    async def execute() -> Any:
        async with await SimulationRunner.from_config(
            configured, run_id=RunId("run-credit-runner-e2e")
        ) as runner:
            return await runner.run()

    result = asyncio.run(execute())
    assert isinstance(result.credit_relationship_ledgers, tuple)
    assert len(result.credit_relationship_ledgers) == 1
    assert result.credit_relationship_ledgers[0].owner_id == AgentId("agent-1")
