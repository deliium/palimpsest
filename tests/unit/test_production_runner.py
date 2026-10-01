"""Runner schema v13 is emitted only for opt-in production."""

from __future__ import annotations

import json

import pytest

from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V12,
    RUNNER_SCHEMA_VERSION_V13,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ProductionKnowledgeMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from tests.unit.test_runner_serialization import _configured
from world.production import example_production_catalog


def _with_cognition(
    base: SimulationRunnerConfig,
    cognition: AgentCognitionSpec,
    *,
    schema_version: str,
) -> SimulationRunnerConfig:
    agent = base.agents[0]
    return SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        schema_version=schema_version,
        agents=(
            AgentRunnerSpec(
                agent_id=agent.agent_id,
                entity_id=agent.entity_id,
                cognition=cognition,
            ),
        ),
        stop_policy=base.stop_policy,
    )


def test_default_write_stays_v4_without_production_keys() -> None:
    encoded = encode_runner_config(_configured(schema_version=RUNNER_SCHEMA_VERSION))
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v4"
    cognition = document["agents"][0]["cognition"]
    assert "production_knowledge_mode" not in cognition
    assert "production_catalog" not in cognition


def test_teaching_only_stays_v12() -> None:
    config = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V12,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
    )
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    assert document["schema_version"] == "runner-config-v12"
    cognition = document["agents"][0]["cognition"]
    assert "production_catalog" not in cognition


def test_catalog_round_trips_only_on_v13() -> None:
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    agent = base.agents[0]
    catalog = example_production_catalog()
    config = _with_cognition(
        base,
        AgentCognitionSpec(
            agent_id=agent.agent_id,
            memory_mode=agent.cognition.memory_mode,
            drive_overrides=agent.cognition.drive_overrides,
            production_catalog=catalog,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V13,
    )
    encoded = encode_runner_config(config)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v13"
    cognition = document["agents"][0]["cognition"]
    assert cognition["production_knowledge_mode"] == "disabled"
    assert len(cognition["production_catalog"]) == 6
    assert decode_runner_config(encoded) == config


def test_deterministic_mode_with_empty_catalog_is_v13() -> None:
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    agent = base.agents[0]
    config = _with_cognition(
        base,
        AgentCognitionSpec(
            agent_id=agent.agent_id,
            memory_mode=agent.cognition.memory_mode,
            drive_overrides=agent.cognition.drive_overrides,
            production_knowledge_mode=ProductionKnowledgeMode.DETERMINISTIC,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V13,
    )
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    assert document["schema_version"] == "runner-config-v13"
    assert document["agents"][0]["cognition"]["production_catalog"] == []


def test_v13_without_production_is_rejected() -> None:
    with pytest.raises(ValueError, match="v13_requires_production"):
        _configured(schema_version=RUNNER_SCHEMA_VERSION_V13)


def test_earlier_schema_rejects_production() -> None:
    base = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V12,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
    )
    agent = base.agents[0]
    with pytest.raises(ValueError, match="production_requires_v13"):
        _with_cognition(
            base,
            AgentCognitionSpec(
                agent_id=agent.agent_id,
                memory_mode=agent.cognition.memory_mode,
                drive_overrides=agent.cognition.drive_overrides,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
                production_catalog=example_production_catalog(),
            ),
            schema_version=RUNNER_SCHEMA_VERSION_V12,
        )


def test_v13_keeps_skill_and_teaching_legal() -> None:
    base = _configured(schema_version=RUNNER_SCHEMA_VERSION)
    agent = base.agents[0]
    config = _with_cognition(
        base,
        AgentCognitionSpec(
            agent_id=agent.agent_id,
            memory_mode=agent.cognition.memory_mode,
            drive_overrides=agent.cognition.drive_overrides,
            skill_learning_mode=SkillLearningMode.DETERMINISTIC,
            teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
            production_knowledge_mode=ProductionKnowledgeMode.DETERMINISTIC,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V13,
    )
    assert decode_runner_config(encode_runner_config(config)) == config
