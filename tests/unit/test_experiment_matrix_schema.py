"""Unit tests for matrix highest-wins schema finalize."""

from __future__ import annotations

from experiments.matrix_factors import (
    apply_factor_levels,
    matrix_reference_fixture_base,
)
from experiments.matrix_schema import finalize_matrix_cell_config
from dataclasses import replace

from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V6,
    RUNNER_SCHEMA_VERSION_V14,
    RUNNER_SCHEMA_VERSION_V22,
    RUNNER_SCHEMA_VERSION_V23,
    V3CapabilityFlags,
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


def test_v3_flags_finalize_keeps_v23_as_highest_wins() -> None:
    base = matrix_reference_fixture_base()
    # Config must already be schema-valid: flags-on requires v23 before finalize.
    flagged = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V23,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    finalized = finalize_matrix_cell_config(flagged)
    assert finalized.schema_version == RUNNER_SCHEMA_VERSION_V23
    assert finalized.v3_capability_flags.generational_population is True

    with_budget = apply_factor_levels(
        flagged,
        (("cognitive_budget", "high_cost"),),
    )
    finalized_budget = finalize_matrix_cell_config(with_budget)
    assert finalized_budget.schema_version == RUNNER_SCHEMA_VERSION_V23
