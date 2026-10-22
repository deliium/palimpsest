"""Experiment BM: paired population-level generational comparisons."""

from __future__ import annotations

import logging
from typing import Final

from experiments.generational_comparison import build_generational_comparison
from experiments.generational_comparison_base import generational_comparison_base
from experiments.generational_comparison_models import (
    GenerationalComparison,
    GenerationalComparisonAxis,
    GenerationalComparisonSpec,
)
from experiments.models import ExperimentDefinition, ExperimentSeedMatrix
from simulation.runner_models import SimulationRunnerConfig

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_comparison_scenario"
)

EXPERIMENT_ID: Final[str] = "generational_comparison@1"


def generational_comparison_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 12,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    """Build the five requested paired generational comparisons."""
    base_config = generational_comparison_base(
        seed=seed, max_ticks=max_ticks, base=base
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base_config.seed,))
    comparisons = (
        GenerationalComparison(
            comparison_id="bm-oral-vs-records",
            axis=GenerationalComparisonAxis.RECORD_AVAILABILITY,
            control_level_id="absent",
            treatment_level_id="present",
            label_code="oral_transmission_vs_durable_records",
        ),
        GenerationalComparison(
            comparison_id="bm-short-vs-long-lifespan",
            axis=GenerationalComparisonAxis.LIFESPAN,
            control_level_id="short",
            treatment_level_id="long",
            label_code="short_vs_long_lifespan",
        ),
        GenerationalComparison(
            comparison_id="bm-isolated-vs-connected",
            axis=GenerationalComparisonAxis.MIGRATION,
            control_level_id="isolated",
            treatment_level_id="connected",
            label_code="isolated_vs_connected_groups",
        ),
        GenerationalComparison(
            comparison_id="bm-low-vs-high-teaching",
            axis=GenerationalComparisonAxis.TEACHING_FREQUENCY,
            control_level_id="low",
            treatment_level_id="high",
            label_code="low_vs_high_teaching",
        ),
        GenerationalComparison(
            comparison_id="bm-reference-vs-reconstructive-memory",
            axis=GenerationalComparisonAxis.MEMORY_ARCHITECTURE,
            control_level_id="reference",
            treatment_level_id="reconstructive",
            label_code="reference_vs_reconstructive_memory",
        ),
    )
    spec = GenerationalComparisonSpec(
        experiment_id=EXPERIMENT_ID,
        base=base_config,
        comparisons=comparisons,
        seed_matrix=matrix,
        max_ticks=max_ticks,
    )
    definition = build_generational_comparison(spec)
    _LOG.info(
        "generational_scenario_built experiment_id=%s arms=%s max_ticks=%s",
        EXPERIMENT_ID,
        len(definition.conditions),
        max_ticks,
    )
    return definition


__all__ = ["EXPERIMENT_ID", "generational_comparison_scenario"]
