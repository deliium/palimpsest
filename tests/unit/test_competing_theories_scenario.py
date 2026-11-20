# mypy: ignore-errors

"""Off-gate competing-theories scenario: real configs, no seeded content."""

from __future__ import annotations

import pytest

from experiments.competing_theories_scenario import (
    COMPETING_THEORIES_EXPERIMENT_ID,
    competing_theories_scenario,
)
from experiments.scientific_models_scenario import scientific_models_scenario
from simulation.runner_models import V4CapabilityFlags
from tests.unit.test_scientific_models_scenario import _base

pytestmark = pytest.mark.unit


def test_four_legible_arms_share_the_science_config() -> None:
    definition = competing_theories_scenario(_base(), max_ticks=96)
    assert definition.experiment_id == COMPETING_THEORIES_EXPERIMENT_ID
    assert [row.condition_id for row in definition.conditions] == [
        "theories-observation",
        "theories-science-off",
        "theories-communication",
        "theories-measurement-coexistence",
    ]
    by_id = {row.condition_id: row.runner_config for row in definition.conditions}
    assert by_id["theories-science-off"].v4_capability_flags == V4CapabilityFlags()
    assert by_id["theories-observation"].v4_capability_flags.science is True
    source = scientific_models_scenario(_base(), max_ticks=96)
    source_model = next(
        row.runner_config
        for row in source.conditions
        if row.condition_id == "models-season-resource"
    )
    assert (
        by_id["theories-observation"].environmental_dynamics
        == source_model.environmental_dynamics
    )
    assert by_id["theories-observation"].seed == source_model.seed
    assert not hasattr(by_id["theories-observation"], "competing_theories")
