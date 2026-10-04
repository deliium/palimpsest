"""Observer/scale benchmark scenarios required by the long-experiment plan.

Scenarios (deterministic fake cognition, disposable DB):
1. live observation while simulation runs (catch-up pages during/after run)
2. viewer paused far behind live (buffer discard + catch-up)
3. jumping mid-horizon ticks (snapshot-assisted seek)
4. reconnect after many missed events (sequence resume)
5. multiple read-only observers (one slow, others healthy)
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from api.routes.observer_stream import ObserverStreamConfig, ObserverStreamSession
from infrastructure.database import DatabaseResources
from persistence import create_tick_journal_repository
from simulation.runner import SimulationRunner
from tests.benchmarks.harness import (
    build_scale_config,
    durable_factories,
    measure_observer_catchup_ms,
    measure_seek_ms,
    run_durable_scale_scenario,
    unique_run_id,
)

_LOG = logging.getLogger("scale.bench")

pytestmark = [pytest.mark.integration, pytest.mark.scale]

_SCENARIO_TICKS = 200
_CHECKPOINT_CADENCE = 50


@pytest.mark.asyncio
async def test_scale_live_observation_and_runner_progress(
    database_resources: DatabaseResources,
) -> None:
    metrics = await run_durable_scale_scenario(
        database_resources,
        scenario="live_observation",
        max_ticks=_SCENARIO_TICKS,
        checkpoint_cadence=_CHECKPOINT_CADENCE,
    )
    assert metrics.ticks == _SCENARIO_TICKS
    assert metrics.catchup_ms >= 0.0
    _LOG.info(
        "[scale.bench] scenario_complete name=%s passed=%s",
        "live_observation",
        True,
    )


@pytest.mark.asyncio
async def test_scale_behind_live_catchup_and_seek(
    database_resources: DatabaseResources,
) -> None:
    metrics = await run_durable_scale_scenario(
        database_resources,
        scenario="behind_live_catchup",
        max_ticks=_SCENARIO_TICKS,
        checkpoint_cadence=_CHECKPOINT_CADENCE,
    )
    assert metrics.catchup_ms >= 0.0
    assert metrics.seek_ms >= 0.0
    assert metrics.snapshots >= _SCENARIO_TICKS // _CHECKPOINT_CADENCE
    _LOG.info(
        "[scale.bench] scenario_complete name=%s passed=%s",
        "behind_live_catchup",
        True,
    )


@pytest.mark.asyncio
async def test_scale_snapshot_seek_and_reconnect_catchup(
    database_resources: DatabaseResources,
) -> None:
    session_factory = database_resources.session_factory
    run_id = unique_run_id("seek-reconnect")
    config = build_scale_config(
        max_ticks=_SCENARIO_TICKS, checkpoint_cadence=_CHECKPOINT_CADENCE
    )
    async with await SimulationRunner.from_config(
        config,
        run_id=run_id,
        factories=durable_factories(session_factory),
    ) as runner:
        result = await runner.run()
    assert result.ticks_committed == _SCENARIO_TICKS

    mid = _SCENARIO_TICKS // 2
    seek_ms = await measure_seek_ms(session_factory, run_id, target_tick=mid)
    catchup_ms = await measure_observer_catchup_ms(
        session_factory, run_id, page_size=25
    )
    assert seek_ms >= 0.0
    assert catchup_ms >= 0.0

    journal = create_tick_journal_repository(session_factory)
    first = await journal.list_events_keyset(
        run_id, after_tick=0, after_sequence=-1, to_tick=None, limit=10
    )
    assert first
    last = first[-1]
    resumed = await journal.list_events_keyset(
        run_id,
        after_tick=last.tick,
        after_sequence=last.sequence,
        to_tick=None,
        limit=10,
    )
    assert all(
        (event.tick, event.sequence) > (last.tick, last.sequence) for event in resumed
    )
    _LOG.info(
        "[scale.bench] scenario_complete name=%s passed=%s",
        "snapshot_seek_reconnect",
        True,
    )


@pytest.mark.asyncio
async def test_scale_multi_observer_slow_consumer_isolation(
    database_resources: DatabaseResources,
) -> None:
    del database_resources
    journal = [
        {"tick": index, "sequence": 0, "event_id": f"evt-{index}"} for index in range(40)
    ]

    async def read_events(
        after_tick: int, after_sequence: int, limit: int
    ) -> tuple[object, ...]:
        selected = [
            event
            for event in journal
            if (int(event["tick"]), int(event["sequence"]))
            > (after_tick, after_sequence)
        ]
        return tuple(selected[:limit])

    async def head() -> int:
        return 39

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
                run_id="scale-slow",
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
            await asyncio.sleep(0.03)
        return count

    async def drain_healthy() -> int:
        events = 0
        async for item in healthy.subscribe(
            ObserverStreamConfig(
                run_id="scale-ok",
                after_tick=0,
                after_sequence=-1,
                queue_size=64,
                catchup_batch_size=8,
                heartbeat_seconds=30.0,
                poll_seconds=0.01,
                hello={"kind": "hello"},
                head_tick=0,
            )
        ):
            if item.get("kind") == "event":
                events += 1
            if events >= 40:
                break
        return events

    slow_count, healthy_events = await asyncio.gather(drain_slow(), drain_healthy())
    assert slow_count < 40
    assert healthy_events == 40
    _LOG.info(
        "[scale.bench] scenario_complete name=%s passed=%s",
        "multi_observer_isolation",
        True,
    )
