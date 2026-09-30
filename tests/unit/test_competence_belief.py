"""Subjective competence stays a separate store from objective skill."""

from __future__ import annotations

import logging
import math

import pytest

from agents.cognition.competence import (
    CompetenceDomain,
    CompetenceUpdateChannel,
    apply_belief_channel,
    default_competence_belief_policy,
    empty_competence_model,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionSkillLearningMode,
)
from agents.models import AgentId
from world._skills import ObjectiveSkillLedger


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def test_success_belief_uses_prior_not_the_raw_rate() -> None:
    policy = default_competence_belief_policy()
    model = empty_competence_model(AgentId("agent-1"))
    updated = apply_belief_channel(
        model,
        CompetenceDomain.FORAGING,
        CompetenceUpdateChannel.SUCCESS,
        policy,
    )
    belief = updated.belief_for(CompetenceDomain.FORAGING)
    assert belief.support_mass == policy.belief_success_rate
    assert belief.counter_mass == 0.0
    assert belief.believed_level == _quantize(0.10 / 1.10)


def test_failure_belief_support_stays_zero() -> None:
    policy = default_competence_belief_policy()
    model = empty_competence_model(AgentId("agent-1"))
    updated = apply_belief_channel(
        model,
        CompetenceDomain.FORAGING,
        CompetenceUpdateChannel.FAILURE,
        policy,
    )
    belief = updated.belief_for(CompetenceDomain.FORAGING)
    assert belief.support_mass == 0.0
    assert belief.counter_mass == 0.0
    assert belief.believed_level == 0.0


def test_policy_construction_logs_and_rejects_weight(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.competence")
    policy = default_competence_belief_policy()
    assert policy.version == "competence-belief-v1"
    assert policy.allow_provider is False
    debug = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.DEBUG
    ]
    assert any("policy_version=competence-belief-v1" in line for line in debug)
    assert any("domain_count=8" in line for line in debug)
    caplog.clear()
    with pytest.raises(ValueError, match="out_of_range"):
        type(policy)(belief_action_weight=1.5)
    assert "reason_code=out_of_range" in caplog.text


def test_non_finite_belief_rate_logs_reason_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="agents.cognition.competence")
    with pytest.raises(ValueError, match="not_finite"):
        default_competence_belief_policy().__class__(belief_success_rate=math.inf)
    assert "field=belief_success_rate" in caplog.text
    assert "reason_code=not_finite" in caplog.text


def test_objective_ledger_is_not_a_belief_argument() -> None:
    policy = default_competence_belief_policy()
    model = empty_competence_model(AgentId("agent-1"))
    with pytest.raises(TypeError):
        apply_belief_channel(
            model,
            CompetenceDomain.FORAGING,
            CompetenceUpdateChannel.SUCCESS,
            policy,
            ledger=ObjectiveSkillLedger.bootstrap(()),
        )


def test_skill_learning_mode_defaults_disabled() -> None:
    config = CognitionLoopConfig()
    assert config.skill_learning_mode is CognitionSkillLearningMode.DISABLED
    assert config.competence_belief_policy is None
    material = config.condition_fingerprint_material()
    assert material["skill_learning_mode"] == "disabled"
    assert material["competence_belief_policy_version"] is None
    enabled = CognitionLoopConfig(
        skill_learning_mode=CognitionSkillLearningMode.DETERMINISTIC
    )
    assert enabled.competence_belief_policy is not None
    assert enabled.competence_belief_policy.version == "competence-belief-v1"
    assert enabled.competence_belief_policy.allow_provider is False
