"""Generic generational comparison builder over a shared v55 base."""

from __future__ import annotations

import logging
from typing import Final

from experiments.generational_axes import apply_generational_level
from experiments.generational_comparison_base import (
    assert_comparable_generational_conditions,
    assert_comparable_generational_pair,
)
from experiments.generational_comparison_models import (
    GenerationalComparisonAxis,
    GenerationalComparisonError,
    GenerationalComparisonSpec,
)
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
)
from simulation.runner_models import SimulationRunnerConfig

_LOG: Final[logging.Logger] = logging.getLogger("experiments.generational_comparison")


def build_generational_comparison(
    spec: GenerationalComparisonSpec,
) -> ExperimentDefinition:
    """Build independent paired conditions, not a cross product."""
    if type(spec) is not GenerationalComparisonSpec:
        raise TypeError("spec must be GenerationalComparisonSpec")
    if spec.base.stop_policy.max_ticks != spec.max_ticks:
        raise GenerationalComparisonError(
            "comparison_horizon_mismatch",
            "spec.max_ticks must match base.stop_policy.max_ticks",
        )

    conditions: list[ExperimentCondition] = []
    condition_ids: set[str] = set()
    configs: list[SimulationRunnerConfig] = []
    for comparison in spec.comparisons:
        control = apply_generational_level(
            spec.base, comparison.axis, comparison.control_level_id
        )
        treatment = apply_generational_level(
            spec.base, comparison.axis, comparison.treatment_level_id
        )
        assert_comparable_generational_pair(
            control,
            treatment,
            allow_population_size=(
                comparison.axis is GenerationalComparisonAxis.POPULATION_SIZE
            ),
        )
        configs.extend((control, treatment))
        for suffix, level_id, config in (
            ("control", comparison.control_level_id, control),
            ("treatment", comparison.treatment_level_id, treatment),
        ):
            condition_id = f"{comparison.comparison_id}-{suffix}"
            if condition_id in condition_ids:
                raise GenerationalComparisonError(
                    "duplicate_comparison_id",
                    f"duplicate condition id: {condition_id}",
                )
            condition_ids.add(condition_id)
            conditions.append(
                ExperimentCondition(
                    condition_id=condition_id,
                    label_code=f"{comparison.label_code}_{suffix}",
                    runner_config=config,
                )
            )
            _LOG.debug(
                "generational_comparison_condition_built comparison_id=%s "
                "axis=%s level_id=%s",
                comparison.comparison_id,
                comparison.axis.value,
                level_id,
            )

    assert_comparable_generational_conditions(configs, allow_population_size=True)
    definition = ExperimentDefinition(
        experiment_id=spec.experiment_id,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=spec.seed_matrix,
        conditions=tuple(conditions),
        paired_world_group=f"{spec.experiment_id}-paired-world",
    )
    _LOG.info(
        "generational_comparison_built experiment_id=%s comparison_count=%s "
        "condition_count=%s",
        spec.experiment_id,
        len(spec.comparisons),
        len(conditions),
    )
    return definition


__all__ = ["build_generational_comparison"]
