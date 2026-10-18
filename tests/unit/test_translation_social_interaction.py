"""Translated testimony overlay and outbound foreign-term selection."""

from __future__ import annotations

from agents.cognition.communication import build_communicated_memory_trace
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.semantic_naming import NamingReferentKind, label_binding_id
from agents.cognition.translation import (
    TranslationFit,
    TranslationLedger,
    TranslationMapping,
    TranslationMappingStatus,
    TranslationSourceKind,
    TranslationTarget,
    translation_communicate_utterance,
    translation_mapping_id,
    translation_source_digest,
    translation_usage_update,
)
from agents.models import AgentId
from world.actions import Talk
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


def _ledger(*, evidence_actor: AgentId | None = None) -> TranslationLedger:
    owner = AgentId("bob")
    binding_id = label_binding_id(owner, NamingReferentKind.LOCATION, "own_a")
    digest = translation_source_digest("foreign_a")
    mapping = TranslationMapping(
        mapping_id=translation_mapping_id(owner, digest),
        owner_id=owner,
        source_token="foreign_a",
        source_digest=digest,
        source_kind=TranslationSourceKind.LABEL,
        targets=(
            TranslationTarget(
                binding_id=binding_id,
                label_token="own_a",
                referent_kind=NamingReferentKind.LOCATION,
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
    if evidence_actor is not None:
        from agents.cognition.translation import TranslationEvidenceItem

        mapping = TranslationMapping(
            mapping_id=mapping.mapping_id,
            owner_id=owner,
            source_token=mapping.source_token,
            source_digest=mapping.source_digest,
            source_kind=mapping.source_kind,
            targets=mapping.targets,
            status=mapping.status,
            fit=mapping.fit,
            strength=mapping.strength,
            evidence_count=mapping.evidence_count,
            first_tick=mapping.first_tick,
            last_tick=mapping.last_tick,
            evidence=(
                TranslationEvidenceItem(
                    evidence_id="b" * 64,
                    ordinal=0,
                    channel=__import__(
                        "agents.cognition.translation",
                        fromlist=["TranslationEvidenceChannel"],
                    ).TranslationEvidenceChannel.SHARED_OBSERVATION,
                    lineage_ref="lineage",
                    tick=1,
                    actor_id=evidence_actor,
                    target_binding_ids=(binding_id,),
                ),
            ),
        )
    return TranslationLedger(owner_id=owner, mappings=(mapping,))


def _observation(relations: tuple[CommunicationRelation, ...]) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-bob"),
        revision=WorldRevision(1),
        tick=3,
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=2,
                    source_event_id=EventId("evt-1"),
                ),
                speaker_id=EntityId("body-alice"),
                listener_id=EntityId("body-bob"),
                utterance=origin_utterance(
                    text="call",
                    speaker_id=EntityId("body-alice"),
                    communication_id="comm-1",
                    relations=relations,
                    source_basis=CommunicationSourceBasis.UNREFERENCED,
                ),
                action_kind="talk",
            ),
        ),
    )


def test_overlay_appends_translated_relation_and_preserves_original() -> None:
    observation = _observation(
        (
            CommunicationRelation(
                subject="foreign_a", predicate="call", object="location"
            ),
        )
    )
    message = observation.communications[0]
    trace = build_communicated_memory_trace(
        owner_id=AgentId("bob"),
        observation_tick=3,
        observation_revision=WorldRevision(1),
        message=message,
        location_id=None,
        translation=_ledger(),
    )
    concepts = {item.concept for item in trace.concepts}
    assert "foreign_a" in concepts
    assert "own_a" in concepts
    assert len(trace.relations) == 2


def test_outbound_rewrites_only_for_matching_recipient() -> None:
    owner = AgentId("bob")
    recipient_agent = AgentId("alice")
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-bob"),
        counterparts=(
            CounterpartBinding(
                agent_id=recipient_agent,
                entity_id=EntityId("body-alice"),
            ),
        ),
    )
    command = Talk(
        recipient_id=EntityId("body-alice"),
        utterance=origin_utterance(
            text="call",
            speaker_id=EntityId("body-bob"),
            communication_id="talk-1",
            relations=(
                CommunicationRelation(
                    subject="own_a", predicate="call", object="location"
                ),
            ),
        ),
    )
    rewritten = translation_communicate_utterance(
        command,
        owner_id=owner,
        tick=3,
        observation=_observation(()),
        identity=identity,
        translation=_ledger(evidence_actor=recipient_agent),
        terminology=__import__(
            "agents.cognition.semantic_naming", fromlist=["TerminologyLedger"]
        ).TerminologyLedger(owner_id=owner),
        mode=__import__(
            "agents.cognition.configuration", fromlist=["CognitionTranslationMode"]
        ).CognitionTranslationMode.DETERMINISTIC,
    )
    assert isinstance(rewritten, Talk)
    assert rewritten.utterance.content.relations[0].subject == "foreign_a"


def test_outbound_keeps_own_term_without_recipient_evidence() -> None:
    owner = AgentId("bob")
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-bob"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("alice"), entity_id=EntityId("body-alice")
            ),
        ),
    )
    command = Talk(
        recipient_id=EntityId("body-alice"),
        utterance=origin_utterance(
            text="call",
            speaker_id=EntityId("body-bob"),
            communication_id="talk-1",
            relations=(
                CommunicationRelation(
                    subject="own_a", predicate="call", object="location"
                ),
            ),
        ),
    )
    unchanged = translation_communicate_utterance(
        command,
        owner_id=owner,
        tick=3,
        observation=_observation(()),
        identity=identity,
        translation=_ledger(),
        terminology=__import__(
            "agents.cognition.semantic_naming", fromlist=["TerminologyLedger"]
        ).TerminologyLedger(owner_id=owner),
        mode=__import__(
            "agents.cognition.configuration", fromlist=["CognitionTranslationMode"]
        ).CognitionTranslationMode.DETERMINISTIC,
    )
    assert unchanged is command


def test_usage_update_records_talk_command_kind() -> None:
    owner = AgentId("bob")
    command = Talk(
        recipient_id=EntityId("body-alice"),
        utterance=origin_utterance(
            text="call",
            speaker_id=EntityId("body-bob"),
            communication_id="talk-2",
            relations=(
                CommunicationRelation(
                    subject="foreign_a", predicate="call", object="location"
                ),
            ),
        ),
    )
    from agents.cognition.semantic_naming import (
        LabelBinding,
        NamingCandidate,
        NamingStatus,
        TerminologyLedger,
    )

    terminology = TerminologyLedger(
        owner_id=owner,
        bindings=(
            LabelBinding(
                binding_id=label_binding_id(
                    owner, NamingReferentKind.LOCATION, "own_a"
                ),
                owner_id=owner,
                label_token="own_a",
                referent_kind=NamingReferentKind.LOCATION,
                status=NamingStatus.ACTIVE,
                strength=0.6,
                candidates=(
                    NamingCandidate(
                        kind=NamingReferentKind.LOCATION,
                        entity_id="loc-1",
                        confidence=0.7,
                    ),
                ),
                evidence_count=3,
            ),
        ),
    )
    updated = translation_usage_update(
        _ledger(evidence_actor=AgentId("alice")),
        command,
        tick=3,
        terminology=terminology,
        mode=__import__(
            "agents.cognition.configuration", fromlist=["CognitionTranslationMode"]
        ).CognitionTranslationMode.DETERMINISTIC,
    )
    application = updated.mappings[0].applications[0]
    assert application.command_kind == "talk"
