"""Resumable WebSocket streaming from the durable run stream/outbox.

The durable cursor is the sole replayable source. Polling (and optional
LISTEN/NOTIFY wake-up) only wakes catch-up; they are never authoritative.
"""

from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Final

from api.errors import bad_request, conflict
from api.schemas import STREAM_ENVELOPE_VERSION, StreamEnvelopeOut, StreamFrameKind
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.models import RunId
from simulation.persistence import StreamRepository
from simulation.run_control import StreamRecord, StreamRecordKind

_LOGGER = get_logger("api.streaming")
_KIND_MAP: Final[dict[StreamRecordKind, StreamFrameKind]] = {
    StreamRecordKind.STATUS: StreamFrameKind.STATUS,
    StreamRecordKind.EVENTLESS_TICK: StreamFrameKind.EVENTLESS_TICK,
    StreamRecordKind.EVENT: StreamFrameKind.EVENT,
    StreamRecordKind.METRIC: StreamFrameKind.METRIC,
    StreamRecordKind.RESULT: StreamFrameKind.RESULT,
    StreamRecordKind.RECOVERABLE_ERROR: StreamFrameKind.ERROR,
    StreamRecordKind.COMPLETION: StreamFrameKind.COMPLETION,
}
STREAM_CHANNEL_PREFIX: Final[str] = "palimpsest_stream_"


@dataclass(frozen=True, slots=True)
class StreamSessionConfig:
    run_id: str
    after_cursor: int
    queue_size: int
    heartbeat_seconds: float
    poll_seconds: float
    page_size: int = 100


class SlowConsumerError(RuntimeError):
    """Subscriber queue overflow — disconnect without blocking simulation."""

    def __init__(self) -> None:
        super().__init__("slow_consumer")
        self.code = "slow_consumer"


def stream_record_to_envelope(
    record: StreamRecord, *, high_water: int | None = None
) -> StreamEnvelopeOut:
    kind = _KIND_MAP[record.kind]
    return StreamEnvelopeOut(
        envelope_version=STREAM_ENVELOPE_VERSION,
        run_id=record.run_id.value,
        cursor=record.cursor,
        kind=kind,
        related_tick=record.related_tick,
        content_hash_prefix=record.envelope.content_hash[:12],
        payload_b64=base64.b64encode(record.envelope.payload).decode("ascii"),
        high_water=high_water,
    )


def heartbeat_envelope(
    *, run_id: str, cursor: int, high_water: int
) -> StreamEnvelopeOut:
    return StreamEnvelopeOut(
        envelope_version=STREAM_ENVELOPE_VERSION,
        run_id=run_id,
        cursor=cursor,
        kind=StreamFrameKind.HEARTBEAT,
        high_water=high_water,
    )


class StreamFanout:
    """Non-blocking per-subscriber queues over durable catch-up + live tail."""

    def __init__(
        self,
        *,
        stream_repo: StreamRepository,
        settings: Settings,
        wake: asyncio.Event | None = None,
    ) -> None:
        self._stream_repo = stream_repo
        self._settings = settings
        self._wake = wake or asyncio.Event()
        self._closed = False

    def notify(self) -> None:
        self._wake.set()

    def close(self) -> None:
        self._closed = True
        self._wake.set()

    async def subscribe(
        self, config: StreamSessionConfig
    ) -> AsyncIterator[StreamEnvelopeOut]:
        if config.after_cursor < 0:
            raise bad_request(code="invalid_cursor", run_id=config.run_id)
        run_id = RunId(config.run_id)
        queue: asyncio.Queue[StreamEnvelopeOut | None] = asyncio.Queue(
            maxsize=config.queue_size
        )
        connection_id = f"ws-{int(time.time() * 1000) % 1_000_000_000}"
        _LOGGER.info(
            "stream_session_accepted",
            run_id=config.run_id,
            connection_id=connection_id,
            cursor=config.after_cursor,
        )

        async def _producer() -> None:
            cursor = config.after_cursor
            try:
                # Catch-up to durable high-water before live handoff.
                while not self._closed:
                    high_water = await self._stream_repo.high_water(run_id=run_id)
                    if cursor >= high_water:
                        break
                    batch = await self._stream_repo.read_after(
                        run_id=run_id,
                        after_cursor=cursor,
                        limit=config.page_size,
                    )
                    if not batch:
                        break
                    for record in batch:
                        envelope = stream_record_to_envelope(
                            record, high_water=high_water
                        )
                        await _offer(queue, envelope)
                        cursor = record.cursor
                        if record.kind is StreamRecordKind.COMPLETION:
                            await _offer(queue, None)
                            return
                    _LOGGER.debug(
                        "stream_catchup_page",
                        run_id=config.run_id,
                        connection_id=connection_id,
                        cursor=cursor,
                        high_water=high_water,
                        count=len(batch),
                    )

                _LOGGER.debug(
                    "stream_live_handoff",
                    run_id=config.run_id,
                    connection_id=connection_id,
                    cursor=cursor,
                )
                last_heartbeat = time.monotonic()
                while not self._closed:
                    high_water = await self._stream_repo.high_water(run_id=run_id)
                    if cursor < high_water:
                        batch = await self._stream_repo.read_after(
                            run_id=run_id,
                            after_cursor=cursor,
                            limit=config.page_size,
                        )
                        for record in batch:
                            envelope = stream_record_to_envelope(
                                record, high_water=high_water
                            )
                            await _offer(queue, envelope)
                            cursor = record.cursor
                            if record.kind is StreamRecordKind.COMPLETION:
                                await _offer(queue, None)
                                return
                    now = time.monotonic()
                    if now - last_heartbeat >= config.heartbeat_seconds:
                        await _offer(
                            queue,
                            heartbeat_envelope(
                                run_id=config.run_id,
                                cursor=cursor,
                                high_water=high_water,
                            ),
                        )
                        last_heartbeat = now
                    self._wake.clear()
                    try:
                        await asyncio.wait_for(
                            self._wake.wait(), timeout=config.poll_seconds
                        )
                    except TimeoutError:
                        continue
            except SlowConsumerError:
                _LOGGER.warning(
                    "stream_slow_consumer",
                    run_id=config.run_id,
                    connection_id=connection_id,
                    cursor=cursor,
                    reason_code="slow_consumer",
                )
                # Ensure the consumer unblocks even when the queue is full.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
            except Exception:
                _LOGGER.error(
                    "stream_producer_failed",
                    run_id=config.run_id,
                    connection_id=connection_id,
                    reason_code="stream_producer_failed",
                )
                await _offer(queue, None)

        task = asyncio.create_task(
            _producer(), name=f"stream-{config.run_id}-{connection_id}"
        )
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            _LOGGER.info(
                "stream_session_closed",
                run_id=config.run_id,
                connection_id=connection_id,
            )


async def _offer(
    queue: asyncio.Queue[StreamEnvelopeOut | None], item: StreamEnvelopeOut | None
) -> None:
    if item is None:
        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        return
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull as exc:
        raise SlowConsumerError() from exc


def validate_after_cursor(after_cursor: int, *, high_water: int) -> None:
    """Reject cursors beyond durable high-water (except equal for live tail)."""
    if after_cursor < 0:
        raise bad_request(code="invalid_cursor")
    if after_cursor > high_water:
        raise conflict(code="cursor_ahead_of_high_water")
