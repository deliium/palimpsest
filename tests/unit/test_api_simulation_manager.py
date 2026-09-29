"""Recoverable simulation manager lifecycle and lease behavior."""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import pytest

from api.errors import ApiError
from api.simulation_manager import SimulationManager, TickExecutionResult
from infrastructure.settings import load_settings
from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.models import RunId
from simulation.run_control import RunControlRecord, RunLifecycleState

pytestmark = pytest.mark.unit

_PAYLOAD = b'{"schema_version":"runner-config-v2","agents":[]}'
_FINGERPRINT = hashlib.sha256(_PAYLOAD).hexdigest()
_GOLDEN_V2_PAYLOAD = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runner_configs"
    / "catalog_a_condition_v2.json"
).read_bytes()
_API_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "api"


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PALIMPSEST_"):
            monkeypatch.delenv(key, raising=False)


def _manager(
    *,
    ticks: list[TickExecutionResult] | None = None,
    clock: list[int] | None = None,
) -> tuple[SimulationManager, InMemoryRunControlRepository, list[str]]:
    repo = InMemoryRunControlRepository()
    executed: list[str] = []
    results = list(
        ticks
        or [
            TickExecutionResult(ticks_committed=1),
            TickExecutionResult(ticks_committed=2, completed=True, stop_reason="done"),
        ]
    )
    now = clock if clock is not None else [1_000_000]

    async def executor(run_id: str) -> TickExecutionResult:
        executed.append(run_id)
        if not results:
            return TickExecutionResult(ticks_committed=len(executed), completed=True)
        return results.pop(0)

    manager = SimulationManager(
        settings=load_settings(env_file=False),
        run_control=repo,
        tick_executor=executor,
        clock_ms=lambda: now[0],
    )
    return manager, repo, executed


@pytest.mark.asyncio
async def test_create_builds_runner_before_control_row_and_tick_uses_it() -> None:
    repo = InMemoryRunControlRepository()
    order: list[str] = []

    class _Runner:
        ticks_committed = 0

        async def run_tick(self) -> object:
            order.append("tick")
            self.ticks_committed = 1
            return type("Receipt", (), {"tick": 0, "stop_reason": None})()

    runner = _Runner()

    async def factory(record: RunControlRecord) -> _Runner:
        order.append("factory")
        assert await repo.get(record.run_id) is None
        return runner

    manager = SimulationManager(
        settings=load_settings(env_file=False),
        run_control=repo,
        runner_factory=factory,
    )
    created = await manager.create(
        run_id="run-durable",
        config_schema_version="runner-config-v4",
        config_fingerprint=_FINGERPRINT,
        config_payload=_PAYLOAD,
    )
    assert created.lifecycle_state.value == "configured"
    assert order == ["factory"]
    await manager.start(run_id="run-durable")
    ticked = await manager.tick(run_id="run-durable")
    assert ticked.ticks_committed == 1
    assert order == ["factory", "tick"]


@pytest.mark.asyncio
async def test_create_start_tick_ready_transitions() -> None:
    manager, repo, executed = _manager(
        ticks=[TickExecutionResult(ticks_committed=1)]
    )
    created = await manager.create(
        run_id="run-1",
        config_schema_version="runner-config-v2",
        config_fingerprint=_FINGERPRINT,
        config_payload=_PAYLOAD,
    )
    assert created.lifecycle_state.value == "configured"
    ready = await manager.start(run_id="run-1")
    assert ready.lifecycle_state.value == "ready"
    tick = await manager.tick(run_id="run-1")
    assert tick.ticks_committed == 1
    assert tick.lifecycle_state.value == "ready"
    assert executed == ["run-1"]
    record = await repo.get(RunId("run-1"))
    assert record is not None
    assert record.lifecycle_state is RunLifecycleState.READY
    assert record.lease is None


@pytest.mark.asyncio
async def test_create_idempotent_and_conflict() -> None:
    manager, _, _ = _manager()
    first = await manager.create(
        run_id="run-1",
        config_schema_version="runner-config-v2",
        config_fingerprint=_FINGERPRINT,
        config_payload=_PAYLOAD,
        idempotency_key="idem-1",
    )
    second = await manager.create(
        run_id="run-1",
        config_schema_version="runner-config-v2",
        config_fingerprint=_FINGERPRINT,
        config_payload=_PAYLOAD,
        idempotency_key="idem-1",
    )
    assert first == second
    with pytest.raises(ApiError) as exc:
        other = b'{"other":true}'
        await manager.create(
            run_id="run-1",
            config_schema_version="runner-config-v2",
            config_fingerprint=hashlib.sha256(other).hexdigest(),
            config_payload=other,
        )
    assert exc.value.code == "run_already_exists"


@pytest.mark.asyncio
async def test_run_stop_at_finalized_boundary() -> None:
    # Non-completing ticks so stop can land on a finalized boundary.
    ticks = [
        TickExecutionResult(ticks_committed=1),
        TickExecutionResult(ticks_committed=2),
        TickExecutionResult(ticks_committed=3),
        TickExecutionResult(ticks_committed=4),
        TickExecutionResult(ticks_committed=5),
        TickExecutionResult(ticks_committed=6),
        TickExecutionResult(ticks_committed=7),
        TickExecutionResult(ticks_committed=8),
    ]
    manager, repo, _ = _manager(ticks=ticks)
    # Override executor so it never auto-completes when the list drains.
    counter = {"n": 0}

    async def forever(run_id: str) -> TickExecutionResult:
        del run_id
        counter["n"] += 1
        await asyncio.sleep(0.01)
        return TickExecutionResult(ticks_committed=counter["n"], completed=False)

    manager._tick_executor = forever
    await manager.create(
        run_id="run-2",
        config_schema_version="runner-config-v2",
        config_fingerprint=_FINGERPRINT,
        config_payload=_PAYLOAD,
    )
    await manager.start(run_id="run-2")
    await manager.run(run_id="run-2")
    await asyncio.sleep(0.05)
    stopped = await manager.stop(run_id="run-2")
    assert stopped.lifecycle_state.value in {"stopping", "paused", "ready", "running"}
    for _ in range(100):
        status = await manager.status(run_id="run-2")
        if status.lifecycle_state.value == "paused":
            break
        await asyncio.sleep(0.02)
    final = await manager.status(run_id="run-2")
    assert final.lifecycle_state.value == "paused"
    assert final.ticks_committed >= 1
    record = await repo.get(RunId("run-2"))
    assert record is not None
    assert record.lease is None


@pytest.mark.asyncio
async def test_drain_rejects_new_work() -> None:
    manager, _, _ = _manager()
    await manager.drain()
    with pytest.raises(ApiError) as exc:
        await manager.create(
            run_id="run-3",
            config_schema_version="runner-config-v2",
            config_fingerprint=_FINGERPRINT,
            config_payload=_PAYLOAD,
        )
    assert exc.value.code == "draining"


@pytest.mark.asyncio
async def test_list_and_status_keyset() -> None:
    manager, _, _ = _manager()
    for name in ("run-a", "run-b", "run-c"):
        await manager.create(
            run_id=name,
            config_schema_version="runner-config-v2",
            config_fingerprint=_FINGERPRINT,
            config_payload=_PAYLOAD,
        )
    page = await manager.list_runs(limit=2)
    assert page.count == 2
    assert page.next_cursor == "run-b"
    rest = await manager.list_runs(after_run_id=page.next_cursor, limit=2)
    assert [item.run_id for item in rest.items] == ["run-c"]


@pytest.mark.asyncio
async def test_create_accepts_golden_runner_config_v2_payload() -> None:
    from simulation.models import RunId as SimRunId
    from simulation.runner import SimulationRunner
    from simulation.runner_models import V2CapabilityFlags
    from simulation.runner_serialization import decode_runner_config

    payload = _GOLDEN_V2_PAYLOAD
    fingerprint = hashlib.sha256(payload).hexdigest()
    manager, repo, _ = _manager()
    created = await manager.create(
        run_id="run-golden-v2",
        config_schema_version="runner-config-v2",
        config_fingerprint=fingerprint,
        config_payload=payload,
    )
    assert created.config_schema_version == "runner-config-v2"
    record = await repo.get(RunId("run-golden-v2"))
    assert record is not None
    assert record.config_payload == payload
    decoded = decode_runner_config(record.config_payload)
    assert decoded.capability_flags == V2CapabilityFlags()
    async with await SimulationRunner.from_config(
        decoded, run_id=SimRunId("run-golden-v2-runner")
    ) as runner:
        assert runner.run_id.value == "run-golden-v2-runner"


def test_api_keeps_v1_routes_and_ws_protocol() -> None:
    from api.security import WS_PROTOCOL_VERSION

    assert WS_PROTOCOL_VERSION == "palimpsest.v1"
    hits: list[str] = []
    markers = (
        'prefix="/v2"',
        "prefix='/v2'",
        'APIRouter(prefix="/v2"',
        '@router.get("/v2/',
        '@router.post("/v2/',
        '@router.websocket("/v2/',
    )
    for path in _API_SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in markers):
            hits.append(str(path.relative_to(_API_SRC_ROOT)))
    assert hits == []
