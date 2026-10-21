"""Deterministic invariants for institutional decay and analysis."""

from __future__ import annotations

import pytest

from agents.cognition.institution_concepts import (
    InstitutionPatternChannel,
    empty_institution_concept_ledger,
)
from agents.cognition.institutional_decay import (
    InstitutionDecayPolicy,
    InstitutionDecayUpdate,
    apply_institution_decay_update,
    empty_institution_decay_ledger,
    require_owner_institution_decay,
)
from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.models import AgentId
from analysis.institutional_decay import (
    InstitutionTemporalRow,
    compute_institutional_decay,
)
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


def _owner() -> AgentId:
    return AgentId("alice")


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_owner(),
        owner_entity_id=EntityId("alice-body"),
        counterparts=(
            CounterpartBinding(agent_id=AgentId("bob"), entity_id=EntityId("bob-body")),
        ),
    )


def _observe(tick: int, *, event: str | None = None) -> Observation:
    return Observation(
        world_id=WorldId("world"),
        observer_id=EntityId("alice-body"),
        revision=WorldRevision(1),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId("alice-body"),
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
        occurrences=(
            ObservedOccurrence(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.OCCURRENCE,
                    source_tick=max(tick - 1, 0),
                    source_event_id=EventId(event or f"event-{tick}"),
                ),
                kind="public_good_maintained",
                audience_role=ObservationAudienceRole.WITNESS,
                actor_id=EntityId("alice-body"),
                success=True,
            ),
        ),
    )


def _update(
    tick: int,
    *,
    previous_concepts: object | None = None,
    previous_decay: object | None = None,
) -> InstitutionDecayUpdate:
    return apply_institution_decay_update(
        observation=_observe(tick),
        identity=_identity(),
        previous_concepts=previous_concepts
        or empty_institution_concept_ledger(_owner()),
        previous_decay=previous_decay or empty_institution_decay_ledger(_owner()),
    )


def test_every_strength_is_finite_and_bounded() -> None:
    first = _update(1)
    for concept in first.concepts.concepts:
        for channel in InstitutionPatternChannel:
            value = concept.strength_for(channel)
            assert 0.0 <= value <= 1.0


def test_input_order_of_unrelated_agents_does_not_change_this_owner() -> None:
    first = _update(1)
    again = _update(1)
    assert first.concepts == again.concepts
    assert first.decay == again.decay


def test_foreign_owner_decay_state_is_rejected() -> None:
    first = _update(1)
    with pytest.raises(ValueError, match="mismatch"):
        require_owner_institution_decay(first.decay, AgentId("bob"))


def test_hidden_agents_do_not_create_support_or_collapse() -> None:
    first = _update(1)
    rows = []
    for tick in (1, 2, 3, 4):
        rows.append(
            InstitutionTemporalRow(
                owner_id=_owner().value,
                local_pattern_id=first.decay.bindings[0].local_pattern_id,
                observation_tick=tick,
                source_first_tick=tick,
                source_last_tick=tick,
                role_recognition=0.2,
                procedure_recurrence=0.2,
                social_expectation=0.2,
                legitimacy_belief=0.2,
                succession_observed=0.0,
                generational_continuity=0.0,
                recognized=False,
                observed_cohort=(),
            )
        )
    result = compute_institutional_decay(tuple(rows), as_of_tick=4)
    assert result.state_for[
        (_owner().value, first.decay.bindings[0].local_pattern_id)
    ] in {
        "unknown",
        "emerging",
    }


def test_policy_constants_are_locked() -> None:
    with pytest.raises(ValueError, match="unsupported_policy"):
        InstitutionDecayPolicy(channel_loss=0.5)
