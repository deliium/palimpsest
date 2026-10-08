"""Matrix finalize priority for bounded_experimentation_on (v36)."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V35,
    RUNNER_SCHEMA_VERSION_V36,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_bounded_experimentation_spec,
    example_cultural_feature_provenance_spec,
    example_knowledge_genealogy_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

pytestmark = pytest.mark.unit


def _base():
    body = alive_body("body-a")
    return base_runner_config_from_scenario(
        seed=360,
        stochastic_identity="cmp-matrix-v36",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-matrix-v36"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=4),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-a"),
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
            ),
        ),
        max_ticks=4,
    )


def test_bounded_experimentation_on_beats_knowledge_genealogy_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    both = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V36,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
        bounded_experimentation=example_bounded_experimentation_spec(),
        population_lifecycle=None,
        new_agent_initialization=None,
        mentorship=None,
        historical_memory_layers=None,
        artifacts_enabled=True,
    )
    with caplog.at_level(logging.DEBUG, logger="experiments.matrix_schema"):
        finalized = finalize_matrix_cell_config(both)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V36
    assert "bounded_experimentation_on" in caplog.text


def test_genealogy_without_experimentation_stays_v35() -> None:
    genealogy = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V35,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
        bounded_experimentation=None,
        population_lifecycle=None,
        new_agent_initialization=None,
        artifacts_enabled=True,
    )
    finalized = finalize_matrix_cell_config(genealogy)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V35
