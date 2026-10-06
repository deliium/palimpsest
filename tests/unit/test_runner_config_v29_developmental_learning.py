"""runner-config-v29 developmental_learning encode/decode and gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    AgentCognitionSpec,
    AgentRunnerSpec,
    DevelopmentalLearningSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_dependency_care_spec,
    example_developmental_learning_spec,
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
        seed=29,
        stochastic_identity="cmp-v29-developmental-learning",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v29"),
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


def test_developmental_learning_v29_round_trip() -> None:
    base = _two_agent_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V29,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        developmental_learning=example_developmental_learning_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V29
    assert round_trip.developmental_learning is not None
    assert round_trip.developmental_learning.enabled_domains == (
        "locations",
        "resources",
        "hazards",
        "skills",
    )
    assert round_trip.dependency_care is None


def test_developmental_learning_with_dependency_care_round_trip() -> None:
    base = _two_agent_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V29,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=example_dependency_care_spec(),
        developmental_learning=example_developmental_learning_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.dependency_care is not None
    assert round_trip.developmental_learning is not None


def test_developmental_learning_requires_v29() -> None:
    base = _two_agent_base()
    with pytest.raises(ValueError, match="developmental_learning_requires_v29"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V28,
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
            population_lifecycle=example_population_lifecycle_spec(),
            new_agent_initialization=default_new_agent_initialization_spec(),
            dependency_care=example_dependency_care_spec(),
            developmental_learning=example_developmental_learning_spec(),
        )


def test_developmental_learning_requires_lifecycle_flag() -> None:
    base = _two_agent_base()
    with pytest.raises(
        ValueError, match="developmental_learning_without_lifecycle_flag"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V29,
            v3_capability_flags=V3CapabilityFlags(generational_population=False),
            developmental_learning=example_developmental_learning_spec(),
        )


def test_developmental_learning_mode_disabled_rejected() -> None:
    with pytest.raises(ValueError, match="developmental_learning_mode_invalid"):
        DevelopmentalLearningSpec(
            enabled_domains=("locations",),
            enabled_sources=("observation",),
            domain_rates={
                "locations": {
                    "base_rate": 1.0,
                    "stage_compose": "multiply_lifecycle_learning_rate",
                    "min_exposures": 0,
                    "confidence_floor": 0.0,
                }
            },
            source_weights={"observation": 1.0},
            developmental_learning_mode="disabled",
        )


def test_matrix_finalize_prefers_developmental_learning_over_dependency_care() -> None:
    base = _two_agent_base()
    both = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V29,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=example_dependency_care_spec(),
        developmental_learning=example_developmental_learning_spec(),
    )
    assert finalize_matrix_cell_config(both).schema_version == RUNNER_SCHEMA_VERSION_V29
    care_only = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V28,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=example_dependency_care_spec(),
    )
    assert (
        finalize_matrix_cell_config(care_only).schema_version
        == RUNNER_SCHEMA_VERSION_V28
    )
