"""Witnessed public-good acts reuse existing reputation delta rows."""

from __future__ import annotations

import pytest

from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.reputation import ReputationDimension, apply_reputation_update
from agents.models import AgentId
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

pytestmark = pytest.mark.unit


def _occurrence(kind: str, event_id: str, **facts: object) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=2,
            source_event_id=EventId(event_id),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId("body-ben"),
        public_facts=facts,
    )


def test_maintenance_and_opposition_move_reputation_but_draw_does_not() -> None:
    owner = AgentId("ada")
    target = AgentId("ben")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=3,
        occurrences=(
            _occurrence("public_good_maintained", "event-maintain", accepted=True),
            _occurrence(
                "project_contributed",
                "event-contribute",
                accepted=True,
                public_good=True,
            ),
            _occurrence("public_good_opposed", "event-oppose", status="completed"),
            _occurrence("public_good_benefit", "event-draw", benefit_code="draw"),
        ),
    )
    ledger = apply_reputation_update(
        owner_id=owner,
        tick=3,
        observation=observation,
        social_identity=OwnerSafeSocialIdentity(
            owner_id=owner,
            owner_entity_id=EntityId("body-ada"),
            counterparts=(
                CounterpartBinding(target, EntityId("body-ben")),
            ),
        ),
    )
    profile = ledger.profile_for(target)
    assert profile is not None
    assert profile.dimension_state(ReputationDimension.GENEROSITY).value == 0.35
    assert profile.dimension_state(ReputationDimension.HARM).value == 0.25
    assert {item.lineage_ref for item in profile.evidence} == {
        "event-maintain",
        "event-contribute",
        "event-oppose",
    }
