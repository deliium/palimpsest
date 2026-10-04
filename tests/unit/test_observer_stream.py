"""Live observer socket polls the journal and rejects client writes."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import pytest
from starlette.types import Scope

from api.app import DisposableEngine, create_app
from api.observer_service import ObserverReadService
from api.routes.observer_stream import (
    ObserverStreamConfig,
    ObserverStreamSession,
    events_strictly_after,
)
from api.simulation_manager import SimulationManager
from infrastructure.settings import Settings, load_settings
from observer.adapt import adapt_event
from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.models import RunId
from tests.unit.test_observer_replay import RUN_ID, observer_replay_service

pytestmark = pytest.mark.unit


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = FakeEngine()


def _settings(**overrides: object) -> Settings:
    return load_settings(
        env_file=False,
        api_stream_heartbeat_seconds=30.0,
        api_stream_poll_seconds=0.01,
        api_stream_queue_size=8,
        **overrides,
    )


class _Session:
    def __init__(self) -> None:
        self._app_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._client_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.close_code: int | None = None

    async def receive(self) -> dict[str, Any]:
        return await self._app_queue.get()

    async def send(self, message: dict[str, Any]) -> None:
        await self._client_queue.put(message)

    async def connect(self) -> None:
        await self._app_queue.put({"type": "websocket.connect"})

    async def disconnect(self) -> None:
        await self._app_queue.put({"type": "websocket.disconnect", "code": 1000})

    async def send_text(self, text: str) -> None:
        await self._app_queue.put({"type": "websocket.receive", "text": text})

    async def next_payload(self) -> dict[str, Any]:
        while True:
            message = await asyncio.wait_for(self._client_queue.get(), timeout=2)
            if message["type"] == "websocket.accept":
                continue
            if message["type"] == "websocket.close":
                self.close_code = int(message.get("code", 1000))
                raise RuntimeError("websocket_closed")
            if message["type"] == "websocket.send":
                return json.loads(message["text"])


async def _open(
    app: Any, path: str, *, query: bytes = b"", subprotocols: list[str] | None = None
) -> tuple[_Session, asyncio.Task[None]]:
    session = _Session()
    scope: Scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "headers": [],
        "client": ("test", 50000),
        "server": ("test", 80),
        "subprotocols": subprotocols or ["palimpsest.v1"],
        "state": {},
        "extensions": {},
        "app": app,
    }

    task = asyncio.create_task(app(scope, session.receive, session.send))
    await session.connect()
    return session, task


def _app(settings: Settings | None = None) -> Any:
    resolved = settings or _settings()
    app = create_app(
        settings=resolved,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=resolved,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    service, _events = observer_replay_service()
    app.state.observer_service = ObserverReadService(service)
    app.state.observer_run_completed = lambda _run_id: False
    return app


@pytest.mark.asyncio
async def test_journal_tail_is_exclusive_and_ordered(
    capsys: pytest.CaptureFixture[str],
) -> None:
    service, events = observer_replay_service()
    replay = service

    async def read_events(
        after_tick: int, after_sequence: int, limit: int
    ) -> tuple[object, ...]:
        page = await replay.read_event_keyset_page(
            RunId(RUN_ID),
            after_tick=after_tick,
            after_sequence=after_sequence,
            limit=limit,
        )
        return tuple(adapt_event(event) for event in page.events)

    async def head() -> int:
        return 1

    async def done() -> bool:
        return True

    session = ObserverStreamSession(
        read_events=read_events, head_tick=head, completed=done
    )
    config = ObserverStreamConfig(
        run_id=RUN_ID,
        after_tick=0,
        after_sequence=-1,
        queue_size=8,
        catchup_batch_size=50,
        heartbeat_seconds=30.0,
        poll_seconds=0.01,
        hello={"kind": "hello"},
        head_tick=1,
    )
    envelopes = [item async for item in session.subscribe(config)]
    kinds = [item["kind"] for item in envelopes]
    assert kinds[0] == "hello"
    assert kinds[-1] == "completion"
    emitted = [
        item["event"]["event_id"] for item in envelopes if item["kind"] == "event"
    ]
    assert emitted == [event.event_id.value for event in events]
    resumed = ObserverStreamConfig(
        run_id=RUN_ID,
        after_tick=0,
        after_sequence=1,
        queue_size=8,
        catchup_batch_size=50,
        heartbeat_seconds=30.0,
        poll_seconds=0.01,
        hello={"kind": "hello"},
        head_tick=1,
    )
    again = [item async for item in session.subscribe(resumed)]
    assert [item["kind"] for item in again] == ["hello", "completion"]
    gap = events_strictly_after(
        tuple(adapt_event(event) for event in events),
        after_tick=0,
        after_sequence=0,
    )
    assert [item.event_id for item in gap] == ["evt-wait"]
    captured = capsys.readouterr()
    assert "observer_stream_open" in captured.out
    assert "observer_stream_disconnect" in captured.out


def test_stream_route_does_not_subscribe_to_fanout() -> None:
    from pathlib import Path

    source = Path("src/api/routes/observer_stream.py").read_text(encoding="utf-8")
    assert "StreamFanout(" not in source
    assert "import StreamFanout" not in source


@pytest.mark.asyncio
async def test_slow_consumer_disconnects_without_waiting() -> None:
    async def read_events(
        after_tick: int, after_sequence: int, limit: int
    ) -> tuple[object, ...]:
        del after_tick, after_sequence, limit
        return tuple(
            {"tick": index, "sequence": 0, "event_id": f"evt-{index}"}
            for index in range(30)
        )

    async def head() -> int:
        return 30

    async def done() -> bool:
        return False

    session = ObserverStreamSession(
        read_events=read_events, head_tick=head, completed=done
    )
    envelopes = []
    async for item in session.subscribe(
        ObserverStreamConfig(
            run_id=RUN_ID,
            after_tick=0,
            after_sequence=-1,
            queue_size=1,
            catchup_batch_size=50,
            heartbeat_seconds=30.0,
            poll_seconds=0.01,
            hello={"kind": "hello"},
            head_tick=0,
        )
    ):
        envelopes.append(item)
        await asyncio.sleep(0.02)
    assert len(envelopes) < 30


@pytest.mark.asyncio
async def test_slow_observer_does_not_block_sibling_subscriber(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One slow queue disconnects; a healthy sibling still drains to completion."""
    shared: list[dict[str, object]] = [
        {"tick": index, "sequence": 0, "event_id": f"evt-{index}"} for index in range(20)
    ]
    read_limits: list[int] = []

    async def read_events(
        after_tick: int, after_sequence: int, limit: int
    ) -> tuple[object, ...]:
        read_limits.append(limit)
        selected = [
            event
            for event in shared
            if (int(event["tick"]), int(event["sequence"]))
            > (after_tick, after_sequence)
        ]
        return tuple(selected[:limit])

    async def head() -> int:
        return 19

    async def done() -> bool:
        # Completion is driven by the producer once the journal is drained;
        # keep False so catch-up may span multiple batches.
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
                run_id=f"{RUN_ID}-slow",
                after_tick=0,
                after_sequence=-1,
                queue_size=1,
                catchup_batch_size=10,
                heartbeat_seconds=30.0,
                poll_seconds=0.01,
                hello={"kind": "hello"},
                head_tick=0,
            )
        ):
            count += 1
            await asyncio.sleep(0.05)
        return count

    async def drain_healthy() -> list[str]:
        kinds: list[str] = []
        async for item in healthy.subscribe(
            ObserverStreamConfig(
                run_id=f"{RUN_ID}-ok",
                after_tick=0,
                after_sequence=-1,
                queue_size=64,
                catchup_batch_size=10,
                heartbeat_seconds=30.0,
                poll_seconds=0.01,
                hello={"kind": "hello"},
                head_tick=0,
            )
        ):
            kinds.append(str(item["kind"]))
            if kinds.count("event") >= 20:
                break
        return kinds

    slow_count, healthy_kinds = await asyncio.gather(drain_slow(), drain_healthy())
    assert slow_count < 20
    assert healthy_kinds[0] == "hello"
    assert healthy_kinds.count("event") == 20
    assert 10 in read_limits
    captured = capsys.readouterr()
    assert "observer_stream_slow_consumer" in captured.out
    assert "catchup_batch" in captured.out


@pytest.mark.asyncio
async def test_client_text_is_rejected(caplog: pytest.LogCaptureFixture) -> None:
    app = _app()
    session, task = await _open(app, f"/v1/simulations/{RUN_ID}/observer/stream")
    try:
        with caplog.at_level(logging.WARNING):
            hello = await session.next_payload()
            assert hello["kind"] == "hello"
            assert "StreamFanout" not in hello
            await session.send_text('{"mutate": true}')
            rejected = await session.next_payload()
        assert rejected["kind"] == "rejected"
        assert rejected["reason_code"] == "client_mutation_rejected"
        assert "client_mutation_rejected" in caplog.text
    finally:
        await session.disconnect()
        try:
            await asyncio.wait_for(task, timeout=2)
        except (asyncio.CancelledError, Exception):
            task.cancel()


@pytest.mark.asyncio
async def test_ahead_cursor_and_missing_auth_close() -> None:
    app = _app()
    ahead, ahead_task = await _open(
        app,
        f"/v1/simulations/{RUN_ID}/observer/stream",
        query=b"after_tick=9&after_sequence=0",
    )
    with pytest.raises(RuntimeError, match="websocket_closed"):
        await ahead.next_payload()
    assert ahead.close_code == 4409
    ahead_task.cancel()

    locked = _app(
        _settings(
            api_auth_required=True,
            api_control_credential="a" * 32,
            api_inspection_credential="b" * 32,
            api_agent_visible_credential="c" * 32,
        )
    )
    denied, denied_task = await _open(
        locked,
        f"/v1/simulations/{RUN_ID}/observer/stream",
        subprotocols=[],
    )
    with pytest.raises(RuntimeError, match="websocket_closed"):
        await denied.next_payload()
    assert denied.close_code == 4401
    denied_task.cancel()
