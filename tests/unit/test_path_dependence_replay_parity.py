"""Uninterrupted continuation parity for complete fork restoration."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.cultural_evidence import CulturalEvidenceRecorder
from experiments.generational_comparison_base import generational_comparison_base
from simulation.branch_service import rematerialize_event, rematerialize_snapshot
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.fork_checkpoint import fork_state_digest
from simulation.models import RunId
from simulation.persistence import SnapshotId
from simulation.runner import SimulationRunner

pytestmark = pytest.mark.unit


def _config():
    return generational_comparison_base(seed=23, max_ticks=8)


def _restored_engine(checkpoint, prefix_events, run_id: RunId):
    config = checkpoint.config
    catalog = config.agents[0].cognition.production_catalog
    bootstrap = rematerialize_snapshot(
        checkpoint.bootstrap_snapshot,
        child_run_id=run_id,
        snapshot_id=SnapshotId(f"bootstrap-{run_id.value}"),
        predecessor_commit_hash=None,
        next_tick=Tick(0),
    )
    events = tuple(rematerialize_event(event, run_id) for event in prefix_events)
    return WorldEngine.restore_from_snapshot(
        bootstrap,
        events=events,
        committed_through_tick=Tick(checkpoint.boundary_tick.value - 1),
        population_lifecycle=config.population_lifecycle,
        new_agent_initialization=config.new_agent_initialization,
        kinship_spec=config.kinship,
        environmental_dynamics=config.environmental_dynamics,
        artifacts_enabled=config.artifacts_enabled,
        production_catalog=catalog if catalog.recipe_count > 0 else None,
    )


@pytest.mark.asyncio
async def test_same_identity_restore_matches_uninterrupted_continuation() -> None:
    config = _config()
    run_id = RunId("parity-run")
    uninterrupted = await SimulationRunner.from_config(config, run_id=run_id)
    try:
        await uninterrupted.initialize_finalized_boundary()
        await uninterrupted.run_tick()
        checkpoint = await uninterrupted.capture_fork_checkpoint()
        prefix_events = tuple(
            event
            for event in uninterrupted._engine.export_events().events  # type: ignore[attr-defined]
            if event.tick < checkpoint.boundary_tick.value
        )
        restored_engine = _restored_engine(checkpoint, prefix_events, run_id)
        restored = await SimulationRunner.from_fork_checkpoint(
            config,
            run_id=run_id,
            checkpoint=checkpoint,
            restored_engine=restored_engine,
        )
        try:
            await uninterrupted.run_tick()
            await restored.run_tick()
            left = await uninterrupted.capture_fork_checkpoint()
            right = await restored.capture_fork_checkpoint()
            assert left.boundary_tick == right.boundary_tick
            assert left.boundary_revision == right.boundary_revision
            assert fork_state_digest(left) == fork_state_digest(right)
            for registration in left.registrations:
                owner_id = registration.agent_id
                assert left.owner_state(owner_id) == right.owner_state(owner_id)
                assert left.runtime_state(owner_id) == right.runtime_state(owner_id)
            left_events = tuple(
                event
                for event in uninterrupted._engine.export_events().events  # type: ignore[attr-defined]
                if event.tick >= checkpoint.boundary_tick.value
            )
            right_events = tuple(
                event
                for event in restored._engine.export_events().events  # type: ignore[attr-defined]
                if event.tick >= checkpoint.boundary_tick.value
            )
            assert left_events == right_events
        finally:
            await restored.aclose()
    finally:
        await uninterrupted.aclose()


@pytest.mark.asyncio
async def test_distinct_child_starts_from_exact_pre_treatment_state() -> None:
    config = _config()
    parent_run = RunId("parent-run")
    parent = await SimulationRunner.from_config(config, run_id=parent_run)
    try:
        await parent.initialize_finalized_boundary()
        await parent.run_tick()
        checkpoint = await parent.capture_fork_checkpoint()
        prefix_events = tuple(
            event
            for event in parent._engine.export_events().events  # type: ignore[attr-defined]
            if event.tick < checkpoint.boundary_tick.value
        )
        child_run = RunId("child-run")
        child = await SimulationRunner.from_fork_checkpoint(
            config,
            run_id=child_run,
            checkpoint=checkpoint,
            restored_engine=_restored_engine(checkpoint, prefix_events, child_run),
        )
        try:
            child_checkpoint = await child.capture_fork_checkpoint()
            for registration in checkpoint.registrations:
                owner_id = registration.agent_id
                parent_owner = checkpoint.owner_state(owner_id)
                child_owner = child_checkpoint.owner_state(owner_id)
                assert child_owner.memory.traces == parent_owner.memory.traces
                assert child_owner.belief.beliefs == parent_owner.belief.beliefs
                assert (
                    child_owner.relationship.profiles
                    == parent_owner.relationship.profiles
                )
                assert child_owner.commit.revision == parent_owner.commit.revision
                parent_runtime = checkpoint.runtime_state(owner_id)
                child_runtime = child_checkpoint.runtime_state(owner_id)
                assert child_runtime.processed_invocations == (
                    parent_runtime.processed_invocations
                )
                assert child_runtime.finalized_hashes == (
                    parent_runtime.finalized_hashes
                )
                assert (
                    child_runtime.invocation_counts
                    == parent_runtime.invocation_counts
                )
        finally:
            await child.aclose()
    finally:
        await parent.aclose()


@pytest.mark.asyncio
async def test_fork_restore_publishes_exactly_one_baseline_then_next_tick() -> None:
    config = _config()
    run_id = RunId("baseline-run")
    parent = await SimulationRunner.from_config(config, run_id=run_id)
    try:
        await parent.initialize_finalized_boundary()
        await parent.run_tick()
        checkpoint = await parent.capture_fork_checkpoint()
        prefix_events = tuple(
            event
            for event in parent._engine.export_events().events  # type: ignore[attr-defined]
            if event.tick < checkpoint.boundary_tick.value
        )
        recorder = CulturalEvidenceRecorder()
        child_run = RunId("baseline-child")
        child = await SimulationRunner.from_fork_checkpoint(
            config,
            run_id=child_run,
            checkpoint=checkpoint,
            restored_engine=_restored_engine(checkpoint, prefix_events, child_run),
            cultural_sink=recorder,
        )
        try:
            result = recorder.result()
            assert len(result.frames) == 1
            assert result.frames[0].boundary_tick == checkpoint.boundary_tick.value
            await child.run_tick()
            result = recorder.result()
            assert [frame.boundary_tick for frame in result.frames] == [
                checkpoint.boundary_tick.value,
                checkpoint.boundary_tick.value + 1,
            ]
        finally:
            await child.aclose()
    finally:
        await parent.aclose()


@pytest.mark.asyncio
async def test_fork_state_digest_detects_mutated_hidden_state() -> None:
    config = _config()
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("digest-run")
    )
    try:
        await runner.initialize_finalized_boundary()
        checkpoint = await runner.capture_fork_checkpoint()
        baseline = fork_state_digest(checkpoint)
        owner = checkpoint.owner_states[0]
        mutated_owner = replace(
            owner,
            memory=replace(
                owner.memory,
                access_operations=(
                    *owner.memory.access_operations,
                    ("x", "y"),
                ),
            ),
        )
        mutated = replace(
            checkpoint,
            owner_states=(mutated_owner, *checkpoint.owner_states[1:]),
        )
        assert fork_state_digest(mutated) != baseline
    finally:
        await runner.aclose()
