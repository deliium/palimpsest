# mypy: ignore-errors
"""V4-33 off-gate scenario: paired science arms and v57 companion."""

from __future__ import annotations

import pytest

from experiments.catalog import experiment_science_diffusion
from experiments.science_diffusion_scenario import (
    SCIENCE_DIFFUSION_EXPERIMENT_ID,
    science_diffusion_scenario,
)
from simulation.runner_models import RUNNER_SCHEMA_VERSION_V57
from tests.unit.test_scientific_institutions_scenario import _base

pytestmark = pytest.mark.unit


def _definition():
    return science_diffusion_scenario(_base(), max_ticks=128)


def _conditions():
    return {row.condition_id: row.runner_config for row in _definition().conditions}


def test_scenario_declares_paired_arms_and_v57_companion() -> None:
    definition = _definition()
    assert definition.experiment_id == SCIENCE_DIFFUSION_EXPERIMENT_ID
    assert [row.condition_id for row in definition.conditions] == [
        "diffusion-science",
        "diffusion-science-off",
        "diffusion-instruments-v57",
    ]
    assert definition.paired_world_group
    assert all(
        row.runner_config.stop_policy.max_ticks == 128
        for row in definition.conditions
    )


def test_only_the_owned_science_flag_differs_between_paired_arms() -> None:
    conditions = _conditions()
    science = conditions["diffusion-science"]
    off = conditions["diffusion-science-off"]
    assert science.v4_capability_flags.science is True
    assert off.v4_capability_flags.science is False
    assert science.v4_capability_flags.organizations
    assert science.knowledge_genealogy is not None
    assert science.durable_records is not None
    assert science.artifacts_enabled is True
    assert all(
        agent.cognition.artifact_interpretation_mode.value == "deterministic"
        for agent in science.agents
    )
    assert conditions["diffusion-instruments-v57"].schema_version == (
        RUNNER_SCHEMA_VERSION_V57
    )
    assert (
        conditions["diffusion-instruments-v57"].measurement_instruments
        is not None
    )


def test_catalog_factory_registers_three_arms() -> None:
    definition = experiment_science_diffusion(_base(), max_ticks=128)
    assert definition.experiment_id == "science_diffusion@1"
    assert len(definition.conditions) == 3


def test_minimum_horizon_is_128() -> None:
    with pytest.raises(ValueError):
        science_diffusion_scenario(_base(), max_ticks=127)
