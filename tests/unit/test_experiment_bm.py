"""Experiment BM construction and registration."""

from __future__ import annotations

import pytest

from experiments import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    GenerationalComparison,
    GenerationalComparisonAxis,
    GenerationalComparisonError,
    GenerationalComparisonSpec,
    build_generational_comparison,
    experiment_bm_generational_comparison,
    generational_comparison_base,
    generational_comparison_scenario,
)
from experiments.models import ExperimentDefinition, condition_fingerprint
from simulation.runner_models import MemoryMode

_EXPECTED_IDS = (
    "bm-oral-vs-records-control",
    "bm-oral-vs-records-treatment",
    "bm-short-vs-long-lifespan-control",
    "bm-short-vs-long-lifespan-treatment",
    "bm-isolated-vs-connected-control",
    "bm-isolated-vs-connected-treatment",
    "bm-low-vs-high-teaching-control",
    "bm-low-vs-high-teaching-treatment",
    "bm-reference-vs-reconstructive-memory-control",
    "bm-reference-vs-reconstructive-memory-treatment",
)


def _definition() -> ExperimentDefinition:
    return generational_comparison_scenario(seed=23, max_ticks=12)


def test_bm_builds_ten_ordered_comparable_arms() -> None:
    definition = _definition()
    assert tuple(item.condition_id for item in definition.conditions) == _EXPECTED_IDS
    assert definition.experiment_id == "generational_comparison@1"
    for condition in definition.conditions:
        config = condition.runner_config
        assert config.schema_version == "runner-config-v55"
        assert config.generational_run is not None
        assert config.stop_policy.max_ticks == 12
        assert config.stop_policy.stop_on_all_agents_terminal is False
        assert config.seed == 23
    assert "generational_comparison@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS


def test_each_pair_differs_by_the_declared_axis() -> None:
    conditions = {
        item.condition_id: item.runner_config for item in _definition().conditions
    }
    assert conditions["bm-oral-vs-records-control"].durable_records is None
    assert conditions["bm-oral-vs-records-treatment"].durable_records is not None

    short = conditions["bm-short-vs-long-lifespan-control"]
    long = conditions["bm-short-vs-long-lifespan-treatment"]
    assert short.population_lifecycle is not None
    assert long.population_lifecycle is not None
    assert short.population_lifecycle.lifespan_ticks == 8
    assert long.population_lifecycle.lifespan_ticks == 24

    isolated = conditions["bm-isolated-vs-connected-control"]
    connected = conditions["bm-isolated-vs-connected-treatment"]
    assert isolated.regions_migration is None
    assert isolated.v3_capability_flags.multi_polity_migration is False
    assert connected.regions_migration is not None
    assert connected.v3_capability_flags.multi_polity_migration is True

    low = conditions["bm-low-vs-high-teaching-control"]
    high = conditions["bm-low-vs-high-teaching-treatment"]
    assert low.agents[0].cognition.offer_window == 4
    assert high.agents[0].cognition.offer_window == 12
    assert (
        low.agents[0].cognition.skill_learning_mode
        is high.agents[0].cognition.skill_learning_mode
    )

    reference = conditions["bm-reference-vs-reconstructive-memory-control"]
    reconstructive = conditions["bm-reference-vs-reconstructive-memory-treatment"]
    assert all(
        agent.cognition.memory_mode is MemoryMode.REFERENCE
        for agent in reference.agents
    )
    assert all(
        agent.cognition.memory_mode is MemoryMode.RECONSTRUCTIVE_V2
        for agent in reconstructive.agents
    )


def test_non_treatment_fields_are_equal_within_pairs() -> None:
    conditions = {
        item.condition_id: item.runner_config for item in _definition().conditions
    }
    for control_id, treatment_id in zip(
        _EXPECTED_IDS[0::2], _EXPECTED_IDS[1::2], strict=True
    ):
        control = conditions[control_id]
        treatment = conditions[treatment_id]
        assert control.seed == treatment.seed
        assert control.stochastic_identity == treatment.stochastic_identity
        assert control.scenario.world_id == treatment.scenario.world_id
        assert control.scenario.locations == treatment.scenario.locations
        assert control.scenario.bodies == treatment.scenario.bodies
        assert control.stop_policy == treatment.stop_policy
        assert control.generational_run == treatment.generational_run
        assert control.new_agent_initialization == treatment.new_agent_initialization
        assert [
            a.agent_id for a in control.agents
        ] == [a.agent_id for a in treatment.agents]
        if "memory" not in control_id:
            assert [
                a.cognition.memory_mode for a in control.agents
            ] == [a.cognition.memory_mode for a in treatment.agents]


def test_condition_fingerprints_are_deterministic_and_pair_differs() -> None:
    first = {item.condition_id: item for item in _definition().conditions}
    second = {item.condition_id: item for item in _definition().conditions}
    for condition_id, condition in first.items():
        assert condition_fingerprint(condition) == condition_fingerprint(
            second[condition_id]
        )
    assert condition_fingerprint(
        first["bm-short-vs-long-lifespan-control"]
    ) != condition_fingerprint(first["bm-short-vs-long-lifespan-treatment"])


def test_generic_spec_mixing_population_and_lifespan_passes() -> None:
    base = generational_comparison_base(seed=23, max_ticks=8)
    comparisons = (
        GenerationalComparison(
            comparison_id="cmp-pop",
            axis=GenerationalComparisonAxis.POPULATION_SIZE,
            control_level_id="small",
            treatment_level_id="large",
            label_code="small_vs_large",
        ),
        GenerationalComparison(
            comparison_id="cmp-life",
            axis=GenerationalComparisonAxis.LIFESPAN,
            control_level_id="short",
            treatment_level_id="long",
            label_code="short_vs_long",
        ),
    )
    from experiments.models import ExperimentSeedMatrix

    spec = GenerationalComparisonSpec(
        experiment_id="mix-test",
        base=base,
        comparisons=comparisons,
        seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
        max_ticks=8,
    )
    definition = build_generational_comparison(spec)
    assert len(definition.conditions) == 4


def test_horizon_errors() -> None:
    with pytest.raises(ValueError, match="generational_base_horizon_too_short"):
        generational_comparison_scenario(seed=23, max_ticks=7)

    base = generational_comparison_base(seed=23, max_ticks=8)
    comparison = GenerationalComparison(
        comparison_id="cmp",
        axis=GenerationalComparisonAxis.LIFESPAN,
        control_level_id="short",
        treatment_level_id="long",
        label_code="lifespan",
    )
    from experiments.models import ExperimentSeedMatrix

    spec = GenerationalComparisonSpec(
        experiment_id="horizon-test",
        base=base,
        comparisons=(comparison,),
        seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
        max_ticks=9,
    )
    with pytest.raises(GenerationalComparisonError) as error:
        build_generational_comparison(spec)
    assert error.value.code == "comparison_horizon_mismatch"


def test_catalog_builder_and_public_exports() -> None:
    base = generational_comparison_base(seed=23, max_ticks=8)
    definition = experiment_bm_generational_comparison(base=base, max_ticks=8)
    assert len(definition.conditions) == 10
    assert definition.experiment_id == "generational_comparison@1"
