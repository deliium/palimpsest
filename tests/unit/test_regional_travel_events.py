"""Schema-v21 journey event contracts and detached wire round trips."""

from __future__ import annotations

import json

import pytest

from analysis.prospective_imagination_metrics import _first_command
from simulation.serialization import (
    DomainSerializationError,
    decode_domain,
    encode_domain,
)
from world._perception import _audience_role, _public_facts_for_role
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V20,
    EVENT_SCHEMA_REPLAY_V21,
    JourneyArrived,
    JourneyEnded,
    JourneyStarted,
    OccurrenceContext,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import ObservationAudienceRole
from world.regions import Journey


def _journey() -> Journey:
    return Journey(
        journey_id="journey-1",
        participant_body_ids=(EntityId("body-1"), EntityId("body-2")),
        actor_body_id=EntityId("body-1"),
        origin_location_id=EntityId("loc-a"),
        destination_location_id=EntityId("loc-b"),
        origin_region_id="north",
        destination_region_id="south",
        start_tick=4,
        due_tick=6,
        charged_fatigue_cost=4.5,
        arrival_wait_deadline_tick=8,
    )


def _event(
    details,
    *,
    event_id: str,
    tick: int,
    sequence: int,
    origin,
    destination=None,
):
    actor = (
        details.journey.actor_body_id if isinstance(details, JourneyStarted) else None
    )
    cause = (
        ActionCause(RequestId(f"request-{event_id}"), actor)
        if actor is not None
        else SystemCause(
            RequestId(f"request-{event_id}"),
            SystemEffectFamily.TRAVEL,
            EntityId("journey-1"),
            sequence,
        )
    )
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id="run-regional",
        world_id=WorldId("world-regional"),
        tick=tick,
        sequence=sequence,
        cause=cause,
        resulting_revision=WorldRevision(tick),
        details=details,
        occurrence=build_occurrence_context(
            details,
            origin_location_id=origin,
            destination_location_id=destination,
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V21,
    )


def test_journey_events_round_trip_as_closed_schema_v21_details() -> None:
    journey = _journey()
    started = _event(
        JourneyStarted(journey, "transport", 4.5, 13.5),
        event_id="event-start",
        tick=4,
        sequence=0,
        origin=journey.origin_location_id,
    )
    arrived = _event(
        JourneyArrived(
            journey.journey_id,
            journey.participant_body_ids,
            journey.origin_location_id,
            journey.destination_location_id,
        ),
        event_id="event-arrival",
        tick=6,
        sequence=0,
        origin=None,
        destination=journey.destination_location_id,
    )
    ended = _event(
        JourneyEnded(
            journey.journey_id,
            journey.participant_body_ids,
            journey.origin_location_id,
            journey.destination_location_id,
            "arrival_timeout",
        ),
        event_id="event-end",
        tick=8,
        sequence=0,
        origin=journey.origin_location_id,
    )
    for event in (started, arrived, ended):
        decoded = decode_domain(encode_domain(event))
        assert decoded == event
        assert event.schema_version == EVENT_SCHEMA_REPLAY_V21
    assert started.occurrence == OccurrenceContext(
        origin_location_id=journey.origin_location_id,
        affected_entity_ids=journey.participant_body_ids,
    )
    assert _first_command((started,)) == "transport"
    participant_facts = _public_facts_for_role(started, ObservationAudienceRole.TARGET)
    assert participant_facts["journey_destination_id"] == "loc-b"
    witness_facts = _public_facts_for_role(started, ObservationAudienceRole.BYSTANDER)
    assert "journey_destination_id" not in witness_facts
    assert arrived.occurrence is not None
    assert arrived.occurrence.origin_location_id is None
    assert arrived.occurrence.destination_location_id == journey.destination_location_id
    assert (
        _audience_role(
            arrived,
            observer_id=EntityId("origin-witness"),
            location_id=journey.origin_location_id,
            content_visible=True,
        )
        is None
    )
    assert (
        _audience_role(
            arrived,
            observer_id=EntityId("arrival-witness"),
            location_id=journey.destination_location_id,
            content_visible=True,
        )
        is ObservationAudienceRole.WITNESS
    )


def test_journey_details_reject_older_replay_schemas() -> None:
    journey = _journey()
    with pytest.raises(ValueError):
        make_physical_replayable_event(
            event_id=EventId("old-schema-start"),
            run_id="run-regional",
            world_id=WorldId("world-regional"),
            tick=4,
            sequence=0,
            cause=ActionCause(RequestId("request-old"), journey.actor_body_id),
            resulting_revision=WorldRevision(4),
            details=JourneyStarted(journey, "move", 4.5, 13.5),
            occurrence=OccurrenceContext(origin_location_id=journey.origin_location_id),
            schema_version=EVENT_SCHEMA_REPLAY_V20,
        )


@pytest.mark.parametrize("reason", ["cancelled", "", 1, None])
def test_journey_end_decode_rejects_unknown_or_non_string_reason(
    reason: object,
) -> None:
    journey = _journey()
    event = _event(
        JourneyEnded(
            journey.journey_id,
            journey.participant_body_ids,
            journey.origin_location_id,
            journey.destination_location_id,
            "arrival_timeout",
        ),
        event_id="event-invalid-end",
        tick=8,
        sequence=0,
        origin=journey.origin_location_id,
    )
    payload = json.loads(encode_domain(event))
    payload["data"]["details"]["reason"] = reason
    with pytest.raises(DomainSerializationError) as exc:
        decode_domain(json.dumps(payload).encode("utf-8"))
    assert exc.value.path.endswith(".reason")
