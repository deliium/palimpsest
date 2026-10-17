"""Replay/codec registration for neutral contact events (replay-v22 / v20)."""

from __future__ import annotations

import pytest

from simulation.persistence import checkpoint_schema_for_production
from simulation.serialization import decode_domain, encode_domain
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V21,
    EVENT_SCHEMA_REPLAY_V22,
    ContactRecorded,
    OccurrenceContext,
    WorldEvent,
    build_occurrence_context,
    event_is_replayable,
    make_physical_replayable_event,
    target_id_for_details,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _contact(*, relocation_kind: str = "journey_arrived") -> ContactRecorded:
    return ContactRecorded(
        relocation_kind=relocation_kind,  # type: ignore[arg-type]
        journey_id="journey-1" if relocation_kind == "journey_arrived" else None,
        location_id=EntityId("loc-b"),
        participant_ids=(EntityId("body-1"),),
        present_ids=(EntityId("body-2"),),
        origin_region_id="north",
        destination_region_id="south",
    )


def _event(
    details: ContactRecorded,
    *,
    schema_version: int = EVENT_SCHEMA_REPLAY_V22,
) -> WorldEvent:
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
        schema_version=schema_version,
    )


def test_contact_event_is_replayable_and_projects_as_noop() -> None:
    event = _event(_contact())
    assert event.schema_version == EVENT_SCHEMA_REPLAY_V22
    assert event_is_replayable(event) is True
    assert event.target_id is None
    assert target_id_for_details(event.details) is None
    assert event.occurrence == OccurrenceContext(
        destination_location_id=EntityId("loc-b"),
        affected_entity_ids=(EntityId("body-1"),),
    )


def test_contact_event_round_trips_through_domain_codec() -> None:
    event = _event(_contact())
    decoded = decode_domain(encode_domain(event))
    assert decoded == event


def test_flee_contact_round_trips_without_journey_id() -> None:
    event = _event(_contact(relocation_kind="fled"))
    decoded = decode_domain(encode_domain(event))
    assert isinstance(decoded, WorldEvent)
    assert isinstance(decoded.details, ContactRecorded)
    assert decoded.details.journey_id is None
    assert decoded.details.relocation_kind == "fled"


def test_contact_rejects_pre_v22_schema() -> None:
    with pytest.raises(ValueError, match="invalid_event_schema_version"):
        _event(_contact(), schema_version=EVENT_SCHEMA_REPLAY_V21)


def test_contact_decode_rejects_pre_v22_schema() -> None:
    event = _event(_contact())
    payload = encode_domain(event)
    import json

    document = json.loads(payload)
    document["schema_version"] = EVENT_SCHEMA_REPLAY_V21
    with pytest.raises((ValueError, RuntimeError)):
        decode_domain(json.dumps(document).encode("utf-8"))


def test_checkpoint_pair_v20_v22_only_when_contact_active() -> None:
    assert checkpoint_schema_for_production(
        production_active=False,
        dynamics_active=False,
        regions_migration_active=True,
        cultural_contact_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V22, "v20")
    assert checkpoint_schema_for_production(
        production_active=False,
        dynamics_active=False,
        regions_migration_active=True,
        cultural_contact_active=False,
    ) == (EVENT_SCHEMA_REPLAY_V21, "v19")
