# mypy: ignore-errors
"""V4-28 bounded replication experiment registration."""

from __future__ import annotations

import pytest

from experiments.catalog import OFF_GATE_MATRIX_EXPERIMENT_IDS
from experiments.replication_scenario import (
    SCIENTIFIC_REPLICATION_EXPERIMENT_ID,
    scientific_replication_scenario,
)
from simulation.runner_models import RUNNER_SCHEMA_VERSION_V56
from tests.unit.test_scientific_hypotheses_end_to_end import _config

pytestmark = pytest.mark.unit


def test_four_arms_share_seed_and_use_v56_science_prerequisites() -> None:
    base = _config(science=False, ticks=64)
    definition = scientific_replication_scenario(base)
    assert definition.experiment_id == "scientific_replication@1"
    assert definition.seed_matrix.seeds == (base.seed,)
    ids = tuple(condition.condition_id for condition in definition.conditions)
    assert ids == (
        "replication-baseline",
        "replication-individual",
        "replication-community",
        "replication-conflicting-conditions",
    )
    for condition in definition.conditions:
        assert condition.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V56
    baseline, individual, community, conflicting = definition.conditions
    assert baseline.runner_config.v4_capability_flags.science is False
    assert individual.runner_config.v4_capability_flags.science is True
    assert (
        community.runner_config.agents[0].cognition.communication_strategy_mode.value
        == "deterministic"
    )
    assert len(conflicting.runner_config.bounded_experimentation.laws) == 2


def test_scenario_is_off_gate_and_rejects_short_horizon() -> None:
    assert SCIENTIFIC_REPLICATION_EXPERIMENT_ID in OFF_GATE_MATRIX_EXPERIMENT_IDS
    with pytest.raises(ValueError):
        scientific_replication_scenario(_config(ticks=64), max_ticks=63)
