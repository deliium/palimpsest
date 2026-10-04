"""V3 capability flag defaults and scaffolding / V2 regression profiles."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments import v2_regression_profile, v3_scaffolding_profile
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V23,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=3,
        stochastic_identity="cmp-v3-flag-defaults",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-flags"),
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


def test_base_builder_defaults_v3_flags_off() -> None:
    config = _base()
    assert config.v3_capability_flags == V3CapabilityFlags()
    assert v3_scaffolding_profile(config) is config
    assert v2_regression_profile(config) is config


def test_v3_scaffolding_profile_rejects_enabled_flag() -> None:
    flagged = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V23,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    with pytest.raises(ValueError, match="v3_scaffolding_flags_enabled"):
        v3_scaffolding_profile(flagged)
    with pytest.raises(ValueError, match="v3_scaffolding_flags_enabled"):
        v2_regression_profile(flagged)
