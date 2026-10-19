"""Institution-concept loop wiring, updates, and communication."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.configuration import (
    CognitionInstitutionConceptMode,
    CognitionLoopConfig,
)
from agents.cognition.institution_concepts import (
    InstitutionConcept,
    InstitutionConceptLedger,
    InstitutionConceptStatus,
    InstitutionConceptualization,
    InstitutionPatternChannel,
    apply_institution_concept_update,
    institution_concept_id,
)
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.actions import Talk
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


def _agent(value: str = "ada") -> AgentId:
    return AgentId(value)


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_agent(),
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_agent("ben"), entity_id=EntityId("body-ben")),
        ),
    )


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-ada"),
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
            source_event_id=EventId(f"event-{tick}-{kind}"),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId(actor),
        success=True,
    )


def _observe(*occurrences: ObservedOccurrence, tick: int) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        occurrences=occurrences,
    )


def test_loop_defaults_and_slots_match_runner() -> None:
    assert "_institution_concept_mode" in CognitiveLoop.__slots__
    assert "_institution_concept_policy" in CognitiveLoop.__slots__
    config = CognitionLoopConfig()
    assert config.institution_concept_mode is CognitionInstitutionConceptMode.DISABLED
    assert config.institution_concept_policy is None


def test_fingerprint_separates_modes() -> None:
    disabled = CognitionLoopConfig()
    enabled = CognitionLoopConfig(
        institution_concept_mode=CognitionInstitutionConceptMode.DETERMINISTIC
    )
    assert (
        disabled.condition_fingerprint_material()["institution_concept_mode"]
        == "disabled"
    )
    assert (
        enabled.condition_fingerprint_material()["institution_concept_mode"]
        == "deterministic"
    )
    assert enabled.institution_concept_policy is not None


def test_update_builds_role_evidence_and_is_owner_scoped() -> None:
    identity = _identity()
    first = apply_institution_concept_update(
        _observe(_occurrence("repository_maintained", "body-ben", 1), tick=1),
        identity,
    )
    assert first is not None
    assert first.owner_id == identity.owner_id
    role_concepts = [
        concept for concept in first.concepts if concept.role_recognition > 0.0
    ]
    assert len(role_concepts) == 1
    assert role_concepts[0].evidence_count == 1
    assert role_concepts[0].role_recognition == pytest.approx(0.14, abs=1e-6)
    second = apply_institution_concept_update(
        _observe(_occurrence("repository_maintained", "body-ben", 2), tick=2),
        identity,
        first,
    )
    assert second is not None
    concept = next(item for item in second.concepts if item.role_recognition > 0.0)
    assert concept.evidence_count == 2
    assert concept.role_recognition > role_concepts[0].role_recognition
    with pytest.raises(ValueError, match="owner_id mismatch"):
        apply_institution_concept_update(
            _observe(tick=3),
            OwnerSafeSocialIdentity(
                owner_id=_agent("eve"),
                owner_entity_id=EntityId("body-eve"),
            ),
            second,
        )


def _recognized_concept(owner: AgentId) -> InstitutionConcept:
    anchor = "c" * 16
    return InstitutionConcept(
        concept_id=institution_concept_id(owner, (anchor,)),
        owner_id=owner,
        group_key="d" * 64,
        anchor_digests=(anchor,),
        status=InstitutionConceptStatus.RECOGNIZED,
        conceptualization=InstitutionConceptualization.NONE,
        role_recognition=0.6,
        procedure_recurrence=0.5,
        social_expectation=0.5,
        legitimacy_belief=0.0,
        succession_observed=0.0,
        generational_continuity=0.0,
        evidence_count=3,
        first_tick=1,
        last_tick=3,
    )


def _talk() -> Talk:
    utterance = origin_utterance(
        text="hello",
        speaker_id=EntityId("body-ada"),
        communication_id="comm-1",
        relations=(
            CommunicationRelation(subject="body-ada", predicate="call", object="x"),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    return Talk(recipient_id=EntityId("body-ben"), utterance=utterance)


def test_communication_stamps_only_in_deterministic_mode() -> None:
    from agents.cognition.institution_concepts import (
        institution_communicate_utterance,
    )

    identity = _identity()
    ledger = InstitutionConceptLedger(
        owner_id=identity.owner_id, concepts=(_recognized_concept(identity.owner_id),)
    )
    observation = _observe(tick=4)
    disabled = institution_communicate_utterance(
        _talk(),
        owner_id=identity.owner_id,
        tick=4,
        observation=observation,
        identity=identity,
        ledger=ledger,
        mode=CognitionInstitutionConceptMode.DISABLED,
    )
    assert isinstance(disabled, Talk)
    assert disabled.utterance.content.relations[0].predicate == "call"
    stamped = institution_communicate_utterance(
        _talk(),
        owner_id=identity.owner_id,
        tick=4,
        observation=observation,
        identity=identity,
        ledger=ledger,
        mode=CognitionInstitutionConceptMode.DETERMINISTIC,
    )
    assert isinstance(stamped, Talk)
    relation = stamped.utterance.content.relations[0]
    assert relation.predicate == "institution_pattern"
    assert relation.subject in {channel.value for channel in InstitutionPatternChannel}
    assert relation.object == "d" * 64


def test_receiver_forms_independent_concept_from_transmission() -> None:
    from world.observations import ObservedCommunication

    identity = _identity()
    utterance = origin_utterance(
        text="institution_pattern",
        speaker_id=EntityId("body-ben"),
        communication_id="comm-2",
        relations=(
            CommunicationRelation(
                subject=InstitutionPatternChannel.ROLE_RECOGNITION.value,
                predicate="institution_pattern",
                object="e" * 64,
            ),
        ),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=4,
            source_event_id=EventId("event-comm"),
        ),
        speaker_id=EntityId("body-ben"),
        listener_id=EntityId("body-ada"),
        utterance=utterance,
        action_kind="tell",
    )
    observation = Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=5,
        self_body=_self(),
        communications=(communication,),
    )
    ledger = apply_institution_concept_update(observation, identity)
    assert ledger is not None
    assert len(ledger.concepts) == 1
    concept = ledger.concepts[0]
    assert concept.evidence[0].channel.value == "communicated"
    assert concept.owner_id == identity.owner_id
    assert concept.group_key != "e" * 64


def test_custom_label_is_reachable_without_semantic_naming_mode() -> None:
    from agents.cognition.institution_concepts import (
        institution_communicate_utterance,
    )
    from world.observations import ObservedCommunication

    sender_identity = _identity()
    sender_concept = InstitutionConcept(
        concept_id=institution_concept_id(sender_identity.owner_id, ("c" * 16,)),
        owner_id=sender_identity.owner_id,
        group_key="d" * 64,
        anchor_digests=("c" * 16,),
        status=InstitutionConceptStatus.RECOGNIZED,
        conceptualization=InstitutionConceptualization.NAMED_CUSTOM,
        role_recognition=0.6,
        procedure_recurrence=0.5,
        social_expectation=0.5,
        legitimacy_belief=0.0,
        succession_observed=0.0,
        generational_continuity=0.0,
        evidence_count=3,
        first_tick=1,
        last_tick=3,
        label_token="custom_label",
    )
    sender_ledger = InstitutionConceptLedger(
        owner_id=sender_identity.owner_id, concepts=(sender_concept,)
    )
    talk = _talk()
    stamped = institution_communicate_utterance(
        talk,
        owner_id=sender_identity.owner_id,
        tick=4,
        observation=_observe(tick=4),
        identity=sender_identity,
        ledger=sender_ledger,
        mode=CognitionInstitutionConceptMode.DETERMINISTIC,
    )
    assert isinstance(stamped, Talk)
    predicates = [
        relation.predicate for relation in stamped.utterance.content.relations
    ]
    assert predicates == ["institution_pattern", "custom"]

    receiver_identity = OwnerSafeSocialIdentity(
        owner_id=_agent("ben"),
        owner_entity_id=EntityId("body-ben"),
        counterparts=(
            CounterpartBinding(agent_id=_agent("ada"), entity_id=EntityId("body-ada")),
        ),
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=4,
            source_event_id=EventId("event-custom"),
        ),
        speaker_id=EntityId("body-ada"),
        listener_id=EntityId("body-ben"),
        utterance=stamped.utterance,
        action_kind="tell",
    )
    observation = Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ben"),
        revision=WorldRevision(1),
        tick=5,
        self_body=replace(_self(), entity_id=EntityId("body-ben")),
        communications=(communication,),
    )
    receiver_ledger = apply_institution_concept_update(observation, receiver_identity)
    assert receiver_ledger is not None
    assert len(receiver_ledger.concepts) == 1
    concept = receiver_ledger.concepts[0]
    assert concept.owner_id == receiver_identity.owner_id
    assert concept.conceptualization is InstitutionConceptualization.NAMED_CUSTOM
    assert concept.label_token == "custom_label"
    assert concept.concept_id != sender_concept.concept_id
    assert any(item.channel.value == "communicated" for item in concept.evidence)
