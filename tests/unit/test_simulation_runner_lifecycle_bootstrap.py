"""Bootstrap lifecycle seeding when generational_population is owned/on."""

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
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.lifecycle import OriginProvenance
from world.models import default_physical_rules

_LOG = logging.getLogger("tests.simulation_runner_lifecycle_bootstrap")


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=5,
        stochastic_identity="cmp-lifecycle-bootstrap",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-lifecycle-boot"),
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
        max_ticks=2,
    )


@pytest.mark.asyncio
async def test_flag_off_does_not_seed_lifecycle_records() -> None:
    _LOG.debug("case_id=flag_off_no_lifecycle")
    runner = await SimulationRunner.from_config(
        _base(), run_id=RunId("run-lifecycle-off")
    )
    assert runner.engine.lifecycle_channel_active is False
    assert runner.engine.lifecycle_records == ()


@pytest.mark.asyncio
async def test_flag_on_seeds_bootstrap_lifecycle_without_birth_events() -> None:
    _LOG.debug("case_id=flag_on_bootstrap_seed")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
    )
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-lifecycle-on")
    )
    assert runner.engine.lifecycle_channel_active is True
    records = runner.engine.lifecycle_records
    assert len(records) == 1
    record = records[0]
    assert record.entry_tick == 0
    assert record.provenance is OriginProvenance.BOOTSTRAP
    assert record.cohort_id == "cohort-bootstrap"
    assert record.generation_index == 0
    # Bootstrap does not emit created/entered events.
    assert runner.engine.last_tick_result is None
