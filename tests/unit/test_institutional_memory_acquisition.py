"""Physical, record-reading and delivered-speech acquisition paths."""

from __future__ import annotations

from agents.cognition.artifacts import (
    ArtifactInterpretation,
    ArtifactInterpretationLedger,
)
from agents.cognition.institutional_memory import (
    InstitutionalBindingKind,
    InstitutionalFact,
    InstitutionalMemoryChannel,
    InstitutionalMemoryLedger,
    apply_institutional_memory_update,
    empty_institutional_memory_ledger,
    institutional_role_token,
)
from agents.cognition.institutional_memory_frames import (
    InstitutionalMemoryFrame,
    encode_institutional_marks,
    institutional_frame_relation,
    institutional_frame_root,
)
from agents.cognition.models import (
    CounterpartBinding,
    OwnerSafeSocialIdentity,
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
    office_concept_id,
    office_inception_digest,
    office_role_signature,
)
from agents.models import AgentId
from world.artifacts import ArtifactContent, ArtifactKind, RecordIntegrity
from world.communications import (
    CommunicationRelation,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedArtifact,
    ObservedCommunication,
    ObservedItemPlacement,
)

_CONTEXT = "a" * 16
_INCEPTION = "c" * 64
_OWNER = AgentId("alice")
_BOB = AgentId("bob")
_ALICE_BODY = EntityId("alice-body")
_BOB_BODY = EntityId("bob-body")


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=_ALICE_BODY,
        counterparts=(CounterpartBinding(agent_id=_BOB, entity_id=_BOB_BODY),),
    )


def _observation(
    *,
    tick: int = 2,
    artifacts: tuple[ObservedArtifact, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world"),
        observer_id=_ALICE_BODY,
        revision=WorldRevision(tick),
        tick=tick,
        artifacts=artifacts,
        communications=communications,
    )


def _office_concept() -> OfficeConcept:
    inception = office_inception_digest(OfficeFunction.EXCHANGE, _CONTEXT, _INCEPTION)
    evidence = OfficeEvidence(
        evidence_id="1" * 64,
        ordinal=0,
        channel=OfficeEvidenceChannel.OBSERVED,
        lineage_ref="event-1",
        root_ref="root-1",
        tick=1,
        context_key=_CONTEXT,
        function=OfficeFunction.EXCHANGE,
        actor_id=AgentId("actor-x"),
    )
    return OfficeConcept(
        office_id=office_concept_id(_OWNER, inception, 0),
        owner_id=_OWNER,
        function=OfficeFunction.EXCHANGE,
        context_key=_CONTEXT,
        inception_digest=inception,
        collision_discriminator=0,
        role_signature=office_role_signature(
            OfficeFunction.EXCHANGE, _CONTEXT, (OfficeDutyKind.PERFORM,)
        ),
        status=OfficeConceptStatus.RECOGNIZED,
        function_strength=0.7,
        expectation_strength=0.6,
        endorsement_strength=0.5,
        first_tick=1,
        last_tick=1,
        evidence_count=1,
        independent_root_count=1,
        duties=(
            OfficeDutyBelief(
                duty_id="d" * 64,
                kind=OfficeDutyKind.PERFORM,
                function=OfficeFunction.EXCHANGE,
                context_key=_CONTEXT,
                strength=0.6,
                first_tick=1,
                last_tick=1,
                evidence_ids=(evidence.evidence_id,),
            ),
        ),
        evidence=(evidence,),
    )


def _role_setup() -> tuple[InstitutionalMemoryLedger, str]:
    concept = _office_concept()
    ledger = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=1),
        identity=_identity(),
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,)),
    )
    return ledger, institutional_role_token(OfficeFunction.EXCHANGE.value, _CONTEXT)


def _frame(
    *,
    function_token: str,
    facts: tuple[tuple[str, str, str], ...] = (("trade", "owes", "grain"),),
    declared: int | None = None,
    parent: str = "p_none",
) -> InstitutionalMemoryFrame:
    return InstitutionalMemoryFrame(
        binding_kind=InstitutionalBindingKind.ROLE,
        function_token=function_token,
        context_digest="c_" + _CONTEXT,
        root=institutional_frame_root("record-root"),
        parent=parent,
        facts=tuple(InstitutionalFact(*fact) for fact in facts),
        declared_fact_count=declared,
    )


def _interpretation(
    artifact: ObservedArtifact,
    *,
    marks: tuple[str, ...],
    revision: int = 0,
    confidence: float = 0.8,
    distorted: bool = False,
) -> ArtifactInterpretationLedger:
    return ArtifactInterpretationLedger(
        owner_id=_OWNER,
        interpretations=(
            ArtifactInterpretation(
                artifact_id=artifact.entity_id,
                observed_revision=revision,
                reading_marks=marks,
                reading_relations=(),
                confidence=confidence,
                distorted=distorted,
                source_tick=1,
                source_event_id=EventId("reading-event"),
            ),
        ),
    )


def _artifact(integrity: RecordIntegrity = RecordIntegrity.INTACT) -> ObservedArtifact:
    return ObservedArtifact(
        entity_id=EntityId("record-1"),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("author-1"),
        created_tick=1,
        content=ArtifactContent(),
        content_revision=0,
        placement=ObservedItemPlacement.GROUND_HERE,
        integrity=integrity,
    )


def _acquire(
    *,
    ledger: InstitutionalMemoryLedger,
    observation: Observation,
    interpretations: ArtifactInterpretationLedger | None = None,
    teaching_enabled: bool = False,
) -> InstitutionalMemoryLedger:
    return apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=observation,
        identity=_identity(),
        previous=ledger,
        artifact_interpretations=interpretations,
        teaching_enabled=teaching_enabled,
    )


def test_current_visible_reading_acquires_record_entry() -> None:
    ledger, function_token = _role_setup()
    artifact = _artifact()
    frame = _frame(function_token=function_token)
    interpretations = _interpretation(artifact, marks=encode_institutional_marks(frame))
    updated = _acquire(
        ledger=ledger,
        observation=_observation(artifacts=(artifact,)),
        interpretations=interpretations,
    )
    record_entries = [
        entry
        for entry in updated.entries
        if entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.RECORD
    ]
    assert len(record_entries) == 1
    entry = record_entries[0]
    assert entry.facts == frame.facts
    assert entry.channel_id == ledger.channels[0].channel_id
    assert entry.provenance[0].artifact_id == artifact.entity_id
    assert entry.provenance[0].artifact_revision == 0
    assert entry.provenance[0].declared_frame_root == frame.root
    assert entry.provenance[0].declared_transmission is None


def test_no_reading_ledger_means_no_record_acquisition() -> None:
    ledger, function_token = _role_setup()
    artifact = _artifact()
    _frame(function_token=function_token)
    updated = _acquire(
        ledger=ledger,
        observation=_observation(artifacts=(artifact,)),
        interpretations=None,
    )
    assert not any(
        entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.RECORD
        for entry in updated.entries
    )


def test_stale_reading_is_not_new_access() -> None:
    ledger, function_token = _role_setup()
    artifact = _artifact()
    frame = _frame(function_token=function_token)
    interpretations = _interpretation(
        artifact, marks=encode_institutional_marks(frame), revision=1
    )
    updated = _acquire(
        ledger=ledger,
        observation=_observation(artifacts=(artifact,)),
        interpretations=interpretations,
    )
    assert not any(
        entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.RECORD
        for entry in updated.entries
    )


def test_partial_and_wrong_frames_are_retained_as_claims() -> None:
    ledger, function_token = _role_setup()
    artifact = _artifact()
    frame = _frame(
        function_token=function_token,
        facts=(
            ("trade", "owes", "grain"),
            ("trade", "owes", "salt"),
            ("trade", "owes", "cloth"),
        ),
        declared=3,
    )
    marks = encode_institutional_marks(frame)
    partial = _acquire(
        ledger=ledger,
        observation=_observation(artifacts=(artifact,)),
        interpretations=_interpretation(artifact, marks=marks[:10]),
    )
    entry = next(
        entry
        for entry in partial.entries
        if entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.RECORD
    )
    assert len(entry.facts) == 1
    assert entry.partial is True
    assert entry.declared_fact_count == 3

    swapped = _frame(
        function_token=function_token,
        facts=(("grain", "owes", "trade"),),
    )
    wrong = _acquire(
        ledger=ledger,
        observation=_observation(artifacts=(artifact,)),
        interpretations=_interpretation(
            artifact, marks=encode_institutional_marks(swapped)
        ),
    )
    wrong_entry = next(
        entry
        for entry in wrong.entries
        if entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.RECORD
    )
    assert wrong_entry.facts[0].subject == "grain"


def test_damaged_record_reduces_confidence_and_marks_distorted() -> None:
    ledger, function_token = _role_setup()
    artifact = _artifact(RecordIntegrity.DAMAGED)
    frame = _frame(function_token=function_token)
    updated = _acquire(
        ledger=ledger,
        observation=_observation(artifacts=(artifact,)),
        interpretations=_interpretation(
            artifact, marks=encode_institutional_marks(frame), confidence=0.8
        ),
    )
    entry = next(
        entry
        for entry in updated.entries
        if entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.RECORD
    )
    assert entry.distorted is True
    assert entry.confidence == 0.4


def _communication(
    *,
    relation: CommunicationRelation,
    listener: EntityId = _ALICE_BODY,
    event: str = "delivery-1",
    tick: int = 1,
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="an institutional statement",
        speaker_id=_BOB_BODY,
        communication_id="comm-1",
        relations=(relation,),
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick,
            source_event_id=EventId(event),
        ),
        speaker_id=_BOB_BODY,
        listener_id=listener,
        utterance=utterance,
        action_kind="tell",
    )


def test_addressed_transmission_is_acquired_with_separate_envelope() -> None:
    ledger, function_token = _role_setup()
    frame = _frame(function_token=function_token)
    relation = institutional_frame_relation(frame)
    assert relation is not None
    updated = _acquire(
        ledger=ledger,
        observation=_observation(communications=(_communication(relation=relation),)),
    )
    entry = next(
        entry
        for entry in updated.entries
        if entry.provenance[0].immediate_channel
        is InstitutionalMemoryChannel.TRANSMISSION
    )
    provenance = entry.provenance[0]
    assert provenance.resolved_source_agent_id == _BOB
    assert provenance.observed_entity_id == _BOB_BODY
    assert provenance.declared_transmission is not None
    assert (
        provenance.declared_transmission.root_communication_id.value
        != provenance.declared_frame_root
    )
    assert entry.confidence == 0.375


def test_unaddressed_or_unknown_speaker_is_ignored() -> None:
    ledger, function_token = _role_setup()
    relation = institutional_frame_relation(_frame(function_token=function_token))
    assert relation is not None
    unaddressed = _acquire(
        ledger=ledger,
        observation=_observation(
            communications=(_communication(relation=relation, listener=EntityId("x")),)
        ),
    )
    assert not any(
        entry.provenance[0].immediate_channel
        in {
            InstitutionalMemoryChannel.TRANSMISSION,
            InstitutionalMemoryChannel.TEACHING,
        }
        for entry in unaddressed.entries
    )


def test_teaching_requires_receiver_mode() -> None:
    ledger, function_token = _role_setup()
    relation = institutional_frame_relation(
        _frame(function_token=function_token), teaching=True
    )
    assert relation is not None
    communication = _communication(relation=relation)
    disabled = _acquire(
        ledger=ledger,
        observation=_observation(communications=(communication,)),
        teaching_enabled=False,
    )
    assert not any(
        entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.TEACHING
        for entry in disabled.entries
    )
    enabled = _acquire(
        ledger=ledger,
        observation=_observation(communications=(communication,)),
        teaching_enabled=True,
    )
    teaching = [
        entry
        for entry in enabled.entries
        if entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.TEACHING
    ]
    assert len(teaching) == 1
    assert teaching[0].facts[0].subject == "trade"


def test_conflicting_institutional_relations_are_ambiguous() -> None:
    ledger, function_token = _role_setup()
    first = institutional_frame_relation(_frame(function_token=function_token))
    second = institutional_frame_relation(
        _frame(
            function_token=function_token,
            facts=(("trade", "owes", "salt"),),
        )
    )
    assert first is not None and second is not None
    utterance = origin_utterance(
        text="two claims",
        speaker_id=_BOB_BODY,
        communication_id="comm-1",
        relations=(first, second),
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=1,
            source_event_id=EventId("delivery-1"),
        ),
        speaker_id=_BOB_BODY,
        listener_id=_ALICE_BODY,
        utterance=utterance,
        action_kind="tell",
    )
    updated = _acquire(
        ledger=ledger,
        observation=_observation(communications=(communication,)),
    )
    assert not any(
        entry.provenance[0].immediate_channel
        in {
            InstitutionalMemoryChannel.TRANSMISSION,
            InstitutionalMemoryChannel.TEACHING,
        }
        for entry in updated.entries
    )


def test_duplicate_delivery_is_idempotent() -> None:
    ledger, function_token = _role_setup()
    relation = institutional_frame_relation(_frame(function_token=function_token))
    assert relation is not None
    communication = _communication(relation=relation)
    first = _acquire(
        ledger=ledger,
        observation=_observation(communications=(communication,)),
    )
    second = _acquire(
        ledger=first,
        observation=_observation(communications=(communication,)),
    )
    assert len(second.entries) == len(first.entries)
    assert second.acquisition_receipt_keys == first.acquisition_receipt_keys


def test_unbound_record_entry_rebinds_when_role_appears() -> None:
    frame = _frame(function_token="exchange_aaaaaaaa")
    artifact = _artifact()
    empty = empty_institutional_memory_ledger(_OWNER)
    first = _acquire(
        ledger=empty,
        observation=_observation(artifacts=(artifact,)),
        interpretations=_interpretation(
            artifact, marks=encode_institutional_marks(frame)
        ),
    )
    record_entry = next(
        entry
        for entry in first.entries
        if entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.RECORD
    )
    assert record_entry.channel_id is None
    concept = _office_concept()
    rebound = apply_institutional_memory_update(
        owner_id=_OWNER,
        observation=_observation(tick=3),
        identity=_identity(),
        previous=first,
        office_concepts=OfficeConceptLedger(owner_id=_OWNER, concepts=(concept,)),
    )
    rebound_record = next(
        entry
        for entry in rebound.entries
        if entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.RECORD
    )
    assert rebound_record.channel_id is not None
