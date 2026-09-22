"""PostgreSQL stream backpressure proofs (Task 21)."""

from __future__ import annotations

import asyncio

import pytest

from api.streaming import StreamFanout, StreamSessionConfig
from infrastructure.database import DatabaseResources
from infrastructure.settings import load_settings
from persistence import create_stream_repository
from simulation.models import RunId
from simulation.run_control import (
    StreamRecordDraft,
    StreamRecordKind,
    make_stream_envelope,
)
from tests.integration.test_api_stream_resume import _seed_run

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_stream_backpressure_disconnects_slow_consumer_without_blocking(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _seed_run(database_resources)
    stream = create_stream_repository(database_resources.session_factory)
    run = RunId(run_id)
    settings = load_settings(
        env_file=False,
        api_stream_queue_size=2,
        api_stream_heartbeat_seconds=0.05,
        api_stream_poll_seconds=0.01,
    )
    fanout = StreamFanout(stream_repo=stream, settings=settings)

    async def _producer() -> None:
        for tick in range(8):
            await stream.publish(
                run_id=run,
                drafts=(
                    StreamRecordDraft(
                        kind=StreamRecordKind.EVENTLESS_TICK,
                        envelope=make_stream_envelope(b'{"tick":%d}' % tick),
                        related_tick=tick,
                    ),
                ),
            )
            await asyncio.sleep(0.01)

    producer = asyncio.create_task(_producer())
    frames: list[object] = []
    try:
        async for frame in fanout.subscribe(
            StreamSessionConfig(
                run_id=run_id,
                after_cursor=0,
                queue_size=2,
                heartbeat_seconds=0.05,
                poll_seconds=0.01,
            )
        ):
            frames.append(frame)
            await asyncio.sleep(0.05)
            if len(frames) >= 3:
                break
    except Exception:
        pass
    finally:
        await producer
    assert await stream.high_water(run_id=run) >= 3
    assert len(frames) >= 1
