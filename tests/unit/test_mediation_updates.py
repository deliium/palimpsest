"""Deterministic owner-local mediation updates, deduplication, and expiry."""

from __future__ import annotations

import pytest

from agents.cognition.mediation import (
    MediationCaseStatus,
    MediationRecommendationStatus,
    MediationResponseKind,
    apply_mediation_update,
    default_mediation_policy,
    empty_mediation_ledger,
    generate_mediation_opportunities,
    mediation_case_ref,
    mediation_context_key,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
    ObservedSelf,
    VisibleBody,
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
_BEN = AgentId("ben")
_CAROL = AgentId("carol")
_CASE = "f" * 64
_CONTEXT = "a" * 16


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_BEN, entity_id=EntityId("body-ben")),
            CounterpartBinding(agent_id=_CAROL, entity_id=EntityId("body-carol")),
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


def _observation(
    *,
    tick: int,
    communications: tuple[ObservedCommunication, ...] = (),
    visible: tuple[VisibleBody, ...] = (),
    occurrences: tuple[ObservedOccurrence, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        communications=communications,
        visible_bodies=visible,
        occurrences=occurrences,
    )


def _message(
    *,
    tick: int,
    speaker: str,
    root: str,
    relations: tuple[CommunicationRelation, ...],
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="mediation",
        speaker_id=EntityId(speaker),
        communication_id=root,
        relations=relations,
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


def _relation(predicate: str, object_text: str) -> CommunicationRelation:
    return CommunicationRelation(
        subject="item_share", predicate=predicate, object=object_text
    )


def _mediate(*, speaker: str = "body-carol") -> ObservedCommunication:
    return _message(
        tick=1,
        speaker=speaker,
        root="root-1",
        relations=(_relation("mediation_mediate", f"{_CASE}|0"),),
    )


def _compromise(*, root: str = "root-2", tick: int = 1) -> ObservedCommunication:
    payload = f"{_CASE}|0|give|body-ben|bread|1|return_item|1|8"
    return _message(
        tick=tick,
        speaker="body-carol",
        root=root,
        relations=(_relation("mediation_compromise", payload),),
    )


def test_delivered_mediate_creates_one_local_case() -> None:
    ledger = apply_mediation_update(
        _observation(tick=1, communications=(_mediate(),)), _identity()
    )
    assert len(ledger.cases) == 1
    case = ledger.cases[0]
    assert case.case_ref == _CASE
    assert case.owner_id == _OWNER
    assert case.party_ids == (_CAROL,)
    assert case.actionable is False
    assert ledger.observation_count == 1


def test_duplicate_and_replayed_evidence_are_deduplicated() -> None:
    observation = _observation(tick=1, communications=(_mediate(),))
    first = apply_mediation_update(observation, _identity())
    second = apply_mediation_update(observation, _identity(), first)
    assert len(second.cases) == len(first.cases)
    assert second.cases[0].evidence == first.cases[0].evidence
    assert second.observation_count == first.observation_count


def test_reordering_two_observers_yields_the_same_case_set() -> None:
    left = _mediate(speaker="body-carol")
    right = _message(
        tick=1,
        speaker="body-ben",
        root="root-other",
        relations=(_relation("mediation_mediate", f"{_CASE}|0"),),
    )
    forward = apply_mediation_update(
        _observation(tick=1, communications=(left, right)), _identity()
    )
    reverse = apply_mediation_update(
        _observation(tick=1, communications=(right, left)), _identity()
    )
    assert [case.case_ref for case in forward.cases] == [
        case.case_ref for case in reverse.cases
    ]


def test_foreign_previous_ledger_is_rejected() -> None:
    foreign = empty_mediation_ledger(_BEN)
    with pytest.raises(ValueError, match="owner_id mismatch"):
        apply_mediation_update(_observation(tick=1), _identity(), foreign)


def test_compromise_and_revision_scoped_acceptance() -> None:
    first = apply_mediation_update(
        _observation(tick=1, communications=(_compromise(),)), _identity()
    )
    assert len(first.recommendations) == 1
    recommendation = first.recommendations[0]
    assert recommendation.revision == 0
    assert recommendation.actionable is True

    accept = _message(
        tick=2,
        speaker="body-ben",
        root="root-accept",
        relations=(
            _relation(
                "mediation_accept",
                f"{_CASE}|0|{recommendation.recommendation_id}|0|give_bread|-|-|-|-",
            ),
        ),
    )
    second = apply_mediation_update(
        _observation(tick=2, communications=(accept,)), _identity(), first
    )
    responses = [item for item in second.responses if item.active]
    assert len(responses) == 1
    assert responses[0].kind is MediationResponseKind.ACCEPT
    assert responses[0].recommendation_revision == 0
    assert responses[0].direct is True

    stale = _message(
        tick=3,
        speaker="body-ben",
        root="root-stale",
        relations=(
            _relation(
                "mediation_accept",
                f"{_CASE}|0|{recommendation.recommendation_id}|1|give_bread|-|-|-|-",
            ),
        ),
    )
    third = apply_mediation_update(
        _observation(tick=3, communications=(stale,)), _identity(), second
    )
    assert "unknown_recommendation" in third.notices


def test_private_peer_perturbation_requires_delivered_evidence() -> None:
    baseline = apply_mediation_update(_observation(tick=1), _identity())
    assert baseline.cases == ()
    assert baseline.responses == ()


def test_case_and_recommendation_expire_after_window() -> None:
    policy = default_mediation_policy()
    first = apply_mediation_update(
        _observation(tick=1, communications=(_compromise(),)), _identity()
    )
    later = apply_mediation_update(
        _observation(tick=1 + policy.default_action_window + 1),
        _identity(),
        first,
    )
    assert later.cases[0].status is MediationCaseStatus.EXPIRED
    assert later.recommendations[0].status is MediationRecommendationStatus.EXPIRED


def test_opportunity_generation_requires_observed_contention() -> None:
    ledger = empty_mediation_ledger(_OWNER)
    co_present = _observation(
        tick=1,
        visible=(
            VisibleBody(
                entity_id=EntityId("body-ben"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
            VisibleBody(
                entity_id=EntityId("body-carol"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
    )
    assert generate_mediation_opportunities(ledger, co_present, _identity()) == ledger
    contention = _observation(
        tick=1,
        occurrences=(
            ObservedOccurrence(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.OCCURRENCE,
                    source_tick=0,
                    source_event_id=EventId("event-attack"),
                ),
                kind="attack",
                audience_role=ObservationAudienceRole.WITNESS,
                actor_id=EntityId("body-ben"),
                other_entity_id=EntityId("body-carol"),
            ),
        ),
    )
    generated = generate_mediation_opportunities(ledger, contention, _identity())
    assert len(generated.cases) == 1
    assert generated.cases[0].actionable is True
    assert generated.cases[0].party_ids == (_BEN, _CAROL)
    assert generated.cases[0].subject_token == "observed_contention"


def test_case_ref_and_context_are_deterministic() -> None:
    observation = _observation(tick=1)
    assert mediation_context_key(observation) == mediation_context_key(observation)
    left = mediation_case_ref(
        _OWNER,
        origin_id=_BEN,
        subject_token="item_share",
        context_key=mediation_context_key(observation),
        inception_tick=1,
        inception_lineage="lineage",
    )
    right = mediation_case_ref(
        _OWNER,
        origin_id=_BEN,
        subject_token="item_share",
        context_key=mediation_context_key(observation),
        inception_tick=1,
        inception_lineage="lineage",
    )
    assert left == right
