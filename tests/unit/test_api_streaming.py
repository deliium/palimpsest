"""Resumable WebSocket streaming from durable outbox."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterator
from typing import Any

import pytest
from starlette.types import Scope

from api.app import DisposableEngine, create_app
from api.schemas import StreamFrameKind
from api.simulation_manager import SimulationManager
from api.streaming import StreamFanout, StreamSessionConfig, stream_record_to_envelope
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings
from simulation.evidence import opaque_envelope_from_payload
from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.memory_scientific_evidence import (
    InMemoryScientificEvidenceRepository,
    InMemoryStreamRepository,
)
from simulation.models import RunId
from simulation.run_control import (
    STREAM_RECORD_SCHEMA_VERSION,
    StreamRecord,
    StreamRecordDraft,
    StreamRecordKind,
    make_stream_envelope,
)

pytestmark = pytest.mark.unit


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self) -> None:
        self.engine: DisposableEngine = FakeEngine()


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        yield
    finally:
        reset_logging_for_tests(original_handlers, original_level)


def _settings(**overrides: object) -> Settings:
    return load_settings(
        env_file=False,
        api_stream_heartbeat_seconds=0.05,
        api_stream_poll_seconds=0.01,
        api_stream_queue_size=8,
        **overrides,
    )


def _stream_repo() -> InMemoryStreamRepository:
    return InMemoryStreamRepository(InMemoryScientificEvidenceRepository())


async def _publish(
    repo: InMemoryStreamRepository, *, run_id: str, kind: StreamRecordKind, tick: int
) -> None:
    draft = StreamRecordDraft(
        kind=kind,
        envelope=make_stream_envelope(b'{"ok":true}'),
        related_tick=tick,
    )
    await repo.publish(run_id=RunId(run_id), drafts=(draft,))


class _AsgiWebSocketSession:
    """Minimal in-process ASGI WebSocket client (httpx lacks WebSockets)."""

    def __init__(self) -> None:
        self._app_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._client_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.accepted = False
        self.close_code: int | None = None

    async def receive(self) -> dict[str, Any]:
        return await self._app_queue.get()

    async def send(self, message: dict[str, Any]) -> None:
        await self._client_queue.put(message)

    async def client_connect(self) -> None:
        await self._app_queue.put({"type": "websocket.connect"})

    async def client_disconnect(self) -> None:
        await self._app_queue.put({"type": "websocket.disconnect", "code": 1000})

    async def receive_json(self) -> dict[str, Any]:
        while True:
            message = await self._client_queue.get()
            if message["type"] == "websocket.accept":
                self.accepted = True
                continue
            if message["type"] == "websocket.close":
                self.close_code = int(message.get("code", 1000))
                raise RuntimeError("websocket_closed")
            if message["type"] == "websocket.send":
                import json

                return json.loads(message["text"])


async def _run_websocket(app: Any, path: str) -> tuple[_AsgiWebSocketSession, asyncio.Task[None]]:
    session = _AsgiWebSocketSession()
    scope: Scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("test", 50000),
        "server": ("test", 80),
        "subprotocols": [],
        "state": {},
        "extensions": {},
        "app": app,
    }

    async def receive() -> dict[str, Any]:
        return await session.receive()

    async def send(message: dict[str, Any]) -> None:
        await session.send(message)

    task = asyncio.create_task(app(scope, receive, send))
    await session.client_connect()
    return session, task


@pytest.mark.asyncio
async def test_catchup_then_completion_frames() -> None:
    repo = _stream_repo()
    await _publish(repo, run_id="run-1", kind=StreamRecordKind.STATUS, tick=0)
    await _publish(repo, run_id="run-1", kind=StreamRecordKind.EVENTLESS_TICK, tick=1)
    await _publish(repo, run_id="run-1", kind=StreamRecordKind.COMPLETION, tick=1)
    fanout = StreamFanout(stream_repo=repo, settings=_settings())
    frames = [
        frame
        async for frame in fanout.subscribe(
            StreamSessionConfig(
                run_id="run-1",
                after_cursor=0,
                queue_size=8,
                heartbeat_seconds=10.0,
                poll_seconds=0.01,
            )
        )
    ]
    kinds = [frame.kind for frame in frames]
    assert StreamFrameKind.STATUS in kinds
    assert StreamFrameKind.EVENTLESS_TICK in kinds
    assert StreamFrameKind.COMPLETION in kinds
    assert frames[-1].cursor == 3


@pytest.mark.asyncio
async def test_slow_consumer_ends_session() -> None:
    repo = _stream_repo()
    for index in range(30):
        await _publish(
            repo,
            run_id="run-slow",
            kind=StreamRecordKind.EVENT,
            tick=index,
        )
    fanout = StreamFanout(stream_repo=repo, settings=_settings())
    frames = []
    async for frame in fanout.subscribe(
        StreamSessionConfig(
            run_id="run-slow",
            after_cursor=0,
            queue_size=1,
            heartbeat_seconds=30.0,
            poll_seconds=0.01,
            page_size=30,
        )
    ):
        frames.append(frame)
        await asyncio.sleep(0.02)
    assert len(frames) < 30


@pytest.mark.asyncio
async def test_websocket_route_with_asgi_harness(logging_sandbox: None) -> None:
    settings = _settings()
    repo = _stream_repo()
    await _publish(repo, run_id="run-ws", kind=StreamRecordKind.STATUS, tick=0)
    await _publish(repo, run_id="run-ws", kind=StreamRecordKind.COMPLETION, tick=0)

    app = create_app(
        settings=settings,
        database_factory=lambda _s: FakeResources(),
        simulation_manager=SimulationManager(
            settings=settings,
            run_control=InMemoryRunControlRepository(),
        ),
        attach_default_manager=False,
    )
    app.state.stream_repository = repo
    app.state.stream_fanout = StreamFanout(stream_repo=repo, settings=settings)

    session, task = await _run_websocket(app, "/v1/simulations/run-ws/stream")
    try:
        first = await asyncio.wait_for(session.receive_json(), timeout=2.0)
        assert first["envelope_version"] == "stream-envelope-v1"
        assert first["kind"] == "status"
        second = await asyncio.wait_for(session.receive_json(), timeout=2.0)
        assert second["kind"] == "completion"
    finally:
        await session.client_disconnect()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def test_stream_record_envelope_mapping() -> None:
    record = StreamRecord(
        run_id=RunId("run-1"),
        cursor=1,
        kind=StreamRecordKind.METRIC,
        envelope=opaque_envelope_from_payload(
            schema_version=STREAM_RECORD_SCHEMA_VERSION,
            payload=b"{}",
        ),
        related_tick=2,
    )
    envelope = stream_record_to_envelope(record, high_water=1)
    assert envelope.kind is StreamFrameKind.METRIC
    assert envelope.cursor == 1
    assert envelope.payload_b64 is not None


@pytest.mark.integration
async def test_api_stream_resume_integration_stub() -> None:
    pytest.skip("integration stub reserved for Task 21")


@pytest.mark.integration
async def test_api_stream_backpressure_integration_stub() -> None:
    pytest.skip("integration stub reserved for Task 21")
