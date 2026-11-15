# mypy: ignore-errors
"""Ordering and cap invariants for disruption harvest."""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.economic_cascades_events import harvest_economic_cascade_disruptions
from analysis.economic_cascades_policy import policy_with
from world.effects import ActionCause, DeathCause
from world.events import Died, OccurrenceContext, WorldEvent, target_id_for_details
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)

_WORLD = WorldId("world-cascades-properties")


def _died(index: int, tick: int) -> WorldEvent:
    details = Died(EntityId(f"body-{index}"), DeathCause.COMBINED_NEEDS)
    return WorldEvent(
        event_id=EventId(f"evt-{index}"),
        run_id="run-cascades",
        world_id=_WORLD,
        tick=tick,
        sequence=index,
        request_id=RequestId(f"req-{index}"),
        resulting_revision=WorldRevision(tick),
        schema_version=27,
        details=details,
        actor_id=EntityId(f"body-{index}"),
        target_id=target_id_for_details(details),
        cause=ActionCause(
            RequestId(f"req-{index}"), EntityId(f"body-{index}")
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


@settings(max_examples=50, deadline=None)
@given(st.lists(st.integers(min_value=0, max_value=40), min_size=1, max_size=20))
def test_shuffled_input_is_order_independent(ticks: list[int]) -> None:
    events = [_died(index, tick) for index, tick in enumerate(ticks)]
    expected = harvest_economic_cascade_disruptions(events)
    shuffled = list(events)
    random.Random(7).shuffle(shuffled)
    assert harvest_economic_cascade_disruptions(shuffled) == expected


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=8))
def test_rows_never_exceed_the_cap(cap: int) -> None:
    events = [_died(index, index) for index in range(12)]
    result = harvest_economic_cascade_disruptions(
        events, policy=policy_with(max_disruptions=cap)
    )
    assert len(result.rows) <= cap
    assert result.rows == tuple(
        sorted(
            result.rows,
            key=lambda row: (
                row.window_index,
                row.kind.value,
                row.sequence,
                row.subject_token,
            ),
        )
    )
