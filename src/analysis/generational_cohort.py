"""Detached generational cohort comparison metric.

The family folds one finalized ``PopulationProgress`` into scalar counts and
survival shares. It never reads live world state, cognition, or prompts.
"""

from __future__ import annotations

import logging
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from simulation.generational_models import PopulationProgress
from world.identifiers import require_exact_nonneg_int, require_stable_id

GENERATIONAL_COHORT_COMPARISON_METRIC_VERSION: Final[str] = (
    "generational_cohort_comparison@1"
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.generational_cohort")


def _share(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return quantize_float(numerator / denominator)


def compute_generational_cohort_comparison(
    progress: PopulationProgress,
    *,
    run_id: str,
    input_revision: str,
    window_end: int,
) -> MetricDocument:
    """Compute the analysis-only family from finalized population progress."""
    if type(progress) is not PopulationProgress:
        raise TypeError("progress must be PopulationProgress")
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    window_end = require_exact_nonneg_int("window_end", window_end)

    spec = metric_specification(
        MetricFamilyId.GENERATIONAL_COHORT_COMPARISON
    )
    if spec.version_identifier != GENERATIONAL_COHORT_COMPARISON_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")

    generation_map = {
        row.generation_index: row for row in progress.generations
    }
    cohort_totals: dict[int, list[int]] = {}
    for cohort in progress.cohorts:
        totals = cohort_totals.setdefault(cohort.generation_index, [0, 0, 0])
        totals[0] += cohort.admitted
        totals[1] += cohort.living
        totals[2] += cohort.dead
    alignment_violations = 0
    for generation_index, totals in cohort_totals.items():
        row = generation_map.get(generation_index)
        if row is None or (row.admitted, row.living, row.dead) != tuple(totals):
            mismatch = sum(
                1
                for cohort in progress.cohorts
                if cohort.generation_index == generation_index
            )
            alignment_violations += mismatch

    generation_span = 0
    if len(progress.cohorts) >= 2:
        entry_ticks = [row.entry_tick for row in progress.cohorts]
        generation_span = max(entry_ticks) - min(entry_ticks)

    post_founder_admitted = sum(
        row.admitted
        for row in progress.generations
        if row.generation_index > 0
    )
    founder_living = generation_map.get(0)
    founder_living_count = 0 if founder_living is None else founder_living.living

    values: dict[str, object] = {
        "layer": "generational",
        "boundary_tick": progress.boundary_tick,
        "admitted_total": progress.total_admitted,
        "living_total": progress.living_population,
        "dead_total": progress.total_deaths,
        "max_generation_index": progress.max_generation_index_seen,
        "generation_count": len(progress.generations),
        "cohort_count": len(progress.cohorts),
        "generation_span_ticks": generation_span,
        "post_founder_admitted_share": _share(
            post_founder_admitted, progress.total_admitted
        ),
        "founder_living_share": _share(
            founder_living_count, progress.living_population
        ),
        "cohort_generation_alignment_violations": alignment_violations,
    }
    for row in progress.generations:
        generation = row.generation_index
        values[f"generation:{generation}:admitted"] = row.admitted
        values[f"generation:{generation}:living"] = row.living
        values[f"generation:{generation}:dead"] = row.dead
        values[f"generation:{generation}:survival_rate"] = _share(
            row.living, row.admitted
        )
    for cohort in progress.cohorts:
        prefix = f"cohort:{cohort.cohort_id}"
        values[f"{prefix}:generation_index"] = cohort.generation_index
        values[f"{prefix}:entry_tick"] = cohort.entry_tick
        values[f"{prefix}:admitted"] = cohort.admitted
        values[f"{prefix}:living"] = cohort.living
        values[f"{prefix}:dead"] = cohort.dead
        values[f"{prefix}:survival_rate"] = _share(
            cohort.living, cohort.admitted
        )

    observed = len(progress.cohorts) + len(progress.generations)
    _LOG.debug(
        "generational_cohort_comparison_complete run_id=%s generation_count=%s "
        "cohort_count=%s boundary_tick=%s",
        run_id,
        len(progress.generations),
        len(progress.cohorts),
        progress.boundary_tick,
    )
    _LOG.debug(
        "generational_cohort_comparison_window run_id=%s window_end=%s",
        run_id,
        window_end,
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(
            observed=observed,
            expected=observed,
            ratio=1.0,
        ),
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="population_progress",
            source_ids=(run_id,),
            notes_code="ok",
        ),
    )


__all__ = [
    "GENERATIONAL_COHORT_COMPARISON_METRIC_VERSION",
    "compute_generational_cohort_comparison",
]
