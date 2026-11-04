"""V4-10 in-process end-to-end diplomacy path.

This scenario runs without PostgreSQL or Docker. It drives real objective
admission (a cross-region journey arrival that records co-presence), a real
``Talk`` carrying a ``dip_v1`` frame, a real representation ledger, the real
owner-scoped update, the real publication store, and the real read-only API
router. It does not write ledger rows directly into a runner result.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from agents.cognition import (
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticInstrumentStatus,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    apply_diplomacy_update,
    apply_representation_update,
    default_diplomacy_policy,
    default_representation_policy,
    diplomacy_communicate_utterance,
    diplomacy_envoy_status,
    diplomacy_instrument_status,
    empty_diplomacy_ledger,
    parse_diplomacy_frame_relation,
)
from agents.cognition.delegation_representation import RepresentationLedger
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)
from agents.cognition.diplomacy import DiplomacyLedger
from agents.models import AgentId
from analysis.diplomacy_lanes import (
    relation_rows_from_agreements,
    relation_rows_from_trade,
)
from api.dependencies import get_diplomacy_reader, get_settings
from api.diplomacy_cursor import DiplomacyCursorCodec
from api.errors import ApiError, api_error_handler
from api.routes.diplomacy import router
from experiments.catalog import base_runner_config_from_scenario
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
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
    weather_for_locations,
)
from world.actions import Talk, Wait
from world.communications import (
    CommunicationContent,
    CommunicationId,
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
)
from world.events import ExchangeCompleted
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.observations import Observation
from world.regions import (
    CognitionMode,
    Journey,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)

pytestmark = pytest.mark.unit

OWNER = "agent-b"
COUNTERPARTY = "agent-a"
ENVOY = "envoy-e"
BODY_OWNER = "body-e2e-b"
BODY_COUNTERPARTY = "body-e2e-a"
TOKEN = "test-debug-token-0123456789abcdef"
HEADERS = {"x-palimpsest-token": TOKEN}
RUN = "run-e2e"
_ENTITY_TO_AGENT = {BODY_COUNTERPARTY: COUNTERPARTY, BODY_OWNER: OWNER}


def _regions() -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "west"),
            LocationRegion(EntityId("loc-d"), "east"),
        ),
        routes=(RouteSpec(EntityId("loc-a"), EntityId("loc-d"), 1, 1),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=1,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _bootstrap() -> WorldBootstrap:
    locations = (
        make_location("loc-a", name="Camp", adjacent=("loc-d",)),
        make_location("loc-d", name="Market", adjacent=("loc-a",)),
    )
    journey = Journey(
        journey_id="journey-e2e",
        participant_body_ids=(EntityId(BODY_COUNTERPARTY),),
        actor_body_id=EntityId(BODY_COUNTERPARTY),
        origin_location_id=EntityId("loc-a"),
        destination_location_id=EntityId("loc-d"),
        origin_region_id="west",
        destination_region_id="east",
        start_tick=0,
        due_tick=1,
        charged_fatigue_cost=1,
        arrival_wait_deadline_tick=2,
    )
    return WorldBootstrap(
        world_id=WorldId("world-diplomacy-e2e"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body(
                BODY_COUNTERPARTY, location_id="loc-a", inventory=(EntityId("item-a"),)
            ),
            alive_body(
                BODY_OWNER, location_id="loc-d", inventory=(EntityId("item-b"),)
            ),
        ),
        items=(
            make_item("item-a", holder_id=BODY_COUNTERPARTY, location_id=None),
            make_item("item-b", holder_id=BODY_OWNER, location_id=None),
        ),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId(COUNTERPARTY), EntityId(BODY_COUNTERPARTY)),
            AgentRegistration(AgentId(OWNER), EntityId(BODY_OWNER)),
        ),
        regions_migration=_regions(),
        journeys=(journey,),
    )


def _contact_observation() -> Observation:
    engine = WorldEngine(
        config=SimulationRunConfig(seed=41),
        bootstrap=_bootstrap(),
        cultural_contact_active=True,
    )
    for _ in range(2):
        batch = engine.observe()
        resolved = engine.resolve_tick(
            (
                ActionSubmission(
                    token=batch.token,
                    agent_id=AgentId(COUNTERPARTY),
                    command=Wait(),
                ),
            )
        )
        assert resolved.resolutions[0].status is ActionResolutionStatus.APPLIED

    observation = next(
        item
        for item in engine.observe().observations
        if item.observer_id == EntityId(BODY_OWNER)
    )
    contacts = tuple(
        occurrence
        for occurrence in observation.occurrences
        if occurrence.kind == "contact_recorded"
    )
    assert contacts

    def _agent_ids(values: Sequence[object]) -> list[str]:
        return [
            _ENTITY_TO_AGENT[str(getattr(value, "value", value))]
            for value in values
        ]

    mapped = tuple(
        replace(
            occurrence,
            public_facts={
                **occurrence.public_facts,
                "contact_participant_ids": _agent_ids(
                    cast(
                        Sequence[object],
                        occurrence.public_facts.get("contact_participant_ids", ()),
                    )
                ),
            },
        )
        for occurrence in contacts
    )
    return replace(observation, occurrences=mapped)


def _representation_frame(
    act: RepresentationAct,
    *,
    actor: str,
    mandate_ref: str | None = None,
) -> RepresentationFrame:
    return RepresentationFrame(
        act=act,
        mandate_ref=mandate_ref,
        principal_kind=RepresentationPrincipalKind.AGENT,
        principal_ref=OWNER,
        representative_ref=ENVOY,
        scope_kind=RepresentationScopeKind.NEGOTIATE,
        scope_subject="trade",
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        provenance=RepresentationProvenance.SELF_DECLARED,
        actor_ref=actor,
    )


def _recognized_representation() -> tuple[RepresentationLedger, str]:
    policy = default_representation_policy()
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=1,
        observation=None,
        prior=None,
        frames=(_representation_frame(RepresentationAct.CLAIM, actor=ENVOY),),
        policy=policy,
    )
    mandate_id = ledger.mandates[-1].mandate_id
    ledger = apply_representation_update(
        owner_id=OWNER,
        tick=2,
        observation=None,
        prior=ledger,
        frames=(
            _representation_frame(
                RepresentationAct.ACCEPT, actor=OWNER, mandate_ref=mandate_id
            ),
        ),
        policy=policy,
    )
    mandate = next(row for row in ledger.mandates if row.mandate_id == mandate_id)
    assert mandate.status.value == "recognized"
    return ledger, mandate_id


def _talk(frame: DiplomacyFrame) -> DiplomacyFrame:
    speech_frame = replace(
        frame, envoy_ref=BODY_OWNER, actor_ref=BODY_OWNER
    )
    command = Talk(
        recipient_id=EntityId(BODY_COUNTERPARTY),
        utterance=StructuredUtterance(
            content=CommunicationContent(
                text="diplomacy",
                concepts=(),
                relations=(),
            ),
            declared=DeclaredTransmission(
                communication_id=CommunicationId("comm-dip-e2e"),
                immediate_source_id=EntityId(BODY_OWNER),
                parent_communication_id=None,
                root_communication_id=CommunicationId("comm-dip-e2e"),
                source_agent_chain=(EntityId(BODY_OWNER),),
                hop_count=0,
                sender_confidence=0.8,
                source_basis=CommunicationSourceBasis.GOAL,
            ),
        ),
    )
    attached = cast(Talk, diplomacy_communicate_utterance(command, speech_frame))
    relation = next(
        atom
        for atom in attached.utterance.content.relations
        if atom.subject == "dip_v1"
    )
    parsed = parse_diplomacy_frame_relation(
        relation.subject, relation.predicate, relation.object
    )
    assert parsed is not None
    return replace(parsed, envoy_ref=OWNER, actor_ref=OWNER)


def _frame(act: DiplomaticAct, **overrides: object) -> DiplomacyFrame:
    values: dict[str, object] = {
        "act": act,
        "envoy_ref": OWNER,
        "actor_ref": OWNER,
        "party_kind": DiplomaticPartyKind.AGENT,
        "party_ref": COUNTERPARTY,
    }
    if act in {
        DiplomaticAct.PROPOSE,
        DiplomaticAct.PROMISE,
        DiplomaticAct.SHARED_PROJECT,
        DiplomaticAct.OPEN_NEGOTIATION,
        DiplomaticAct.DISPUTE,
    }:
        values["topic_subject"] = "trade"
    if act in {
        DiplomaticAct.PROPOSE,
        DiplomaticAct.PROMISE,
        DiplomaticAct.SHARED_PROJECT,
        DiplomaticAct.DISPUTE,
    }:
        values["term_kind"] = DiplomaticTermKind.MATERIAL_EXCHANGE
    values.update(overrides)
    return DiplomacyFrame(**values)  # type: ignore[arg-type]


def _update(
    prior: DiplomacyLedger | None,
    frames: tuple[DiplomacyFrame, ...],
    *,
    tick: int,
    representation: object = None,
) -> DiplomacyLedger:
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=None,
        prior=prior,
        frames=frames,
        representation=representation,
        policy=default_diplomacy_policy(),
    )


def test_full_diplomacy_path(tmp_path: Path) -> None:
    observation = _contact_observation()
    representation, mandate_id = _recognized_representation()

    ledger = empty_diplomacy_ledger(OWNER, tick=0)
    speech = _talk(_frame(DiplomaticAct.PROPOSE))
    ledger = apply_diplomacy_update(
        owner_id=OWNER,
        tick=1,
        observation=observation,
        prior=ledger,
        frames=(speech,),
        representation=representation,
        policy=default_diplomacy_policy(),
    )
    assert ledger.relations
    assert ledger.contacts
    relation_id = ledger.relations[0].relation_id
    instrument_id = ledger.instruments[0].instrument_id

    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.ACCREDIT,
                envoy_ref=ENVOY,
                actor_ref=ENVOY,
                party_ref=OWNER,
                mandate_ref=mandate_id,
                relation_ref=relation_id,
            ),
        ),
        tick=2,
        representation=representation,
    )
    envoy = ledger.envoys[-1]
    assert (
        diplomacy_envoy_status(
            envoy, representation, tick=2, policy=default_diplomacy_policy()
        ).value
        == "recognized"
    )

    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.OPEN_NEGOTIATION,
                envoy_ref=ENVOY,
                actor_ref=ENVOY,
                party_ref=OWNER,
                relation_ref=relation_id,
            ),
        ),
        tick=2,
        representation=representation,
    )
    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.PROMISE,
                envoy_ref=ENVOY,
                actor_ref=ENVOY,
                party_ref=OWNER,
                relation_ref=relation_id,
            ),
            _frame(
                DiplomaticAct.SHARED_PROJECT,
                envoy_ref=ENVOY,
                actor_ref=ENVOY,
                party_ref=OWNER,
                relation_ref=relation_id,
            ),
        ),
        tick=3,
        representation=representation,
    )

    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.ACCEPT,
                envoy_ref=COUNTERPARTY,
                actor_ref=COUNTERPARTY,
                party_ref=COUNTERPARTY,
                instrument_ref=instrument_id,
                revision=1,
            ),
            _frame(
                DiplomaticAct.ACCEPT,
                envoy_ref=OWNER,
                actor_ref=OWNER,
                party_ref=OWNER,
                instrument_ref=instrument_id,
                revision=1,
            ),
        ),
        tick=4,
    )
    status, _ = diplomacy_instrument_status(
        ledger.instruments[0],
        ledger.declarations,
        tick=4,
        policy=default_diplomacy_policy(),
        representation=representation,
        envoys=ledger.envoys,
    )
    assert status is DiplomaticInstrumentStatus.APPARENTLY_ACCEPTED

    ledger = _update(
        ledger,
        (
            _frame(
                DiplomaticAct.RECALL,
                envoy_ref=ENVOY,
                actor_ref=ENVOY,
                party_ref=OWNER,
                relation_ref=relation_id,
            ),
        ),
        tick=5,
    )
    assert any(row.target_kind == "envoy" for row in ledger.terminations)

    runner_result = SimpleNamespace(
        run_id=SimpleNamespace(value=RUN),
        ticks_committed=5,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(ledger,),
    )
    harvest = build_completed_run_diplomacy_harvest(runner_result)
    assert harvest.rows.relations
    assert harvest.rows.instruments
    assert harvest.rows.declarations
    assert harvest.rows.contacts
    assert relation_rows_from_agreements(harvest.rows.declarations)

    completed = ExchangeCompleted(
        actor_id=EntityId(BODY_COUNTERPARTY),
        counterparty_id=EntityId(BODY_OWNER),
        act="accept",
        give_item_ids=(EntityId("item-a"),),
        take_item_ids=(EntityId("item-b"),),
        give_item_kinds=("generic",),
        take_item_kinds=("generic",),
    )
    trade_rows = relation_rows_from_trade((SimpleNamespace(details=completed),))
    assert trade_rows

    frozen = runner_result.diplomacy_ledgers
    result = build_diplomacy_harvest_result(
        harvest, run_id=RUN, revision="rev-e2e", window_end=5
    )
    assert result.snapshot is not None, result.receipt
    publisher = FilesystemDiplomacyPublisher(tmp_path / "store")
    published = publish_diplomacy_snapshot(result, publisher)
    assert published.published
    assert runner_result.diplomacy_ledgers == frozen

    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    settings = Settings(api_debug_enabled=True, api_debug_credential=SecretStr(TOKEN))
    app.dependency_overrides[get_settings] = lambda: settings
    reader = create_diplomacy_reader(tmp_path / "store")
    app.dependency_overrides[get_diplomacy_reader] = lambda: reader
    app.state.diplomacy_reader = reader
    app.state.diplomacy_cursor_codec = DiplomacyCursorCodec(b"k" * 32)

    async def read_all() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            summary = await client.get(
                f"/v1/simulations/{RUN}/diplomacy", headers=HEADERS
            )
            assert summary.status_code == 200
            assert summary.json()["relation_count"] >= 1

            relations = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/relations", headers=HEADERS
            )
            assert relations.status_code == 200
            relation_payload = relations.json()["items"]
            assert relation_payload
            detail = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/relations/"
                f"{relation_payload[0]['relation_id']}",
                headers=HEADERS,
            )
            assert detail.status_code == 200
            assert detail.json()["terminations"]

            instruments = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/instruments", headers=HEADERS
            )
            assert instruments.status_code == 200
            instrument_payload = instruments.json()["items"]
            assert instrument_payload
            instrument_detail = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/instruments/"
                f"{instrument_payload[0]['instrument_id']}",
                headers=HEADERS,
            )
            assert instrument_detail.status_code == 200
            assert instrument_detail.json()["declarations"]

            lineage = await client.get(
                f"/v1/simulations/{RUN}/diplomacy/lineage", headers=HEADERS
            )
            assert lineage.status_code == 200

            assert OWNER not in str(detail.json())

    asyncio.run(read_all())


def test_flags_off_yield_no_harvest_rows() -> None:
    result = SimpleNamespace(
        run_id=SimpleNamespace(value="run-off"),
        ticks_committed=1,
        stop_reason=SimpleNamespace(value="max_ticks"),
        diplomacy_ledgers=(),
    )
    harvest = build_completed_run_diplomacy_harvest(result)
    assert not harvest.rows.has_any_rows()
    assert (
        build_diplomacy_harvest_result(
            harvest, run_id="run-off", revision="rev", window_end=1
        ).receipt["status"]
        == "disabled"
    )


@pytest.mark.asyncio
async def test_runner_exports_owner_diplomacy_ledgers() -> None:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    config = replace(
        base_runner_config_from_scenario(
            seed=11,
            stochastic_identity="cmp-v4-diplomacy-e2e-export",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-diplomacy-export"),
                revision=WorldRevision(0),
                physical_rules=default_physical_rules(),
                locations=(make_location("loc-1", name="Camp"),),
                bodies=(body,),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_id,
                    entity_id=body.entity_id,
                    cognition=AgentCognitionSpec(agent_id=agent_id),
                ),
            ),
            max_ticks=1,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(diplomacy=True, organizations=True),
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-diplomacy-export")
    ) as runner:
        result = await runner.run()

    assert len(result.diplomacy_ledgers) == 1
    ledger = cast(DiplomacyLedger, result.diplomacy_ledgers[0])
    assert ledger.owner_id == "agent-1"
    assert ledger.policy_version == "diplomacy.v1"
