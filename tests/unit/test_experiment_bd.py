"""Experiment BD cross-cultural translation structure."""

from __future__ import annotations

import pytest

from experiments.catalog import OFF_GATE_MATRIX_EXPERIMENT_IDS
from experiments.translation_scenario import (
    assert_translation_structure,
    bd_unsupported_config,
    translation_arbiter,
    translation_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V20,
    RUNNER_SCHEMA_VERSION_V47,
    SemanticNamingMode,
    TranslationMode,
)


def test_experiment_bd_is_registered_off_gate() -> None:
    assert "cross_cultural_translation@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS


def test_experiment_bd_arms_and_modes() -> None:
    definition = translation_scenario()
    assert definition.experiment_id == "cross_cultural_translation@1"
    arms = {condition.condition_id: condition for condition in definition.conditions}
    assert set(arms) == {
        "bd-off",
        "bd-naming-only",
        "bd-shared-observation",
        "bd-demonstration",
        "bd-repeated-teaching-artifact",
        "bd-ambiguous-wrong",
    }
    assert arms["bd-off"].runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert arms["bd-naming-only"].runner_config.schema_version == (
        RUNNER_SCHEMA_VERSION_V20
    )
    for name in (
        "bd-shared-observation",
        "bd-demonstration",
        "bd-repeated-teaching-artifact",
        "bd-ambiguous-wrong",
    ):
        config = arms[name].runner_config
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V47
        assert all(
            agent.cognition.translation_mode is TranslationMode.DETERMINISTIC
            for agent in config.agents
        )
        assert all(
            agent.cognition.semantic_naming_mode
            is SemanticNamingMode.DETERMINISTIC
            for agent in config.agents
        )
    assert arms["bd-shared-observation"].runner_config.cultural_contact is not None


def test_off_arm_structure_has_no_mappings() -> None:
    definition = translation_scenario()
    condition = definition.conditions[0]
    counts = assert_translation_structure(
        condition.condition_id, condition.runner_config
    )
    assert counts["mapping_count"] == 0
    assert counts["translation_agent_count"] == 0


def test_unsupported_config_fails_closed() -> None:
    with pytest.raises(ValueError, match="translation_requires_semantic_naming"):
        bd_unsupported_config()


def test_arbiter_is_none_for_off_and_present_for_enabled() -> None:
    definition = translation_scenario()
    arms = {condition.condition_id: condition for condition in definition.conditions}
    assert translation_arbiter("bd-off", arms["bd-off"].runner_config) is None
    arbiter = translation_arbiter(
        "bd-demonstration", arms["bd-demonstration"].runner_config
    )
    assert arbiter is not None
