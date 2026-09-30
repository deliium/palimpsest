"""Teaching mode stays off the v11 schema and fails closed on bad wiring."""

from __future__ import annotations

import inspect
import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V11,
    RUNNER_SCHEMA_VERSION_V12,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    SkillLearningMode,
    TeachingInteractionMode,
    V2CapabilityFlags,
)
from tests.simulation_helpers import alive_body
from tests.unit.test_runner_models import _config


def _with_modes(
    schema_version: str,
    *,
    skill: SkillLearningMode,
    teaching: TeachingInteractionMode,
) -> object:
    base = _config()
    agent = base.agents[0]
    spec = replace(
        agent.cognition,
        skill_learning_mode=skill,
        teaching_interaction_mode=teaching,
    )
    return replace(
        base,
        agents=(replace(agent, cognition=spec),),
        schema_version=schema_version,
    )


def _cognition(agent_id: AgentId, *, demonstration_rate: float) -> AgentCognitionSpec:
    base = _config().agents[0].cognition
    return replace(
        base,
        agent_id=agent_id,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        demonstration_rate=demonstration_rate,
    )


def test_teaching_requires_skill_learning_and_shared_weights(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="simulation.runner_models")
    with pytest.raises(ValueError, match="teaching_requires_skill_learning"):
        _with_modes(
            RUNNER_SCHEMA_VERSION_V12,
            skill=SkillLearningMode.DISABLED,
            teaching=TeachingInteractionMode.DETERMINISTIC,
        )
    with pytest.raises(ValueError, match="teaching_interaction_mode_requires_v12"):
        _with_modes(
            RUNNER_SCHEMA_VERSION_V11,
            skill=SkillLearningMode.DETERMINISTIC,
            teaching=TeachingInteractionMode.DETERMINISTIC,
        )
    base = _config()
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    with pytest.raises(ValueError, match="teaching_weight_mismatch"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V12,
            scenario=replace(base.scenario, bodies=(body_a, body_b)),
            agents=(
                AgentRunnerSpec(
                    agent_id=AgentId("agent-a"),
                    entity_id=body_a.entity_id,
                    cognition=_cognition(AgentId("agent-a"), demonstration_rate=0.02),
                ),
                AgentRunnerSpec(
                    agent_id=AgentId("agent-b"),
                    entity_id=body_b.entity_id,
                    cognition=_cognition(AgentId("agent-b"), demonstration_rate=0.03),
                ),
            ),
        )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "reason_code=teaching_requires_skill_learning" in messages
    assert "reason_code=teaching_weight_mismatch" in messages
    assert "agent_count=" in messages
    assert "0.03" not in messages


def test_cognition_config_logs_teaching_mode(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.runner_models")
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    disabled = _config()
    validated = " ".join(
        record.getMessage()
        for record in caplog.records
        if "runner_config_validated" in record.getMessage()
    )
    assert "teaching_interaction_mode=disabled" in validated
    enabled = _with_modes(
        RUNNER_SCHEMA_VERSION_V12,
        skill=SkillLearningMode.DETERMINISTIC,
        teaching=TeachingInteractionMode.DETERMINISTIC,
    )
    built = _cognition_config_for(
        enabled.agents[0].cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert built.teaching_interaction_mode.value == "deterministic"
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "cognition_config_teaching_mode mode=deterministic" in messages
    assert "policy_version=teaching-interaction-v1" in messages
    assert "teaching_interaction_mode=deterministic" in messages
    off = _cognition_config_for(
        disabled.agents[0].cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert off.teaching_interaction_mode.value == "disabled"
    assert "cognition_config_teaching_mode mode=disabled policy_version=None" in (
        " ".join(record.getMessage() for record in caplog.records)
    )


def test_engine_teaching_policy_defaults_to_none() -> None:
    parameters = inspect.signature(WorldEngine.__init__).parameters
    assert parameters["teaching_policy"].default is None
    assert parameters["teaching_entity_ids"].default is None
    restored = inspect.signature(WorldEngine.restore_from_snapshot).parameters
    assert restored["teaching_policy"].default is None
    assert restored["teaching_entity_ids"].default is None
