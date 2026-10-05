"""Off-gate Experiment AF for NewAgentInitialization on runner-config-v25."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments import (
    experiment_af_new_agent_bootstrap,
    new_agent_bootstrap_profile,
    v3_scaffolding_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V25,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import AgentInitializationRecorded
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.new_agent_bootstrap_catalog_arm")


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=113,
        stochastic_identity="cmp-af-new-agent",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-af-new-agent"),
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


def test_af_profile_requires_v25_and_explicit_init() -> None:
    definition = experiment_af_new_agent_bootstrap(_base(), max_ticks=10)
    assert definition.experiment_id == "experiment-af-new-agent-bootstrap"
    on = next(
        item
        for item in definition.conditions
        if item.condition_id == "af-new-agent-on"
    )
    assert on.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V25
    assert new_agent_bootstrap_profile(on.runner_config) is on.runner_config
    off = definition.conditions[0].runner_config
    assert v3_scaffolding_profile(off) is off
    with pytest.raises(ValueError, match="v3_scaffolding_flags_enabled"):
        v3_scaffolding_profile(on.runner_config)


@pytest.mark.asyncio
async def test_af_on_arm_emits_initialization_recorded() -> None:
    definition = experiment_af_new_agent_bootstrap(_base(), max_ticks=8)
    on = next(
        item
        for item in definition.conditions
        if item.condition_id == "af-new-agent-on"
    )
    _LOG.info(
        "case_id=af_on_arm experiment_id=%s schema_version=%s",
        definition.experiment_id,
        on.runner_config.schema_version,
    )
    async with await SimulationRunner.from_config(
        on.runner_config, run_id=RunId("run-af-on")
    ) as runner:
        await runner.run()
        assert runner.engine.new_agent_provenance_active is True
        assert on.runner_config.v3_capability_flags == V3CapabilityFlags(
            generational_population=True
        )
        init_events = [
            event
            for event in runner.engine._snapshot.event_history
            if type(event.details) is AgentInitializationRecorded
        ]
        _LOG.debug(
            "case_id=af_on_arm init_event_count=%s registration_count=%s",
            len(init_events),
            len(runner.engine.ordered_registrations),
        )
        assert len(init_events) >= 1
        assert len(runner.engine.ordered_registrations) > 1
