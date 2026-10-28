"""Replay qualification for benchmark trajectories.

Objective replay, deterministic rerun, process-local fork continuation and
captured subjective lineage stay separate guarantees. No test in this module
claims durable subjective restart or reconstructs technology lineage from
objective event exports.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from experiments.civilization_benchmark_coordination import (
    build_coordination_benchmark,
)
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_execution import (
    execute_stepped_benchmark_runner,
)
from experiments.civilization_benchmark_forks import _materialize_engine
from experiments.civilization_benchmark_institutions import (
    build_institutions_benchmark,
)
from experiments.civilization_benchmark_memory import build_memory_benchmark
from experiments.civilization_benchmark_population import (
    build_population_benchmark,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
)
from experiments.civilization_benchmark_technology import (
    build_technology_benchmark,
    technology_benchmark_arbiter,
)
from experiments.composition import practical_lineage_rows_from_audits
from simulation.fork_checkpoint import (
    FinalizedResearchBoundary,
    ForkCheckpointError,
    fork_state_digest,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    PopulationLifecycleSpec,
    SimulationRunnerConfig,
    SimulationRunnerResult,
)
from simulation.runner_serialization import runner_config_fingerprint
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _short_config(
    config: SimulationRunnerConfig,
    *,
    max_ticks: int,
    interval: int = 8,
) -> SimulationRunnerConfig:
    lifecycle = config.population_lifecycle
    assert isinstance(lifecycle, PopulationLifecycleSpec)
    short = replace(
        lifecycle,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(LifecycleStageId("adult"), 23),
        ),
        demographic_policy_params={
            **dict(lifecycle.demographic_policy_params),
            "interval_ticks": interval,
            "generation_length_ticks": interval,
        },
        max_population=12,
    )
    return replace(
        config,
        population_lifecycle=short,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
    )


async def _run(
    config: SimulationRunnerConfig, *, run_id: str
) -> tuple[SimulationRunnerResult, BenchmarkBoundaryProbe]:
    probe = BenchmarkBoundaryProbe()
    async with await SimulationRunner.from_config(
        config, run_id=RunId(run_id)
    ) as runner:
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
    return stepped.result, probe


@pytest.mark.asyncio
async def test_deterministic_rerun_matches_objective_and_boundary_inventory() -> None:
    config = _short_config(
        build_population_benchmark(V3_BENCH_01_BLANK_SLATE).arms[0].config,
        max_ticks=16,
    )
    first, first_probe = await _run(config, run_id="replay-a")
    second, second_probe = await _run(config, run_id="replay-b")
    assert first.ticks_committed == second.ticks_committed == 16
    assert first.stop_reason is second.stop_reason
    assert first.objective_state_hash == second.objective_state_hash
    assert first.final_objective_projection == second.final_objective_projection
    assert first.initial_lifecycle_records == second.initial_lifecycle_records
    assert first.generational_progress == second.generational_progress
    assert first_probe.event_kind_totals == second_probe.event_kind_totals
    assert first_probe.death_ticks_by_body == second_probe.death_ticks_by_body
    assert runner_config_fingerprint(config) == runner_config_fingerprint(config)


@pytest.mark.asyncio
async def test_terminal_research_projection_is_safe_at_horizon() -> None:
    config = _short_config(
        build_memory_benchmark("v3-bench-06-record-after-witnesses").arms[0].config,
        max_ticks=10,
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("terminal-projection")
    ) as runner:
        stepped = await execute_stepped_benchmark_runner(runner)
        boundary = cast(
            FinalizedResearchBoundary,
            await runner.export_finalized_research_boundary(),
        )
        assert type(boundary) is FinalizedResearchBoundary
        assert boundary.boundary_tick.value == stepped.result.ticks_committed == 10
        with pytest.raises(ForkCheckpointError):
            await runner.capture_fork_checkpoint()


@pytest.mark.asyncio
async def test_in_process_fork_twins_share_prefix_and_leave_parent_unchanged() -> None:
    config = _short_config(
        build_institutions_benchmark("v3-bench-26-office-succession").arms[0].config,
        max_ticks=12,
    )
    factories = RunnerDependencyFactories()
    parent = await SimulationRunner.from_config(
        config, run_id=RunId("fork-parent"), factories=factories
    )
    try:
        await parent.initialize_finalized_boundary()
        for _ in range(4):
            await parent.run_tick()
        checkpoint = await parent.capture_fork_checkpoint()
        prefix_digest = fork_state_digest(checkpoint)
        prefix_hash = checkpoint.snapshot.integrity_hash
        hashes: list[str] = []
        for ordinal in range(2):
            child = await SimulationRunner.from_fork_checkpoint(
                config,
                run_id=RunId(f"fork-child-{ordinal}"),
                checkpoint=checkpoint,
                restored_engine=await _materialize_engine(
                    checkpoint, RunId(f"fork-child-{ordinal}")
                ),
                factories=factories,
            )
            try:
                child_result = await child.run()
                assert child_result.ticks_committed == 12
                assert child_result.objective_state_hash is not None
                hashes.append(child_result.objective_state_hash)
            finally:
                await child.aclose()
        assert hashes[0] == hashes[1]
        after = await parent.capture_fork_checkpoint()
        assert fork_state_digest(after) == prefix_digest
        assert after.snapshot.integrity_hash == prefix_hash
    finally:
        await parent.aclose()


@pytest.mark.asyncio
async def test_captured_lineage_rebuild_uses_owner_audits_only() -> None:
    scenario_id = V3_BENCH_11_TECHNOLOGY_REDISCOVERY
    build = build_technology_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=10)
    arbiter = technology_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(arbiter)
        stepped = await execute_stepped_benchmark_runner(runner)
    audits = tuple(stepped.result.practical_knowledge_audits)
    rows = practical_lineage_rows_from_audits(audits)
    assert practical_lineage_rows_from_audits(()) == ()
    assert rows == practical_lineage_rows_from_audits(audits)
    for row in rows:
        assert row.owner_id
        assert row.parent_person_ids
        assert row.origin


@pytest.mark.asyncio
async def test_fork_checkpoint_is_not_reconstructed_from_objective_export() -> None:
    config = _short_config(
        build_coordination_benchmark("v3-bench-16-collective-project").arms[0].config,
        max_ticks=6,
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("no-objective-fork")
    ) as runner:
        stepped = await execute_stepped_benchmark_runner(runner)
        boundary = cast(
            FinalizedResearchBoundary,
            await runner.export_finalized_research_boundary(),
        )
        assert type(boundary) is FinalizedResearchBoundary
        assert boundary.boundary_tick.value == stepped.result.ticks_committed == 6
        kinds = {
            type(getattr(event, "details", None)).__name__ for event in boundary.events
        }
        assert not any("ForkCheckpoint" in kind for kind in kinds)
        # A terminal projection is inspectable but is not a fork checkpoint.
        with pytest.raises(ForkCheckpointError):
            await runner.capture_fork_checkpoint()
