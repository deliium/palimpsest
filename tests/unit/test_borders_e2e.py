# mypy: ignore-errors
"""In-process V4-13 border scenario with real ticks, commands, and routes."""

from __future__ import annotations

import asyncio
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
    BorderLedger,
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
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from tests.physical_helpers import stressed_body
from tests.simulation_helpers import connected_locations, weather_for_locations
from world.actions import Move, Tell, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
PEER = AgentId("agent-2")
PEER3 = AgentId("agent-3")
OWNER_ENTITY = EntityId("body-1")
PEER_ENTITY = EntityId("body-2")
PEER3_ENTITY = EntityId("body-3")
LOC_A = EntityId("loc-a")
LOC_B = EntityId("loc-b")
RUN = "run-e2e"
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}

IDENTITY = SimpleNamespace(
    owner_id=OWNER,
    owner_entity_id=OWNER_ENTITY,
    counterparts=(
        SimpleNamespace(entity_id=PEER_ENTITY, agent_id=PEER),
        SimpleNamespace(entity_id=PEER3_ENTITY, agent_id=PEER3),
    ),
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
    party_ref: str = "agent-1",
    provision: AgreementProvision | None = None,
    access_mode: AccessExpectationMode | None = None,
) -> BorderFrame:
    return BorderFrame(
        act=act,
        domain_id=domain_claim_token_id(owner, locations),
        party_kind=CounterpartyKind.AGENT,
        party_ref=party_ref,
        locations=locations,
        access_mode=access_mode,
        provision=provision,
    )


def _tell(
    *,
    speaker_entity: EntityId,
    frame: BorderFrame,
) -> Tell:
    return Tell(
        recipient_id=OWNER_ENTITY,
        utterance=origin_utterance(
            text=BORDER_FRAME_SUBJECT,
            speaker_id=speaker_entity,
            relations=border_claim_relation(frame),
        ),
    )


def _bootstrap() -> WorldBootstrap:
    locations = connected_locations(("loc-a", "Camp"), ("loc-b", "Field"))
    return WorldBootstrap(
        world_id=WorldId("world-border-e2e"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            stressed_body(
                "body-1",
                location_id="loc-a",
                health=100,
                hunger=0,
                thirst=0,
                fatigue=0,
            ),
            stressed_body(
                "body-2",
                location_id="loc-b",
                health=100,
                hunger=0,
                thirst=0,
                fatigue=0,
            ),
            stressed_body(
                "body-3",
                location_id="loc-b",
                health=100,
                hunger=0,
                thirst=0,
                fatigue=0,
            ),
        ),
        items=(),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(OWNER, OWNER_ENTITY),
            AgentRegistration(PEER, PEER_ENTITY),
            AgentRegistration(PEER3, PEER3_ENTITY),
        ),
    )


def _observe(engine: WorldEngine, body_id: EntityId):
    batch = engine.observe()
    observation = next(
        item for item in batch.observations if item.observer_id == body_id
    )
    return batch, observation


def _submit(batch, agent_id: AgentId, command) -> ActionSubmission:
    return ActionSubmission(token=batch.token, agent_id=agent_id, command=command)


def _apply(prior: BorderLedger, observation, tick: int) -> BorderLedger:
    return apply_borders_update(
        owner_id=OWNER,
        tick=tick,
        observation=observation,
        territorial_claims=_claims(),
        prior=prior,
        identity=IDENTITY,
        organization_concepts=None,
        diplomacy=None,
        policy=default_borders_policy(),
    )


def _real_world_run() -> tuple[BorderLedger, tuple[object, ...]]:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=31),
        bootstrap=_bootstrap(),
    )
    ledger = empty_border_ledger(OWNER)
    events: list[object] = []

    # Tick 0: the owner moves to the peer location; this is a real Moved event.
    batch, _ = _observe(engine, OWNER_ENTITY)
    result = engine.resolve_tick(
        (
            _submit(batch, OWNER, Move(destination_id=LOC_B)),
            _submit(batch, PEER, Wait()),
            _submit(batch, PEER3, Wait()),
        )
    )
    events.extend(record.event for record in result.events)

    # Tick 1: the peer claims the same logical set.
    batch, _ = _observe(engine, OWNER_ENTITY)
    result = engine.resolve_tick(
        (
            _submit(batch, OWNER, Wait()),
            _submit(
                batch,
                PEER,
                _tell(
                    speaker_entity=PEER_ENTITY,
                    frame=_frame(AgreementAct.CLAIM_DOMAIN),
                ),
            ),
            _submit(batch, PEER3, Wait()),
        )
    )
    events.extend(record.event for record in result.events)
    _, observation = _observe(engine, OWNER_ENTITY)
    ledger = _apply(ledger, observation, 1)

    # Tick 2: the peer proposes a territorial acknowledgement.
    batch, _ = _observe(engine, OWNER_ENTITY)
    result = engine.resolve_tick(
        (
            _submit(batch, OWNER, Wait()),
            _submit(
                batch,
                PEER,
                _tell(
                    speaker_entity=PEER_ENTITY,
                    frame=_frame(
                        AgreementAct.PROPOSE,
                        provision=AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT,
                    ),
                ),
            ),
            _submit(batch, PEER3, Wait()),
        )
    )
    events.extend(record.event for record in result.events)
    _, observation = _observe(engine, OWNER_ENTITY)
    ledger = _apply(ledger, observation, 2)

    # Tick 3: a different peer accepts; the proposer cannot self-accept.
    batch, _ = _observe(engine, OWNER_ENTITY)
    result = engine.resolve_tick(
        (
            _submit(batch, OWNER, Wait()),
            _submit(batch, PEER, Wait()),
            _submit(
                batch,
                PEER3,
                _tell(
                    speaker_entity=PEER3_ENTITY,
                    frame=_frame(
                        AgreementAct.ACCEPT,
                        owner=PEER3,
                        provision=AgreementProvision.TERRITORIAL_ACKNOWLEDGEMENT,
                    ),
                ),
            ),
        )
    )
    events.extend(record.event for record in result.events)
    _, observation = _observe(engine, OWNER_ENTITY)
    ledger = _apply(ledger, observation, 3)

    # Tick 4: the peer declares an explicit access expectation.
    batch, _ = _observe(engine, OWNER_ENTITY)
    result = engine.resolve_tick(
        (
            _submit(batch, OWNER, Wait()),
            _submit(
                batch,
                PEER,
                _tell(
                    speaker_entity=PEER_ENTITY,
                    frame=_frame(
                        AgreementAct.EXPECT_ACCESS,
                        access_mode=AccessExpectationMode.RESTRICTED,
                    ),
                ),
            ),
            _submit(batch, PEER3, Wait()),
        )
    )
    events.extend(record.event for record in result.events)
    _, observation = _observe(engine, OWNER_ENTITY)
    ledger = _apply(ledger, observation, 4)
    return ledger, tuple(events)


def _move_only_run() -> BorderLedger:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=37),
        bootstrap=_bootstrap(),
    )
    ledger = empty_border_ledger(OWNER)
    batch, _ = _observe(engine, OWNER_ENTITY)
    engine.resolve_tick(
        (
            _submit(batch, OWNER, Move(destination_id=LOC_B)),
            _submit(batch, PEER, Wait()),
            _submit(batch, PEER3, Wait()),
        )
    )
    _, observation = _observe(engine, OWNER_ENTITY)
    return _apply(ledger, observation, 1)


def _publish_and_read(tmp_path):
    ledger, events = _real_world_run()
    assert ledger.domains
    assert ledger.agreements
    assert ledger.access_expectations
    assert ledger.disputes
    event_kinds = {
        getattr(getattr(event, "details", None), "kind", None) for event in events
    }
    assert {"move", "tell"} <= event_kinds

    from experiments.borders_publication import build_borders_harvest_result

    runner = SimpleNamespace(
        stop_reason=SimpleNamespace(value="max_ticks"),
        border_ledgers=(ledger,),
        organization_candidates=(),
        macro_society_analysis=None,
    )
    harvest_result = build_borders_harvest_result(runner, events, RUN)
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
        api_debug_credential=SecretStr(TOKEN),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_borders_reader(root)
    app.dependency_overrides[get_borders_reader] = lambda: reader
    app.state.borders_reader = reader
    app.state.borders_cursor_codec = BordersCursorCodec(b"k" * 32, now=lambda: 0.0)

    claim_id = snapshot.claims[0].claim_token
    agreement_id = snapshot.agreements[0].agreement_token

    async def call_routes():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            paths = (
                f"/v1/simulations/{RUN}/borders",
                f"/v1/simulations/{RUN}/borders/claims",
                f"/v1/simulations/{RUN}/borders/claims/{claim_id}",
                f"/v1/simulations/{RUN}/borders/agreements",
                f"/v1/simulations/{RUN}/borders/agreements/{agreement_id}",
                f"/v1/simulations/{RUN}/borders/control?layer=all",
            )
            return [await client.get(path, headers=HEADERS) for path in paths]

    return asyncio.run(call_routes())


def test_real_world_ticks_publication_and_all_six_routes(tmp_path) -> None:
    responses = _publish_and_read(tmp_path)
    assert [response.status_code for response in responses] == [200] * 6
    for response in responses:
        text = response.text
        assert "agent-1" not in text
        assert "loc-a" not in text
        for forbidden in ("winner", "score", "sovereignty", "legitimacy"):
            assert forbidden not in text


def test_no_peer_frames_yields_no_peer_beliefs() -> None:
    ledger = _move_only_run()
    assert ledger.domains
    assert not ledger.agreements
    assert not ledger.access_expectations
    assert not ledger.disputes


def test_deterministic_twin_digest() -> None:
    first, _ = _real_world_run()
    second, _ = _real_world_run()
    assert first.digest == second.digest
    assert first.agreements[0].status is AgreementStatus.APPARENT_ACCEPTANCE
    assert first.domains[0].status in {
        DomainClaimStatus.DISPUTED,
        DomainClaimStatus.RECOGNIZED,
    }
