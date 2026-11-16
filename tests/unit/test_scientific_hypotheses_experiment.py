# mypy: ignore-errors
"""Off-gate registration and three-arm composition for V4-27."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_scientific_hypotheses,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base():
    body = alive_body("body-1")
    owner = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-science-experiment",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-science-experiment"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=owner,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=owner),
            ),
        ),
        max_ticks=64,
    )


def test_registration_and_off_gate() -> None:
    definition = experiment_scientific_hypotheses(_base(), max_ticks=64)
    assert definition.experiment_id == "scientific_hypotheses@1"
    assert "scientific_hypotheses@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert () == tuple(
        condition
        for condition in EXPERIMENT_A_V1_CONDITION_IDS
        if "scientific" in condition
    )
    assert len(definition.conditions) == 3


def test_three_ordered_arms_and_flags() -> None:
    definition = experiment_scientific_hypotheses(_base(), max_ticks=64)
    ids = tuple(condition.condition_id for condition in definition.conditions)
    assert ids == (
        "science-baseline",
        "science-enabled",
        "science-communicated",
    )
    for condition in definition.conditions:
        config = condition.runner_config
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V56
        assert config.bounded_experimentation is not None
        assert config.v3_capability_flags.cultural_historical_memory is True
    baseline, enabled, communicated = definition.conditions
    assert baseline.runner_config.v4_capability_flags.science is False
    assert baseline.runner_config.capability_flags.predictive_world_model is False
    for condition in (enabled, communicated):
        assert condition.runner_config.v4_capability_flags.science is True
        assert (
            condition.runner_config.capability_flags.predictive_world_model
            is True
        )
    assert (
        communicated.runner_config.agents[0].cognition.communication_strategy_mode.value
        == "deterministic"
    )


def test_unowned_flags_stay_false() -> None:
    definition = experiment_scientific_hypotheses(_base(), max_ticks=64)
    for condition in definition.conditions:
        flags = condition.runner_config.v4_capability_flags
        assert flags.epidemics is False
        assert flags.ecological_feedback is False
        assert flags.disasters is False


def test_min_ticks_rejected() -> None:
    with pytest.raises(ValueError, match="scientific_hypotheses_min_ticks"):
        experiment_scientific_hypotheses(_base(), max_ticks=32)
