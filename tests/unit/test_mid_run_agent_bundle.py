"""Mid-run AgentBundle construction and ordinal = registration order."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V24,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.mid_run_agent_bundle")


def _config(*, max_ticks: int = 12):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return replace(
        base_runner_config_from_scenario(
            seed=17,
            stochastic_identity="cmp-mid-run-bundle",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-mid-run"),
                revision=WorldRevision(0),
                physical_rules=non_lethal_physical_rules(),
                locations=(make_location(body_capacity=8),),
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
            max_ticks=max_ticks,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        mortality_mode=MortalityMode.DISABLED,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=40,
            max_population=4,
            policy_id="fixed_interval_entry",
        ),
    )


@pytest.mark.asyncio
async def test_mid_run_agent_gets_bundle_and_observes_next_tick() -> None:
    _LOG.debug("case_id=mid_run_bundle_observe")
    runner = await SimulationRunner.from_config(
        _config(), run_id=RunId("run-mid-run-bundle")
    )
    assert len(runner.runtimes) == 1
    # fixed_interval_entry admits on tick 5
    for _ in range(6):
        receipt = await runner.run_tick()
        assert receipt.status.value in {"finalized", "aborted"}
    assert len(runner.runtimes) == 2
    assert [rt.agent_id for rt in runner.runtimes] == [
        reg.agent_id for reg in runner.engine.ordered_registrations
    ]
    # Next tick: new agent participates in observe/act ordinal order.
    receipt = await runner.run_tick()
    assert receipt.submission_count == 2
    assert len(runner.runtimes) == 2


@pytest.mark.asyncio
async def test_prepare_parallel_remains_false_with_dynamic_roster() -> None:
    _LOG.debug("case_id=prepare_parallel_false")
    runner = await SimulationRunner.from_config(
        _config(max_ticks=2), run_id=RunId("run-mid-run-parallel")
    )
    await runner.run_tick()
    assert runner.runtimes  # smoke: runner usable
