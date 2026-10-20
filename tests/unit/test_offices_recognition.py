"""Office recognition, duties, authority, and attributed support updates."""

from __future__ import annotations

from agents.cognition.models import (
    CounterpartBinding,
    OwnerSafeSocialIdentity,
    RetrievedMemoryContext,
)
from agents.cognition.offices import (
    OfficeAuthorityKind,
    OfficeConceptStatus,
    OfficeDutyKind,
    apply_office_concept_update,
    office_inception_digest,
)
from agents.models import AgentId
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryRelation,
    MemorySituationContext,
    MentionId,
    ReconstructedMemory,
    ReconstructionId,
    RelationEndpoint,
    RelationEndpointKind,
)
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

_OWNER = AgentId("ada")
_CONTEXT_HEAD = None


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=AgentId("ben"), entity_id=EntityId("body-ben")),
            CounterpartBinding(
                agent_id=AgentId("carol"), entity_id=EntityId("body-carol")
            ),
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
    occurrences: tuple[ObservedOccurrence, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        occurrences=occurrences,
        communications=communications,
    )


def _context_key(observation: Observation) -> str:
    from agents.cognition.offices import _context_key as context_key

    return context_key(observation)


def _message(
    *,
    tick: int,
    speaker: str,
    root: str,
    predicate: str,
    function: str,
    context: str,
    occupant: str = "-",
    alleged: str = "-",
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="office",
        speaker_id=EntityId(speaker),
        communication_id=root,
        relations=(
            CommunicationRelation(
                subject=function,
                predicate=predicate,
                object=f"{context}|{occupant}|{alleged}",
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


def _reconstructed(
    *,
    episode_id: str,
    predicate: str,
    function: str,
    context: str,
) -> ReconstructedMemory:
    return ReconstructedMemory(
        reconstruction_id=ReconstructionId(episode_id),
        owner_id=_OWNER,
        narrative="remembered role",
        concepts=(
            ConceptMention(mention_id=MentionId("c-subject"), concept=function),
            ConceptMention(mention_id=MentionId("c-object"), concept=context),
        ),
        entities=(),
        relations=(
            MemoryRelation(
                relation_id=MentionId("r-1"),
                predicate=predicate,
                subject=RelationEndpoint(
                    kind=RelationEndpointKind.CONCEPT,
                    mention_id=MentionId("c-subject"),
                ),
                object=RelationEndpoint(
                    kind=RelationEndpointKind.CONCEPT,
                    mention_id=MentionId("c-object"),
                ),
            ),
        ),
        context=MemorySituationContext(),
        confidence=0.8,
        emotional_salience=0.3,
        source_memory_ids=(MemoryId(f"m-{episode_id}"),),
        generation=1,
        reconstructed_at_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )


def _recall(*episodes: ReconstructedMemory) -> RetrievedMemoryContext:
    return RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=tuple(
            MemoryId(f"m-{item.reconstruction_id.value}") for item in episodes
        ),
        belief_ids=(),
        confidence=0.8,
        reconstructions=episodes,
    )


def test_repeated_influence_alone_stays_personal() -> None:
    ledger = None
    for tick in range(1, 6):
        observation = _observation(
            tick=tick, occurrences=(_occurrence("help", "body-ben", tick),)
        )
        ledger = apply_office_concept_update(observation, _identity(), ledger)
    assert ledger is not None
    assert len(ledger.concepts) == 1
    concept = ledger.concepts[0]
    assert concept.status is OfficeConceptStatus.PROPOSED
    assert concept.function_strength > 0.0
    assert concept.independent_root_count == 0
    assert "influence_only" in concept.notices


def test_independent_role_directed_evidence_promotes() -> None:
    ledger = None
    base = _observation(tick=2)
    context = _context_key(base)
    for tick in range(2, 6):
        messages = (
            _message(
                tick=tick,
                speaker="body-ben",
                root=f"comm-ben-{tick}",
                predicate="office_role",
                function="help",
                context=context,
            ),
            _message(
                tick=tick,
                speaker="body-carol",
                root=f"comm-carol-{tick}",
                predicate="office_role",
                function="help",
                context=context,
            ),
        )
        ledger = apply_office_concept_update(
            _observation(
                tick=tick,
                occurrences=(_occurrence("help", "body-ben", tick),),
                communications=messages,
            ),
            _identity(),
            ledger,
        )
    assert ledger is not None
    concept = ledger.concepts[0]
    assert concept.independent_root_count >= 2
    assert concept.status is OfficeConceptStatus.RECOGNIZED


def test_same_root_retellings_do_not_inflate_independence() -> None:
    base = _observation(tick=1, occurrences=(_occurrence("help", "body-ben", 1),))
    context = _context_key(base)
    ledger = None
    for tick in range(1, 5):
        ledger = apply_office_concept_update(
            _observation(
                tick=tick,
                occurrences=(_occurrence("help", "body-ben", tick),),
                communications=(
                    _message(
                        tick=tick,
                        speaker="body-ben",
                        root="comm-shared-root",
                        predicate="office_role",
                        function="help",
                        context=context,
                    ),
                ),
            ),
            _identity(),
            ledger,
        )
    assert ledger is not None
    concept = ledger.concepts[0]
    assert concept.independent_root_count == 1
    assert concept.status is not OfficeConceptStatus.RECOGNIZED


def test_duties_and_authority_are_tracked_separately() -> None:
    base = _observation(tick=1, occurrences=(_occurrence("help", "body-ben", 1),))
    context = _context_key(base)
    ledger = apply_office_concept_update(
        _observation(
            tick=2,
            occurrences=(_occurrence("help", "body-ben", 2),),
            communications=(
                _message(
                    tick=2,
                    speaker="body-ben",
                    root="comm-duty",
                    predicate="office_duty",
                    function="help",
                    context=f"{context}|coordinate",
                ),
                _message(
                    tick=2,
                    speaker="body-carol",
                    root="comm-authority",
                    predicate="office_authority",
                    function="help",
                    context=f"{context}|deference",
                ),
            ),
        ),
        _identity(),
    )
    concept = ledger.concepts[0]
    duty_kinds = {duty.kind for duty in concept.duties}
    authority_kinds = {authority.kind for authority in concept.authorities}
    assert OfficeDutyKind.PERFORM in duty_kinds
    assert OfficeDutyKind.COORDINATE in duty_kinds
    assert OfficeAuthorityKind.DEFERENCE in authority_kinds
    assert concept.status is not OfficeConceptStatus.RECOGNIZED


def test_unknown_alleged_supporter_stays_unresolved() -> None:
    base = _observation(tick=1, occurrences=(_occurrence("help", "body-ben", 1),))
    context = _context_key(base)
    ledger = apply_office_concept_update(
        _observation(
            tick=2,
            occurrences=(_occurrence("help", "body-ben", 2),),
            communications=(
                _message(
                    tick=2,
                    speaker="body-ben",
                    root="comm-endorse",
                    predicate="office_endorse",
                    function="help",
                    context=context,
                    occupant="body-carol",
                    alleged="body-ghost",
                ),
            ),
        ),
        _identity(),
    )
    concept = ledger.concepts[0]
    assert concept.supporters
    support = concept.supporters[0]
    assert support.resolved is False
    assert support.supporter_id is None
    assert support.independently_evidenced is False


def test_self_endorsement_is_rejected() -> None:
    base = _observation(tick=1, occurrences=(_occurrence("help", "body-ben", 1),))
    context = _context_key(base)
    ledger = apply_office_concept_update(
        _observation(
            tick=2,
            occurrences=(_occurrence("help", "body-ben", 2),),
            communications=(
                _message(
                    tick=2,
                    speaker="body-ben",
                    root="comm-self",
                    predicate="office_endorse",
                    function="help",
                    context=context,
                    occupant="body-ben",
                ),
            ),
        ),
        _identity(),
    )
    concept = ledger.concepts[0]
    assert concept.supporters == ()
    assert "self_endorsement" in concept.notices


def test_remembered_contradictions_are_preserved() -> None:
    base = _observation(tick=1, occurrences=(_occurrence("help", "body-ben", 1),))
    context = _context_key(base)
    recall = _recall(
        _reconstructed(
            episode_id="episode-1",
            predicate="office_role",
            function="help",
            context=context,
        ),
        _reconstructed(
            episode_id="episode-2",
            predicate="office_role",
            function="help",
            context=context,
        ),
    )
    ledger = None
    for tick in range(1, 5):
        ledger = apply_office_concept_update(
            _observation(
                tick=tick, occurrences=(_occurrence("help", "body-ben", tick),)
            ),
            _identity(),
            ledger,
            recall,
        )
    assert ledger is not None
    concept = ledger.concepts[0]
    remembered = [
        item for item in concept.evidence if item.channel.value == "remembered"
    ]
    assert len(remembered) >= 2
    assert concept.independent_root_count >= 2


def test_empty_recall_does_not_trigger_unbudgeted_scan() -> None:
    empty = RetrievedMemoryContext(
        owner_id=_OWNER, memory_ids=(), belief_ids=(), confidence=0.0
    )
    ledger = apply_office_concept_update(
        _observation(tick=1, occurrences=(_occurrence("help", "body-ben", 1),)),
        _identity(),
        None,
        empty,
    )
    assert ledger.concepts
    assert all(
        item.channel.value != "remembered"
        for concept in ledger.concepts
        for item in concept.evidence
    )


def test_office_id_ignores_changed_label_and_supporters() -> None:
    ledger = None
    for tick in range(1, 5):
        ledger = apply_office_concept_update(
            _observation(
                tick=tick, occurrences=(_occurrence("help", "body-ben", tick),)
            ),
            _identity(),
            ledger,
        )
    assert ledger is not None
    first = ledger.concepts[0]
    inception = office_inception_digest(
        first.function, first.context_key, first.evidence[0].lineage_ref
    )
    assert first.inception_digest == inception


def test_local_norm_ledger_supplies_role_expectation_evidence() -> None:
    from types import SimpleNamespace

    base = _observation(tick=2)
    context = _context_key(base)
    ledger = apply_office_concept_update(
        _observation(tick=3, occurrences=(_occurrence("help", "body-ben", 3),)),
        _identity(),
        norms=SimpleNamespace(
            owner_id=_OWNER,
            concepts=(
                SimpleNamespace(
                    function="help",
                    context_key=context,
                    status="recognized",
                    concept_id="norm-concept-1",
                ),
            ),
        ),
    )
    concept = ledger.concepts[0]
    assert any(item.channel.value == "observed" for item in concept.evidence)
    assert concept.expectation_strength > 0.0


def test_foreign_local_ledger_rejects() -> None:
    from types import SimpleNamespace

    import pytest

    with pytest.raises(ValueError, match="owner_id mismatch"):
        apply_office_concept_update(
            _observation(tick=2),
            _identity(),
            norms=SimpleNamespace(owner_id=AgentId("other"), concepts=()),
        )
