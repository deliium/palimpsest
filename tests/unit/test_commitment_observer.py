"""Observer labels a declaration without changing the protocol id."""

from __future__ import annotations

from observer.adapt import adapt_event
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V17,
    CommitmentDeclared,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def test_declaration_exports_commitment_declared_and_protocol_stays() -> None:
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert len(SEMANTIC_EVENT_TYPES) == 66
    assert SEMANTIC_EVENT_TYPES[-9] == "COMMITMENT_DECLARED"
    event = make_physical_replayable_event(
        event_id=EventId("evt-declare"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=ActionCause(RequestId("req-declare"), EntityId("body-a")),
        resulting_revision=WorldRevision(0),
        details=CommitmentDeclared(
            EntityId("body-a"),
            EntityId("body-b"),
            "promise",
            "propose",
            "self",
            "none",
            1,
            "none",
            "material",
            None,
            None,
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V17,
    )
    exported = adapt_event(event)
    assert exported.type == "COMMITMENT_DECLARED"
