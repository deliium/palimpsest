"""Shared-upkeep beliefs use maintenance and opposition, never benefit receipt."""

from __future__ import annotations

import pytest

from agents.cognition.models import CounterpartBinding, OwnerSafeSocialIdentity
from agents.cognition.social_norms import (
    NormEvidenceChannel,
    NormExpectation,
    NormPattern,
    apply_norm_update,
)
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


def test_shared_upkeep_records_maintain_and_oppose_but_ignores_draw() -> None:
    owner = AgentId("ada")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(1),
        tick=3,
        occurrences=(
            _occurrence("public_good_maintained", "event-maintain", accepted=True),
            _occurrence("public_good_opposed", "event-oppose", status="completed"),
            _occurrence("public_good_benefit", "event-draw", benefit_code="draw"),
        ),
    )
    ledger = apply_norm_update(
        observation,
        OwnerSafeSocialIdentity(
            owner_id=owner,
            owner_entity_id=EntityId("body-ada"),
            counterparts=(
                CounterpartBinding(AgentId("ben"), EntityId("body-ben")),
            ),
        ),
    )
    belief = next(
        item for item in ledger.beliefs if item.pattern is NormPattern.SHARED_UPKEEP
    )
    assert belief.expectation is NormExpectation.MAINTAIN_STRUCTURE
    assert tuple(item.channel for item in belief.evidence) == (
        NormEvidenceChannel.CONFORMING,
        NormEvidenceChannel.VIOLATION,
    )
    assert {item.lineage_ref for item in belief.evidence} == {
        "event-maintain",
        "event-oppose",
    }
