"""Fallible occupant loss, replacement, abandonment, and role revision."""

from __future__ import annotations

from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.offices import (
    OfficeConceptLedger,
    OfficeConceptStatus,
    OfficeRevisionKind,
    OfficeSuccessionKind,
    apply_office_concept_update,
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


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_OWNER,
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=AgentId("ben"), entity_id=EntityId("body-ben")),
            CounterpartBinding(
                agent_id=AgentId("carol"), entity_id=EntityId("body-carol")
            ),
            CounterpartBinding(agent_id=AgentId("dan"), entity_id=EntityId("body-dan")),
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
    visible: tuple[VisibleBody, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        occurrences=occurrences,
        communications=communications,
        visible_bodies=visible,
    )


def _context(observation: Observation) -> str:
    from agents.cognition.offices import _context_key

    return _context_key(observation)


def _message(
    *,
    tick: int,
    speaker: str,
    root: str,
    predicate: str,
    function: str = "help",
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


def _seed_recognized_with_occupant() -> tuple[OfficeConceptLedger, str]:
    base = _observation(tick=2)
    context = _context(base)
    ledger = None
    for tick in range(1, 6):
        ledger = apply_office_concept_update(
            _observation(
                tick=tick,
                occurrences=(_occurrence("help", "body-ben", tick),),
                communications=(
                    _message(
                        tick=tick,
                        speaker="body-ben",
                        root=f"role-ben-{tick}",
                        predicate="office_role",
                        context=context,
                    ),
                    _message(
                        tick=tick,
                        speaker="body-carol",
                        root=f"role-carol-{tick}",
                        predicate="office_role",
                        context=context,
                    ),
                ),
            ),
            _identity(),
            ledger,
        )
    ledger = apply_office_concept_update(
        _observation(
            tick=6,
            occurrences=(_occurrence("help", "body-ben", 6),),
            communications=(
                _message(
                    tick=6,
                    speaker="body-carol",
                    root="endorse-ben",
                    predicate="office_endorse",
                    context=context,
                    occupant="body-ben",
                ),
            ),
        ),
        _identity(),
        ledger,
    )
    assert ledger is not None
    concept = ledger.concepts[0]
    assert concept.status is OfficeConceptStatus.RECOGNIZED
    assert concept.occupants
    return ledger, context


def test_observed_death_records_loss_without_erasing_claims() -> None:
    ledger, _ = _seed_recognized_with_occupant()
    concept = ledger.concepts[0]
    ledger = apply_office_concept_update(
        _observation(
            tick=7,
            occurrences=(_occurrence("died", "body-ben", 7),),
        ),
        _identity(),
        ledger,
    )
    concept = next(
        item for item in ledger.concepts if item.office_id == concept.office_id
    )
    assert any(
        item.kind is OfficeSuccessionKind.OCCUPANT_LOST
        and item.proposed_occupant_id == AgentId("ben")
        for item in concept.succession
    )
    assert concept.occupants


def test_departure_without_relinquishment_is_not_vacancy() -> None:
    ledger, _ = _seed_recognized_with_occupant()
    concept_id = ledger.concepts[0].office_id
    ledger = apply_office_concept_update(
        _observation(
            tick=7,
            occurrences=(_occurrence("journey_started", "body-ben", 7),),
        ),
        _identity(),
        ledger,
    )
    concept = next(item for item in ledger.concepts if item.office_id == concept_id)
    kinds = {item.kind for item in concept.succession}
    assert OfficeSuccessionKind.OCCUPANT_ABSENT in kinds
    assert OfficeSuccessionKind.OCCUPANT_LOST not in kinds


def test_explicit_relinquishment_is_recorded() -> None:
    ledger, context = _seed_recognized_with_occupant()
    concept_id = ledger.concepts[0].office_id
    ledger = apply_office_concept_update(
        _observation(
            tick=7,
            communications=(
                _message(
                    tick=7,
                    speaker="body-ben",
                    root="relinquish-ben",
                    predicate="office_relinquish",
                    context=context,
                    occupant="body-ben",
                ),
            ),
        ),
        _identity(),
        ledger,
    )
    concept = next(item for item in ledger.concepts if item.office_id == concept_id)
    assert any(
        item.kind is OfficeSuccessionKind.OCCUPANT_RELINQUISHED
        for item in concept.succession
    )


def test_false_death_testimony_can_be_contradicted_by_return() -> None:
    ledger, context = _seed_recognized_with_occupant()
    concept_id = ledger.concepts[0].office_id
    ledger = apply_office_concept_update(
        _observation(
            tick=7,
            communications=(
                _message(
                    tick=7,
                    speaker="body-carol",
                    root="report-death",
                    predicate="office_lost",
                    context=context,
                    occupant="body-ben",
                ),
            ),
        ),
        _identity(),
        ledger,
    )
    ledger = apply_office_concept_update(
        _observation(
            tick=8,
            visible=(
                VisibleBody(
                    entity_id=EntityId("body-ben"),
                    life_status=LifeStatus.ALIVE,
                    coarse_health=CoarseHealth.STABLE,
                ),
            ),
        ),
        _identity(),
        ledger,
    )
    concept = next(item for item in ledger.concepts if item.office_id == concept_id)
    kinds = [item.kind for item in concept.succession]
    assert OfficeSuccessionKind.OCCUPANT_LOST in kinds
    assert OfficeSuccessionKind.OCCUPANT_RETURNED in kinds


def test_competing_successors_are_disputed() -> None:
    ledger, context = _seed_recognized_with_occupant()
    for tick, speaker, occupant in (
        (7, "body-carol", "body-dan"),
        (7, "body-dan", "body-carol"),
    ):
        ledger = apply_office_concept_update(
            _observation(
                tick=tick,
                communications=(
                    _message(
                        tick=tick,
                        speaker=speaker,
                        root=f"succession-{speaker}-{occupant}",
                        predicate="office_succession",
                        context=context,
                        occupant=occupant,
                    ),
                ),
            ),
            _identity(),
            ledger,
        )
    concept = ledger.concepts[0]
    candidates = {claim.occupant_id for claim in concept.occupants}
    assert AgentId("carol") in candidates or AgentId("dan") in candidates
    assert concept.preferred_occupant is None
    assert concept.status is OfficeConceptStatus.DISPUTED


def test_owner_abandonment_retains_history() -> None:
    ledger, context = _seed_recognized_with_occupant()
    concept_id = ledger.concepts[0].office_id
    ledger = apply_office_concept_update(
        _observation(
            tick=7,
            communications=(
                _message(
                    tick=7,
                    speaker="body-ben",
                    root="abandon",
                    predicate="office_abandon",
                    context=context,
                ),
            ),
        ),
        _identity(),
        ledger,
    )
    concept = next(item for item in ledger.concepts if item.office_id == concept_id)
    assert concept.status is OfficeConceptStatus.ABANDONED
    assert any(
        item.kind is OfficeSuccessionKind.ABANDONED for item in concept.succession
    )


def test_minor_duty_revision_keeps_identity_and_records_revision() -> None:
    ledger, context = _seed_recognized_with_occupant()
    concept_id = ledger.concepts[0].office_id
    ledger = apply_office_concept_update(
        _observation(
            tick=7,
            communications=(
                _message(
                    tick=7,
                    speaker="body-carol",
                    root="duty-revision",
                    predicate="office_duty",
                    context=f"{context}|coordinate",
                ),
            ),
        ),
        _identity(),
        ledger,
    )
    concept = next(item for item in ledger.concepts if item.office_id == concept_id)
    assert concept.office_id == concept_id
    assert any(
        item.kind is OfficeRevisionKind.DUTY_REVISED for item in concept.revisions
    )


def test_major_function_change_links_predecessor() -> None:
    ledger, context = _seed_recognized_with_occupant()
    predecessor_id = ledger.concepts[0].office_id
    ledger = apply_office_concept_update(
        _observation(
            tick=7,
            communications=(
                _message(
                    tick=7,
                    speaker="body-carol",
                    root="role-change",
                    predicate="office_change",
                    function="teaching",
                    context=context,
                ),
            ),
        ),
        _identity(),
        ledger,
    )
    changed = next(
        item for item in ledger.concepts if item.predecessor_office_id == predecessor_id
    )
    assert changed.function.value == "teaching"
    assert any(
        item.kind is OfficeSuccessionKind.ROLE_CHANGED for item in changed.succession
    )
    assert any(item.office_id == predecessor_id for item in ledger.concepts)


def test_exact_perception_kind_mapping_is_pinned() -> None:
    from agents.cognition.offices import _DEPARTURE_KINDS

    assert _DEPARTURE_KINDS == {
        "move",
        "journey_started",
        "journey_ended",
        "flee",
        "fled",
    }
