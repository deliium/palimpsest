"""SimulationExport serialization contracts."""

from __future__ import annotations

from simulation.models import ExportMetadata, RunId, SimulationExport
from simulation.serialization import decode_domain, encode_domain
from world.events import Moved, Waited, make_replayable_event
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def test_export_round_trips_and_detaches_events() -> None:
    events = [
        make_replayable_event(
            event_id=EventId("evt-1"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=0,
            sequence=0,
            request_id=RequestId("r-1"),
            resulting_revision=WorldRevision(1),
            details=Waited(),
            actor_id=None,
        ),
        make_replayable_event(
            event_id=EventId("evt-2"),
            run_id="run-1",
            world_id=WorldId("world-1"),
            tick=0,
            sequence=1,
            request_id=RequestId("r-2"),
            resulting_revision=WorldRevision(1),
            details=Moved(EntityId("loc-1")),
            actor_id=EntityId("body-1"),
        ),
    ]
    export = SimulationExport(
        metadata=ExportMetadata(
            run_id=RunId("run-1"),
            seed=7,
            derivation_version="v1",
        ),
        events=events,
    )
    encoded = encode_domain(export)
    events.clear()
    decoded = decode_domain(encoded)
    assert isinstance(decoded, SimulationExport)
    assert decoded.metadata.seed == 7
    assert len(decoded.events) == 2
    assert decoded.events[0].details == Waited()
    assert decoded.events[1].details == Moved(EntityId("loc-1"))
    assert encode_domain(decoded) == encoded
