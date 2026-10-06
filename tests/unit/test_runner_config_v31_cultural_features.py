"""runner-config-v31 cultural_feature_provenance encode/decode and gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V23,
    RUNNER_SCHEMA_VERSION_V31,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CulturalFeatureProvenanceSpec,
    SkillLearningMode,
    TeachingInteractionMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_kinship_spec,
    example_mentorship_spec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _plain_base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=31,
        stochastic_identity="cmp-v31-cultural",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v31"),
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


def _with_teaching(agents):
    return tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
            ),
        )
        for agent in agents
    )


def _cultural_only_config(**extra):
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        **extra,
    )


def test_cultural_only_v31_round_trip() -> None:
    config = _cultural_only_config()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V31
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.v3_capability_flags.cultural_historical_memory is True
    assert round_trip.population_lifecycle is None
    assert list(round_trip.cultural_feature_provenance.enabled_feature_kinds) == [
        "practice",
        "term",
        "narrative_element",
    ]


def test_cultural_without_flag_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="cultural_feature_without_flag"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V31,
            v3_capability_flags=V3CapabilityFlags(),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        )


def test_flag_without_object_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="cultural_feature_requires_flag"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V23,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        )


def test_object_requires_v31() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="cultural_feature_requires_v31"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V23,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        )


def test_v31_requires_cultural_object() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="v31_requires_cultural_feature_provenance"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V31,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        )


def test_mode_disabled_rejected() -> None:
    with pytest.raises(ValueError, match="cultural_feature_mode_invalid"):
        CulturalFeatureProvenanceSpec(
            enabled_feature_kinds=("practice",),
            enabled_provenance_channels=("observation",),
            cultural_feature_mode="disabled",
        )


def test_cultural_only_forbids_lifecycle() -> None:
    with pytest.raises(ValueError, match="cultural_only_forbids_lifecycle_spec"):
        _cultural_only_config(
            population_lifecycle=example_population_lifecycle_spec(),
        )


def test_cultural_only_forbids_new_agent_init() -> None:
    with pytest.raises(ValueError, match="cultural_only_forbids_new_agent_init"):
        _cultural_only_config(
            new_agent_initialization=default_new_agent_initialization_spec(),
        )


def test_kinship_plus_cultural_allowed() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        v3_capability_flags=V3CapabilityFlags(
            cultural_historical_memory=True,
            kinship_inheritance=True,
        ),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        kinship=example_kinship_spec(
            parent_agent_id="agent-a",
            child_agent_id="agent-b",
        ),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.kinship is not None
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.population_lifecycle is None


def test_matrix_finalize_cultural_before_mentorship() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        agents=_with_teaching(base.agents),
        v3_capability_flags=V3CapabilityFlags(
            generational_population=True,
            cultural_historical_memory=True,
        ),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        mentorship=example_mentorship_spec(),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
    )
    finalized = finalize_matrix_cell_config(config)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V31
