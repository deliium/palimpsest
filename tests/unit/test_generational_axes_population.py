"""Population, lifespan, records, migration, and scarcity axis presets."""

from __future__ import annotations

import pytest

from experiments.generational_axes import apply_generational_level
from experiments.generational_comparison_base import generational_comparison_base
from experiments.generational_comparison_models import GenerationalComparisonError
from experiments.matrix_factors import matrix_reference_fixture_base
from simulation.runner_models import SimulationRunnerConfig
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)


def _base() -> SimulationRunnerConfig:
    return generational_comparison_base(seed=23, max_ticks=8)


def _unchanged_outside_lifecycle(
    before: SimulationRunnerConfig, after: SimulationRunnerConfig
) -> None:
    assert after.seed == before.seed
    assert after.stochastic_identity == before.stochastic_identity
    assert after.scenario == before.scenario
    assert after.agents == before.agents
    assert after.stop_policy == before.stop_policy
    assert after.generational_run == before.generational_run
    assert after.schema_version == before.schema_version


def test_lifespan_presets_change_only_lifecycle() -> None:
    base = _base()
    short = apply_generational_level(base, "lifespan", "short")
    long = apply_generational_level(base, "lifespan", "long")
    assert short.population_lifecycle is not None
    assert long.population_lifecycle is not None
    assert short.population_lifecycle.lifespan_ticks == 8
    assert long.population_lifecycle.lifespan_ticks == 24
    assert [
        item.inclusive_max_age
        for item in short.population_lifecycle.stage_thresholds
    ] == [2, 4, 7]
    assert [
        item.inclusive_max_age
        for item in long.population_lifecycle.stage_thresholds
    ] == [2, 6, 23]
    _unchanged_outside_lifecycle(base, short)
    _unchanged_outside_lifecycle(base, long)
    assert apply_generational_level(short, "lifespan", "short") == short


def test_population_size_changes_capacity_and_entry_rate() -> None:
    base = _base()
    base_lifecycle = base.population_lifecycle
    assert base_lifecycle is not None
    small = apply_generational_level(base, "population_size", "small")
    large = apply_generational_level(base, "population_size", "large")
    assert small.population_lifecycle is not None
    assert large.population_lifecycle is not None
    assert small.population_lifecycle.max_population == 6
    assert large.population_lifecycle.max_population == 10
    assert (
        small.population_lifecycle.demographic_policy_params["entries_per_interval"]
        == 1
    )
    assert (
        large.population_lifecycle.demographic_policy_params["entries_per_interval"]
        == 2
    )
    assert (
        small.population_lifecycle.demographic_policy_params["interval_ticks"]
        == base_lifecycle.demographic_policy_params["interval_ticks"]
    )
    assert (
        small.population_lifecycle.demographic_policy_params["spawn_location_ids"]
        == base_lifecycle.demographic_policy_params["spawn_location_ids"]
    )
    _unchanged_outside_lifecycle(base, small)
    assert apply_generational_level(small, "population_size", "small") == small


def test_record_availability_roundtrips() -> None:
    base = _base()
    absent = apply_generational_level(base, "record_availability", "absent")
    present = apply_generational_level(base, "record_availability", "present")
    assert absent.durable_records is None
    assert present.durable_records is not None
    assert present.v3_capability_flags.cultural_historical_memory is True
    assert present.cultural_feature_provenance is not None
    assert decode_runner_config(encode_runner_config(absent)) == absent
    assert decode_runner_config(encode_runner_config(present)) == present
    assert apply_generational_level(absent, "record_availability", "absent") == absent
    assert (
        apply_generational_level(present, "record_availability", "present") == present
    )


def test_migration_levels_preserve_scenario() -> None:
    base = _base()
    connected = apply_generational_level(base, "migration", "connected")
    assert connected.regions_migration is not None
    assert connected.v3_capability_flags.multi_polity_migration is True
    isolated = apply_generational_level(connected, "migration", "isolated")
    assert isolated.regions_migration is None
    assert isolated.v3_capability_flags.multi_polity_migration is False
    assert isolated.scenario == base.scenario
    assert apply_generational_level(isolated, "migration", "isolated") == isolated

    without_template = base
    without_template = apply_generational_level(
        without_template, "migration", "isolated"
    )
    with pytest.raises(GenerationalComparisonError) as error:
        apply_generational_level(without_template, "migration", "connected")
    assert error.value.code == "migration_template_required"


def test_scarcity_scales_resource_magnitudes_only() -> None:
    base = _base()
    scarce = apply_generational_level(base, "resource_scarcity", "scarce")
    abundant = apply_generational_level(base, "resource_scarcity", "abundant")
    assert len(scarce.scenario.resources) == len(base.scenario.resources)
    for original, small, large in zip(
        base.scenario.resources,
        scarce.scenario.resources,
        abundant.scenario.resources,
        strict=True,
    ):
        assert small.entity_id == original.entity_id
        assert small.name == original.name
        assert small.kind == original.kind
        assert small.location_id == original.location_id
        assert small.unit == original.unit
        assert small.quantity == original.quantity * 0.5
        assert small.maximum_quantity == original.maximum_quantity * 0.5
        assert small.regeneration_per_tick == original.regeneration_per_tick * 0.5
        assert small.quantity <= small.maximum_quantity
        assert large.quantity == original.quantity * 1.5
        assert large.quantity <= large.maximum_quantity


def test_non_v55_base_fails_closed() -> None:
    legacy = matrix_reference_fixture_base(max_ticks=2)
    for axis, level in (
        ("lifespan", "short"),
        ("population_size", "small"),
        ("memory_architecture", "reference"),
    ):
        with pytest.raises(GenerationalComparisonError) as error:
            apply_generational_level(legacy, axis, level)
        assert error.value.code == "generational_base_required"
