"""Owner-scoped translation learning: channels, promotion, ambiguity, decay."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.semantic_naming import (
    LabelBinding,
    NamingCandidate,
    NamingReferentKind,
    NamingStatus,
    TerminologyLedger,
    label_binding_id,
)
from agents.cognition.translation import (
    TranslationFit,
    TranslationMappingStatus,
    TranslationSourceKind,
    apply_translation_update,
    empty_translation_ledger,
    resolve_translation_token,
)
from agents.models import AgentId
from world.artifacts import ArtifactContent, ArtifactKind, ArtifactRelation
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedArtifact,
    ObservedCommunication,
    ObservedItemPlacement,
    ObservedLocation,
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


def _agent(value: str) -> AgentId:
    return AgentId(value)


def _identity(owner: str = "bob", speaker: str = "alice") -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_agent(owner),
        owner_entity_id=EntityId(f"body-{owner}"),
        counterparts=(
            CounterpartBinding(
                agent_id=_agent(speaker), entity_id=EntityId(f"body-{speaker}")
            ),
        ),
    )


def _self(owner: str = "bob") -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(f"body-{owner}"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _binding(
    owner: AgentId,
    token: str,
    *,
    kind: NamingReferentKind = NamingReferentKind.LOCATION,
    entities: tuple[str, ...] = ("loc-1",),
    status: NamingStatus = NamingStatus.ACTIVE,
    strength: float = 0.6,
) -> LabelBinding:
    return LabelBinding(
        binding_id=label_binding_id(owner, kind, token),
        owner_id=owner,
        label_token=token,
        referent_kind=kind,
        status=status,
        strength=strength,
        candidates=tuple(
            NamingCandidate(kind=kind, entity_id=entity, confidence=0.7)
            for entity in entities
        ),
        evidence_count=2,
    )


def _terminology(owner: AgentId, *bindings: LabelBinding) -> TerminologyLedger:
    return TerminologyLedger(owner_id=owner, bindings=tuple(bindings))


def _provenance(tick: int) -> ObservationProvenance:
    return ObservationProvenance(
        source_kind=ObservationSourceKind.COMMUNICATION,
        source_tick=max(0, tick - 1),
        source_event_id=EventId(f"evt-{tick}"),
    )


def _communication(
    tick: int,
    relations: tuple[CommunicationRelation, ...],
    *,
    listener: str = "bob",
    speaker: str = "alice",
) -> ObservedCommunication:
    return ObservedCommunication(
        provenance=_provenance(tick),
        speaker_id=EntityId(f"body-{speaker}"),
        listener_id=EntityId(f"body-{listener}"),
        utterance=origin_utterance(
            text="call",
            speaker_id=EntityId(f"body-{speaker}"),
            communication_id=f"comm-{tick}",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
        action_kind="talk",
    )


def _observe(
    tick: int,
    *,
    owner: str = "bob",
    locations: tuple[str, ...] = ("loc-1",),
    communications: tuple[ObservedCommunication, ...] = (),
    artifacts: tuple[ObservedArtifact, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId(f"body-{owner}"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(owner),
        locations=tuple(
            ObservedLocation(entity_id=EntityId(value), name=value)
            for value in sorted(locations)
        ),
        artifacts=artifacts,
        communications=communications,
    )


def _call(token: str, kind: str = "location") -> CommunicationRelation:
    return CommunicationRelation(subject=token, predicate="call", object=kind)


def test_shared_observation_creates_candidate_then_promotes() -> None:
    owner = _agent("bob")
    own = _binding(owner, "own_place")
    terminology = _terminology(owner, own)
    identity = _identity()
    previous = None
    for tick in (1, 2, 3):
        previous = apply_translation_update(
            _observe(
                tick,
                communications=(_communication(tick, (_call("foreign_a"),)),),
            ),
            identity,
            previous,
            terminology,
        )
        assert previous is not None
    mapping = previous.mappings[0]
    assert mapping.source_token == "foreign_a"
    assert mapping.source_kind is TranslationSourceKind.LABEL
    assert mapping.status is TranslationMappingStatus.ACTIVE
    assert mapping.targets[0].label_token == "own_place"
    assert mapping.strength >= 0.45
    assert len(mapping.evidence) >= 3
    resolution = resolve_translation_token(previous, terminology, "foreign_a")
    assert resolution.status == "resolved"
    assert resolution.binding is not None
    assert resolution.binding.label_token == "own_place"


def test_one_observation_stays_candidate() -> None:
    owner = _agent("bob")
    terminology = _terminology(owner, _binding(owner, "own_place"))
    ledger = apply_translation_update(
        _observe(1, communications=(_communication(1, (_call("foreign_a"),)),)),
        _identity(),
        None,
        terminology,
    )
    assert ledger is not None
    assert ledger.mappings[0].status is TranslationMappingStatus.CANDIDATE


def test_two_close_targets_are_ambiguous() -> None:
    owner = _agent("bob")
    terminology = _terminology(
        owner,
        _binding(owner, "own_a", entities=("loc-1",)),
        _binding(owner, "own_b", entities=("loc-2",)),
    )
    ledger = None
    for tick in (1, 2, 3):
        ledger = apply_translation_update(
            _observe(
                tick,
                locations=("loc-1", "loc-2"),
                communications=(_communication(tick, (_call("foreign_a"),)),),
            ),
            _identity(),
            ledger,
            terminology,
        )
    assert ledger is not None
    mapping = ledger.mappings[0]
    assert len(mapping.targets) == 2
    assert mapping.fit is TranslationFit.AMBIGUOUS
    assert resolve_translation_token(ledger, terminology, "foreign_a").status in {
        "ambiguous",
        "resolved",
    }


def test_partial_fit_when_target_has_multiple_candidates() -> None:
    owner = _agent("bob")
    own = _binding(owner, "own_place", entities=("loc-1", "loc-2"))
    terminology = _terminology(owner, own)
    ledger = None
    for tick in (1, 2, 3):
        ledger = apply_translation_update(
            _observe(
                tick,
                locations=("loc-1", "loc-2"),
                communications=(_communication(tick, (_call("foreign_a"),)),),
            ),
            _identity(),
            ledger,
            terminology,
        )
    assert ledger is not None
    assert ledger.mappings[0].fit is TranslationFit.PARTIAL
    assert resolve_translation_token(ledger, terminology, "foreign_a").status == (
        "ambiguous"
    )


def test_demonstration_channel_uses_cooccurring_own_token() -> None:
    owner = _agent("bob")
    terminology = _terminology(owner, _binding(owner, "own_place"))
    ledger = apply_translation_update(
        _observe(
            1,
            communications=(
                _communication(
                    1,
                    (_call("foreign_a"), _call("own_place")),
                ),
            ),
        ),
        _identity(),
        None,
        terminology,
    )
    assert ledger is not None
    mapping = ledger.mappings[0]
    channels = {item.channel.value for item in mapping.evidence}
    assert "demonstration" in channels
    assert mapping.targets[0].label_token == "own_place"


def test_demonstration_channel_reads_composition_atoms() -> None:
    owner = _agent("bob")
    terminology = _terminology(owner, _binding(owner, "own_place"))
    relation = CommunicationRelation(
        subject="foreign_a", predicate="attributive", object="own_place"
    )
    ledger = apply_translation_update(
        _observe(1, communications=(_communication(1, (relation,)),)),
        _identity(),
        None,
        terminology,
    )
    assert ledger is not None
    mapping = ledger.mappings[0]
    assert mapping.source_token == "foreign_a"
    assert mapping.targets[0].label_token == "own_place"
    assert "demonstration" in {
        item.channel.value for item in mapping.evidence
    }


def test_repeated_interaction_channel_requires_two_prior_ticks() -> None:
    owner = _agent("bob")
    terminology = _terminology(owner, _binding(owner, "own_place"))
    ledger = None
    for tick in (1, 2, 3):
        ledger = apply_translation_update(
            _observe(
                tick,
                communications=(_communication(tick, (_call("foreign_a"),)),),
            ),
            _identity(),
            ledger,
            terminology,
        )
    assert ledger is not None
    channels = {item.channel.value for item in ledger.mappings[0].evidence}
    assert "repeated_interaction" in channels


def test_teaching_channel_and_window() -> None:
    owner = _agent("bob")
    terminology = _terminology(owner, _binding(owner, "own_place"))
    advice = (
        SimpleNamespace(
            occurrence_id="advice-1",
            source_agent_id=_agent("alice"),
            delivery_tick=1,
        ),
    )
    ledger = apply_translation_update(
        _observe(2, communications=(_communication(2, (_call("foreign_a"),)),)),
        _identity(),
        None,
        terminology,
        advice_delta=advice,
    )
    assert ledger is not None
    channels = {item.channel.value for item in ledger.mappings[0].evidence}
    assert "teaching" in channels


def test_artifact_channel_reads_objective_marks() -> None:
    owner = _agent("bob")
    terminology = _terminology(owner, _binding(owner, "own_place"))
    artifact = ObservedArtifact(
        entity_id=EntityId("artifact-1"),
        kind=ArtifactKind.SIGN,
        author_id=EntityId("body-alice"),
        created_tick=1,
        content=ArtifactContent(
            relations=(ArtifactRelation("foreign_a", "call", "location"),)
        ),
        content_revision=0,
        placement=ObservedItemPlacement.GROUND_HERE,
    )
    ledger = apply_translation_update(
        _observe(2, artifacts=(artifact,)),
        _identity(),
        None,
        terminology,
    )
    assert ledger is not None
    mapping = ledger.mappings[0]
    assert mapping.evidence[0].channel.value == "artifact"
    assert mapping.targets[0].label_token == "own_place"


def test_context_fallback_only_when_no_other_channel_fires() -> None:
    owner = _agent("bob")
    terminology = _terminology(owner, _binding(owner, "own_place"))
    ledger = apply_translation_update(
        _observe(
            1,
            locations=("loc-9",),
            communications=(_communication(1, (_call("foreign_a"),)),),
        ),
        _identity(),
        None,
        terminology,
    )
    assert ledger is not None
    mapping = ledger.mappings[0]
    assert [item.channel.value for item in mapping.evidence] == ["context"]


def test_foreign_token_without_own_binding_stays_unresolved() -> None:
    owner = _agent("bob")
    terminology = _terminology(owner)
    ledger = apply_translation_update(
        _observe(1, communications=(_communication(1, (_call("foreign_a"),)),)),
        _identity(),
        None,
        terminology,
    )
    assert ledger is not None
    assert ledger.mappings == ()
    assert resolve_translation_token(ledger, terminology, "foreign_a").status == (
        "unresolved"
    )


def test_disabled_owner_has_empty_ledger() -> None:
    owner = _agent("bob")
    ledger = empty_translation_ledger(owner)
    assert ledger.mappings == ()


def test_wrong_target_stored_without_correction() -> None:
    owner = _agent("bob")
    wrong = _binding(owner, "own_place", entities=("loc-1",))
    terminology = _terminology(owner, wrong)
    ledger = None
    for tick in (1, 2, 3):
        ledger = apply_translation_update(
            _observe(
                tick,
                communications=(_communication(tick, (_call("foreign_a"),)),),
            ),
            _identity(),
            ledger,
            terminology,
        )
    assert ledger is not None
    mapping = ledger.mappings[0]
    assert mapping.fit is TranslationFit.RESOLVED
    assert mapping.status is TranslationMappingStatus.ACTIVE
