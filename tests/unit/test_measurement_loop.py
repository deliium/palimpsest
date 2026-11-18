# mypy: ignore-errors

"""Live v57 composition enables the owner measurement channel exactly once."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.measurement import MeasurementLedger
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.measurement_scenario import measurement_instruments_scenario
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base():
    bodies = (alive_body("body-1"), alive_body("body-2"))
    agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index + 1}"),
            entity_id=bodies[index].entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index + 1}")),
        )
        for index in range(2)
    )
    return base_runner_config_from_scenario(
        seed=31,
        stochastic_identity="measurement-loop",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-measurement-loop"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=agents,
        max_ticks=1,
    )


def _arm(condition_id: str):
    definition = measurement_instruments_scenario(_base(), max_ticks=64)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == condition_id
    )
    return replace(config, stop_policy=RunnerStopPolicy(max_ticks=1))


@pytest.mark.asyncio
async def test_v57_runner_binds_measurement_channel_and_ledger() -> None:
    runner = await SimulationRunner.from_config(
        _arm("measurement-unbiased"),
        run_id=RunId("run-measurement-loop"),
        factories=RunnerDependencyFactories(),
    )
    assert all(runtime._loop._measurement_enabled for runtime in runner.runtimes)
    async with runner:
        await runner.run()
    ledgers = runner.export_measurement_ledgers()
    assert len(ledgers) == 2
    assert all(type(ledger) is MeasurementLedger for ledger in ledgers)
    assert [ledger.owner_id.value for ledger in ledgers] == [
        "agent-1",
        "agent-2",
    ]


@pytest.mark.asyncio
async def test_absent_spec_keeps_the_channel_off() -> None:
    runner = await SimulationRunner.from_config(
        _arm("measurement-absent"),
        run_id=RunId("run-measurement-off"),
        factories=RunnerDependencyFactories(),
    )
    assert all(
        not runtime._loop._measurement_enabled for runtime in runner.runtimes
    )
    async with runner:
        await runner.run()
    assert runner.export_measurement_ledgers() == ()
