"""Observer journal stream backpressure: slow subscriber must not block siblings."""

from __future__ import annotations

import asyncio

import pytest

from api.routes.observer_stream import ObserverStreamConfig, ObserverStreamSession

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_observer_stream_slow_consumer_isolates_from_sibling(
    database_resources: object,
) -> None:
    """Mirrors control-stream backpressure: one slow queue disconnects; peer continues.

    Uses synthetic journal readers (same session class as the WS route) so the
    proof stays independent of WorldEngine commit timing while still running
    under the integration + disposable-DB gate.
    """
    del database_resources
    journal = [
        {"tick": index, "sequence": 0, "event_id": f"evt-{index}"} for index in range(24)
    ]
    producer_progress = {"reads": 0}

    async def read_events(
        after_tick: int, after_sequence: int, limit: int
    ) -> tuple[object, ...]:
        producer_progress["reads"] += 1
        selected = [
            event
            for event in journal
            if (int(event["tick"]), int(event["sequence"]))
            > (after_tick, after_sequence)
        ]
        return tuple(selected[:limit])

    async def head() -> int:
        return 23

    async def done() -> bool:
        return False

    slow = ObserverStreamSession(
        read_events=read_events, head_tick=head, completed=done
    )
    healthy = ObserverStreamSession(
        read_events=read_events, head_tick=head, completed=done
    )

    async def drain_slow() -> int:
        count = 0
        async for _item in slow.subscribe(
            ObserverStreamConfig(
                run_id="obs-bp-slow",
                after_tick=0,
                after_sequence=-1,
                queue_size=1,
                catchup_batch_size=8,
                heartbeat_seconds=30.0,
                poll_seconds=0.01,
                hello={"kind": "hello"},
                head_tick=0,
            )
        ):
            count += 1
            await asyncio.sleep(0.04)
        return count

    async def drain_healthy() -> int:
        events = 0
        async for item in healthy.subscribe(
            ObserverStreamConfig(
                run_id="obs-bp-ok",
                after_tick=0,
                after_sequence=-1,
                queue_size=32,
                catchup_batch_size=8,
                heartbeat_seconds=30.0,
                poll_seconds=0.01,
                hello={"kind": "hello"},
                head_tick=0,
            )
        ):
            if item.get("kind") == "event":
                events += 1
            if events >= 24:
                break
        return events

    slow_count, healthy_events = await asyncio.gather(drain_slow(), drain_healthy())
    assert slow_count < 24
    assert healthy_events == 24
    assert producer_progress["reads"] >= 2
