"""Off-gate catalog arm for owned generational_population."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments import (
    experiment_ae_generational_population,
    generational_population_profile,
    v3_scaffolding_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import AgentCreated, AgentEnteredWorld, LifecycleStageChanged
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.generational_population_catalog_arm")


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=83,
        stochastic_identity="cmp-ae-generational",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ae-generational"),
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
        max_ticks=12,
    )


def test_v3_scaffolding_still_requires_all_v3_flags_off() -> None:
    config = _base()
    assert v3_scaffolding_profile(config) is config
    definition = experiment_ae_generational_population(config)
    off = definition.conditions[0].runner_config
    on = definition.conditions[1].runner_config
    assert v3_scaffolding_profile(off) is off
    with pytest.raises(ValueError, match="v3_scaffolding_flags_enabled"):
        v3_scaffolding_profile(on)


def test_generational_population_profile_accepts_owned_arm() -> None:
    definition = experiment_ae_generational_population(_base(), max_ticks=10)
    assert definition.experiment_id == "experiment-ae-generational-population"
    assert len(definition.conditions) == 2
    on = next(
        item
        for item in definition.conditions
        if item.condition_id == "ae-generational-on"
    )
    assert generational_population_profile(on.runner_config) is on.runner_config
    assert on.runner_config.v3_capability_flags == V3CapabilityFlags(
        generational_population=True
    )


@pytest.mark.asyncio
async def test_catalog_arm_emits_lifecycle_event_kinds() -> None:
    definition = experiment_ae_generational_population(_base(), max_ticks=12)
    config = next(
        item.runner_config
        for item in definition.conditions
        if item.condition_id == "ae-generational-on"
    )
    _LOG.info(
        "case_id=ae_catalog_run experiment_id=%s flag=generational_population "
        "tick_count=%s",
        definition.experiment_id,
        config.stop_policy.max_ticks,
    )
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-ae-generational")
    )
    kinds: set[str] = set()
    for _ in range(10):
        await runner.run_tick()
        assert runner.engine.last_tick_result is not None
        for record in runner.engine.last_tick_result.events:
            details = record.event.details
            if type(details) in {
                LifecycleStageChanged,
                AgentCreated,
                AgentEnteredWorld,
            }:
                kinds.add(details.kind)
    _LOG.debug(
        "case_id=ae_catalog_run lifecycle_event_kinds=%s population=%s",
        sorted(kinds),
        len(runner.engine.ordered_registrations),
    )
    assert "lifecycle_stage_changed" in kinds
    assert "agent_created" in kinds
    assert "agent_entered_world" in kinds
    assert len(runner.engine.ordered_registrations) >= 2
