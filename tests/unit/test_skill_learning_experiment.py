"""Experiment R pairs skill mode without joining the V1 regression gate."""

from __future__ import annotations

import logging

import pytest

from experiments.catalog import experiment_r_skill_learning, v1_regression_profile
from simulation.runner_models import RUNNER_SCHEMA_VERSION_V4, RUNNER_SCHEMA_VERSION_V11
from tests.unit.test_v2_flag_defaults import _base

pytestmark = pytest.mark.unit


def test_experiment_r_pairs_schema_and_skill_mode(
    caplog: pytest.LogCaptureFixture,
) -> None:
    base = _base()
    with caplog.at_level(logging.INFO, logger="experiments.catalog"):
        definition = experiment_r_skill_learning(base)
    disabled, enabled = definition.conditions
    assert disabled.condition_id == "r-disabled"
    assert enabled.condition_id == "r-enabled"
    assert disabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert enabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V11
    assert disabled.runner_config.seed == enabled.runner_config.seed
    assert (
        disabled.runner_config.stochastic_identity
        == enabled.runner_config.stochastic_identity
    )
    assert disabled.runner_config.scenario == enabled.runner_config.scenario
    assert all(
        agent.cognition.skill_learning_mode.value == "disabled"
        for agent in disabled.runner_config.agents
    )
    assert all(
        agent.cognition.skill_learning_mode.value == "deterministic"
        for agent in enabled.runner_config.agents
    )
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "experiment_r_built" in messages
    assert "arm_id=r-enabled" in messages
    assert "schema_version=runner-config-v11" in messages
    assert "skill_mode=deterministic" in messages
    profiled = v1_regression_profile(disabled.runner_config)
    assert profiled.schema_version == RUNNER_SCHEMA_VERSION_V4
