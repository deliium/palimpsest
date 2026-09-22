"""Integration proofs for finalization recovery (network-free / in-process).

PostgreSQL-backed recovery is exercised when Task 6/21 durable run-control is
available. This file remains marked integration and covers in-process crash
boundaries with injectable pending repositories.
"""

from __future__ import annotations

import pytest
from tests.simulation_helpers import alive_body, make_location, make_weather

from agents.models import AgentId
from simulation.memory_finalization import InMemoryPendingFinalizationRepository
from simulation.models import RunId, StochasticIdentity
from simulation.run_control import (
    ResumeMode,
    RunnerCrashInjected,
    RunnerCrashPoint,
)
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerAttemptStatus,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.integration


def _config(*, max_ticks: int = 3) -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return SimulationRunnerConfig(
        seed=17,
        stochastic_identity=StochasticIdentity("cmp-recovery-int"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
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
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
    )


def _crash(point: RunnerCrashPoint):
    def _hook(seen: RunnerCrashPoint, _ordinal: int | None) -> None:
        if seen is point:
            raise RunnerCrashInjected(seen)

    return _hook


@pytest.mark.asyncio
async def test_integration_crash_matrix_never_duplicates_objective() -> None:
    for point in (
        RunnerCrashPoint.AFTER_OBJECTIVE_COMMIT,
        RunnerCrashPoint.DURING_OWNER_FINALIZATION,
        RunnerCrashPoint.BEFORE_COLLECTOR_PUBLICATION,
        RunnerCrashPoint.AFTER_ACKNOWLEDGEMENT,
    ):
        pending_repo = InMemoryPendingFinalizationRepository()
        async with await SimulationRunner.from_config(
            _config(),
            run_id=RunId(f"run-int-{point.value}"),
            factories=RunnerDependencyFactories(pending_finalizations=pending_repo),
        ) as runner:
            runner.set_crash_hook(_crash(point))
            with pytest.raises(RunnerCrashInjected):
                await runner.run_tick()
            engine_tick = runner.engine.tick.value
            assert engine_tick == 1
            runner.set_crash_hook(None)
            receipt = await runner.recover_pending_finalizations()
            assert receipt.status is RunnerAttemptStatus.FINALIZED
            assert runner.engine.tick.value == engine_tick
            plan = runner.classify_resume(pending_count=0, pending_tick=None)
            assert plan.mode in {
                ResumeMode.CONTINUED_EXECUTION,
                ResumeMode.OBJECTIVE_REPLAY,
            }
            continued = await runner.run_tick()
            assert continued.status is RunnerAttemptStatus.FINALIZED
            assert runner.engine.tick.value == 2
