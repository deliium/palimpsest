"""Owner-local grounding and deterministic retention for institutional memory."""

from __future__ import annotations

import pytest

from agents.cognition.institution_concepts import (
    InstitutionConcept,
    InstitutionConceptEvidence,
    InstitutionConceptLedger,
    InstitutionConceptStatus,
    InstitutionConceptualization,
    InstitutionEvidenceChannel,
    InstitutionPatternChannel,
    institution_concept_id,
)
from agents.cognition.institutional_memory import (
    InstitutionalBindingKind,
    InstitutionalMemoryChannel,
    InstitutionalOccupantStatus,
    apply_institutional_memory_update,
    empty_institutional_memory_ledger,
    institutional_entity_token,
    institutional_role_token,
)
from agents.cognition.models import (
    OwnerSafeSocialIdentity,
    RetrievedMemoryContext,
)
from agents.cognition.offices import (
    OfficeConcept,
    OfficeConceptLedger,
    OfficeConceptStatus,
    OfficeDutyBelief,
    OfficeDutyKind,
    OfficeEvidence,
    OfficeEvidenceChannel,
    OfficeFunction,
    OfficeOccupantClaim,
    OfficeOccupantStatus,
    office_concept_id,
    office_inception_digest,
    office_role_signature,
)
from agents.models import AgentId
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

_CONTEXT = "a" * 16
_OTHER_CONTEXT = "b" * 16
_INCEPTION = "c" * 64
_OWNER = AgentId("alice")


def _identity(owner: AgentId = _OWNER) -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId(f"{owner.value}-body"),
    )


def _observation(
    *,
    tick: int = 1,
    occurrences: tuple[ObservedOccurrence, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world"),
        observer_id=EntityId(f"{_OWNER.value}-body"),
        revision=WorldRevision(tick),
        tick=tick,
        occurrences=occurrences,
    )


def _office_evidence(
    *,
    event_ref: str = "event-1",
    tick: int = 1,
    context: str = _CONTEXT,
    function: OfficeFunction = OfficeFunction.EXCHANGE,
) -> OfficeEvidence:
    return OfficeEvidence(
        evidence_id="1" * 64,
        ordinal=0,
        channel=OfficeEvidenceChannel.OBSERVED,
        lineage_ref=event_ref,
        root_ref="root-1",
        tick=tick,
        context_key=context,
        function=function,
        actor_id=AgentId("actor-x"),
    )


def _office_concept(
    *,
    owner: AgentId = _OWNER,
    context: str = _CONTEXT,
    function: OfficeFunction = OfficeFunction.EXCHANGE,
    collision: int = 0,
    status: OfficeConceptStatus = OfficeConceptStatus.RECOGNIZED,
    occupant: AgentId | None = None,
    duty_kind: OfficeDutyKind = OfficeDutyKind.PERFORM,
    duty_id: str | None = None,
    tick: int = 1,
) -> OfficeConcept:
    inception = office_inception_digest(function, context, _INCEPTION)
    office_id = office_concept_id(owner, inception, collision)
    evidence = _office_evidence(tick=tick, context=context, function=function)
    duties = (
        OfficeDutyBelief(
            duty_id=duty_id or "d" * 64,
            kind=duty_kind,
            function=function,
            context_key=context,
            strength=0.6,
            first_tick=tick,
            last_tick=tick,
            evidence_ids=(evidence.evidence_id,),
        ),
    )
    occupants: tuple[OfficeOccupantClaim, ...] = ()
    if occupant is not None:
        occupants = (
            OfficeOccupantClaim(
                claim_id="2" * 64,
                occupant_id=occupant,
                status=OfficeOccupantStatus.PREFERRED,
                support_strength=0.6,
                opposition_strength=0.0,
                first_tick=tick,
                last_tick=tick,
                evidence_ids=(evidence.evidence_id,),
            ),
        )
    return OfficeConcept(
        office_id=office_id,
        owner_id=owner,
        function=function,
        context_key=context,
        inception_digest=inception,
        collision_discriminator=collision,
        role_signature=office_role_signature(function, context, (duty_kind,)),
        status=status,
        function_strength=0.7,
        expectation_strength=0.6,
        endorsement_strength=0.5,
        first_tick=tick,
        last_tick=tick,
        evidence_count=1,
        independent_root_count=1,
        duties=duties,
        occupants=occupants,
        evidence=(evidence,),
    )


def _procedure_concept(
    *,
    owner: AgentId = _OWNER,
    anchors: tuple[str, ...] = ("a" * 16,),
    group_key: str = "ab" * 32,
    recurrence: float = 0.5,
    evidence_tick: int = 1,
) -> InstitutionConcept:
    evidence = InstitutionConceptEvidence(
        evidence_id="3" * 64,
        ordinal=0,
        channel=InstitutionEvidenceChannel.OBSERVED,
        pattern=InstitutionPatternChannel.PROCEDURE_RECURRENCE,
        lineage_ref="event-1",
        tick=evidence_tick,
        anchor_digest=anchors[0],
        actor_id=AgentId("actor-x"),
    )
    return InstitutionConcept(
        concept_id=institution_concept_id(owner, anchors),
        owner_id=owner,
        group_key=group_key,
        anchor_digests=anchors,
        status=InstitutionConceptStatus.RECOGNIZED,
        conceptualization=InstitutionConceptualization.NONE,
        role_recognition=0.0,
        procedure_recurrence=recurrence,
        social_expectation=0.0,
        legitimacy_belief=0.0,
        succession_observed=0.0,
        generational_continuity=0.0,
        evidence_count=1,
        first_tick=evidence_tick,
        last_tick=evidence_tick,
        evidence=(evidence,),
    )


def test_role_channel_uses_stable_office_identity_and_copies_claims() -> None:
    concept = _office_concept(occupant=AgentId("bob"))
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,)),
    )
    assert len(ledger.channels) == 1
    channel = ledger.channels[0]
    assert channel.binding_kind is InstitutionalBindingKind.ROLE
    assert channel.inception_reference == concept.office_id
    assert channel.current_local_reference == concept.office_id
    assert channel.public_function_token == institutional_role_token(
        concept.function.value, concept.context_key
    )
    assert channel.occupants[0].occupant_id == AgentId("bob")
    assert channel.occupants[0].status is InstitutionalOccupantStatus.CLAIMED
    assert any(
        fact.object == institutional_entity_token("bob")
        for entry in ledger.entries
        for fact in entry.facts
    )


def test_occupant_replacement_keeps_channel_but_adds_no_private_content() -> None:
    first = _office_concept(occupant=AgentId("bob"))
    second = _office_concept(occupant=AgentId("carol"), tick=3)
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=1),
        identity=_identity(),
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(first,)),
    )
    channel_id = ledger.channels[0].channel_id
    bob_facts = tuple(
        fact
        for entry in ledger.entries
        for fact in entry.facts
        if fact.object == institutional_entity_token("bob")
    )
    updated = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=3),
        identity=_identity(),
        previous=ledger,
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(second,)),
    )
    assert updated.channels[0].channel_id == channel_id
    assert updated.channels[0].occupants[0].occupant_id == AgentId("carol")
    retained_bob = tuple(
        fact
        for entry in updated.entries
        for fact in entry.facts
        if fact.object == institutional_entity_token("bob")
    )
    assert retained_bob == bob_facts


def test_role_signature_revision_does_not_reset_channel() -> None:
    first = _office_concept(duty_kind=OfficeDutyKind.PERFORM)
    second = _office_concept(
        duty_kind=OfficeDutyKind.COORDINATE, tick=4, duty_id="e" * 64
    )
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(first,)),
    )
    channel_id = ledger.channels[0].channel_id
    updated = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=4),
        identity=_identity(),
        previous=ledger,
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(second,)),
    )
    assert updated.channels[0].channel_id == channel_id
    assert updated.channels[0].revision_count == 0
    assert {fact.object for entry in updated.entries for fact in entry.facts} >= {
        OfficeDutyKind.PERFORM.value,
        OfficeDutyKind.COORDINATE.value,
    }


def test_procedure_channel_requires_retained_procedure_evidence() -> None:
    concept = _procedure_concept()
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        institution_concepts=InstitutionConceptLedger(
            owner_id=_OWNER, concepts=(concept,)
        ),
    )
    assert len(ledger.channels) == 1
    assert ledger.channels[0].binding_kind is InstitutionalBindingKind.PROCEDURE
    assert ledger.entries[0].facts[0].subject == "procedure"
    assert ledger.entries[0].facts[0].predicate == "observed_pattern"

    weak = _procedure_concept(recurrence=0.0)
    empty = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        institution_concepts=InstitutionConceptLedger(
            owner_id=_OWNER, concepts=(weak,)
        ),
    )
    assert empty.channels == ()


def test_ambiguous_procedure_overlap_does_not_merge() -> None:
    first = _procedure_concept(anchors=("a" * 16,), group_key="ab" * 32)
    second = _procedure_concept(
        anchors=("b" * 16,), group_key="cd" * 32, evidence_tick=2
    )
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        institution_concepts=InstitutionConceptLedger(
            owner_id=_OWNER, concepts=(first, second)
        ),
    )
    assert len(ledger.channels) == 2
    ambiguous = _procedure_concept(
        anchors=("a" * 16, "b" * 16),
        group_key="ef" * 32,
        evidence_tick=3,
    )
    updated = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=3),
        identity=_identity(),
        previous=ledger,
        institution_concepts=InstitutionConceptLedger(
            owner_id=_OWNER, concepts=(ambiguous,)
        ),
    )
    assert len(updated.channels) == 2


def test_occurrence_requires_matching_local_evidence() -> None:
    concept = _office_concept()
    matched = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("event-1"),
        ),
        kind="exchange_offer",
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId("actor-x"),
        other_entity_id=EntityId("actor-y"),
    )
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=2, occurrences=(matched,)),
        identity=_identity(),
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,)),
    )
    occurrence_facts = tuple(
        fact
        for entry in ledger.entries
        for fact in entry.facts
        if fact.subject.startswith("e_")
    )
    assert len(occurrence_facts) == 1
    assert occurrence_facts[0].object == institutional_entity_token("actor-y")

    unmatched = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("unknown-event"),
        ),
        kind="exchange_offer",
        audience_role=matched.audience_role,
        actor_id=EntityId("unknown-actor"),
        other_entity_id=EntityId("actor-y"),
    )
    none = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=2, occurrences=(unmatched,)),
        identity=_identity(),
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,)),
    )
    assert not any(
        fact.subject.startswith("e_") for entry in none.entries for fact in entry.facts
    )


def test_reference_only_recall_introduces_no_content() -> None:
    context = RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(),
        belief_ids=(),
        confidence=0.5,
    )
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        retrieved_memory_context=context,
    )
    assert ledger.entries == ()
    assert ledger.channels == ()


def test_repeated_observation_is_idempotent() -> None:
    concept = _office_concept()
    stores = OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,))
    first = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        office_concepts=stores,
    )
    second = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        previous=first,
        office_concepts=stores,
    )
    assert len(second.entries) == len(first.entries)
    assert second.acquisition_receipt_keys == first.acquisition_receipt_keys


def test_no_content_when_no_local_evidence() -> None:
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
    )
    assert ledger.channels == ()
    assert ledger.entries == ()
    assert ledger.observation_count == 1


def test_owner_and_store_mismatch_are_rejected() -> None:
    other = AgentId("bob")
    with pytest.raises(ValueError, match="owner_mismatch"):
        apply_institutional_memory_update(
            owner_id=_OWNER,
            observation=_observation(),
            identity=_identity(other),
        )
    with pytest.raises(ValueError, match="owner_mismatch"):
        apply_institutional_memory_update(
            owner_id=_OWNER,
            observation=_observation(),
            identity=_identity(),
            office_concepts=OfficeConceptLedger(owner_id=other),
        )
    with pytest.raises((TypeError, ValueError)):
        apply_institutional_memory_update(
            owner_id=_OWNER,
            observation=object(),  # type: ignore[arg-type]
            identity=_identity(),
        )


def test_retained_ignored_state_and_coverage_are_preserved() -> None:
    concept = _office_concept()
    first = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,)),
    )
    from dataclasses import replace

    ignored_entry = replace(first.entries[0], ignored=True)
    previous = replace(
        first,
        entries=(ignored_entry,),
        pruned_entry_count=1,
    )
    updated = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=2),
        identity=_identity(),
        previous=previous,
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,)),
    )
    assert updated.entries[0].ignored is True
    assert updated.coverage == "partial"
    assert (
        updated.entries[0].provenance[0].immediate_channel
        is InstitutionalMemoryChannel.OBSERVATION
    )


def test_unbound_entry_rebinds_when_local_channel_appears() -> None:
    from dataclasses import replace

    from agents.cognition.institutional_memory import (
        InstitutionalFact,
        InstitutionalMemoryEntry,
        InstitutionalProvenance,
        institutional_entry_id,
    )

    concept = _office_concept()
    role_token = institutional_role_token(concept.function.value, concept.context_key)
    entry = InstitutionalMemoryEntry(
        owner_id=_OWNER,
        entry_id=institutional_entry_id(_OWNER, None, 0),
        channel_id=None,
        ordinal=0,
        revision=0,
        facts=(InstitutionalFact(role_token, "duty", "perform"),),
        declared_fact_count=1,
        acquisition_tick=1,
        confidence=0.5,
        distorted=False,
        partial=False,
        active=True,
        ignored=False,
        provenance=(InstitutionalProvenance(InstitutionalMemoryChannel.TRANSMISSION),),
        binding_kind=InstitutionalBindingKind.ROLE,
        binding_function_token=role_token,
        binding_context_digest=concept.context_key,
    )
    previous = replace(empty_institutional_memory_ledger(_OWNER), entries=(entry,))
    updated = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(),
        identity=_identity(),
        previous=previous,
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,)),
    )
    assert updated.entries[0].channel_id is not None
    assert updated.entries[0].entry_id == institutional_entry_id(
        _OWNER, updated.entries[0].channel_id, 0
    )
    assert updated.entries[0].facts[0].subject == role_token
