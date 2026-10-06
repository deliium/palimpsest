"""Off-gate Experiment AJ for developmental learning on runner-config-v29."""

from __future__ import annotations

import logging

from agents.models import AgentId
from experiments import (
    developmental_learning_profile,
    experiment_aj_developmental_learning,
    generational_population_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.new_agent_initialization import SPECIES_DEFAULT_DEVELOPMENTAL_V1
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V29,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.developmental_learning_catalog_arm")


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=207,
        stochastic_identity="cmp-aj-developmental-learning",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-aj-dev"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-a"),
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-b"),
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-b")),
            ),
        ),
        max_ticks=8,
    )


def test_aj_profile_and_arms() -> None:
    _LOG.debug("case_id=aj_catalog_arms")
    definition = experiment_aj_developmental_learning(_base(), max_ticks=6)
    assert definition.experiment_id == "experiment-aj-developmental-learning"
    condition_ids = tuple(item.condition_id for item in definition.conditions)
    assert condition_ids == (
        "aj-channel-off",
        "aj-isolated",
        "aj-socialized",
        "aj-artifact",
    )
    off = definition.conditions[0].runner_config
    assert generational_population_profile(off) is off
    assert off.developmental_learning is None
    assert off.v3_capability_flags.generational_population is True
    isolated = next(
        item for item in definition.conditions if item.condition_id == "aj-isolated"
    ).runner_config
    assert isolated.schema_version == RUNNER_SCHEMA_VERSION_V29
    assert developmental_learning_profile(isolated) is isolated
    assert isolated.developmental_learning is not None
    assert isolated.new_agent_initialization is not None
    assert (
        isolated.new_agent_initialization.species_defaults_id
        == SPECIES_DEFAULT_DEVELOPMENTAL_V1
    )
    assert set(isolated.developmental_learning.enabled_sources) == {
        "observation",
        "experimentation",
    }
    socialized = next(
        item for item in definition.conditions if item.condition_id == "aj-socialized"
    ).runner_config
    assert "instruction" in socialized.developmental_learning.enabled_sources
    artifact = next(
        item for item in definition.conditions if item.condition_id == "aj-artifact"
    ).runner_config
    assert "artifact" in artifact.developmental_learning.enabled_sources
