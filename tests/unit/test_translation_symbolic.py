"""Translation-assisted symbolic interpretation and application rows."""

from __future__ import annotations

from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.semantic_naming import (
    LabelBinding,
    NamingCandidate,
    NamingReferentKind,
    NamingStatus,
    TerminologyLedger,
    label_binding_id,
)
from agents.cognition.symbolic_language import apply_symbolic_update
from agents.cognition.translation import (
    TranslationFit,
    TranslationLedger,
    TranslationMapping,
    TranslationMappingStatus,
    TranslationSourceKind,
    TranslationTarget,
    translation_mapping_id,
    translation_source_digest,
)
from agents.models import AgentId
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)


def _binding(owner: AgentId, token: str) -> LabelBinding:
    return LabelBinding(
        binding_id=label_binding_id(owner, NamingReferentKind.LOCATION, token),
        owner_id=owner,
        label_token=token,
        referent_kind=NamingReferentKind.LOCATION,
        status=NamingStatus.ACTIVE,
        strength=0.6,
        candidates=(
            NamingCandidate(
                kind=NamingReferentKind.LOCATION,
                entity_id=f"loc-{token}",
                confidence=0.7,
            ),
        ),
        evidence_count=3,
    )


def _mapping(owner: AgentId, source: str, target: LabelBinding) -> TranslationMapping:
    digest = translation_source_digest(source)
    return TranslationMapping(
        mapping_id=translation_mapping_id(owner, digest),
        owner_id=owner,
        source_token=source,
        source_digest=digest,
        source_kind=TranslationSourceKind.LABEL,
        targets=(
            TranslationTarget(
                binding_id=target.binding_id,
                label_token=target.label_token,
                referent_kind=target.referent_kind,
                weight=0.6,
            ),
        ),
        status=TranslationMappingStatus.ACTIVE,
        fit=TranslationFit.RESOLVED,
        strength=0.6,
        evidence_count=3,
        first_tick=1,
        last_tick=2,
    )


def test_foreign_parts_resolve_to_own_composition() -> None:
    owner = AgentId("bob")
    own_a = _binding(owner, "own_a")
    own_b = _binding(owner, "own_b")
    terminology = TerminologyLedger(owner_id=owner, bindings=(own_a, own_b))
    translation = TranslationLedger(
        owner_id=owner,
        mappings=(
            _mapping(owner, "foreign_a", own_a),
            _mapping(owner, "foreign_b", own_b),
        ),
    )
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-bob"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("alice"), entity_id=EntityId("body-alice")
            ),
        ),
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=1,
            source_event_id=EventId("evt-1"),
        ),
        speaker_id=EntityId("body-alice"),
        listener_id=EntityId("body-bob"),
        utterance=origin_utterance(
            text="compose",
            speaker_id=EntityId("body-alice"),
            communication_id="comm-1",
            relations=(
                CommunicationRelation(
                    subject="foreign_a",
                    predicate="attributive",
                    object="foreign_b",
                ),
            ),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
        action_kind="talk",
    )
    observation = Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-bob"),
        revision=WorldRevision(1),
        tick=2,
        communications=(communication,),
    )
    applications: list[dict[str, object]] = []
    ledger = apply_symbolic_update(
        observation,
        identity,
        None,
        terminology,
        translation=translation,
        translation_applications=applications,
    )
    assert ledger.compositions
    assert ledger.compositions[0].parts == ("own_a", "own_b")
    assert len(applications) == 2
    assert {row["outcome"] for row in applications} == {"applied"}


def test_without_translation_foreign_parts_stay_unresolved() -> None:
    owner = AgentId("bob")
    designation = _binding(owner, "own_a")
    terminology = TerminologyLedger(owner_id=owner, bindings=(designation,))
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-bob"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("alice"), entity_id=EntityId("body-alice")
            ),
        ),
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=1,
            source_event_id=EventId("evt-1"),
        ),
        speaker_id=EntityId("body-alice"),
        listener_id=EntityId("body-bob"),
        utterance=origin_utterance(
            text="compose",
            speaker_id=EntityId("body-alice"),
            communication_id="comm-1",
            relations=(
                CommunicationRelation(
                    subject="foreign_a",
                    predicate="attributive",
                    object="foreign_b",
                ),
            ),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
        action_kind="talk",
    )
    observation = Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-bob"),
        revision=WorldRevision(1),
        tick=2,
        communications=(communication,),
    )
    ledger = apply_symbolic_update(observation, identity, None, terminology)
    assert ledger.compositions == ()
