"""Institutional decay evidence attrition and bounded retention."""

from __future__ import annotations

import pytest

from agents.cognition.institution_concepts import (
    InstitutionPatternChannel,
    empty_institution_concept_ledger,
)
from agents.cognition.institutional_decay import (
    InstitutionDecayUpdate,
    apply_institution_decay_update,
    empty_institution_decay_ledger,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
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


def _agent(value: str = "ada") -> AgentId:
    return AgentId(value)


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_agent(),
        owner_entity_id=EntityId("body-ada"),
        counterparts=(
            CounterpartBinding(agent_id=_agent("ben"), entity_id=EntityId("body-ben")),
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


def _occurrence(
    kind: str = "public_good_maintained",
    *,
    tick: int,
    event: str | None = None,
    success: bool | None = True,
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=max(tick - 1, 0),
            source_event_id=EventId(event or f"event-{tick}-{kind}"),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId("body-ada"),
        success=success,
    )


def _observe(*occurrences: ObservedOccurrence, tick: int) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(),
        occurrences=occurrences,
    )


def _first_update() -> InstitutionDecayUpdate:
    update = apply_institution_decay_update(
        observation=_observe(_occurrence(tick=1), tick=1),
        identity=_identity(),
        previous_concepts=empty_institution_concept_ledger(_agent()),
        previous_decay=empty_institution_decay_ledger(_agent()),
    )
    return update


def test_evidence_can_strengthen_then_weaken_without_scripted_collapse() -> None:
    update = _first_update()
    assert update.decay.bindings
    assert update.decay.samples
    concept = update.concepts.concepts[0]
    assert concept.role_recognition > 0.0

    idle = apply_institution_decay_update(
        observation=_observe(tick=2),
        identity=_identity(),
        previous_concepts=update.concepts,
        previous_decay=update.decay,
    )
    weakened = idle.concepts.concepts[0]
    assert weakened.role_recognition < concept.role_recognition
    assert (
        idle.decay.bindings[0].local_pattern_id
        == update.decay.bindings[0].local_pattern_id
    )

    renewed = apply_institution_decay_update(
        observation=_observe(
            _occurrence(tick=3, event="event-3-public_good_maintained"), tick=3
        ),
        identity=_identity(),
        previous_concepts=idle.concepts,
        previous_decay=idle.decay,
    )
    recovered = renewed.concepts.concepts[0]
    assert recovered.role_recognition >= weakened.role_recognition
    assert recovered.role_recognition > 0.0


def test_same_tick_is_idempotent_and_adds_no_sample() -> None:
    update = _first_update()
    repeated = apply_institution_decay_update(
        observation=_observe(
            _occurrence(tick=1, event="event-1-public_good_maintained"), tick=1
        ),
        identity=_identity(),
        previous_concepts=update.concepts,
        previous_decay=update.decay,
    )
    assert repeated.concepts == update.concepts
    assert repeated.decay == update.decay
    assert len(repeated.decay.samples) == len(update.decay.samples)


def test_tick_regression_fails_closed() -> None:
    update = _first_update()
    try:
        apply_institution_decay_update(
            observation=_observe(tick=0),
            identity=_identity(),
            previous_concepts=update.concepts,
            previous_decay=update.decay,
        )
    except ValueError as exc:
        assert "tick_regression" in str(exc)
    else:
        raise AssertionError("expected tick regression rejection")


def test_covered_inactivity_eventually_retires_private_concept() -> None:
    update = _first_update()
    concepts = update.concepts
    decay = update.decay
    for tick in range(2, 30):
        update = apply_institution_decay_update(
            observation=_observe(tick=tick),
            identity=_identity(),
            previous_concepts=concepts,
            previous_decay=decay,
        )
        concepts = update.concepts
        decay = update.decay
    assert (
        max(
            concept.strength_for(channel)
            for concept in concepts.concepts
            for channel in InstitutionPatternChannel
        )
        == 0.0
    )
    assert all(sample.recognized is False for sample in decay.samples[-4:])


def test_failed_occurrence_does_not_create_accepted_participation() -> None:
    update = apply_institution_decay_update(
        observation=_observe(_occurrence(tick=1, success=False), tick=1),
        identity=_identity(),
        previous_concepts=empty_institution_concept_ledger(_agent()),
        previous_decay=empty_institution_decay_ledger(_agent()),
    )
    for sample in update.decay.samples:
        assert sample.evidence.participant_actions == ()


def test_receipts_and_samples_are_bounded() -> None:
    update = _first_update()
    concepts = update.concepts
    decay = update.decay
    for tick in range(2, 600):
        update = apply_institution_decay_update(
            observation=_observe(
                _occurrence(tick=tick, event=f"event-{tick}-public_good_maintained"),
                tick=tick,
            ),
            identity=_identity(),
            previous_concepts=concepts,
            previous_decay=decay,
        )
        concepts = update.concepts
        decay = update.decay
    assert len(decay.samples) <= 256
    assert len(decay.receipts) <= 512
    assert decay.sample_count_pruned > 0
    for record in decay.records:
        assert record.inception_tick >= 1


def test_norm_office_and_memory_sources_populate_dimensions() -> None:
    from types import SimpleNamespace

    norm_belief = SimpleNamespace(
        status=SimpleNamespace(value="active"),
        belief_id="n1",
        supporters=(_agent("ben"),),
    )
    support = SimpleNamespace(
        independently_evidenced=True,
        resolved=True,
        supporter_id=_agent("ben"),
        root_ref="root-1",
    )
    transition = SimpleNamespace(
        succession_id="s1",
        kind=SimpleNamespace(value="occupant_lost"),
        proposed_occupant_id=None,
    )
    office_concept = SimpleNamespace(
        supporters=(support,),
        succession=(transition,),
    )
    entry = SimpleNamespace(entry_id="e1", active=True, ignored=False)
    update = apply_institution_decay_update(
        observation=_observe(_occurrence(tick=1), tick=1),
        identity=_identity(),
        previous_concepts=empty_institution_concept_ledger(_agent()),
        previous_decay=empty_institution_decay_ledger(_agent()),
        norms=SimpleNamespace(owner_id=_agent(), beliefs=(norm_belief,)),
        prior_offices=SimpleNamespace(owner_id=_agent(), concepts=(office_concept,)),
        prior_institutional_memory=SimpleNamespace(
            owner_id=_agent(), entries=(entry,)
        ),
    )
    evidence = update.decay.samples[-1].evidence
    assert (_agent("ben"), "norm-n1") in evidence.supporters
    assert (_agent("ben"), "root-1") in evidence.supporters
    assert evidence.succession_transitions == ("s1",)
    assert evidence.knowledge_assessments[0].before_entry_ids == ("e1",)
    assert evidence.knowledge_assessments[0].retained_entry_ids == ("e1",)


def test_conflicting_same_tick_evidence_is_rejected() -> None:
    first = _first_update()
    with pytest.raises(ValueError, match="conflicting_update"):
        apply_institution_decay_update(
            observation=_observe(
                _occurrence(tick=1, event="different-event"), tick=1
            ),
            identity=_identity(),
            previous_concepts=first.concepts,
            previous_decay=first.decay,
        )
