"""Deterministic long-run scale harness helpers (metadata-only metrics).

Measures wall time, event throughput, snapshot counts, RSS proxies, observer
catch-up page latency, and seek latency. Never logs seeds, payloads, or
embeddings.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.models import AgentId
from infrastructure.database import DatabaseResources, session_scope
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from persistence.orm import WorldEventOrm, WorldSnapshotOrm
from simulation.clock import Tick
from simulation.models import RunId, StochasticIdentity
from simulation.persistence import ReplayRequest
from simulation.replay import ReplayService, scene_at_tick
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    RunnerCheckpointPolicy,
    RunnerPersistenceSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

_LOG = logging.getLogger("scale.bench")
_PROFILE_LOG = logging.getLogger("scale.profile")

SCALE_BENCH_EXTENDED_ENV = "PALIMPSEST_SCALE_BENCH_EXTENDED"
SCALE_BENCH_TICKS_ENV = "PALIMPSEST_SCALE_BENCH_TICKS"
_DEFAULT_CI_TARGETS: tuple[int, ...] = (1_000, 10_000)
_EXTENDED_TARGET = 50_000
_CATCHUP_PAGE_SIZE = 200


@dataclass(frozen=True, slots=True)
class ScaleBenchMetrics:
    """Structured metric bag — counts and durations only."""

    scenario: str
    ticks: int
    elapsed_ms: float
    events: int
    snapshots: int
    events_per_sec: float
    peak_rss_kb: int | None
    catchup_ms: float
    seek_ms: float
    snapshot_write_proxy_ms: float


def resolve_tick_targets() -> tuple[int, ...]:
    """Return tick horizons for the scale suite.

    Defaults to 1k and 10k. Optional ``PALIMPSEST_SCALE_BENCH_TICKS`` overrides
    to a single positive integer. ``PALIMPSEST_SCALE_BENCH_EXTENDED=1`` appends
    a 50k horizon.
    """
    override = os.environ.get(SCALE_BENCH_TICKS_ENV, "").strip()
    if override:
        try:
            ticks = int(override)
        except ValueError as exc:
            raise ValueError(
                f"{SCALE_BENCH_TICKS_ENV} must be a positive integer"
            ) from exc
        if ticks < 1:
            raise ValueError(f"{SCALE_BENCH_TICKS_ENV} must be >= 1")
        targets: list[int] = [ticks]
    else:
        targets = list(_DEFAULT_CI_TARGETS)
    if os.environ.get(SCALE_BENCH_EXTENDED_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        if _EXTENDED_TARGET not in targets:
            targets.append(_EXTENDED_TARGET)
    return tuple(targets)


def peak_rss_kb() -> int | None:
    """Linux VmHWM (peak RSS) from /proc; None when unavailable."""
    status = Path("/proc/self/status")
    if not status.is_file():
        return None
    for line in status.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmHWM:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    return None


def unique_run_id(prefix: str = "scale") -> RunId:
    return RunId(f"{prefix}-{uuid.uuid4().hex[:12]}")


def build_scale_config(
    *,
    max_ticks: int,
    checkpoint_cadence: int | None = None,
    seed: int = 42,
) -> SimulationRunnerConfig:
    """Minimal single-agent durable config with deterministic fake cognition."""
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    if checkpoint_cadence is None:
        persistence = RunnerPersistenceSpec(durable=True)
    else:
        persistence = RunnerPersistenceSpec(
            durable=True,
            checkpoint=RunnerCheckpointPolicy(
                enabled=True, cadence_ticks=checkpoint_cadence
            ),
        )
    return SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=StochasticIdentity("scale-bench-v1"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-scale-1"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(
                    agent_id=agent_id,
                    memory_mode=MemoryMode.REFERENCE,
                    imagination_mode=ImaginationMode.DISABLED,
                ),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        mortality_mode=MortalityMode.DISABLED,
        persistence=persistence,
    )


def durable_factories(
    session_factory: async_sessionmaker[AsyncSession],
) -> RunnerDependencyFactories:
    return RunnerDependencyFactories(
        run_repository=create_run_repository(session_factory),
        journal=create_tick_journal_repository(session_factory),
    )


async def count_events(
    session_factory: async_sessionmaker[AsyncSession], run_id: RunId
) -> int:
    async with session_scope(session_factory) as session:
        result = await session.execute(
            select(func.count())
            .select_from(WorldEventOrm)
            .where(WorldEventOrm.run_id == run_id.value)
        )
        return int(result.scalar_one())


async def count_snapshots(
    session_factory: async_sessionmaker[AsyncSession], run_id: RunId
) -> int:
    async with session_scope(session_factory) as session:
        result = await session.execute(
            select(func.count())
            .select_from(WorldSnapshotOrm)
            .where(WorldSnapshotOrm.run_id == run_id.value)
        )
        return int(result.scalar_one())


async def measure_observer_catchup_ms(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: RunId,
    *,
    page_size: int = _CATCHUP_PAGE_SIZE,
) -> float:
    """Simulate reconnect catch-up via exclusive keyset event pages."""
    journal = create_tick_journal_repository(session_factory)
    after_tick = 0
    after_sequence = -1
    started = time.perf_counter()
    pages = 0
    events = 0
    while True:
        batch = await journal.list_events_keyset(
            run_id,
            after_tick=after_tick,
            after_sequence=after_sequence,
            to_tick=None,
            limit=page_size,
        )
        pages += 1
        if not batch:
            break
        events += len(batch)
        last = batch[-1]
        after_tick = last.tick
        after_sequence = last.sequence
        if len(batch) < page_size:
            break
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    _LOG.debug(
        "[scale.bench] phase=observer_catchup duration_ms=%.3f pages=%s events=%s",
        elapsed_ms,
        pages,
        events,
    )
    _PROFILE_LOG.debug(
        "[scale.profile] component=observer operation=catchup "
        "duration_ms=%.3f count=%s",
        elapsed_ms,
        events,
    )
    return elapsed_ms


async def measure_seek_ms(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: RunId,
    *,
    target_tick: int,
) -> float:
    """Replay/scene_at_tick latency to a target tick."""
    runs = create_run_repository(session_factory)
    journal = create_tick_journal_repository(session_factory)
    snapshots = create_snapshot_repository(session_factory)
    replay = ReplayService(runs, journal, snapshots)
    started = time.perf_counter()
    history = await scene_at_tick(
        replay, run_id, target_tick=Tick(target_tick)
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    _LOG.debug(
        "[scale.bench] phase=seek duration_ms=%.3f target_tick=%s event_count=%s",
        elapsed_ms,
        target_tick,
        len(history.events),
    )
    _PROFILE_LOG.debug(
        "[scale.profile] component=replay operation=scene_at_tick "
        "duration_ms=%.3f count=%s",
        elapsed_ms,
        len(history.events),
    )
    # Touch replay path once more for warm/cold contrast logging only.
    warm_started = time.perf_counter()
    outcome = await replay.replay(
        ReplayRequest(run_id=run_id, target_tick=Tick(target_tick))
    )
    warm_ms = (time.perf_counter() - warm_started) * 1000.0
    _LOG.debug(
        "[scale.bench] phase=seek_replay duration_ms=%.3f status=%s",
        warm_ms,
        outcome.result.status.value,
    )
    return elapsed_ms


async def run_durable_scale_scenario(
    database_resources: DatabaseResources,
    *,
    scenario: str,
    max_ticks: int,
    checkpoint_cadence: int | None = 100,
) -> ScaleBenchMetrics:
    """Run a durable fake-cognition scenario and return metadata metrics."""
    session_factory = database_resources.session_factory
    run_id = unique_run_id(scenario.replace("_", "-")[:24])
    config = build_scale_config(
        max_ticks=max_ticks, checkpoint_cadence=checkpoint_cadence
    )
    rss_before = peak_rss_kb()
    _LOG.debug(
        "[scale.bench] phase=start scenario=%s ticks=%s cadence=%s rss_kb=%s",
        scenario,
        max_ticks,
        checkpoint_cadence,
        rss_before,
    )
    started = time.perf_counter()
    async with await SimulationRunner.from_config(
        config,
        run_id=run_id,
        factories=durable_factories(session_factory),
    ) as runner:
        result = await runner.run()
    run_elapsed_ms = (time.perf_counter() - started) * 1000.0
    _LOG.debug(
        "[scale.bench] phase=run duration_ms=%.3f ticks_committed=%s",
        run_elapsed_ms,
        result.ticks_committed,
    )

    events = await count_events(session_factory, run_id)
    snapshots = await count_snapshots(session_factory, run_id)
    # Snapshot write cost proxy: fraction of run time attributed to cadence
    # hits when cadence is set (exact timers land in task 2 instrumentation).
    snapshot_write_proxy_ms = (
        (run_elapsed_ms * snapshots / max(max_ticks, 1)) if snapshots else 0.0
    )
    catchup_ms = await measure_observer_catchup_ms(session_factory, run_id)
    seek_target = max(max_ticks // 2, 1)
    seek_ms = await measure_seek_ms(
        session_factory, run_id, target_tick=seek_target
    )
    total_ms = (time.perf_counter() - started) * 1000.0
    rss_peak = peak_rss_kb()
    events_per_sec = (
        (events / (run_elapsed_ms / 1000.0)) if run_elapsed_ms > 0 else 0.0
    )
    metrics = ScaleBenchMetrics(
        scenario=scenario,
        ticks=result.ticks_committed,
        elapsed_ms=total_ms,
        events=events,
        snapshots=snapshots,
        events_per_sec=events_per_sec,
        peak_rss_kb=rss_peak,
        catchup_ms=catchup_ms,
        seek_ms=seek_ms,
        snapshot_write_proxy_ms=snapshot_write_proxy_ms,
    )
    _LOG.info(
        "[scale.bench] scenario=%s ticks=%s elapsed_ms=%.3f events=%s "
        "snapshots=%s",
        metrics.scenario,
        metrics.ticks,
        metrics.elapsed_ms,
        metrics.events,
        metrics.snapshots,
    )
    _LOG.debug(
        "[scale.bench] phase=complete events_per_sec=%.3f catchup_ms=%.3f "
        "seek_ms=%.3f snapshot_write_proxy_ms=%.3f peak_rss_kb=%s",
        metrics.events_per_sec,
        metrics.catchup_ms,
        metrics.seek_ms,
        metrics.snapshot_write_proxy_ms,
        metrics.peak_rss_kb,
    )
    return metrics


def metrics_as_artifact_row(metrics: ScaleBenchMetrics) -> Mapping[str, object]:
    """Plain mapping suitable for checked-in CSV/markdown templates."""
    return {
        "scenario": metrics.scenario,
        "ticks": metrics.ticks,
        "elapsed_ms": round(metrics.elapsed_ms, 3),
        "events": metrics.events,
        "snapshots": metrics.snapshots,
        "events_per_sec": round(metrics.events_per_sec, 3),
        "peak_rss_kb": metrics.peak_rss_kb,
        "catchup_ms": round(metrics.catchup_ms, 3),
        "seek_ms": round(metrics.seek_ms, 3),
        "snapshot_write_proxy_ms": round(metrics.snapshot_write_proxy_ms, 3),
    }
