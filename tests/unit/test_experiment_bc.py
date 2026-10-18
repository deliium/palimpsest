"""Experiment BC registers structural semantic-drift arms off the V1 gate."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments.catalog import OFF_GATE_MATRIX_EXPERIMENT_IDS
from experiments.semantic_drift_scenario import (
    assert_semantic_drift_structure,
    bc_unsupported_config,
    semantic_drift_arbiter,
    semantic_drift_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V46,
    SemanticNamingMode,
    SymbolicLanguageMode,
)


def _definition():
    return semantic_drift_scenario()


def _by_id(config):
    return {
        condition.condition_id: condition.runner_config
        for condition in config.conditions
    }


def test_experiment_bc_is_registered_off_gate() -> None:
    assert "semantic_drift@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    definition = _definition()
    assert definition.experiment_id == "semantic_drift@1"
    assert {condition.condition_id for condition in definition.conditions} == {
        "bc-off",
        "bc-stable",
        "bc-isolated",
        "bc-contact",
        "bc-generation",
    }


def test_off_arm_is_disabled_and_v4() -> None:
    off = _by_id(_definition())["bc-off"]
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert all(
        agent.cognition.semantic_naming_mode is SemanticNamingMode.DISABLED
        for agent in off.agents
    )
    assert semantic_drift_arbiter("bc-off", off) is None


def test_enabled_arms_use_v46_and_both_modes() -> None:
    for condition_id in ("bc-stable", "bc-isolated", "bc-contact", "bc-generation"):
        config = _by_id(_definition())[condition_id]
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V46
        assert all(
            agent.cognition.semantic_naming_mode is SemanticNamingMode.DETERMINISTIC
            for agent in config.agents
        )
        assert all(
            agent.cognition.symbolic_language_mode
            is SymbolicLanguageMode.DETERMINISTIC
            for agent in config.agents
        )


def test_isolated_arm_has_no_contact_and_contact_arm_does() -> None:
    by_id = _by_id(_definition())
    assert by_id["bc-isolated"].cultural_contact is None
    assert by_id["bc-contact"].cultural_contact is not None


def test_generation_arm_sets_lifecycle_and_blank_slate_bootstrap() -> None:
    generation = _by_id(_definition())["bc-generation"]
    assert generation.population_lifecycle is not None
    assert generation.new_agent_initialization is not None
    assert generation.v3_capability_flags.generational_population is True


def _binding(history):
    return SimpleNamespace(sense_revision=1, sense_history=tuple(history))


def _ledger(*bindings):
    return SimpleNamespace(bindings=tuple(bindings))


def test_off_arm_rejects_sense_history() -> None:
    off = _by_id(_definition())["bc-off"]
    ledger = _ledger(
        _binding(
            (
                SimpleNamespace(
                    ordinal=0,
                    tick=1,
                    trigger=SimpleNamespace(value="promoted"),
                ),
            )
        )
    )
    with pytest.raises(AssertionError, match="sense_history_present_in_off_arm"):
        assert_semantic_drift_structure("bc-off", off, naming_ledgers=(ledger,))


def test_enabled_arm_accepts_monotonic_history() -> None:
    config = _by_id(_definition())["bc-stable"]
    ledger = _ledger(
        _binding(
            (
                SimpleNamespace(
                    ordinal=0,
                    tick=1,
                    trigger=SimpleNamespace(value="promoted"),
                ),
                SimpleNamespace(
                    ordinal=1,
                    tick=3,
                    trigger=SimpleNamespace(value="shifted"),
                ),
            )
        )
    )
    summary = assert_semantic_drift_structure(
        "bc-stable", config, naming_ledgers=(ledger,)
    )
    assert summary["sense_record_count"] == 2


def test_non_monotonic_history_is_rejected() -> None:
    config = _by_id(_definition())["bc-stable"]
    ledger = _ledger(
        _binding(
            (
                SimpleNamespace(
                    ordinal=1,
                    tick=1,
                    trigger=SimpleNamespace(value="shifted"),
                ),
                SimpleNamespace(
                    ordinal=0,
                    tick=2,
                    trigger=SimpleNamespace(value="promoted"),
                ),
            )
        )
    )
    with pytest.raises(AssertionError, match="sense_history_not_monotonic"):
        assert_semantic_drift_structure(
            "bc-stable", config, naming_ledgers=(ledger,)
        )


def test_generation_arm_requires_lifecycle_records() -> None:
    config = _by_id(_definition())["bc-generation"]
    with pytest.raises(
        AssertionError, match="generation_arm_missing_lifecycle_records"
    ):
        assert_semantic_drift_structure("bc-generation", config)


def test_unsupported_fixture_fails_closed() -> None:
    with pytest.raises(ValueError, match="symbolic_language_requires_semantic_naming"):
        bc_unsupported_config()
