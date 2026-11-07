# mypy: ignore-errors
"""In-process V4-13 border scenario with real ticks, publication, and routes."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition.borders import (
    AccessExpectationMode,
    AgreementAct,
    AgreementProvision,
    AgreementStatus,
    CounterpartyKind,
    DomainClaimStatus,
    apply_borders_update,
    default_borders_policy,
    domain_claim_token_id,
    empty_border_ledger,
)
from agents.cognition.borders_communication import (
    BORDER_FRAME_SUBJECT,
    BorderFrame,
    border_claim_relation,
)
from agents.cognition.territorial import (
    ClaimTargetKind,
    TerritorialClaim,
    TerritorialClaimLedger,
    territorial_claim_id,
)
from agents.models import AgentId
from api.borders_cursor import BordersCursorCodec
from api.dependencies import get_borders_reader, get_settings
from api.errors import ApiError, api_error_handler
from api.routes.borders import router
from infrastructure.settings import Settings
from persistence.borders_filesystem import (
    create_borders_publisher,
    create_borders_reader,
)
from world.communications import origin_utterance
from world.identifiers import EntityId, EventId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
PEER = AgentId("agent-2")
OWNER_ENTITY = EntityId("body-1")
PEER_ENTITY = EntityId("body-2")
LOC_A = EntityId("loc-a")
LOC_B = EntityId("loc-b")

IDENTITY = SimpleNamespace(
    owner_id=OWNER,
    owner_entity_id=OWNER_ENTITY,
    counterparts=(SimpleNamespace(entity_id=PEER_ENTITY, agent_id=PEER),),
)


def _claims() -> TerritorialClaimLedger:
    rows = []
    for location in (LOC_A, LOC_B):
        rows.append(
            TerritorialClaim(
                claim_id=territorial_claim_id(
                    OWNER, ClaimTargetKind.LOCATION, location
                ),
                owner_id=OWNER,
                target_kind=ClaimTargetKind.LOCATION,
                target_entity_id=location,
                strength=0.8,
                support_mass=0.8,
                contradiction_mass=0.0,
            )
        )
    return TerritorialClaimLedger(owner_id=OWNER, claims=tuple(rows))


def _frame(
    act: AgreementAct,
    *,
    owner: AgentId = PEER,
    locations: tuple[str, ...] = ("loc-a", "loc-b"),
    provision: AgreementProvision | None = None,
    access_mode: AccessExpectationMode | None = None,
) -> BorderFrame:
    return BorderFrame(
        act=act,
        domain_id=domain_claim_token_id(owner, locations),
        party_kind=CounterpartyKind.AGENT,
        party_ref="agent-1",
        locations=locations,
        access_mode=access_mode,
        provision=provision,
    )


def _communication(frame: BorderFrame):
    return SimpleNamespace(
        speaker_id=PEER_ENTITY,
        listener_id=OWNER_ENTITY,
        utterance=origin_utterance(
            text=BORDER_FRAME_SUBJECT,
            speaker_id=PEER_ENTITY,
            relations=border_claim_relation(frame),
        ),
    )


def _observation(*frames: BorderFrame):
    return SimpleNamespace(
        self_body=SimpleNamespace(location_id=LOC_A),
        exits=(SimpleNamespace(destination_id=LOC_B),),
        communications=tuple(_communication(frame) for frame in frames),
        regional_context=None,
    )


def _update(prior, observation):
    return apply_borders_update(
        owner_id=OWNER,
        tick=2,
        observation=observation,
        territorial_claims=_claims(),
        prior=prior,
        identity=IDENTITY,
        organization_concepts=None,
        diplomacy=None,
        policy=default_borders_policy(),
    )


def _event() -> SimpleNamespace:
    return SimpleNamespace(
        event_id=EventId("event-1"),
        tick=2,
        actor_id=OWNER_ENTITY,
        details=SimpleNamespace(kind="sleep"),
        occurrence=SimpleNamespace(
            origin_location_id=LOC_A, destination_location_id=None
        ),
    )


def _run_scenario():
    first = _update(
        empty_border_ledger(OWNER),
        _observation(
            _frame(
                AgreementAct.PROPOSE,
                provision=AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT,
            ),
            _frame(AgreementAct.CLAIM_DOMAIN),
            _frame(
                AgreementAct.DISPUTE_DOMAIN,
                locations=("loc-a",),
            ),
            _frame(
                AgreementAct.EXPECT_ACCESS,
                access_mode=AccessExpectationMode.RESTRICTED,
            ),
        ),
    )
    second = _update(
        first,
        _observation(
            _frame(
                AgreementAct.ACCEPT,
                provision=AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT,
            )
        ),
    )
    return second


def test_real_tick_and_border_scenario(tmp_path) -> None:
    from tests.unit.test_borders_carry import (
        _observation as runtime_observation,
    )
    from tests.unit.test_borders_carry import (
        _runtime,
        _token,
    )

    runtime = _runtime(borders=True)
    runtime.start()
    import asyncio

    result = asyncio.run(
        runtime.process_observation(runtime_observation(), token=_token())
    )
    assert result.loop_result is not None
    assert result.loop_result.borders is not None

    ledger = _run_scenario()
    assert len(ledger.domains) == 1
    assert ledger.domains[0].status in {
        DomainClaimStatus.DISPUTED,
        DomainClaimStatus.RECOGNIZED,
    }
    assert ledger.agreements[0].status is AgreementStatus.APPARENT_ACCEPTANCE
    assert ledger.access_expectations
    assert ledger.disputes

    from experiments.borders_publication import build_borders_harvest_result

    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        border_ledgers=(ledger,),
        organization_candidates=(),
        macro_society_analysis=None,
    )
    harvest_result = build_borders_harvest_result(runner, (_event(),), "run-e2e")
    assert harvest_result.snapshot is not None
    snapshot = harvest_result.snapshot
    assert snapshot.claims
    assert snapshot.agreements
    assert snapshot.physical
    assert snapshot.patterns

    root = tmp_path / "store"
    create_borders_publisher(root).publish(snapshot)

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(
        api_debug_enabled=True,
        api_debug_credential=SecretStr("test-debug-token-0123456789abcdef"),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_borders_reader(root)
    app.dependency_overrides[get_borders_reader] = lambda: reader
    app.state.borders_reader = reader
    app.state.borders_cursor_codec = BordersCursorCodec(b"k" * 32, now=lambda: 0.0)
    headers = {"x-palimpsest-token": "test-debug-token-0123456789abcdef"}

    async def call_routes():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            summary = await client.get(
                "/v1/simulations/run-e2e/borders", headers=headers
            )
            claims = await client.get(
                "/v1/simulations/run-e2e/borders/claims", headers=headers
            )
            agreements = await client.get(
                "/v1/simulations/run-e2e/borders/agreements", headers=headers
            )
            control = await client.get(
                "/v1/simulations/run-e2e/borders/control?layer=all",
                headers=headers,
            )
            return summary, claims, agreements, control

    summary, claims, agreements, control = asyncio.run(call_routes())
    assert summary.status_code == 200
    assert claims.status_code == 200
    assert agreements.status_code == 200
    assert control.status_code == 200
    for response in (summary, claims, agreements, control):
        text = response.text
        assert "agent-1" not in text
        assert "loc-a" not in text
        for forbidden in ("winner", "score", "sovereignty", "legitimacy"):
            assert forbidden not in text


def test_deterministic_twin_digest() -> None:
    first = _run_scenario()
    second = _run_scenario()
    assert first.digest == second.digest
