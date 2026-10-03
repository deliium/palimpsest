"""Unit tests for closed matrix factor applicators."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.matrix_factors import (
    apply_factor_level,
    apply_factor_levels,
    matrix_reference_fixture_base,
)
from experiments.matrix_models import MatrixFactorId, MatrixValidationError
from simulation.runner_models import (
    CognitiveBudgetMode,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    ReflectionMode,
    V2CapabilityFlags,
)


def test_memory_mortality_imagination_reflection_tom() -> None:
    base = matrix_reference_fixture_base()
    schema = base.schema_version
    mem = apply_factor_level(base, MatrixFactorId.MEMORY_TYPE, "reconstructive_v2")
    assert mem.agents[0].cognition.memory_mode is MemoryMode.RECONSTRUCTIVE_V2
    assert mem.schema_version == schema

    mort = apply_factor_level(base, "mortality", "enabled")
    assert mort.mortality_mode is MortalityMode.ENABLED

    imag = apply_factor_level(base, MatrixFactorId.IMAGINATION, "enabled")
    assert imag.agents[0].cognition.imagination_mode is ImaginationMode.ENABLED
    assert imag.agents[0].cognition.prospective_mode.value == "disabled"

    refl = apply_factor_level(base, MatrixFactorId.REFLECTION, "deterministic")
    assert refl.agents[0].cognition.reflection_mode is ReflectionMode.DETERMINISTIC

    tom = apply_factor_level(base, MatrixFactorId.TOM, "on")
    assert tom.capability_flags.advanced_social_inference is True
    assert tom.capability_flags.multi_hop_testimony_tracking is False


def test_tom_never_enables_unowned_flag() -> None:
    base = matrix_reference_fixture_base()
    tainted = replace(
        base,
        capability_flags=V2CapabilityFlags(multi_hop_testimony_tracking=True),
    )
    with pytest.raises(MatrixValidationError) as exc:
        apply_factor_level(tainted, MatrixFactorId.TOM, "on")
    assert exc.value.code == "unowned_capability_flag"


def test_seasonality_and_budget_and_scarcity() -> None:
    base = matrix_reference_fixture_base()
    seasonal = apply_factor_level(base, MatrixFactorId.SEASONALITY, "on")
    assert seasonal.environmental_dynamics is not None
    assert seasonal.schema_version == base.schema_version

    off = apply_factor_level(seasonal, MatrixFactorId.SEASONALITY, "off")
    assert off.environmental_dynamics is None

    budget = apply_factor_level(base, MatrixFactorId.COGNITIVE_BUDGET, "low_cost")
    assert (
        budget.agents[0].cognition.cognitive_budget_mode is CognitiveBudgetMode.ENFORCED
    )
    assert budget.agents[0].cognition.cognitive_budget_limits is not None

    scarce = apply_factor_level(base, MatrixFactorId.RESOURCE_SCARCITY, "scarce")
    abundant = apply_factor_level(base, MatrixFactorId.RESOURCE_SCARCITY, "abundant")
    assert scarce.scenario.locations == abundant.scenario.locations
    assert scarce.scenario.resources != abundant.scenario.resources


def test_unknown_level_fails_closed() -> None:
    base = matrix_reference_fixture_base()
    with pytest.raises(MatrixValidationError) as exc:
        apply_factor_level(base, MatrixFactorId.TOM, "maybe")
    assert exc.value.code == "unknown_level_id"


def test_multi_axis_apply_preserves_schema() -> None:
    base = matrix_reference_fixture_base()
    applied = apply_factor_levels(
        base,
        (
            ("memory_type", "reference"),
            ("mortality", "disabled"),
            ("tom", "off"),
        ),
    )
    assert applied.schema_version == base.schema_version
    assert applied.agents[0].cognition.memory_mode is MemoryMode.REFERENCE
