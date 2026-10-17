"""Observer semantic registration for neutral contact events."""

from __future__ import annotations

from observer.adapt import adapt_event
from observer.version import SEMANTIC_EVENT_TYPES, SEMANTIC_TYPE_BY_KIND
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V22,
    ContactRecorded,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _event() -> WorldEvent:
    details = ContactRecorded(
        relocation_kind="fled",
        location_id=EntityId("loc-b"),
        participant_ids=(EntityId("body-1"),),
        present_ids=(EntityId("body-2"),),
        origin_region_id="north",
        destination_region_id="south",
    )
    return make_physical_replayable_event(
        event_id=EventId("event-contact"),
        run_id="run-contact",
        world_id=WorldId("world-contact"),
        tick=6,
        sequence=0,
        cause=SystemCause(
            RequestId("request-contact"),
            SystemEffectFamily.TRAVEL,
            EntityId("body-1"),
            1,
        ),
        resulting_revision=WorldRevision(6),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=None, destination_location_id=EntityId("loc-b")
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V22,
    )


def test_contact_semantic_type_is_registered() -> None:
    assert "CONTACT_RECORDED" in SEMANTIC_EVENT_TYPES
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert SEMANTIC_TYPE_BY_KIND["contact_recorded"] == "CONTACT_RECORDED"


def test_adapted_contact_event_carries_location_and_participants() -> None:
    event = adapt_event(_event())
    assert event.type == "CONTACT_RECORDED"
    assert event.domain_kind == "contact_recorded"
    assert event.destination_location_id == "loc-b"
    assert event.participant_body_ids == ("body-1",)
    assert event.actor_id is None
