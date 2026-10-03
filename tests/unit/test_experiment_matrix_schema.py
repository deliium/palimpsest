"""Unit tests for matrix highest-wins schema finalize."""

from __future__ import annotations

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
