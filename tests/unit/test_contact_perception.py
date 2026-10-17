"""Contact perception exposes co-presence only to participants and present agents."""

from __future__ import annotations

from world._perception import _audience_role, _public_facts_for_role
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V22,
    ContactRecorded,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import ObservationAudienceRole


def _event(*, location: str = "loc-b") -> WorldEvent:
    details = ContactRecorded(
        relocation_kind="journey_arrived",
        journey_id="journey-1",
        location_id=EntityId(location),
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
            details,
            origin_location_id=None,
            destination_location_id=EntityId(location),
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V22,
    )


def test_participant_role_and_facts_include_both_id_sets() -> None:
    event = _event()
    role = _audience_role(
        event,
        observer_id=EntityId("body-1"),
        location_id=EntityId("loc-b"),
        content_visible=True,
    )
    assert role is ObservationAudienceRole.TARGET
    facts = _public_facts_for_role(event, role)
    assert facts["kind"] == "contact_recorded"
    assert facts["contact_location_id"] == "loc-b"
    assert facts["contact_participant_ids"] == ["body-1"]
    assert facts["contact_present_ids"] == ["body-2"]
    assert "origin_region_id" not in facts
    assert "destination_region_id" not in facts


def test_present_agent_is_witness_with_facts() -> None:
    event = _event()
    role = _audience_role(
        event,
        observer_id=EntityId("body-2"),
        location_id=EntityId("loc-b"),
        content_visible=True,
    )
    assert role is ObservationAudienceRole.WITNESS
    assert _public_facts_for_role(event, role)["contact_present_ids"] == ["body-2"]


def test_absent_agent_receives_nothing() -> None:
    event = _event()
    assert (
        _audience_role(
            event,
            observer_id=EntityId("body-3"),
            location_id=EntityId("loc-a"),
            content_visible=True,
        )
        is None
    )
