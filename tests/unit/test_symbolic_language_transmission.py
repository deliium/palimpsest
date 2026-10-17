"""Listener-side composition parsing is owner-scoped and non-copying."""

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
from agents.models import AgentId
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
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


def _binding(
    owner: AgentId, token: str, kind: NamingReferentKind = NamingReferentKind.LOCATION
) -> LabelBinding:
    return LabelBinding(
        binding_id=label_binding_id(owner, kind, token),
        owner_id=owner,
        label_token=token,
        referent_kind=kind,
        status=NamingStatus.ACTIVE,
        strength=0.5,
        candidates=(NamingCandidate(kind=kind, entity_id="ref-1", confidence=0.5),),
        evidence_count=3,
    )


def _observation(
    *,
    tick: int,
    observer: str,
    communication: ObservedCommunication | None = None,
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId(observer),
        revision=WorldRevision(1),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId(observer),
            location_id=EntityId("loc-1"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        occurrences=(),
        visible_bodies=(),
        communications=() if communication is None else (communication,),
    )


def _communication(
    utterance_relations: tuple[CommunicationRelation, ...],
    *,
    event: str = "event-1",
) -> ObservedCommunication:
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=1,
            source_event_id=EventId(event),
        ),
        speaker_id=EntityId("body-1"),
        listener_id=EntityId("body-2"),
        utterance=origin_utterance(
            text="call",
            speaker_id=EntityId("body-1"),
            relations=utterance_relations,
        ),
        action_kind="talk",
    )


def _listener(
    tokens: tuple[str, ...],
) -> tuple[AgentId, OwnerSafeSocialIdentity, TerminologyLedger]:
    owner = AgentId("listener")
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-2"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("speaker"), entity_id=EntityId("body-1")
            ),
        ),
    )
    terminology = TerminologyLedger(
        owner_id=owner, bindings=tuple(_binding(owner, token) for token in tokens)
    )
    return owner, identity, terminology


def test_listener_with_both_constituents_learns_communicated_evidence() -> None:
    _, identity, terminology = _listener(("alpha", "beta"))
    communication = _communication(
        (
            CommunicationRelation(subject="alpha", predicate="call", object="location"),
            CommunicationRelation(subject="beta", predicate="call", object="location"),
            CommunicationRelation(
                subject="alpha", predicate="relational", object="beta"
            ),
        )
    )
    ledger = apply_symbolic_update(
        _observation(tick=2, observer="body-2", communication=communication),
        identity,
        None,
        terminology,
    )
    assert ledger is not None
    assert len(ledger.compositions) == 1
    assert ledger.compositions[0].evidence[0].channel.value == "communicated"
    assert ledger.interpretations[0].outcome.value == "parsed"


def test_missing_constituent_creates_no_composition() -> None:
    _, identity, terminology = _listener(("alpha",))
    communication = _communication(
        (
            CommunicationRelation(
                subject="alpha", predicate="attributive", object="beta"
            ),
        )
    )
    ledger = apply_symbolic_update(
        _observation(tick=2, observer="body-2", communication=communication),
        identity,
        None,
        terminology,
    )
    assert ledger is not None
    assert ledger.compositions == ()
    assert ledger.interpretations[0].outcome.value == "partial"


def test_unsupported_predicate_is_ignored() -> None:
    _, identity, terminology = _listener(("alpha", "beta"))
    communication = _communication(
        (CommunicationRelation(subject="alpha", predicate="implies", object="beta"),)
    )
    ledger = apply_symbolic_update(
        _observation(tick=2, observer="body-2", communication=communication),
        identity,
        None,
        terminology,
    )
    assert ledger is not None
    assert ledger.compositions == ()
    assert ledger.interpretations == ()


def test_two_listeners_with_different_constituent_kinds_form_own_hypotheses() -> None:
    communication = _communication(
        (CommunicationRelation(subject="alpha", predicate="relational", object="beta"),)
    )
    _, location_identity, location_terms = _listener(("alpha", "beta"))
    location_ledger = apply_symbolic_update(
        _observation(tick=2, observer="body-2", communication=communication),
        location_identity,
        None,
        location_terms,
    )
    agent_owner = AgentId("listener2")
    agent_identity = OwnerSafeSocialIdentity(
        owner_id=agent_owner, owner_entity_id=EntityId("body-2")
    )
    agent_terms = TerminologyLedger(
        owner_id=agent_owner,
        bindings=(
            _binding(agent_owner, "alpha", NamingReferentKind.AGENT),
            _binding(agent_owner, "beta", NamingReferentKind.AGENT),
        ),
    )
    agent_ledger = apply_symbolic_update(
        _observation(tick=2, observer="body-2", communication=communication),
        agent_identity,
        None,
        agent_terms,
    )
    assert location_ledger is not None and agent_ledger is not None
    assert (
        location_ledger.compositions[0].composition_id
        != agent_ledger.compositions[0].composition_id
    )
    location_hypothesis = location_ledger.compositions[0].referent_hypothesis
    agent_hypothesis = agent_ledger.compositions[0].referent_hypothesis
    assert location_hypothesis is not None
    assert agent_hypothesis is not None
    assert location_hypothesis.referent_kind is NamingReferentKind.LOCATION
    assert agent_hypothesis.referent_kind is NamingReferentKind.AGENT
