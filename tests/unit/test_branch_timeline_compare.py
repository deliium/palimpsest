"""Unit proofs for detached branch timeline comparison."""

from __future__ import annotations

import pytest

from simulation.branch_compare import JournalBranchCompare, compare_branch_timelines
from simulation.branching import BranchTimelineCompareRequest
from simulation.clock import Tick
from simulation.models import RunId
from world.events import Waited, WorldEvent, make_replayable_event
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def _event(
    *,
    run_id: str,
    tick: int,
    sequence: int,
    event_id: str,
    request_id: str | None = None,
) -> WorldEvent:
    return make_replayable_event(
        event_id=EventId(event_id),
        run_id=run_id,
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        request_id=RequestId(request_id or f"req-{event_id}"),
        resulting_revision=WorldRevision(tick),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )


class _FakeJournal:
    def __init__(self, events: dict[str, tuple[WorldEvent, ...]]) -> None:
        self._events = events

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        _ = from_tick, to_tick, limit, offset
        return self._events.get(run_id.value, ())


@pytest.mark.asyncio
async def test_identical_streams_no_divergence() -> None:
    left = (
        _event(run_id="left", tick=0, sequence=0, event_id="e0"),
        _event(run_id="left", tick=1, sequence=0, event_id="e1"),
        _event(run_id="left", tick=2, sequence=0, event_id="e2"),
    )
    right = (
        _event(run_id="right", tick=0, sequence=0, event_id="e0"),
        _event(run_id="right", tick=1, sequence=0, event_id="e1"),
        _event(run_id="right", tick=2, sequence=0, event_id="e2"),
    )
    journal = _FakeJournal({"left": left, "right": right})
    result = await compare_branch_timelines(
        BranchTimelineCompareRequest(
            left_run_id=RunId("left"),
            right_run_id=RunId("right"),
            fork_tick=2,
            include_event_kind_counts=True,
        ),
        journal=journal,
    )
    assert result.prefix_equivalent is True
    assert result.diverge_tick is None
    assert result.reason_code is None
    assert (
        result.left_post_fork_trajectory_hash
        == result.right_post_fork_trajectory_hash
    )
    assert result.event_kind_counts is not None


@pytest.mark.asyncio
async def test_post_fork_divergence_reported() -> None:
    left = (
        _event(run_id="left", tick=0, sequence=0, event_id="e0"),
        _event(run_id="left", tick=2, sequence=0, event_id="e2"),
    )
    right = (
        _event(run_id="right", tick=0, sequence=0, event_id="e0"),
        _event(run_id="right", tick=2, sequence=0, event_id="e2a"),
        _event(run_id="right", tick=2, sequence=1, event_id="e2b"),
    )
    # Make post-fork payloads differ by sequence count.
    journal = _FakeJournal({"left": left, "right": right})
    compare = JournalBranchCompare(journal=journal)
    result = await compare.compare(
        BranchTimelineCompareRequest(
            left_run_id=RunId("left"),
            right_run_id=RunId("right"),
            fork_tick=1,
        )
    )
    assert result.prefix_equivalent is True
    assert result.diverge_tick == 2
    assert result.reason_code == "post_fork_payload_mismatch"
    assert (
        result.left_post_fork_trajectory_hash
        != result.right_post_fork_trajectory_hash
    )
