"""Experiment BB registers structural symbolic arms off the V1 gate."""

from __future__ import annotations

import pytest

from experiments.catalog import OFF_GATE_MATRIX_EXPERIMENT_IDS
from experiments.symbolic_language_scenario import (
    assert_symbolic_language_structure,
    bb_unsupported_config,
    symbolic_language_arbiter,
    symbolic_language_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V46,
    SemanticNamingMode,
    SymbolicLanguageMode,
)


def test_experiment_bb_is_registered_off_gate() -> None:
    assert "compositional_symbols@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    definition = symbolic_language_scenario()
    assert definition.experiment_id == "compositional_symbols@1"
    assert {condition.condition_id for condition in definition.conditions} == {
        "bb-off",
        "bb-single",
        "bb-isolated",
        "bb-contact",
    }


def test_off_arm_is_disabled_and_v4() -> None:
    definition = symbolic_language_scenario()
    off = definition.conditions[0].runner_config
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert all(
        agent.cognition.symbolic_language_mode is SymbolicLanguageMode.DISABLED
        for agent in off.agents
    )
    assert symbolic_language_arbiter("bb-off", off) is None


def test_symbolic_arms_use_v46_and_require_naming() -> None:
    definition = symbolic_language_scenario()
    for condition in definition.conditions[1:]:
        config = condition.runner_config
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V46
        assert all(
            agent.cognition.symbolic_language_mode is SymbolicLanguageMode.DETERMINISTIC
            for agent in config.agents
        )
        assert all(
            agent.cognition.semantic_naming_mode is SemanticNamingMode.DETERMINISTIC
            for agent in config.agents
        )


def test_isolated_arm_has_no_contact_and_contact_arm_does() -> None:
    definition = symbolic_language_scenario()
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    assert by_id["bb-isolated"].cultural_contact is None
    assert by_id["bb-contact"].cultural_contact is not None


def test_structure_assertion_requires_active_single_arm_composition() -> None:
    from types import SimpleNamespace

    definition = symbolic_language_scenario()
    single = definition.conditions[1].runner_config
    with pytest.raises(AssertionError, match="single_arm_without_active_composition"):
        assert_symbolic_language_structure(
            "bb-single",
            single,
            (),
            (SimpleNamespace(status="candidate"),),
        )
    assert_symbolic_language_structure(
        "bb-single", single, (), (SimpleNamespace(status="active"),)
    )


def test_structure_assertion_rejects_off_arm_activity() -> None:
    definition = symbolic_language_scenario()
    off = definition.conditions[0].runner_config
    assert_symbolic_language_structure("bb-off", off, ())
    with pytest.raises(AssertionError, match="symbolic_mode_missing"):
        assert_symbolic_language_structure("bb-single", off, ())


def test_unsupported_fixture_fails_closed() -> None:
    with pytest.raises(ValueError, match="symbolic_language_requires_semantic_naming"):
        config = bb_unsupported_config()
        from simulation.runner_models import SimulationRunnerConfig

        assert type(config) is SimulationRunnerConfig
