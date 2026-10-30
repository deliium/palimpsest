"""Replay-v22 journal decoding: persistence and ORM-shaped round trips.

`simulation.journal._decode_world_event` is the single gate used by in-memory
persistence payloads and by `persistence.readers.event_from_orm`. It previously
stopped at `EVENT_SCHEMA_REPLAY_V21` while production already writes
`(EVENT_SCHEMA_REPLAY_V22, "v20")` for cultural-contact runs, so a database-backed
restore of those runs failed closed. These tests pin the widened window.

`simulation.journal.verify_tick_events` is deliberately not exercised: it keeps a
legacy V2-V5 window, has no production callers, and is not the decoder used by
persistence or replay.
"""

from __future__ import annotations

import json

import pytest

from persistence.orm import WorldEventOrm
from persistence.readers import (
    event_cause_payload,
    event_details_payload,
    event_from_orm,
    event_occurrence_payload,
)
from simulation.journal import (
    PersistenceSerializationError,
    decode_persistence,
    encode_persistence,
    hash_world_event,
)
from simulation.persistence import ACCEPTED_EVENT_SCHEMA_VERSIONS
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V21,
    EVENT_SCHEMA_REPLAY_V22,
    ContactRecorded,
    ProjectCompleted,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _contact_details(*, relocation_kind: str = "journey_arrived") -> ContactRecorded:
    return ContactRecorded(
        relocation_kind=relocation_kind,  # type: ignore[arg-type]
        journey_id="journey-1" if relocation_kind == "journey_arrived" else None,
        location_id=EntityId("loc-b"),
        participant_ids=(EntityId("body-1"),),
        present_ids=(EntityId("body-2"),),
        origin_region_id="north",
        destination_region_id="south",
    )


def _contact_event(*, schema_version: int = EVENT_SCHEMA_REPLAY_V22) -> WorldEvent:
    details = _contact_details()
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
            destination_location_id=EntityId("loc-b"),
        ),
        schema_version=schema_version,
    )


def _replay_v21_event() -> WorldEvent:
    return make_physical_replayable_event(
        event_id=EventId("event-project-v21"),
        run_id="run-project",
        world_id=WorldId("world-project"),
        tick=3,
        sequence=0,
        cause=ActionCause(RequestId("request-project"), EntityId("body-1")),
        resulting_revision=WorldRevision(3),
        details=ProjectCompleted(
            EntityId("project-1"),
            "well",
            EntityId("structure-1"),
            decay_millis=10,
        ),
        occurrence=build_occurrence_context(
            ProjectCompleted(
                EntityId("project-1"),
                "well",
                EntityId("structure-1"),
                decay_millis=10,
            ),
            origin_location_id=EntityId("loc-1"),
            destination_location_id=None,
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V21,
    )


def _orm_row(event: WorldEvent) -> WorldEventOrm:
    return WorldEventOrm(
        run_id=event.run_id,
        tick=event.tick,
        sequence=event.sequence,
        event_id=event.event_id.value,
        world_id=event.world_id.value,
        request_id=event.request_id.value,
        resulting_revision=event.resulting_revision.value,
        schema_version=event.schema_version,
        event_type=event.event_type,
        actor_id=None if event.actor_id is None else event.actor_id.value,
        target_id=None if event.target_id is None else event.target_id.value,
        details=event_details_payload(event),
        cause=event_cause_payload(event),
        occurrence=event_occurrence_payload(event),
        payload_hash=hash_world_event(event).value,
    )


def test_replay_v22_is_accepted_by_persistence_schemas() -> None:
    assert EVENT_SCHEMA_REPLAY_V22 == 22
    assert EVENT_SCHEMA_REPLAY_V22 in ACCEPTED_EVENT_SCHEMA_VERSIONS


def test_contact_event_round_trips_through_persistence_codec() -> None:
    event = _contact_event()
    assert decode_persistence(encode_persistence(event), WorldEvent) == event


def test_contact_event_rebuilds_from_orm_row() -> None:
    event = _contact_event()
    assert event_from_orm(_orm_row(event)) == event


def test_replay_v21_event_still_decodes() -> None:
    event = _replay_v21_event()
    assert event.schema_version == EVENT_SCHEMA_REPLAY_V21
    assert decode_persistence(encode_persistence(event), WorldEvent) == event


def test_replay_v23_event_is_rejected_as_unsupported() -> None:
    document = json.loads(encode_persistence(_contact_event()))
    document["data"]["schema_version"] = EVENT_SCHEMA_REPLAY_V22 + 1
    payload = json.dumps(document).encode("utf-8")
    with pytest.raises(PersistenceSerializationError) as excinfo:
        decode_persistence(payload, WorldEvent)
    assert excinfo.value.code == "unsupported_version"
    assert excinfo.value.path == "$.data.schema_version"
    assert excinfo.value.version == EVENT_SCHEMA_REPLAY_V22 + 1
