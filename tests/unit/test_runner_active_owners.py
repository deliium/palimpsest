"""Active-ordinal scheduling without changing registration or history."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeStatus,
    AgentStepResult,
    PreparedObservation,
)
from simulation.lifecycle import TickToken
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerPersistenceSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
)
from tests.benchmarks.v3_workloads import V3ScaleLane, V3ScaleWorkload, build_workload
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold
from world.observations import Observation


def _active_config(*, ticks: int) -> tuple[V3ScaleWorkload, SimulationRunnerConfig]:
    workload = build_workload(V3ScaleLane.GENERATIONAL, ticks=ticks)
    config = replace(workload.config, persistence=RunnerPersistenceSpec(durable=False))
    lifecycle = config.population_lifecycle
    assert lifecycle is not None
    params = dict(lifecycle.demographic_policy_params)
    params.update(
        {
            "interval_ticks": 2,
            "entries_per_interval": 1,
            "generation_length_ticks": 2,
        }
    )
    lifecycle = replace(
        lifecycle,
        lifespan_ticks=4,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(LifecycleStageId("adult"), 3),
        ),
        demographic_policy_params=params,
        max_population=6,
    )
    generational = config.generational_run
    assert generational is not None
    return workload, replace(
        config,
        population_lifecycle=lifecycle,
        generational_run=replace(
            generational, max_generation_index=None, stop_on_extinction=False
        ),
        stop_policy=RunnerStopPolicy(
            max_ticks=ticks, stop_on_all_agents_terminal=False
        ),
    )


@pytest.mark.asyncio
async def test_terminal_owners_leave_active_scheduling_without_leaving_roster() -> None:
    workload, config = _active_config(ticks=14)
    calls: dict[str, int] = {}
    original = AgentRuntime.prepare_observation

    async def counting(
        self: AgentRuntime, observation: Observation, *, token: TickToken
    ) -> PreparedObservation | AgentStepResult:
        calls[self.agent_id.value] = calls.get(self.agent_id.value, 0) + 1
        return await original(self, observation, token=token)

    AgentRuntime.prepare_observation = counting  # type: ignore[method-assign]
    try:
        runner = await SimulationRunner.from_config(config, run_id=workload.run_id)
        try:
            retired: set[int] = set()
            assert runner.active_ordinals == tuple(range(len(runner.runtimes)))
            for _ in range(14):
                before = runner.active_ordinals
                calls.clear()
                await runner.run_tick()
                assert sum(calls.values()) == len(before)
                assert set(calls) == {
                    runner.runtimes[ordinal].agent_id.value for ordinal in before
                }
                active_after = set(runner.active_ordinals)
                retired.update(set(before) - active_after)
                assert active_after == {
                    ordinal
                    for ordinal, runtime in enumerate(runner.runtimes)
                    if runtime.status is not AgentRuntimeStatus.TERMINAL
                }
                assert retired.isdisjoint(active_after)
            assert retired
            assert len(runner.runtimes) > len(retired)
        finally:
            await runner.aclose()
    finally:
        AgentRuntime.prepare_observation = original  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_restore_rebuilds_active_ordinals_from_runtime_status() -> None:
    workload, config = _active_config(ticks=12)
    runner = await SimulationRunner.from_config(config, run_id=workload.run_id)
    try:
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        expected_active = runner.active_ordinals
        assert expected_active
    finally:
        await runner.aclose()

    restored = await SimulationRunner.from_config(config, run_id=workload.run_id)
    try:
        restored.apply_runtime_checkpoint(checkpoint)
        assert restored.active_ordinals == expected_active
        assert restored.active_ordinals == tuple(
            ordinal
            for ordinal, runtime in enumerate(restored.runtimes)
            if runtime.status is not AgentRuntimeStatus.TERMINAL
        )
        for _ in range(5):
            await restored.run_tick()
        assert set(restored.active_ordinals).isdisjoint(
            {
                ordinal
                for ordinal, runtime in enumerate(restored.runtimes)
                if runtime.status is AgentRuntimeStatus.TERMINAL
            }
        )
    finally:
        await restored.aclose()


__all__: tuple[str, ...] = ()
