"""Metric assembly and collector wiring for generational progress."""

from __future__ import annotations

from types import SimpleNamespace

from analysis import (
    MetricAvailability,
    MetricComputationInputs,
    assemble_metric_documents,
)
from experiments.collectors import assemble_arm_metric_bundle, collect_catalog_metrics
from experiments.generational_comparison_base import generational_comparison_base
from experiments.metric_collection import inputs_with_opt_in_metric_rows
from simulation.generational_models import (
    CohortPopulationRow,
    GenerationPopulationRow,
    PopulationProgress,
)

_FAMILY = "generational_cohort_comparison"


def _progress() -> PopulationProgress:
    return PopulationProgress(
        boundary_tick=9,
        living_population=2,
        total_admitted=4,
        total_deaths=2,
        max_generation_index_seen=1,
        generations=(
            GenerationPopulationRow(0, 2, 1, 1),
            GenerationPopulationRow(1, 2, 1, 1),
        ),
        cohorts=(
            CohortPopulationRow(0, 0, "cohort-0", 2, 1, 1),
            CohortPopulationRow(1, 4, "cohort-1", 2, 1, 1),
        ),
    )


def _inputs(progress: PopulationProgress | None = None) -> MetricComputationInputs:
    return MetricComputationInputs(
        run_id="run-bm",
        input_revision="rev-bm",
        window_end=9,
        generational_progress=progress,
    )


def _arm(progress: PopulationProgress | None) -> SimpleNamespace:
    base = generational_comparison_base(seed=23, max_ticks=8)
    runner_result = SimpleNamespace(
        ticks_committed=9,
        generational_progress=progress,
        initial_lifecycle_records=(),
        committed_events=None,
    )
    assignment = SimpleNamespace(
        run_id=SimpleNamespace(value="run-bm"),
        condition_id="bm-conditional",
        runner_config=base,
    )
    return SimpleNamespace(
        assignment=assignment,
        runner_result=runner_result,
        config_fingerprint="f" * 64,
    )


def test_progress_present_emits_family() -> None:
    bundle = assemble_metric_documents(_inputs(_progress()))
    by_family = {document.metric_family: document for document in bundle.documents}
    assert _FAMILY in by_family
    assert by_family[_FAMILY].availability is MetricAvailability.PRESENT
    assert by_family[_FAMILY].values["admitted_total"] == 4


def test_missing_progress_omits_family_without_changing_others() -> None:
    with_progress = assemble_metric_documents(_inputs(_progress()))
    without_progress = assemble_metric_documents(_inputs())
    assert _FAMILY not in {
        document.metric_family for document in without_progress.documents
    }
    other_with = {
        document.metric_family: document
        for document in with_progress.documents
        if document.metric_family != _FAMILY
    }
    other_without = {
        document.metric_family: document
        for document in without_progress.documents
    }
    assert {
        family: (document.values, document.availability)
        for family, document in other_with.items()
    } == {
        family: (document.values, document.availability)
        for family, document in other_without.items()
    }


def test_opt_in_rows_replace_only_progress() -> None:
    inputs = _inputs()
    progress = _progress()
    updated = inputs_with_opt_in_metric_rows(
        inputs, generational_progress=progress
    )
    assert updated.generational_progress is progress
    assert updated.run_id == inputs.run_id
    assert updated.input_revision == inputs.input_revision
    assert updated.window_end == inputs.window_end


def test_generational_arm_emits_family_through_collector() -> None:
    arm = _arm(_progress())
    bundle = assemble_arm_metric_bundle(arm)
    assert _FAMILY in {document.metric_family for document in bundle.documents}
    collector = collect_catalog_metrics(arm)
    fields = dict(collector.fields)
    assert fields[f"{_FAMILY}_availability"] == "present"
    assert f"{_FAMILY}_fingerprint_prefix" in fields


def test_legacy_arm_omits_family() -> None:
    arm = _arm(None)
    bundle = assemble_arm_metric_bundle(arm)
    assert _FAMILY not in {document.metric_family for document in bundle.documents}


def test_assembly_is_deterministic() -> None:
    first = assemble_arm_metric_bundle(_arm(_progress()))
    second = assemble_arm_metric_bundle(_arm(_progress()))
    assert first.fingerprints == second.fingerprints
