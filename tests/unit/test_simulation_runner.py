"""Unit tests for SimulationRunner tick scheduling and stop semantics."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.models import RunId, StochasticIdentity
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerAttemptStatus,
    RunnerStopPolicy,
    RunnerStopReasonCode,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _config(*, max_ticks: int = 2) -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return SimulationRunnerConfig(
        seed=42,
        stochastic_identity=StochasticIdentity("cmp-run"),
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


@pytest.mark.asyncio
async def test_runner_run_stops_at_max_ticks() -> None:
    async with await SimulationRunner.from_config(
        _config(max_ticks=2), run_id=RunId("run-tick-1")
    ) as runner:
        result = await runner.run()
        assert result.stop_reason is RunnerStopReasonCode.MAX_TICKS
        assert result.ticks_committed == 2
        assert len(result.attempt_receipts) == 2
        assert all(
            item.status is RunnerAttemptStatus.FINALIZED
            for item in result.attempt_receipts
        )


@pytest.mark.asyncio
async def test_runner_injected_stop() -> None:
    async with await SimulationRunner.from_config(
        _config(max_ticks=10), run_id=RunId("run-tick-2")
    ) as runner:
        receipt = await runner.run_tick()
        assert receipt.status is RunnerAttemptStatus.FINALIZED
        runner.request_stop()
        result = await runner.run()
        assert result.stop_reason is RunnerStopReasonCode.INJECTED_STOP
        assert result.ticks_committed >= 2
