"""Unit tests for matrix highest-wins schema finalize."""

from __future__ import annotations

from dataclasses import replace

from experiments.matrix_factors import (
    apply_factor_levels,
    matrix_reference_fixture_base,
)
from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V6,
    RUNNER_SCHEMA_VERSION_V14,
    RUNNER_SCHEMA_VERSION_V22,
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V44,
    V3CapabilityFlags,
)
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
)


def test_memory_mortality_tom_finalize_to_v4() -> None:
    base = matrix_reference_fixture_base()
    applied = apply_factor_levels(
        base,
        (
            ("memory_type", "reconstructive"),
            ("mortality", "enabled"),
            ("tom", "on"),
        ),
    )
    finalized = finalize_matrix_cell_config(applied)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V4


def test_seasonality_only_finalize_to_v14() -> None:
    base = matrix_reference_fixture_base()
    applied = apply_factor_levels(base, (("seasonality", "on"),))
    finalized = finalize_matrix_cell_config(applied)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V14


def test_reflection_only_finalize_to_v6() -> None:
    base = matrix_reference_fixture_base()
    applied = apply_factor_levels(base, (("reflection", "deterministic"),))
    finalized = finalize_matrix_cell_config(applied)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V6


def test_reflection_plus_budget_finalize_to_v22() -> None:
    base = matrix_reference_fixture_base()
    applied = apply_factor_levels(
        base,
        (
            ("reflection", "deterministic"),
            ("cognitive_budget", "high_cost"),
        ),
    )
    finalized = finalize_matrix_cell_config(applied)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V22


def test_owned_migration_flag_finalizes_to_v44_highest_wins() -> None:
    base = matrix_reference_fixture_base()
    regions = RegionsMigrationSpec(
        regions=(RegionDefinition("matrix-region", "Matrix region"),),
        location_regions=tuple(
            LocationRegion(location.entity_id, "matrix-region")
            for location in base.scenario.locations
        ),
        routes=(),
        max_arrival_wait_ticks=0,
        residence_min_ticks=1,
        destination_memory_limit=1,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    flagged = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V44,
        v3_capability_flags=V3CapabilityFlags(multi_polity_migration=True),
        regions_migration=regions,
    )
    finalized = finalize_matrix_cell_config(flagged)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V44
    assert finalized.v3_capability_flags.multi_polity_migration is True

    with_budget = apply_factor_levels(
        flagged,
        (("cognitive_budget", "high_cost"),),
    )
    finalized_budget = finalize_matrix_cell_config(with_budget)
    assert finalized_budget.schema_version == RUNNER_SCHEMA_VERSION_V44


def test_generational_flag_finalize_to_v24() -> None:
    from simulation.runner_models import example_population_lifecycle_spec

    base = matrix_reference_fixture_base()
    flagged = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
    )
    finalized = finalize_matrix_cell_config(flagged)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V24
    assert finalized.v3_capability_flags.generational_population is True


def test_historical_memory_finalize_beats_cultural_feature() -> None:
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        example_cultural_feature_provenance_spec,
        example_historical_memory_layers_spec,
        example_population_lifecycle_spec,
    )

    base = matrix_reference_fixture_base()
    cultural = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=None,
    )
    assert (
        finalize_matrix_cell_config(cultural).schema_version
        == RUNNER_SCHEMA_VERSION_V31
    )

    layers = replace(
        cultural,
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        historical_memory_layers=example_historical_memory_layers_spec(),
    )
    finalized = finalize_matrix_cell_config(layers)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V32

    with_lifecycle = replace(
        layers,
        v3_capability_flags=V3CapabilityFlags(
            cultural_historical_memory=True,
            generational_population=True,
        ),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    filled = finalize_matrix_cell_config(with_lifecycle)
    assert filled.schema_version == RUNNER_SCHEMA_VERSION_V32
    assert filled.population_lifecycle is not None
    assert filled.new_agent_initialization is not None
