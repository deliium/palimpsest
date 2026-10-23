"""Complete runner fork checkpoint capture and restore proofs."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.generational_comparison_base import generational_comparison_base
from simulation.branch_service import rematerialize_snapshot
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.fork_checkpoint import ForkCheckpointError
from simulation.models import RunId
from simulation.persistence import SnapshotId
from simulation.runner import SimulationRunner
from simulation.runner_models import RecordingPolicy

pytestmark = pytest.mark.unit


def _config(*, max_ticks: int = 8, **overrides: object):
    config = generational_comparison_base(seed=23, max_ticks=max_ticks)
    return replace(config, **overrides)


@pytest.mark.asyncio
async def test_capture_requires_initialized_finalized_boundary() -> None:
    config = _config()
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("parent-run")
    )
    try:
        with pytest.raises(ForkCheckpointError) as exc:
            await runner.capture_fork_checkpoint()
        assert exc.value.code == "fork_boundary_not_finalized"

        await runner.initialize_finalized_boundary()
        await runner.initialize_finalized_boundary()
        checkpoint = await runner.capture_fork_checkpoint()
        assert checkpoint.boundary_tick == Tick(0)
        assert checkpoint.boundary_revision.value == 0
        assert len(checkpoint.owner_states) == len(config.agents)
        assert len(checkpoint.runtime_states) == len(config.agents)

        await runner.run_tick()
        after = await runner.capture_fork_checkpoint()
        assert after.boundary_tick == Tick(1)
        assert after.boundary_tick.value == after.runner_control.ticks_committed
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_fork_checkpoint_restores_complete_state_into_child_engine() -> None:
    config = _config()
    parent = await SimulationRunner.from_config(
        config, run_id=RunId("parent-run")
    )
    try:
        await parent.initialize_finalized_boundary()
        await parent.run_tick()
        checkpoint = await parent.capture_fork_checkpoint()
        child_run = RunId("child-run")
        child_snapshot = rematerialize_snapshot(
            checkpoint.snapshot,
            child_run_id=child_run,
            snapshot_id=SnapshotId("child-fork-snapshot"),
            predecessor_commit_hash=None,
            next_tick=checkpoint.boundary_tick,
        )
        child_engine = WorldEngine.restore_from_snapshot(
            child_snapshot,
            population_lifecycle=config.population_lifecycle,
            new_agent_initialization=config.new_agent_initialization,
            kinship_spec=config.kinship,
            environmental_dynamics=config.environmental_dynamics,
            artifacts_enabled=config.artifacts_enabled,
        )
        child = await SimulationRunner.from_fork_checkpoint(
            config,
            run_id=child_run,
            checkpoint=checkpoint,
            restored_engine=child_engine,
        )
        try:
            restored = await child.capture_fork_checkpoint()
            assert restored.boundary_tick == checkpoint.boundary_tick
            assert restored.boundary_revision == checkpoint.boundary_revision
            assert len(restored.owner_states) == len(checkpoint.owner_states)
            assert len(restored.runtime_states) == len(checkpoint.runtime_states)
            for owner in checkpoint.registrations:
                parent_owner = checkpoint.owner_state(owner.agent_id)
                child_owner = restored.owner_state(owner.agent_id)
                assert child_owner.scope.owner_id == parent_owner.scope.owner_id
                assert child_owner.memory.traces == parent_owner.memory.traces
                assert child_owner.belief.beliefs == parent_owner.belief.beliefs
                assert (
                    child_owner.relationship.profiles
                    == parent_owner.relationship.profiles
                )
                assert child_owner.commit.revision == parent_owner.commit.revision
                parent_runtime = checkpoint.runtime_state(owner.agent_id)
                child_runtime = restored.runtime_state(owner.agent_id)
                assert (
                    child_runtime.processed_invocations
                    == parent_runtime.processed_invocations
                )
                assert (
                    child_runtime.finalized_hashes
                    == parent_runtime.finalized_hashes
                )
                assert (
                    child_runtime.invocation_counts
                    == parent_runtime.invocation_counts
                )
                assert (
                    child_runtime.cultural_fresh_channels
                    == parent_runtime.cultural_fresh_channels
                )
        finally:
            await child.aclose()
    finally:
        await parent.aclose()


@pytest.mark.asyncio
async def test_unsupported_provider_and_terminal_boundary_rejected() -> None:
    config = _config(
        provider=replace(
            _config().provider,
            recording_policy=RecordingPolicy.LIVE,
            exact_reproducibility=__import__(
                "simulation.runner_models",
                fromlist=["ExactReproducibilityMode"],
            ).ExactReproducibilityMode.NOT_REQUIRED,
        )
    )
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("parent-run")
    )
    try:
        await runner.initialize_finalized_boundary()
        checkpoint = await runner.capture_fork_checkpoint()
        child_run = RunId("child-run")
        child_snapshot = rematerialize_snapshot(
            checkpoint.snapshot,
            child_run_id=child_run,
            snapshot_id=SnapshotId("child-snapshot"),
            predecessor_commit_hash=None,
            next_tick=checkpoint.boundary_tick,
        )
        child_engine = WorldEngine.restore_from_snapshot(
            child_snapshot,
            population_lifecycle=config.population_lifecycle,
            new_agent_initialization=config.new_agent_initialization,
            kinship_spec=config.kinship,
            environmental_dynamics=config.environmental_dynamics,
            artifacts_enabled=config.artifacts_enabled,
        )
        with pytest.raises(ForkCheckpointError) as exc:
            await SimulationRunner.from_fork_checkpoint(
                config,
                run_id=child_run,
                checkpoint=checkpoint,
                restored_engine=child_engine,
            )
        assert exc.value.code == "fork_provider_unsupported"
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_terminal_runner_rejects_fork_capture() -> None:
    config = _config(max_ticks=8)
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("parent-run")
    )
    try:
        await runner.initialize_finalized_boundary()
        await runner.run_tick()
        await runner.finish_run(
            __import__(
                "simulation.runner_models",
                fromlist=["RunnerStopReasonCode"],
            ).RunnerStopReasonCode.MAX_TICKS
        )
        with pytest.raises(ForkCheckpointError) as exc:
            await runner.capture_fork_checkpoint()
        assert exc.value.code == "fork_terminal_boundary"
    finally:
        await runner.aclose()
