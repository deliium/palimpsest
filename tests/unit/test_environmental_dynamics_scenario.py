"""Experiment U stays off the V1 gate and counts the objective log."""

from __future__ import annotations

import logging

import pytest

from experiments.catalog import experiment_u_seasonal_scarcity
from experiments.environmental_scenario import (
    ENVIRONMENTAL_DYNAMICS_METRIC_VERSION,
    count_environmental_dynamics,
)
from tests.unit.test_v1_regression_gate import _CATALOG_BUILDERS


def test_scarcity_arms_share_seed_and_stay_off_the_v1_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="experiments.catalog"):
        definition = experiment_u_seasonal_scarcity(seed=11)
    assert definition.experiment_id == "experiment-u-seasonal-scarcity"
    assert ENVIRONMENTAL_DYNAMICS_METRIC_VERSION == "environmental_dynamics@1"
    learned, naive = definition.conditions
    assert learned.condition_id == "u-learned"
    assert naive.condition_id == "u-naive"
    assert learned.runner_config.seed == naive.runner_config.seed
    assert learned.runner_config.schema_version == "runner-config-v14"
    assert naive.runner_config.capability_flags.predictive_world_model is False
    assert learned.runner_config.capability_flags.predictive_world_model is True
    spec = learned.runner_config.environmental_dynamics
    assert spec is not None and spec.season_length_ticks == 4
    assert spec is naive.runner_config.environmental_dynamics
    goal = learned.runner_config.agents[0].initial_goals[0]
    assert goal.horizon.value == "long_term"
    assert goal.outcome is not None and goal.outcome.kind.value == "preserve_life"
    food = learned.runner_config.scenario.resources[0]
    assert food.kind.value == "food"
    assert food.quantity == 1.0
    assert food.maximum_quantity == 1.0
    assert food.regeneration_per_tick == 1.0
    messages = [record.getMessage() for record in caplog.records]
    assert "environment_scenario arm=learned season_length=4" in messages
    assert "environment_scenario arm=naive season_length=4" in messages
    assert all("seed" not in record.getMessage() for record in caplog.records)
    assert "experiment-u-seasonal-scarcity" not in {
        item[0] for item in _CATALOG_BUILDERS
    }


def test_metric_counts_only_the_objective_log() -> None:
    events = (
        _event("season_changed"),
        _event("resource_node_depleted"),
        _event("weather_changed"),
    )
    counts = count_environmental_dynamics(events)
    assert counts == {"season_change_count": 1, "depletion_count": 1}


class _Details:
    def __init__(self, kind: str) -> None:
        self.kind = kind


class _Event:
    def __init__(self, kind: str) -> None:
        self.details = _Details(kind)


def _event(kind: str) -> _Event:
    return _Event(kind)
