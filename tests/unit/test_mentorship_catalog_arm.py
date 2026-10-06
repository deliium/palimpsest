"""Off-gate Experiment AK for intergenerational mentorship on runner-config-v30."""

from __future__ import annotations

import logging

from agents.models import AgentId
from experiments import (
    experiment_ak_intergenerational_mentorship,
    generational_population_profile,
    intergenerational_mentorship_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V30,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.mentorship_catalog_arm")


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=208,
        stochastic_identity="cmp-ak-intergenerational-mentorship",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ak-mentor"),
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


def test_ak_profile_and_arms() -> None:
    _LOG.debug("case_id=ak_catalog_arms")
    definition = experiment_ak_intergenerational_mentorship(_base(), max_ticks=6)
    assert definition.experiment_id == "experiment-ak-intergenerational-mentorship"
    condition_ids = tuple(item.condition_id for item in definition.conditions)
    assert condition_ids == (
        "ak-channel-off",
        "ak-ephemeral",
        "ak-bonded",
        "ak-chain",
        "ak-mutation",
        "ak-false-teaching",
    )
    off = definition.conditions[0].runner_config
    assert generational_population_profile(off) is off
    assert off.mentorship is None
    assert off.v3_capability_flags.generational_population is True
    bonded = next(
        item for item in definition.conditions if item.condition_id == "ak-bonded"
    ).runner_config
    assert bonded.schema_version == RUNNER_SCHEMA_VERSION_V30
    assert intergenerational_mentorship_profile(bonded) is bonded
    assert bonded.mentorship is not None
    assert "practical_skills" in bonded.mentorship.enabled_content_kinds
    mutation = next(
        item for item in definition.conditions if item.condition_id == "ak-mutation"
    ).runner_config
    assert mutation.mentorship.lineage_policy.allow_learner_mutation is True
