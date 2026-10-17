"""Direct-observation contact memory keeps bounded participant/present IDs."""

from __future__ import annotations

from agents.cognition.memory import build_direct_observation_memory_trace
from agents.models import AgentId
from world.identifiers import EntityId, EventId, WorldRevision
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)


def _occurrence() -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=6,
            source_event_id=EventId("event-contact"),
        ),
        kind="contact_recorded",
        audience_role=ObservationAudienceRole.TARGET,
        public_facts={
            "kind": "contact_recorded",
            "contact_location_id": "loc-b",
            "contact_participant_ids": ["body-1"],
            "contact_present_ids": ["body-2", "body-3"],
            "origin_region_id": "north",
        },
    )


def test_contact_memory_contains_sorted_contact_entities_only() -> None:
    trace = build_direct_observation_memory_trace(
        owner_id=AgentId("agent-1"),
        observation_tick=6,
        observation_revision=WorldRevision(6),
        occurrence=_occurrence(),
        location_id=EntityId("loc-b"),
    )
    entity_ids = [mention.entity_id.value for mention in trace.entities]
    assert entity_ids == ["body-1", "body-2", "body-3"]
    assert all("north" not in value for value in entity_ids)
    assert any(item.concept == "contact_recorded" for item in trace.concepts)


def test_contact_memory_caps_entities_deterministically() -> None:
    occurrence = ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=6,
            source_event_id=EventId("event-contact"),
        ),
        kind="contact_recorded",
        audience_role=ObservationAudienceRole.TARGET,
        public_facts={
            "kind": "contact_recorded",
            "contact_participant_ids": ["body-1"],
            "contact_present_ids": [f"body-{index:02d}" for index in range(2, 20)],
        },
    )
    trace = build_direct_observation_memory_trace(
        owner_id=AgentId("agent-1"),
        observation_tick=6,
        observation_revision=WorldRevision(6),
        occurrence=occurrence,
        location_id=EntityId("loc-b"),
    )
    assert len(trace.entities) == 8


def test_contact_memory_is_deterministic_across_rebuilds() -> None:
    first = build_direct_observation_memory_trace(
        owner_id=AgentId("agent-1"),
        observation_tick=6,
        observation_revision=WorldRevision(6),
        occurrence=_occurrence(),
        location_id=EntityId("loc-b"),
    )
    second = build_direct_observation_memory_trace(
        owner_id=AgentId("agent-1"),
        observation_tick=6,
        observation_revision=WorldRevision(6),
        occurrence=_occurrence(),
        location_id=EntityId("loc-b"),
    )
    assert first == second
    assert [(item.mention_id, item.entity_id) for item in first.entities] == [
        (item.mention_id, item.entity_id) for item in second.entities
    ]
