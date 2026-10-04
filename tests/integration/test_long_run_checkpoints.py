"""Durable checkpoint cadence + long-run preset proofs (PostgreSQL)."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest
from tests.benchmarks.harness import (
    build_scale_config,
    count_snapshots,
    durable_factories,
    unique_run_id,
)

from infrastructure.database import DatabaseResources
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.clock import Tick
from simulation.replay import ReplayService, scene_at_tick
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    LONG_RUN_CHECKPOINT_CADENCE_100,
    RunnerCheckpointPolicy,
    RunnerPersistenceSpec,
    long_run_persistence_spec,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_checkpoint_disabled_remains_default_short_run(
    database_resources: DatabaseResources,
) -> None:
    config = build_scale_config(max_ticks=30, checkpoint_cadence=None)
    assert config.persistence.checkpoint.enabled is False
    assert config.persistence.checkpoint.cadence_ticks is None
    run_id = unique_run_id("ckpt-off")
    async with await SimulationRunner.from_config(
        config,
        run_id=run_id,
        factories=durable_factories(database_resources.session_factory),
    ) as runner:
        result = await runner.run()
    assert result.ticks_committed == 30
    snapshots = await count_snapshots(database_resources.session_factory, run_id)
    assert snapshots == 1  # bootstrap only


@pytest.mark.asyncio
async def test_long_run_preset_writes_snapshots_at_cadence(
    database_resources: DatabaseResources,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cadence = LONG_RUN_CHECKPOINT_CADENCE_100
    max_ticks = 250
    config = replace(
        build_scale_config(max_ticks=max_ticks, checkpoint_cadence=None),
        persistence=long_run_persistence_spec(cadence_ticks=cadence),
    )
    assert config.persistence.checkpoint.enabled is True
    assert config.persistence.checkpoint.cadence_ticks == cadence
    run_id = unique_run_id("ckpt-on")
    with caplog.at_level(logging.INFO, logger="simulation.runner"):
        async with await SimulationRunner.from_config(
            config,
            run_id=run_id,
            factories=durable_factories(database_resources.session_factory),
        ) as runner:
            result = await runner.run()
    assert result.ticks_committed == max_ticks
    snapshots = await count_snapshots(database_resources.session_factory, run_id)
    # bootstrap + one snapshot per cadence hit
    assert snapshots == 1 + (max_ticks // cadence)
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "runner_checkpoint_committed" in messages


@pytest.mark.asyncio
async def test_cadence_seek_matches_fold_from_earlier_snapshot(
    database_resources: DatabaseResources,
    caplog: pytest.LogCaptureFixture,
) -> None:
    max_ticks = 200
    cadence = 50
    config = build_scale_config(max_ticks=max_ticks, checkpoint_cadence=cadence)
    run_id = unique_run_id("ckpt-seek")
    async with await SimulationRunner.from_config(
        config,
        run_id=run_id,
        factories=durable_factories(database_resources.session_factory),
    ) as runner:
        await runner.run()

    session_factory = database_resources.session_factory
    runs = create_run_repository(session_factory)
    journal = create_tick_journal_repository(session_factory)
    snapshots = create_snapshot_repository(session_factory)
    replay = ReplayService(runs, journal, snapshots)

    target = Tick(175)
    with caplog.at_level(logging.DEBUG, logger="simulation.replay"):
        history = await scene_at_tick(replay, run_id, target_tick=target)
    assert history.scene.tick == target.value

    nearest = await snapshots.get_latest_at_or_before(run_id, target)
    assert nearest is not None
    assert nearest.next_tick.value == 150

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "seek_snapshot_selected" in messages
    assert f"target_tick={target.value}" in messages
    assert "snapshot_next_tick=150" in messages

    again = await scene_at_tick(replay, run_id, target_tick=target)
    assert len(again.events) == len(history.events)
    assert again.scene.tick == history.scene.tick
    # Cadence-assisted seek must fold fewer commits than bootstrap-only would.
    assert nearest.next_tick.value > 0


def test_runner_checkpoint_policy_rejects_cadence_without_durable() -> None:
    with pytest.raises(ValueError, match="checkpoints require durable"):
        RunnerPersistenceSpec(
            durable=False,
            checkpoint=RunnerCheckpointPolicy(enabled=True, cadence_ticks=100),
        )
