"""Unit tests for matrix expansion into ExperimentDefinition."""

from __future__ import annotations

import pytest

from experiments.matrix_expand import expand_matrix
from experiments.matrix_factors import matrix_reference_fixture_base
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixCatalogBase,
    MatrixConstraints,
    MatrixEmbeddedBase,
    MatrixExcludeCombo,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
    MatrixGroupOverlay,
    MatrixValidationError,
)
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V14,
    MemoryMode,
    MortalityMode,
)


def _spec(**overrides: object) -> ExperimentMatrixSpec:
    kwargs: dict[str, object] = {
        "matrix_id": "matrix-expand-demo",
        "schema_version": EXPERIMENT_MATRIX_SCHEMA_VERSION,
        "base": MatrixEmbeddedBase(runner_config=matrix_reference_fixture_base()),
        "factors": (
            MatrixFactor(
                factor_id=MatrixFactorId.MEMORY_TYPE,
                levels=(
                    MatrixFactorLevel(
                        level_id="reference",
                        label_code="mem_ref",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="reconstructive",
                        label_code="mem_recon",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
            MatrixFactor(
                factor_id=MatrixFactorId.MORTALITY,
                levels=(
                    MatrixFactorLevel(
                        level_id="disabled",
                        label_code="mort_off",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="enabled",
                        label_code="mort_on",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
        ),
        "seed_matrix": ExperimentSeedMatrix(seeds=(11,), replicates_per_seed=1),
    }
    kwargs.update(overrides)
    return ExperimentMatrixSpec(**kwargs)  # type: ignore[arg-type]


def test_expand_cartesian_and_group_roles() -> None:
    definition, cells = expand_matrix(_spec())
    assert len(definition.conditions) == 4
    assert len(cells) == 4
    ids = {item.condition_id for item in definition.conditions}
    assert "memory_type-reference__mortality-disabled" in ids
    # Any treatment level → treatment
    roles = {cell.condition_id: cell.group_role for cell in cells}
    assert (
        roles["memory_type-reference__mortality-disabled"] is GroupRole.CONTROL
    )
    assert (
        roles["memory_type-reconstructive__mortality-disabled"]
        is GroupRole.TREATMENT
    )
    modes = {
        (
            cond.runner_config.agents[0].cognition.memory_mode,
            cond.runner_config.mortality_mode,
        )
        for cond in definition.conditions
    }
    assert (MemoryMode.REFERENCE, MortalityMode.DISABLED) in modes
    assert all(
        cond.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V4
        for cond in definition.conditions
    )


def test_catalog_base_fails_closed_unresolved() -> None:
    spec = _spec(base=MatrixCatalogBase(builder_id="experiment-a-memory"))
    with pytest.raises(MatrixValidationError) as exc:
        expand_matrix(spec)
    assert exc.value.code == "catalog_base_unresolved"


def test_exclude_combos_and_min_two_conditions() -> None:
    spec = _spec(
        constraints=MatrixConstraints(
            exclude_combos=(
                MatrixExcludeCombo(
                    levels=(("memory_type", "reconstructive"),)
                ),
                MatrixExcludeCombo(levels=(("mortality", "enabled"),)),
            )
        )
    )
    # Leaves only reference+disabled → 1 condition → fail closed
    with pytest.raises(MatrixValidationError) as exc:
        expand_matrix(spec)
    assert exc.value.code == "fewer_than_two_conditions"


def test_group_overlay_wins() -> None:
    spec = _spec(
        groups=(
            MatrixGroupOverlay(
                group_id="force-neutral",
                level_match=(
                    ("memory_type", "reconstructive"),
                    ("mortality", "enabled"),
                ),
                group_role=GroupRole.NEUTRAL,
            ),
        )
    )
    _definition, cells = expand_matrix(spec)
    target = "memory_type-reconstructive__mortality-enabled"
    role = next(cell.group_role for cell in cells if cell.condition_id == target)
    assert role is GroupRole.NEUTRAL


def test_seasonality_factor_finalize_and_scarcity_layout() -> None:
    spec = ExperimentMatrixSpec(
        matrix_id="matrix-season-scarce",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(runner_config=matrix_reference_fixture_base()),
        factors=(
            MatrixFactor(
                factor_id=MatrixFactorId.SEASONALITY,
                levels=(
                    MatrixFactorLevel(level_id="off", label_code="season_off"),
                    MatrixFactorLevel(level_id="on", label_code="season_on"),
                ),
            ),
            MatrixFactor(
                factor_id=MatrixFactorId.RESOURCE_SCARCITY,
                levels=(
                    MatrixFactorLevel(level_id="scarce", label_code="scarce"),
                    MatrixFactorLevel(level_id="abundant", label_code="abundant"),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(11,)),
    )
    definition, cells = expand_matrix(spec)
    assert len(definition.conditions) == 4
    assert len(cells) == 4
    seasonal = [
        cond
        for cond in definition.conditions
        if "seasonality-on" in cond.condition_id
    ]
    assert all(
        cond.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V14
        for cond in seasonal
    )
    scarce = next(
        cond
        for cond in definition.conditions
        if cond.condition_id.endswith("resource_scarcity-scarce")
    )
    abundant = next(
        cond
        for cond in definition.conditions
        if cond.condition_id.endswith("resource_scarcity-abundant")
    )
    assert scarce.runner_config.scenario.locations == (
        abundant.runner_config.scenario.locations
    )
