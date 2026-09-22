"""Deterministic end-to-end runner proofs (network-free)."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario, experiment_a_memory
from experiments.coordinator import ExperimentCoordinator
from simulation.models import RunId, StochasticIdentity
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from simulation.runner_serialization import build_runner_result_document
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _config(*, seed: int = 11, stochastic: str = "cmp-e2e") -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=StochasticIdentity(stochastic),
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
        stop_policy=RunnerStopPolicy(max_ticks=2),
    )


@pytest.mark.asyncio
async def test_identical_config_equal_replica_normalized_hashes() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-e2e-a")
    ) as runner_a:
        result_a = await runner_a.run()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-e2e-b")
    ) as runner_b:
        result_b = await runner_b.run()
    doc_a = build_runner_result_document(result=result_a, config=config)
    doc_b = build_runner_result_document(result=result_b, config=config)
    assert doc_a.replica_normalized_trajectory_hash == (
        doc_b.replica_normalized_trajectory_hash
    )
    assert doc_a.exact_trajectory_hash != doc_b.exact_trajectory_hash
    assert result_a.ticks_committed == result_b.ticks_committed == 2


@pytest.mark.asyncio
async def test_seed_change_diverges_fingerprint() -> None:
    left = _config(seed=1)
    right = _config(seed=2)
    async with await SimulationRunner.from_config(
        left, run_id=RunId("run-seed-1")
    ) as runner:
        result_left = await runner.run()
    async with await SimulationRunner.from_config(
        right, run_id=RunId("run-seed-2")
    ) as runner:
        result_right = await runner.run()
    assert (
        build_runner_result_document(result=result_left, config=left).exact_trajectory_hash
        != build_runner_result_document(
            result=result_right, config=right
        ).exact_trajectory_hash
    )


@pytest.mark.asyncio
async def test_experiment_a_arms_share_stochastic_identity() -> None:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    base = base_runner_config_from_scenario(
        seed=5,
        stochastic_identity="cmp-pair",
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
        max_ticks=1,
    )
    definition = experiment_a_memory(base)
    results = await ExperimentCoordinator(definition).run_all()
    assert len(results) == 2
    assert (
        results[0].assignment.runner_config.stochastic_identity
        == results[1].assignment.runner_config.stochastic_identity
    )
    assert results[0].assignment.runner_config.agents[0].cognition.memory_mode != (
        results[1].assignment.runner_config.agents[0].cognition.memory_mode
    )
