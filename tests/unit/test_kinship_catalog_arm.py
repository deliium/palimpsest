"""Off-gate Experiment AH for objective kinship genealogy on runner-config-v27."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments import (
    experiment_ah_kinship_genealogy,
    kinship_genealogy_profile,
    v3_scaffolding_profile,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V27,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.kinship_catalog_arm")


def _base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    body_c = alive_body("body-c")
    return base_runner_config_from_scenario(
        seed=205,
        stochastic_identity="cmp-ah-kinship",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-ah-kinship"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=(body_a, body_b, body_c),
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
            AgentRunnerSpec(
                agent_id=AgentId("agent-c"),
                entity_id=body_c.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-c")),
            ),
        ),
        max_ticks=8,
    )


def test_ah_profile_and_arms() -> None:
    _LOG.debug("case_id=ah_catalog_arms")
    definition = experiment_ah_kinship_genealogy(_base(), max_ticks=6)
    assert definition.experiment_id == "experiment-ah-kinship-genealogy"
    condition_ids = tuple(item.condition_id for item in definition.conditions)
    assert condition_ids == (
        "ah-kinship-off",
        "ah-kinship-only-none",
        "ah-kinship-only-public",
        "ah-kinship-combined",
    )
    off = definition.conditions[0].runner_config
    assert v3_scaffolding_profile(off) is off
    only_none = next(
        item
        for item in definition.conditions
        if item.condition_id == "ah-kinship-only-none"
    ).runner_config
    assert only_none.schema_version == RUNNER_SCHEMA_VERSION_V27
    assert kinship_genealogy_profile(only_none) is only_none
    assert only_none.kinship is not None
    assert only_none.kinship.perception_mode == "none"
    assert only_none.population_lifecycle is None
    public = next(
        item
        for item in definition.conditions
        if item.condition_id == "ah-kinship-only-public"
    ).runner_config
    assert public.kinship is not None
    assert public.kinship.perception_mode == "self_incident_public"
    combined = next(
        item
        for item in definition.conditions
        if item.condition_id == "ah-kinship-combined"
    ).runner_config
    assert combined.v3_capability_flags == V3CapabilityFlags(
        kinship_inheritance=True,
        generational_population=True,
    )
    assert combined.population_lifecycle is not None
    assert combined.new_agent_initialization is not None
    with pytest.raises(ValueError, match="v3_scaffolding_flags_enabled"):
        v3_scaffolding_profile(only_none)
