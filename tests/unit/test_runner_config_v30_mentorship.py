"""runner-config-v30 mentorship encode/decode and gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MentorshipSpec,
    SkillLearningMode,
    TeachingInteractionMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_developmental_learning_spec,
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
        seed=30,
        stochastic_identity="cmp-v30-mentorship",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v30"),
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


def _mentorship_config(**extra):
    base = _plain_base()
    payload = {
        "schema_version": RUNNER_SCHEMA_VERSION_V30,
        "agents": _with_teaching(base.agents),
        "v3_capability_flags": V3CapabilityFlags(generational_population=True),
        "population_lifecycle": example_population_lifecycle_spec(),
        "new_agent_initialization": default_new_agent_initialization_spec(),
        "mentorship": example_mentorship_spec(),
    }
    payload.update(extra)
    return replace(base, **payload)


def test_mentorship_v30_round_trip() -> None:
    config = _mentorship_config()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V30
    assert round_trip.mentorship is not None
    assert round_trip.mentorship.enabled_content_kinds == (
        "practical_skills",
        "factual_beliefs",
        "warnings",
    )
    assert round_trip.developmental_learning is None


def test_mentorship_with_developmental_learning_round_trip() -> None:
    config = _mentorship_config(
        developmental_learning=example_developmental_learning_spec()
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.mentorship is not None
    assert round_trip.developmental_learning is not None


def test_mentorship_requires_v30() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="mentorship_requires_v30"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V29,
            agents=_with_teaching(base.agents),
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
            population_lifecycle=example_population_lifecycle_spec(),
            new_agent_initialization=default_new_agent_initialization_spec(),
            developmental_learning=example_developmental_learning_spec(),
            mentorship=example_mentorship_spec(),
        )


def test_mentorship_requires_lifecycle_flag() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="mentorship_without_lifecycle_flag"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V30,
            agents=_with_teaching(base.agents),
            v3_capability_flags=V3CapabilityFlags(generational_population=False),
            mentorship=example_mentorship_spec(),
        )


def test_mentorship_mode_disabled_rejected() -> None:
    with pytest.raises(ValueError, match="mentorship_mode_invalid"):
        MentorshipSpec(
            enabled_content_kinds=("practical_skills",),
            mentorship_mode="disabled",
        )


def test_mentorship_requires_teaching() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="mentorship_requires_teaching"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V30,
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
            population_lifecycle=example_population_lifecycle_spec(),
            new_agent_initialization=default_new_agent_initialization_spec(),
            mentorship=example_mentorship_spec(),
        )


def test_matrix_finalize_prefers_mentorship_over_developmental_learning() -> None:
    both = _mentorship_config(
        developmental_learning=example_developmental_learning_spec()
    )
    finalized = finalize_matrix_cell_config(both)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V30
    base = _plain_base()
    dev_only = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V29,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        developmental_learning=example_developmental_learning_spec(),
    )
    assert (
        finalize_matrix_cell_config(dev_only).schema_version
        == RUNNER_SCHEMA_VERSION_V29
    )


def test_v29_decode_synthesizes_no_mentorship() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V29,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        developmental_learning=example_developmental_learning_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.mentorship is None
