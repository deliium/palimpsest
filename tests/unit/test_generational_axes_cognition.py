"""Cognition, teaching, innovation, institution, and architecture presets."""

from __future__ import annotations

import pytest

from experiments.generational_axes import apply_generational_level
from experiments.generational_comparison_base import generational_comparison_base
from experiments.generational_comparison_models import GenerationalComparisonError
from experiments.matrix_factors import matrix_reference_fixture_base
from simulation.runner_models import (
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    MemoryMode,
    OfficeSuccessionMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
)


def _base() -> SimulationRunnerConfig:
    return generational_comparison_base(seed=23, max_ticks=8)


def test_memory_architecture_changes_only_memory_mode() -> None:
    base = _base()
    reference = apply_generational_level(base, "memory_architecture", "reference")
    reconstructive = apply_generational_level(
        base, "memory_architecture", "reconstructive"
    )
    assert all(
        item.cognition.memory_mode is MemoryMode.REFERENCE
        for item in reference.agents
    )
    assert all(
        item.cognition.memory_mode is MemoryMode.RECONSTRUCTIVE_V2
        for item in reconstructive.agents
    )
    assert reference.scenario == base.scenario
    assert reference.schema_version == base.schema_version


def test_learning_model_presets() -> None:
    base = _base()
    practice = apply_generational_level(base, "learning_model", "practice_only")
    supported = apply_generational_level(
        base, "learning_model", "teaching_supported"
    )
    for agent in practice.agents:
        assert agent.cognition.skill_learning_mode is SkillLearningMode.DETERMINISTIC
        assert (
            agent.cognition.teaching_interaction_mode
            is TeachingInteractionMode.DISABLED
        )
    for agent in supported.agents:
        assert agent.cognition.skill_learning_mode is SkillLearningMode.DETERMINISTIC
        assert (
            agent.cognition.teaching_interaction_mode
            is TeachingInteractionMode.DETERMINISTIC
        )
        assert agent.cognition.offer_window == 8
        assert agent.cognition.demonstration_rate == 0.02
        assert agent.cognition.practice_together_rate == 0.02
        assert agent.cognition.teaching_response_weight == 0.25


def test_teaching_frequency_presets() -> None:
    base = _base()
    low = apply_generational_level(base, "teaching_frequency", "low")
    high = apply_generational_level(base, "teaching_frequency", "high")
    for agent in low.agents:
        assert agent.cognition.offer_window == 4
        assert agent.cognition.demonstration_rate == 0.01
        assert agent.cognition.practice_together_rate == 0.01
        assert agent.cognition.teaching_response_weight == 0.10
        assert agent.cognition.skill_learning_mode is SkillLearningMode.DETERMINISTIC
    for agent in high.agents:
        assert agent.cognition.offer_window == 12
        assert agent.cognition.demonstration_rate == 0.06
        assert agent.cognition.practice_together_rate == 0.06
        assert agent.cognition.teaching_response_weight == 0.40
        assert agent.cognition.skill_learning_mode is SkillLearningMode.DETERMINISTIC


def test_innovation_rate_presets() -> None:
    base = _base()
    low = apply_generational_level(base, "innovation_rate", "low")
    high = apply_generational_level(base, "innovation_rate", "high")
    for agent in low.agents:
        assert agent.cognition.practice_rate == 0.01
        assert agent.cognition.success_rate == 0.03
        assert agent.cognition.failure_rate == 0.02
        assert agent.cognition.instruction_rate == 0.02
        assert agent.cognition.observation_rate == 0.005
        assert agent.cognition.probability_gain == 0.35
        assert agent.cognition.efficiency_gain == 0.35
        assert agent.cognition.skill_learning_mode is SkillLearningMode.DETERMINISTIC
    for agent in high.agents:
        assert agent.cognition.practice_rate == 0.08
        assert agent.cognition.success_rate == 0.12
        assert agent.cognition.failure_rate == 0.005
        assert agent.cognition.instruction_rate == 0.08
        assert agent.cognition.observation_rate == 0.03
        assert agent.cognition.probability_gain == 0.65
        assert agent.cognition.efficiency_gain == 0.65


def test_institution_support_sets_two_modes_only() -> None:
    base = _base()
    off = apply_generational_level(base, "institution_support", "off")
    on = apply_generational_level(base, "institution_support", "on")
    for agent in off.agents:
        assert (
            agent.cognition.institution_concept_mode
            is InstitutionConceptMode.DISABLED
        )
        assert agent.cognition.office_succession_mode is OfficeSuccessionMode.DISABLED
        assert (
            agent.cognition.institutional_memory_mode
            is InstitutionalMemoryMode.DISABLED
        )
        assert (
            agent.cognition.institutional_decay_mode
            is InstitutionalDecayMode.DISABLED
        )
    for agent in on.agents:
        assert (
            agent.cognition.institution_concept_mode
            is InstitutionConceptMode.DETERMINISTIC
        )
        assert (
            agent.cognition.office_succession_mode
            is OfficeSuccessionMode.DETERMINISTIC
        )
        assert (
            agent.cognition.institutional_memory_mode
            is InstitutionalMemoryMode.DISABLED
        )
        assert (
            agent.cognition.institutional_decay_mode
            is InstitutionalDecayMode.DISABLED
        )


def test_architecture_levels_preserve_v55_siblings() -> None:
    base = _base()
    v1 = apply_generational_level(base, "cognitive_architecture", "v1_memory")
    full = apply_generational_level(base, "cognitive_architecture", "full_v2")
    for applied in (v1, full):
        assert applied.schema_version == base.schema_version
        assert applied.seed == base.seed
        assert applied.scenario == base.scenario
        assert [a.agent_id for a in applied.agents] == [
            a.agent_id for a in base.agents
        ]
        assert [a.entity_id for a in applied.agents] == [
            a.entity_id for a in base.agents
        ]
        assert applied.population_lifecycle == base.population_lifecycle
        assert applied.new_agent_initialization == base.new_agent_initialization
        assert applied.generational_run == base.generational_run
        assert applied.regions_migration == base.regions_migration
        assert applied.v3_capability_flags == base.v3_capability_flags
    assert all(
        agent.cognition.memory_mode is MemoryMode.RECONSTRUCTIVE
        for agent in v1.agents
    )
    assert all(
        agent.cognition.memory_mode is MemoryMode.RECONSTRUCTIVE_V2
        for agent in full.agents
    )


def test_all_cognition_levels_are_idempotent() -> None:
    base = _base()
    cases = (
        ("memory_architecture", "reference"),
        ("learning_model", "teaching_supported"),
        ("teaching_frequency", "high"),
        ("innovation_rate", "low"),
        ("institution_support", "on"),
        ("cognitive_architecture", "full_v2"),
    )
    for axis, level in cases:
        once = apply_generational_level(base, axis, level)
        twice = apply_generational_level(once, axis, level)
        assert twice == once


def test_non_v55_base_fails_closed_for_cognition_axes() -> None:
    legacy = matrix_reference_fixture_base(max_ticks=2)
    for axis, level in (
        ("learning_model", "practice_only"),
        ("teaching_frequency", "low"),
        ("innovation_rate", "high"),
        ("institution_support", "on"),
        ("cognitive_architecture", "full_v2"),
    ):
        with pytest.raises(GenerationalComparisonError) as error:
            apply_generational_level(legacy, axis, level)
        assert error.value.code == "generational_base_required"
