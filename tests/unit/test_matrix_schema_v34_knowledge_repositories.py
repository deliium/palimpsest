"""Matrix finalize priority for knowledge_repositories_on (v34)."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V33,
    RUNNER_SCHEMA_VERSION_V34,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

pytestmark = pytest.mark.unit


def _base():
    body = alive_body("body-a")
    return base_runner_config_from_scenario(
        seed=340,
        stochastic_identity="cmp-matrix-v34",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-matrix-v34"),
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


def test_knowledge_repositories_on_beats_durable_records_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    both = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V34,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=example_knowledge_repositories_spec(),
        population_lifecycle=None,
        new_agent_initialization=None,
        mentorship=None,
        historical_memory_layers=None,
        artifacts_enabled=True,
    )
    with caplog.at_level(logging.DEBUG, logger="experiments.matrix_schema"):
        finalized = finalize_matrix_cell_config(both)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V34
    assert "knowledge_repositories_on" in caplog.text


def test_durable_only_stays_v33() -> None:
    durable_only = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V33,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=None,
        population_lifecycle=None,
        new_agent_initialization=None,
        mentorship=None,
        historical_memory_layers=None,
        artifacts_enabled=True,
    )
    finalized = finalize_matrix_cell_config(durable_only)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V33
