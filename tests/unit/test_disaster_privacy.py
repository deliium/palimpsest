# mypy: ignore-errors

"""Disaster receipts stay private across observer, perception, and journal."""

from __future__ import annotations

import pytest

from observer.adapt import (
    HIDDEN_OBSERVER_EVENT_TYPES,
    adapt_event,
    is_hidden_observer_event,
)
from simulation.journal import (
    hash_tick_events,
)
from world.disasters import DisasterKind, DisasterOrigin
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V26,
    DisasterOutcome,
    DisasterResolved,
    DisasterResourceTargetView,
    DisasterStockEffectRecord,
    Waited,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_RES = EntityId("res-food")
_BODY = EntityId("body-1")
_RUN = "run-privacy"
_WORLD = WorldId("world-privacy")


def _wait(event_id: str, *, tick: int, sequence: int) -> WorldEvent:
    details = Waited()
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=_RUN,
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        cause=SystemCause(
            RequestId(f"req-{event_id}"),
            SystemEffectFamily.LIFECYCLE,
            _BODY,
            sequence,
        ),
        resulting_revision=WorldRevision(tick + 1),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId("loc-camp")
        ),
    )


def _disaster(event_id: str, *, tick: int, sequence: int) -> WorldEvent:
    details = DisasterResolved(
        rule_id="fire-a",
        disaster_kind=DisasterKind.FIRE,
        origin=DisasterOrigin.SCHEDULED,
        target=DisasterResourceTargetView(resource_id=_RES),
        outcome=DisasterOutcome.APPLIED,
        effect=DisasterStockEffectRecord(
            quantity_before_tenths=40,
            quantity_after_tenths=30,
            damage_before_tenths=0,
            damage_after_tenths=0,
        ),
    )
    return WorldEvent(
        event_id=EventId(event_id),
        run_id=_RUN,
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"sys-{event_id}"),
        resulting_revision=WorldRevision(tick + 1),
        schema_version=EVENT_SCHEMA_REPLAY_V26,
        details=details,
        actor_id=None,
        target_id=_RES,
        cause=SystemCause(
            RequestId(f"sys-{event_id}"),
            SystemEffectFamily.DISASTER,
            _RES,
            sequence,
        ),
        occurrence=build_occurrence_context(details, origin_location_id=None),
    )


def test_disaster_resolved_is_hidden_observer_kind() -> None:
    assert "disaster_resolved" in HIDDEN_OBSERVER_EVENT_TYPES
    event = _disaster("evt-d1", tick=1, sequence=0)
    assert is_hidden_observer_event(event)
    with pytest.raises(ValueError, match="observer_event_not_found"):
        adapt_event(event)


def test_journal_still_hashes_hidden_disaster_rows() -> None:
    from simulation.journal import hash_tick_payload

    visible = _wait("evt-w1", tick=1, sequence=0)
    hidden = _disaster("evt-d1", tick=1, sequence=1)
    hashes = hash_tick_events((visible, hidden))
    assert len(hashes) == 2
    digest = hash_tick_payload((visible, hidden))
    assert len(digest.value) == 64


def test_perception_suppresses_disaster_resolved() -> None:
    from world._perception import _project_event_window

    visible = _wait("evt-w1", tick=1, sequence=0)
    hidden = _disaster("evt-d1", tick=1, sequence=1)
    occurrences, _communications = _project_event_window(
        observer_id=_BODY,
        location_id=EntityId("loc-camp"),
        content_visible=True,
        prior_events=(visible, hidden),
    )
    assert len(occurrences) == 1
    assert all(row.kind != "disaster_resolved" for row in occurrences)
