"""runner-config-v28 dependency_care encode/decode and gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_dependency_care_spec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _two_agent_base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=28,
        stochastic_identity="cmp-v28-dependency-care",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v28"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
            AgentRunnerSpec(
                agent_id=agent_b,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_b),
            ),
        ),
        max_ticks=2,
    )


def test_dependency_care_v28_round_trip() -> None:
    base = _two_agent_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V28,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=example_dependency_care_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V28
    assert round_trip.dependency_care is not None
    assert round_trip.dependency_care.enabled_needs == ("food", "water", "safety")
    assert round_trip.dependency_care.caregiving_cognition_mode == "disabled"


def test_dependency_care_requires_v28() -> None:
    base = _two_agent_base()
    with pytest.raises(ValueError, match="dependency_care_requires_v28"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V27,
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
            population_lifecycle=example_population_lifecycle_spec(),
            new_agent_initialization=default_new_agent_initialization_spec(),
            dependency_care=example_dependency_care_spec(),
        )


def test_dependency_care_requires_lifecycle_flag() -> None:
    base = _two_agent_base()
    with pytest.raises(ValueError, match="dependency_care_without_lifecycle_flag"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V28,
            v3_capability_flags=V3CapabilityFlags(generational_population=False),
            dependency_care=example_dependency_care_spec(),
        )


def test_dependency_care_forbids_empty_needs() -> None:
    from simulation.runner_models import DependencyCareSpec

    with pytest.raises(ValueError, match="dependency_care_enabled_needs_empty"):
        DependencyCareSpec(enabled_needs=(), need_policies={})
