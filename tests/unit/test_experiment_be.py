"""Experiment BE is an off-gate generational narrative diagnostic."""

from __future__ import annotations

import pytest

from experiments.catalog import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    experiment_be_generational_narratives,
)
from experiments.generational_narratives_scenario import (
    assert_generational_narrative_structure,
    be_unsupported_config,
    generational_narrative_arbiter,
    generational_narratives_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V21,
    RUNNER_SCHEMA_VERSION_V48,
    MortalityMode,
)


def test_experiment_be_is_off_gate_and_registered() -> None:
    assert "generational_narratives@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    definition = generational_narratives_scenario()
    assert definition.experiment_id == "generational_narratives@1"
    assert len(definition.conditions) == 7
    off, *on = definition.conditions
    assert off.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V21
    assert on[0].runner_config.schema_version == RUNNER_SCHEMA_VERSION_V48
    assert on[0].runner_config.mortality_mode is MortalityMode.ENABLED
    assert on[0].runner_config.population_lifecycle is not None


def test_enabled_arms_are_bounded_and_off_arm_has_no_v2_fields() -> None:
    definition = generational_narratives_scenario()
    for condition in definition.conditions:
        structure = assert_generational_narrative_structure(
            condition.condition_id, condition.runner_config
        )
        assert set(structure) == {
            "variant_count",
            "witness_count",
            "record_count",
            "transition_count",
        }
        if condition.condition_id == "be-off":
            assert condition.runner_config.generational_narratives is None


def test_arbiter_is_none_for_off_and_present_for_on() -> None:
    definition = generational_narratives_scenario()
    by_id = {condition.condition_id: condition for condition in definition.conditions}
    assert generational_narrative_arbiter(
        "be-off", by_id["be-off"].runner_config
    ) is None
    witness_arbiter = generational_narrative_arbiter(
        "be-witness-death", by_id["be-witness-death"].runner_config
    )
    record_arbiter = generational_narrative_arbiter(
        "be-record-backed", by_id["be-record-backed"].runner_config
    )
    assert witness_arbiter is not None
    assert record_arbiter is not None
    witness_kinds = {
        type(milestone.build_command()).__name__
        for milestone in witness_arbiter.milestones
    }
    record_kinds = {
        type(milestone.build_command()).__name__
        for milestone in record_arbiter.milestones
    }
    assert "Talk" in witness_kinds
    assert "Inscribe" in record_kinds


def test_unsupported_config_fails_closed() -> None:
    with pytest.raises(ValueError, match="generational_narratives_requires_lifecycle"):
        be_unsupported_config()


def test_experiment_be_dispatch_builds() -> None:
    base = generational_narratives_scenario().conditions[0].runner_config
    definition = experiment_be_generational_narratives(base)
    assert definition.experiment_id == "generational_narratives@1"
