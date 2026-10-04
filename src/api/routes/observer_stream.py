"""Live observer WebSocket. Polls the ordered event journal, not StreamFanout."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.errors import ApiError
from api.observer_service import ObserverReadService
from api.security import ApiCapability, require_websocket_capability
from api.streaming import SlowConsumerError
from infrastructure.logging import get_logger
from observer.adapt import adapt_event
from observer.version import DEFAULT_LAYOUT_ID
from simulation.models import RunId
from simulation.replay import ReplayService

router = APIRouter(tags=["observer"])
_LOGGER = get_logger("api.routes.observer_stream")

EventReader = Callable[[int, int, int], Awaitable[tuple[object, ...]]]
HeadReader = Callable[[], Awaitable[int]]
DoneReader = Callable[[], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class ObserverStreamConfig:
    run_id: str
    after_tick: int
    after_sequence: int
    queue_size: int
    catchup_batch_size: int
    heartbeat_seconds: float
    poll_seconds: float
    hello: Mapping[str, object]
    head_tick: int


class ObserverStreamSession:
    """Server-push session. A full queue disconnects the subscriber."""

    def __init__(
        self,
        *,
        read_events: EventReader,
        head_tick: HeadReader,
        completed: DoneReader,
    ) -> None:
        self._read_events = read_events
        self._head_tick = head_tick
        self._completed = completed
        self._closed = False

    async def subscribe(
        self, config: ObserverStreamConfig
    ) -> AsyncIterator[dict[str, object]]:
        self._closed = False
        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue(
            maxsize=config.queue_size
        )
        cursor = (config.after_tick, config.after_sequence)
        _LOGGER.info(
            "observer_stream_open",
            run_id=config.run_id,
            after_tick=config.after_tick,
            after_sequence=config.after_sequence,
        )

        async def _producer() -> None:
            nonlocal cursor
            last_head = config.head_tick
            last_heartbeat = time.monotonic()
            try:
                await _offer(queue, config.hello)
                while not self._closed:
                    batch = await self._read_events(
                        cursor[0], cursor[1], config.catchup_batch_size
                    )
                    if batch:
                        _LOGGER.debug(
                            "[api.observer_stream] catchup_batch run_id=%s "
                            "count=%s queue_size=%s",
                            config.run_id,
                            len(batch),
                            queue.qsize(),
                        )
                    for raw in batch:
                        mapping = _event_mapping(raw)
                        pair = _cursor_pair(mapping)
                        if pair <= cursor:
                            continue
                        await _offer(
                            queue,
                            {
                                "kind": "event",
                                "run_id": config.run_id,
                                "event": mapping,
                            },
                        )
                        cursor = pair
                    head = await self._head_tick()
                    if head != last_head:
                        await _offer(
                            queue,
                            {
                                "kind": "tick",
                                "run_id": config.run_id,
                                "tick": head,
                                "after_tick": cursor[0],
                                "after_sequence": cursor[1],
                            },
                        )
                        last_head = head
                    if await self._completed():
                        await _offer(
                            queue,
                            {
                                "kind": "completion",
                                "run_id": config.run_id,
                                "after_tick": cursor[0],
                                "after_sequence": cursor[1],
                            },
                        )
                        await _offer(queue, None)
                        return
                    now = time.monotonic()
                    if now - last_heartbeat >= config.heartbeat_seconds:
                        await _offer(
                            queue,
                            {
                                "kind": "heartbeat",
                                "run_id": config.run_id,
                                "after_tick": cursor[0],
                                "after_sequence": cursor[1],
                            },
                        )
                        last_heartbeat = now
                    await asyncio.sleep(config.poll_seconds)
            except SlowConsumerError:
                _LOGGER.warning(
                    "observer_stream_slow_consumer",
                    run_id=config.run_id,
                    reason_code="slow_consumer",
                )
                await _offer(queue, None)
            except Exception:
                _LOGGER.error(
                    "observer_stream_failed",
                    run_id=config.run_id,
                    reason_code="observer_stream_failed",
                )
                await _offer(queue, None)

        def reject_client_message() -> None:
            _LOGGER.warning(
                "observer_stream_rejected reason_code=client_mutation_rejected",
                run_id=config.run_id,
                reason_code="client_mutation_rejected",
            )
            try:
                queue.put_nowait(
                    {
                        "kind": "rejected",
                        "run_id": config.run_id,
                        "reason_code": "client_mutation_rejected",
                    }
                )
            except asyncio.QueueFull as exc:
                raise SlowConsumerError() from exc

        self.reject_client_message = reject_client_message
        task = asyncio.create_task(_producer(), name=f"observer-stream-{config.run_id}")
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
                if item.get("kind") == "completion":
                    break
        finally:
            self._closed = True
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            _LOGGER.info(
                "observer_stream_disconnect",
                run_id=config.run_id,
                after_tick=cursor[0],
                after_sequence=cursor[1],
            )


async def _offer(
    queue: asyncio.Queue[dict[str, object] | None],
    item: Mapping[str, object] | None,
) -> None:
    if item is None:
        await queue.put(None)
        return
    payload = dict(item)
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull as exc:
        raise SlowConsumerError() from exc


def _event_mapping(raw: object) -> Mapping[str, object]:
    if isinstance(raw, dict):
        return cast(Mapping[str, object], raw)
    public_mapping = getattr(raw, "public_mapping", None)
    if not callable(public_mapping):
        raise TypeError("observer_stream_event")
    mapping = public_mapping()
    if not isinstance(mapping, dict):
        raise TypeError("observer_stream_event")
    return cast(Mapping[str, object], mapping)


def _cursor_pair(mapping: Mapping[str, object]) -> tuple[int, int]:
    return (int(cast(int, mapping["tick"])), int(cast(int, mapping["sequence"])))


def events_strictly_after(
    events: tuple[object, ...],
    *,
    after_tick: int,
    after_sequence: int,
) -> tuple[object, ...]:
    selected = []
    for event in events:
        mapping = _event_mapping(event)
        if _cursor_pair(mapping) > (
            after_tick,
            after_sequence,
        ):
            selected.append(event)
    return tuple(selected)


@router.websocket("/v1/simulations/{run_id}/observer/stream")
async def observer_stream(websocket: WebSocket, run_id: str) -> None:
    settings = websocket.app.state.settings
    try:
        accepted = require_websocket_capability(
            websocket,
            settings,
            capability=ApiCapability.OBJECTIVE_INSPECTION,
        )
    except ApiError as exc:
        _LOGGER.warning(
            "observer_stream_auth_rejected",
            run_id=run_id,
            reason_code=exc.code,
        )
        await websocket.close(code=4401)
        return
    raw_tick = websocket.query_params.get("after_tick")
    raw_sequence = websocket.query_params.get("after_sequence")
    if (raw_tick is None) != (raw_sequence is None):
        await websocket.close(code=4400)
        return
    after_tick = 0
    after_sequence = -1
    if raw_tick is not None and raw_sequence is not None:
        try:
            after_tick = int(raw_tick)
            after_sequence = int(raw_sequence)
        except ValueError:
            await websocket.close(code=4400)
            return
        if after_tick < 0 or after_sequence < 0:
            await websocket.close(code=4400)
            return
    service: ObserverReadService = websocket.app.state.observer_service
    replay: ReplayService = service.replay
    try:
        frame = await service.state(run_id, tick=None, layout_id=DEFAULT_LAYOUT_ID)
        manifest = await service.manifest(run_id, layout_id=DEFAULT_LAYOUT_ID)
    except ApiError as exc:
        await websocket.close(code=4404)
        _LOGGER.warning(
            "observer_stream_rejected",
            run_id=run_id,
            reason_code=exc.code,
        )
        return
    head_tick = frame.world.tick
    if raw_tick is None:
        after_tick = 0 if frame.cursor.after_tick is None else frame.cursor.after_tick
        after_sequence = (
            -1 if frame.cursor.after_sequence is None else frame.cursor.after_sequence
        )
    elif after_tick >= head_tick:
        await websocket.close(code=4409)
        return
    subprotocol = accepted[0] if accepted else None
    await websocket.accept(subprotocol=subprotocol)
    hello = {
        "kind": "hello",
        "run_id": run_id,
        "manifest": manifest.model_dump(mode="json"),
        "frame": frame.model_dump(mode="json"),
        "cursor": frame.cursor.model_dump(mode="json"),
    }

    async def read_events(
        cursor_tick: int, cursor_sequence: int, limit: int
    ) -> tuple[object, ...]:
        page = await replay.read_event_keyset_page(
            RunId(run_id),
            after_tick=cursor_tick,
            after_sequence=cursor_sequence,
            limit=limit,
        )
        adapted = tuple(adapt_event(event) for event in page.events)
        if adapted:
            _LOGGER.debug(
                "observer_stream_gap",
                run_id=run_id,
                after_tick=cursor_tick,
                after_sequence=cursor_sequence,
                to_tick=adapted[-1].tick,
                to_sequence=adapted[-1].sequence,
                event_count=len(adapted),
            )
        return adapted

    async def current_head() -> int:
        live = await service.state(run_id, tick=None, layout_id=DEFAULT_LAYOUT_ID)
        return live.world.tick

    async def completed() -> bool:
        record = getattr(websocket.app.state, "observer_run_completed", None)
        if record is None:
            return False
        return bool(record(run_id))

    session = ObserverStreamSession(
        read_events=read_events,
        head_tick=current_head,
        completed=completed,
    )
    config = ObserverStreamConfig(
        run_id=run_id,
        after_tick=after_tick,
        after_sequence=after_sequence,
        queue_size=settings.observer_stream_queue_size,
        catchup_batch_size=settings.observer_catchup_page_size,
        heartbeat_seconds=settings.api_stream_heartbeat_seconds,
        poll_seconds=settings.api_stream_poll_seconds,
        hello=hello,
        head_tick=head_tick,
    )
    sender = session.subscribe(config)

    async def _send() -> None:
        async for envelope in sender:
            await websocket.send_json(envelope)

    send_task = asyncio.create_task(_send())
    await asyncio.sleep(0)
    try:
        while not send_task.done():
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message["type"] == "websocket.receive":
                session.reject_client_message()
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass
