"""Closed generational comparison contracts."""

from __future__ import annotations

import pytest

from experiments import (
    AXIS_LEVEL_IDS,
    GenerationalComparison,
    GenerationalComparisonAxis,
    GenerationalComparisonError,
    GenerationalComparisonSpec,
)
from experiments.generational_comparison_base import generational_comparison_base
from experiments.models import ExperimentSeedMatrix


def _spec() -> GenerationalComparisonSpec:
    base = generational_comparison_base(seed=23, max_ticks=8)
    axes = (
        GenerationalComparisonAxis.LIFESPAN,
        GenerationalComparisonAxis.LEARNING_MODEL,
        GenerationalComparisonAxis.RECORD_AVAILABILITY,
        GenerationalComparisonAxis.MIGRATION,
        GenerationalComparisonAxis.POPULATION_SIZE,
    )
    comparisons = tuple(
        GenerationalComparison(
            comparison_id=f"cmp-{axis.value}",
            axis=axis,
            control_level_id=sorted(AXIS_LEVEL_IDS[axis])[0],
            treatment_level_id=sorted(AXIS_LEVEL_IDS[axis])[1],
            label_code=f"label_{axis.value}",
        )
        for axis in axes
    )
    return GenerationalComparisonSpec(
        experiment_id="model-test",
        base=base,
        comparisons=comparisons,
        seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
        max_ticks=8,
    )


def test_valid_spec_with_five_axes() -> None:
    spec = _spec()
    assert len(spec.comparisons) == 5


def test_unknown_axis_and_level_fail_closed() -> None:
    with pytest.raises(GenerationalComparisonError) as axis_error:
        GenerationalComparison(
            comparison_id="bad-axis",
            axis="unknown",  # type: ignore[arg-type]
            control_level_id="short",
            treatment_level_id="long",
            label_code="bad_axis",
        )
    assert axis_error.value.code == "unknown_axis"
    with pytest.raises(GenerationalComparisonError) as level_error:
        GenerationalComparison(
            comparison_id="bad-level",
            axis=GenerationalComparisonAxis.LIFESPAN,
            control_level_id="short",
            treatment_level_id="unknown",
            label_code="bad_level",
        )
    assert level_error.value.code == "unknown_level"


def test_duplicate_ids_axes_and_equal_levels_fail() -> None:
    comparison = GenerationalComparison(
        comparison_id="cmp-one",
        axis=GenerationalComparisonAxis.LIFESPAN,
        control_level_id="short",
        treatment_level_id="long",
        label_code="lifespan_label",
    )
    base = generational_comparison_base(seed=23, max_ticks=8)
    matrix = ExperimentSeedMatrix(seeds=(23,))
    with pytest.raises(GenerationalComparisonError) as duplicate_id:
        GenerationalComparisonSpec(
            experiment_id="dupes",
            base=base,
            comparisons=(comparison, comparison),
            seed_matrix=matrix,
            max_ticks=8,
        )
    assert duplicate_id.value.code == "duplicate_comparison_id"

    other = GenerationalComparison(
        comparison_id="cmp-two",
        axis=GenerationalComparisonAxis.LIFESPAN,
        control_level_id="short",
        treatment_level_id="long",
        label_code="other_label",
    )
    with pytest.raises(GenerationalComparisonError) as duplicate_axis:
        GenerationalComparisonSpec(
            experiment_id="dupes",
            base=base,
            comparisons=(comparison, other),
            seed_matrix=matrix,
            max_ticks=8,
        )
    assert duplicate_axis.value.code == "duplicate_axis"

    with pytest.raises(GenerationalComparisonError) as identical:
        GenerationalComparison(
            comparison_id="same",
            axis=GenerationalComparisonAxis.LIFESPAN,
            control_level_id="short",
            treatment_level_id="short",
            label_code="same_levels",
        )
    assert identical.value.code == "identical_levels"


@pytest.mark.parametrize("ticks", (0, -1, True))
def test_invalid_max_ticks(ticks: int) -> None:
    base = generational_comparison_base(seed=23, max_ticks=8)
    comparison = GenerationalComparison(
        comparison_id="cmp",
        axis=GenerationalComparisonAxis.LIFESPAN,
        control_level_id="short",
        treatment_level_id="long",
        label_code="lifespan",
    )
    with pytest.raises(GenerationalComparisonError) as error:
        GenerationalComparisonSpec(
            experiment_id="ticks",
            base=base,
            comparisons=(comparison,),
            seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
            max_ticks=ticks,
        )
    assert error.value.code == "invalid_max_ticks"


def test_axis_table_is_closed_and_non_empty() -> None:
    assert frozenset(AXIS_LEVEL_IDS) == frozenset(GenerationalComparisonAxis)
    assert all(AXIS_LEVEL_IDS[axis] for axis in GenerationalComparisonAxis)


def test_spec_frozen_equality_and_public_import() -> None:
    first = _spec()
    second = _spec()
    assert first == second
