"""Structured office speech and fresh receiver interpretation."""

from __future__ import annotations

from enum import StrEnum

from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.offices import (
    OfficeConceptStatus,
    apply_office_concept_update,
    office_communicate_utterance,
)
from agents.models import AgentId
from world.actions import Talk, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


class _Mode(StrEnum):
    DETERMINISTIC = "deterministic"
    DISABLED = "disabled"


def _identity(owner: str = "ada", entity: str = "body-ada") -> OwnerSafeSocialIdentity:
    candidates = (
        ("ada", "body-ada"),
        ("ben", "body-ben"),
        ("carol", "body-carol"),
    )
    return OwnerSafeSocialIdentity(
        owner_id=AgentId(owner),
        owner_entity_id=EntityId(entity),
        counterparts=tuple(
            CounterpartBinding(agent_id=AgentId(agent), entity_id=EntityId(body))
            for agent, body in candidates
            if agent != owner
        ),
    )


def _self(entity: str = "body-ada") -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(entity),
        location_id=EntityId("clearing"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _occurrence(kind: str, actor: str, tick: int) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(f"event-{tick}-{kind}-{actor}"),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId(actor),
        success=True,
    )


def _observation(
    *,
    tick: int,
    entity: str = "body-ada",
    occurrences: tuple[ObservedOccurrence, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId(entity),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(entity),
        occurrences=occurrences,
        communications=communications,
    )


def _context(observation: Observation) -> str:
    from agents.cognition.offices import _context_key

    return _context_key(observation)


def _message(
    *,
    tick: int,
    speaker: str,
    root: str,
    context: str,
    predicate: str = "office_role",
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="office",
        speaker_id=EntityId(speaker),
        communication_id=root,
        relations=(
            CommunicationRelation(
                subject="help",
                predicate=predicate,
                object=f"{context}|-|-",
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(f"event-{root}"),
        ),
        speaker_id=EntityId(speaker),
        listener_id=EntityId("body-ada"),
        utterance=utterance,
        action_kind="tell",
    )


def _recognized_sender() -> tuple[object, str, _Mode]:
    context = _context(_observation(tick=2))
    ledger = None
    for tick in range(1, 6):
        ledger = apply_office_concept_update(
            _observation(
                tick=tick,
                occurrences=(_occurrence("help", "body-ben", tick),),
                communications=(
                    _message(
                        tick=tick,
                        speaker="body-ben",
                        root=f"role-ben-{tick}",
                        context=context,
                    ),
                    _message(
                        tick=tick,
                        speaker="body-carol",
                        root=f"role-carol-{tick}",
                        context=context,
                    ),
                ),
            ),
            _identity(),
            ledger,
        )
    assert ledger is not None
    assert ledger.concepts[0].status is OfficeConceptStatus.RECOGNIZED
    return ledger, context, _Mode.DETERMINISTIC


def test_office_speech_stamps_existing_talk_and_receiver_forms_fresh_evidence() -> None:
    sender_ledger, context, mode = _recognized_sender()
    talk = Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="base-comms",
            relations=(),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    observation = _observation(tick=6, entity="body-ada")
    stamped = office_communicate_utterance(
        talk,
        owner_id=AgentId("ada"),
        tick=6,
        observation=observation,
        identity=_identity(),
        ledger=sender_ledger,
        mode=mode,
    )
    assert isinstance(stamped, Talk)
    predicates = [
        relation.predicate for relation in stamped.utterance.content.relations
    ]
    assert "office_role" in predicates

    incoming = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=6,
            source_event_id=EventId("event-delivery"),
        ),
        speaker_id=EntityId("body-ada"),
        listener_id=EntityId("body-ben"),
        utterance=stamped.utterance,
        action_kind="talk",
    )
    receiver = apply_office_concept_update(
        _observation(tick=7, entity="body-ben", communications=(incoming,)),
        _identity("ben", "body-ben"),
    )
    assert receiver.concepts
    concept = receiver.concepts[0]
    assert concept.owner_id == AgentId("ben")
    assert all(
        item.channel.value == "communicated"
        for item in concept.evidence
        if item.context_key == context
    )
    assert concept.status is not OfficeConceptStatus.RECOGNIZED


def test_disabled_mode_does_not_stamp_communication() -> None:
    sender_ledger, _, _ = _recognized_sender()
    talk = Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="base-comms",
            relations=(),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    stamped = office_communicate_utterance(
        talk,
        owner_id=AgentId("ada"),
        tick=6,
        observation=_observation(tick=6),
        identity=_identity(),
        ledger=sender_ledger,
        mode=_Mode.DISABLED,
    )
    assert stamped is talk


def test_bare_non_communication_command_is_not_stamped() -> None:
    sender_ledger, _, mode = _recognized_sender()
    wait = Wait()
    stamped = office_communicate_utterance(
        wait,
        owner_id=AgentId("ada"),
        tick=6,
        observation=_observation(tick=6),
        identity=_identity(),
        ledger=sender_ledger,
        mode=mode,
    )
    assert stamped is wait


def test_receiver_trust_gates_uptake() -> None:
    sender_ledger, _context, mode = _recognized_sender()
    talk = Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="base-comms",
            relations=(),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    stamped = office_communicate_utterance(
        talk,
        owner_id=AgentId("ada"),
        tick=6,
        observation=_observation(tick=6),
        identity=_identity(),
        ledger=sender_ledger,
        mode=mode,
    )
    incoming = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=6,
            source_event_id=EventId("event-delivery"),
        ),
        speaker_id=EntityId("body-ada"),
        listener_id=EntityId("body-ben"),
        utterance=stamped.utterance,
        action_kind="talk",
    )
    receiver = apply_office_concept_update(
        _observation(tick=7, entity="body-ben", communications=(incoming,)),
        _identity("ben", "body-ben"),
        speaker_trust={"ada": 0.0},
    )
    assert receiver.concepts == ()


def test_duplicate_delivery_does_not_manufacture_independence() -> None:
    context = _context(_observation(tick=2))
    communication = _message(
        tick=2, speaker="body-ben", root="same-root", context=context
    )
    ledger = None
    for tick in range(2, 6):
        delivery = ObservedCommunication(
            provenance=ObservationProvenance(
                source_kind=ObservationSourceKind.COMMUNICATION,
                source_tick=tick - 1,
                source_event_id=EventId(f"event-copy-{tick}"),
            ),
            speaker_id=communication.speaker_id,
            listener_id=communication.listener_id,
            utterance=communication.utterance,
            action_kind="tell",
        )
        ledger = apply_office_concept_update(
            _observation(tick=tick, communications=(delivery,)),
            _identity(),
            ledger,
        )
    assert ledger is not None
    concept = ledger.concepts[0]
    assert concept.independent_root_count <= 1
    assert concept.status is not OfficeConceptStatus.RECOGNIZED


def test_role_reference_survives_occupant_change() -> None:
    sender_ledger, _, _ = _recognized_sender()
    original = sender_ledger.concepts[0]
    talk = Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="base-comms",
            relations=(),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    stamped = office_communicate_utterance(
        talk,
        owner_id=AgentId("ada"),
        tick=6,
        observation=_observation(tick=6),
        identity=_identity(),
        ledger=sender_ledger,
        mode=_Mode.DETERMINISTIC,
    )
    assert isinstance(stamped, Talk)
    assert stamped.utterance.content.relations[0].object.startswith(
        original.context_key
    )


def test_office_precedence_survives_prior_narrative_relations() -> None:
    sender_ledger, _, mode = _recognized_sender()
    talk = Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="narrative",
            speaker_id=EntityId("body-ada"),
            communication_id="narrative-comms",
            relations=(
                CommunicationRelation(
                    subject="narrative",
                    predicate="narrative_pattern",
                    object="opaque",
                ),
            ),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    stamped = office_communicate_utterance(
        talk,
        owner_id=AgentId("ada"),
        tick=6,
        observation=_observation(tick=6),
        identity=_identity(),
        ledger=sender_ledger,
        mode=mode,
    )
    predicates = {
        relation.predicate
        for relation in stamped.utterance.content.relations  # type: ignore[union-attr]
    }
    assert "office_role" in predicates
