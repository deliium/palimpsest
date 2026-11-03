"""V4-07: a social dispute never changes physical command admission."""

from __future__ import annotations

import inspect

import pytest

import agents.cognition.legal_disputes as legal_disputes
from agents.cognition import (
    DisputeAct,
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeFrame,
    DisputeKind,
    DisputeLedger,
    DisputeSubjectKind,
    apply_dispute_update,
    compile_dispute_undertaking,
    dispute_case_ref,
    dispute_frame_relation,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    weather_for_locations,
)
from world.actions import Give, Take
from world.communications import CommunicationSourceBasis, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)

pytestmark = pytest.mark.unit

OWNER = "agent-1"
OTHER = "agent-2"
OWNER_ENTITY = "body-1"
OTHER_ENTITY = "body-2"
SUBJECT = "item-1"
CASE_REF = dispute_case_ref(SUBJECT, (OWNER, OTHER))


def _bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body(OWNER_ENTITY, inventory=(EntityId(SUBJECT),)),
            alive_body(OTHER_ENTITY),
        ),
        items=(make_item(SUBJECT, holder_id=OWNER_ENTITY, location_id=None),),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId(OWNER), EntityId(OWNER_ENTITY)),
            AgentRegistration(AgentId(OTHER), EntityId(OTHER_ENTITY)),
        ),
    )


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=AgentId(OWNER),
        owner_entity_id=EntityId(OWNER_ENTITY),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId(OTHER), entity_id=EntityId(OTHER_ENTITY)
            ),
        ),
    )


def _frame() -> DisputeFrame:
    return DisputeFrame(
        act=DisputeAct.CLAIM,
        case_ref=CASE_REF,
        role=DisputeClaimRole.CLAIM,
        kind=DisputeKind.CONTESTED_DEBT,
        polarity=DisputeClaimPolarity.AFFIRM,
        party_ref=OTHER_ENTITY,
        subject_kind=DisputeSubjectKind.ITEM,
        subject_token=SUBJECT,
    )


def _disputed_ledger() -> DisputeLedger:
    relation = dispute_frame_relation(_frame())
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=1,
            source_event_id=EventId("event-1"),
        ),
        speaker_id=EntityId(OTHER_ENTITY),
        listener_id=EntityId(OWNER_ENTITY),
        utterance=origin_utterance(
            text="statement",
            speaker_id=EntityId(OTHER_ENTITY),
            communication_id="comm-1",
            relations=(relation,),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
        action_kind="tell",
    )
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId(OWNER_ENTITY),
        revision=WorldRevision(2),
        tick=2,
        communications=(communication,),
    )
    ledger = apply_dispute_update(OWNER, 2, observation, None, identity=_identity())
    assert ledger.cases
    assert ledger.claims
    return ledger


def test_social_dispute_does_not_change_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = _disputed_ledger()
    assert isinstance(ledger, DisputeLedger)
    assert ledger.cases[0].party_ids == (OWNER, OTHER)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("admission consulted a dispute ledger")

    monkeypatch.setattr(legal_disputes, "apply_dispute_update", forbidden)
    monkeypatch.setattr(legal_disputes, "record_dispute_utterance", forbidden)

    engine = WorldEngine(config=SimulationRunConfig(seed=21), bootstrap=_bootstrap())
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId(OWNER),
                command=Give(
                    recipient_id=EntityId(OTHER_ENTITY),
                    item_id=EntityId(SUBJECT),
                ),
            ),
        )
    )
    assert result.resolutions[0].status is not ActionResolutionStatus.REJECTED
    engine.observe()
    observed = engine.observation_for(AgentId(OTHER))
    assert observed.self_body is not None
    assert observed.self_body.inventory == (EntityId(SUBJECT),)


def test_physically_impossible_command_is_still_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = _disputed_ledger()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("admission consulted a dispute ledger")

    monkeypatch.setattr(legal_disputes, "apply_dispute_update", forbidden)
    monkeypatch.setattr(legal_disputes, "record_dispute_utterance", forbidden)

    engine = WorldEngine(config=SimulationRunConfig(seed=22), bootstrap=_bootstrap())
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId(OWNER),
                command=Take(item_id=EntityId("item-missing")),
            ),
        )
    )
    resolution = result.resolutions[0]
    assert resolution.status is ActionResolutionStatus.REJECTED
    assert resolution.reason is not None
    assert resolution.reason.value == "invalid_target"
    engine.observe()
    observed = engine.observation_for(AgentId(OTHER))
    assert observed.self_body is not None
    assert observed.self_body.inventory == ()
    transferred = [
        record.event
        for record in result.events
        if getattr(record.event.details, "kind", "") == "item_given"
    ]
    assert transferred == []


def test_admission_modules_never_import_dispute_cognition() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src"
    for relative in (
        "world/_rules.py",
        "world/_operations.py",
        "world/_perception.py",
        "simulation/engine.py",
        "simulation/actions.py",
    ):
        text = (root / relative).read_text(encoding="utf-8").lower()
        assert "dispute" not in text, relative


def test_only_the_mediation_undertaking_delegation_can_reach_a_command() -> None:
    source = inspect.getsource(compile_dispute_undertaking)
    assert "compile_mediation_undertaking(" in source
    for token in (
        "AgentCommand(",
        "Give(",
        "Take(",
        "Attack(",
        "Talk(",
        "Tell(",
        "Feed(",
        "Transport(",
        "Help(",
    ):
        assert token not in source, token
    assert ".submit(" not in source
    assert "resolve_tick" not in source
