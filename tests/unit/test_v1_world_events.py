"""Immutable closed world events and transition correlation."""

from __future__ import annotations

import pytest

from world._transitions import TransitionResult, require_transition_events
from world.actions import TransitionOutcome
from world.events import Moved, Waited, make_replayable_event, normalize_events
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)


def test_event_details_are_closed_and_correlated() -> None:
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=Moved(EntityId("loc-1")),
        actor_id=EntityId("body-1"),
    )
    assert event.details.kind == "move"
    assert normalize_events([event]) == (event,)
    with pytest.raises(ValueError, match="duplicate event_id"):
        normalize_events([event, event])


def test_transition_result_rejects_mismatched_events() -> None:
    from world._state import WorldState

    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("r-1"),
        resulting_revision=WorldRevision(2),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    result = TransitionResult(
        base_revision=WorldRevision(1),
        resulting_revision=WorldRevision(2),
        outcome=TransitionOutcome.APPLIED,
        events=(event,),
        resulting_state=WorldState(WorldRevision(2)),
    )
    assert result.events[0].details == Waited()
    with pytest.raises(ValueError, match="request_id mismatch"):
        require_transition_events(
            world_id=WorldId("world-1"),
            request_id=RequestId("other"),
            resulting_revision=WorldRevision(2),
            events=(event,),
        )
