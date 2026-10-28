"""Durable benchmark history: restart reads, replay parity and append-only."""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from tests.benchmarks.harness import durable_factories, unique_run_id

from experiments.civilization_benchmark_population import (
    build_population_benchmark,
)
from experiments.civilization_benchmark_suite import V3_BENCH_01_BLANK_SLATE
from infrastructure.database import DatabaseResources, session_scope
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.clock import Tick
from simulation.persistence import ReplayRequest, ReplayStatus
from simulation.replay import ReplayService
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerCheckpointPolicy,
    RunnerPersistenceSpec,
)

pytestmark = pytest.mark.integration


async def test_durable_benchmark_history_replays_after_restart(
    database_resources: DatabaseResources,
) -> None:
    base = build_population_benchmark(V3_BENCH_01_BLANK_SLATE).arms[0].config
    config = replace(
        base,
        persistence=RunnerPersistenceSpec(
            durable=True,
            checkpoint=RunnerCheckpointPolicy(enabled=True, cadence_ticks=2),
        ),
        stop_policy=replace(base.stop_policy, max_ticks=6),
    )
    run_id = unique_run_id("v3bench")
    factories = durable_factories(database_resources.session_factory)
    async with await SimulationRunner.from_config(
        config, run_id=run_id, factories=factories
    ) as runner:
        result = await runner.run()
    assert result.ticks_committed == 6

    # New read services after the live runner is gone.
    runs = create_run_repository(database_resources.session_factory)
    journal = create_tick_journal_repository(database_resources.session_factory)
    snapshots = create_snapshot_repository(database_resources.session_factory)
    replay = ReplayService(runs, journal, snapshots)
    outcome = await replay.replay(
        ReplayRequest(
            run_id=run_id,
            target_tick=Tick(6),
            population_lifecycle=config.population_lifecycle,
        )
    )
    assert outcome.result.status is ReplayStatus.OK
    assert outcome.engine is not None
    assert outcome.engine.tick.value == 6

    # Authoritative history stays append-only after the restart.
    async with session_scope(database_resources.session_factory) as session:
        with pytest.raises((DBAPIError, IntegrityError)):
            await session.execute(
                text("DELETE FROM world_events WHERE run_id = :run_id"),
                {"run_id": run_id.value},
            )
