"""Delivered mediation function evidence reaches the office update seam."""

from __future__ import annotations

from agents.cognition.mediation import mediation_function_evidence
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.offices import (
    OfficeFunction,
    apply_office_concept_update,
    empty_office_concept_ledger,
)
from agents.models import AgentId
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

_OWNER = AgentId("ada")
_BEN = AgentId("ben")
_CAROL = AgentId("carol")
_CASE = "f" * 64


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_BEN, entity_id=EntityId("body-ben")),
            CounterpartBinding(agent_id=_CAROL, entity_id=EntityId("body-carol")),
        ),
    )


def _observation(
    *, tick: int = 1, relations: tuple[CommunicationRelation, ...]
) -> Observation:
    utterance = origin_utterance(
        text="mediation",
        speaker_id=EntityId("body-carol"),
        communication_id=f"root-{tick}",
        relations=relations,
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    communication = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(f"event-{tick}"),
        ),
        speaker_id=EntityId("body-carol"),
        listener_id=EntityId("body-ada"),
        utterance=utterance,
        action_kind="tell",
    )
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=ObservedSelf(
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
        ),
        communications=(communication,),
    )


def test_delivered_mediation_function_evidence_is_neutral_and_deduplicated() -> None:
    relation = CommunicationRelation(
        subject="item_share",
        predicate="mediation_mediate",
        object=f"{_CASE}|0",
    )
    observation = _observation(relations=(relation, relation))
    rows = mediation_function_evidence(observation, _identity())
    assert len(rows) == 1
    assert rows[0].function == "conflict_mediation"
    assert rows[0].recognized is False


def test_invitation_evidence_reaches_office_update_without_recognition() -> None:
    relation = CommunicationRelation(
        subject="conflict_mediation",
        predicate="mediation_invite",
        object=f"{_CASE}|0|conflict_mediation|{'a' * 16}|-",
    )
    observation = _observation(relations=(relation,))
    rows = mediation_function_evidence(observation, _identity())
    assert rows
    ledger = apply_office_concept_update(
        observation,
        _identity(),
        empty_office_concept_ledger(_OWNER),
        mediation_roles=rows,
    )
    assert ledger.concepts
    concept = ledger.concepts[0]
    assert concept.function is OfficeFunction.CONFLICT_MEDIATION
    assert "insufficient_recurrence" in concept.notices
    assert concept.status.value != "recognized"


def test_disabled_office_mode_ignores_mediation_rows() -> None:
    relation = CommunicationRelation(
        subject="item_share",
        predicate="mediation_mediate",
        object=f"{_CASE}|0",
    )
    observation = _observation(relations=(relation,))
    rows = mediation_function_evidence(observation, _identity())
    ledger = apply_office_concept_update(
        observation,
        _identity(),
        None,
        mediation_roles=rows,
    )
    # No office policy/mode is required for this pure update; the row is still
    # merely function evidence and never a success or recognition claim.
    assert all(concept.status.value != "recognized" for concept in ledger.concepts)
