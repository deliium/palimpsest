"""Generational cohort comparison metric family."""

from __future__ import annotations

from typing import cast

import pytest

from analysis import (
    GENERATIONAL_COHORT_COMPARISON_METRIC_VERSION,
    compute_generational_cohort_comparison,
    validate_metric_catalog,
)
from analysis.models import MetricAvailability, MetricDocument
from analysis.serialization import (
    decode_metric_document,
    encode_metric_document,
    metric_document_fingerprint,
)
from simulation.generational_models import (
    CohortPopulationRow,
    GenerationPopulationRow,
    PopulationProgress,
)


def _progress() -> PopulationProgress:
    return PopulationProgress(
        boundary_tick=9,
        living_population=3,
        total_admitted=6,
        total_deaths=3,
        max_generation_index_seen=2,
        generations=(
            GenerationPopulationRow(0, 3, 1, 2),
            GenerationPopulationRow(1, 2, 1, 1),
            GenerationPopulationRow(2, 1, 1, 0),
        ),
        cohorts=(
            CohortPopulationRow(0, 0, "cohort-0", 3, 1, 2),
            CohortPopulationRow(1, 4, "cohort-1", 2, 1, 1),
            CohortPopulationRow(2, 8, "cohort-2", 1, 1, 0),
        ),
    )


def _document(progress: PopulationProgress | None = None) -> MetricDocument:
    return compute_generational_cohort_comparison(
        progress or _progress(),
        run_id="run-bm",
        input_revision="rev-bm",
        window_end=9,
    )


def test_totals_dynamic_keys_and_shares() -> None:
    document = _document()
    values = document.values
    assert document.metric_family == "generational_cohort_comparison"
    assert document.availability is MetricAvailability.PRESENT
    assert values["layer"] == "generational"
    assert values["boundary_tick"] == 9
    assert values["admitted_total"] == 6
    assert values["living_total"] == 3
    assert values["dead_total"] == 3
    assert values["max_generation_index"] == 2
    assert values["generation_count"] == 3
    assert values["cohort_count"] == 3
    assert values["generation_span_ticks"] == 8
    assert values["post_founder_admitted_share"] == pytest.approx(0.5)
    assert values["founder_living_share"] == pytest.approx(1 / 3)
    assert values["cohort_generation_alignment_violations"] == 0
    assert values["generation:0:admitted"] == 3
    assert values["generation:0:living"] == 1
    assert values["generation:0:dead"] == 2
    assert values["generation:0:survival_rate"] == pytest.approx(1 / 3)
    assert values["generation:2:survival_rate"] == 1.0
    assert values["cohort:cohort-1:generation_index"] == 1
    assert values["cohort:cohort-1:entry_tick"] == 4
    assert values["cohort:cohort-1:admitted"] == 2
    assert values["cohort:cohort-1:survival_rate"] == pytest.approx(0.5)


def test_extinction_is_present_zero_living() -> None:
    progress = PopulationProgress(
        boundary_tick=4,
        living_population=0,
        total_admitted=2,
        total_deaths=2,
        max_generation_index_seen=0,
        generations=(GenerationPopulationRow(0, 2, 0, 2),),
        cohorts=(CohortPopulationRow(0, 0, "cohort-0", 2, 0, 2),),
    )
    document = _document(progress)
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["living_total"] == 0
    assert document.values["generation:0:survival_rate"] == 0.0
    assert document.values["founder_living_share"] == 0.0


def test_single_cohort_span_is_zero() -> None:
    progress = PopulationProgress(
        boundary_tick=1,
        living_population=2,
        total_admitted=2,
        total_deaths=0,
        max_generation_index_seen=0,
        generations=(GenerationPopulationRow(0, 2, 2, 0),),
        cohorts=(CohortPopulationRow(0, 0, "cohort-0", 2, 2, 0),),
    )
    document = _document(progress)
    assert document.values["generation_span_ticks"] == 0
    assert document.values["post_founder_admitted_share"] == 0.0


def test_empty_progress_present_without_dynamic_keys() -> None:
    progress = PopulationProgress(
        boundary_tick=0,
        living_population=0,
        total_admitted=0,
        total_deaths=0,
        max_generation_index_seen=0,
    )
    document = _document(progress)
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["admitted_total"] == 0
    assert document.values["generation_count"] == 0
    assert document.values["cohort_count"] == 0
    assert not any(
        key.startswith("generation:") or key.startswith("cohort:")
        for key in document.values
    )


def test_invalid_progress_and_version_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(TypeError):
        compute_generational_cohort_comparison(
            cast(PopulationProgress, object()),
            run_id="run-bm",
            input_revision="rev-bm",
            window_end=9,
        )
    monkeypatch.setattr(
        "analysis.generational_cohort.metric_specification",
        lambda _family: type(
            "Spec",
            (),
            {"version_identifier": "generational_cohort_comparison@0"},
        )(),
    )
    with pytest.raises(ValueError, match="unsupported_metric_version"):
        _document()


def test_catalog_validates_at_130() -> None:
    specs = validate_metric_catalog()
    assert len(specs) == 130
    assert GENERATIONAL_COHORT_COMPARISON_METRIC_VERSION == (
        "generational_cohort_comparison@1"
    )


def test_deterministic_and_serializable() -> None:
    first = _document()
    second = _document()
    assert first.values == second.values
    assert metric_document_fingerprint(first) == metric_document_fingerprint(second)
    assert decode_metric_document(encode_metric_document(first)) == first
