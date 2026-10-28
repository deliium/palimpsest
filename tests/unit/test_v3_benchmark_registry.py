"""Unit tests for the V3 generational civilization benchmark registry."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from experiments import (
    BENCHMARK_SCENARIO_COUNT,
    BENCHMARK_SCENARIO_IDS,
    EVIDENCE_SELECTOR_VERSIONS,
    V3_BENCHMARK_SCENARIO_COUNT,
    V3_BENCHMARK_SCENARIO_IDS,
    V3_BENCHMARK_SUITE_ID,
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkContrastKind,
    V3BenchmarkCoverage,
    V3BenchmarkError,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkEvidenceSelector,
    V3BenchmarkExecutionKind,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkPhenomenon,
    V3BenchmarkProfile,
    V3BenchmarkRecipe,
    V3BenchmarkRunResult,
    V3BenchmarkSourceKind,
    V3BenchmarkSourceReference,
    V3BenchmarkSpec,
    V3BenchmarkSuiteResult,
    V3BenchmarkTreatmentScope,
    get_v3_benchmark_scenario,
    list_v3_benchmark_scenarios,
    registered_v3_benchmark_scenario_ids,
    v3_benchmark_scenario_id_for_request,
    v3_benchmark_suite_registry,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_30_MULTIGENERATION_FORK,
)

# Test-only deny-list. Never imported into production registry code.
_FORBIDDEN_MANDATE_PHRASES: tuple[str, ...] = (
    "must emerge",
    "government must",
    "money must",
    "religion must",
    "myth must",
    "institution must",
)


def _first_spec() -> V3BenchmarkSpec:
    return list_v3_benchmark_scenarios()[0]


def _check(**overrides: object) -> V3BenchmarkCheck:
    values: dict[str, object] = {
        "selector_id": "population_lifecycle_evidence",
        "selector_version": 1,
        "status": V3BenchmarkCheckStatus.PASS,
        "reason_code": "bounded_window_complete",
        "evidence": V3BenchmarkEvidenceAvailability.COMPLETE,
        "coverage": V3BenchmarkCoverage.EXERCISED,
        "source_references": (
            V3BenchmarkSourceReference(
                source_kind=V3BenchmarkSourceKind.OBJECTIVE_INSPECTION,
                reference_id="run-1",
                tick=8,
            ),
        ),
        "boundary_start_tick": 0,
        "boundary_end_tick": 8,
        "numerator": 1,
        "denominator": 2,
    }
    values.update(overrides)
    return V3BenchmarkCheck(**values)  # type: ignore[arg-type]


def test_registered_ids_match_locked_catalog_exactly() -> None:
    ids = registered_v3_benchmark_scenario_ids()
    assert ids == V3_BENCHMARK_SCENARIO_IDS
    assert len(ids) == V3_BENCHMARK_SCENARIO_COUNT == 30
    assert ids[0] == V3_BENCH_01_BLANK_SLATE
    assert ids[-1] == V3_BENCH_30_MULTIGENERATION_FORK
    assert len(set(ids)) == 30
    assert all(item.startswith("v3-bench-") for item in ids)
    assert V3_BENCHMARK_SUITE_ID == "v3-generational-civilization-benchmark-v1"


def test_request_numbers_cover_the_ordered_request_sequence() -> None:
    specs = list_v3_benchmark_scenarios()
    assert [spec.request_number for spec in specs] == list(range(1, 31))
    for request_number in range(1, 31):
        assert (
            v3_benchmark_scenario_id_for_request(request_number)
            == specs[request_number - 1].scenario_id
        )
    with pytest.raises(V3BenchmarkError) as excinfo:
        v3_benchmark_scenario_id_for_request(0)
    assert excinfo.value.code == "invalid_request_number"


def test_list_and_registry_cover_all_specs() -> None:
    listed = list_v3_benchmark_scenarios()
    registry = v3_benchmark_suite_registry()
    assert len(listed) == 30
    assert len(registry) == 30
    assert [item.scenario_id for item in listed] == list(V3_BENCHMARK_SCENARIO_IDS)
    for spec in listed:
        assert registry[spec.scenario_id] is spec
        assert type(spec) is V3BenchmarkSpec
        assert spec.off_v1_gate is True
        assert spec.lanes == (
            V3BenchmarkLane.MECHANISM,
            V3BenchmarkLane.RESEARCH,
        )
        assert spec.required_specs
        assert spec.required_modes
        assert spec.evidence_selectors
        assert spec.required_capture_lanes
        assert spec.non_goals
        assert spec.comparison_axis
        assert spec.recipe.horizon_ticks >= 1
        assert spec.recipe.seeds
        assert spec.recipe.arm_count >= 1


def test_every_selector_is_registered_at_the_declared_version() -> None:
    for spec in list_v3_benchmark_scenarios():
        for selector in spec.evidence_selectors:
            assert type(selector) is V3BenchmarkEvidenceSelector
            assert (
                EVIDENCE_SELECTOR_VERSIONS[selector.selector_id]
                == selector.selector_version
            )
        required = [item for item in spec.evidence_selectors if item.required]
        assert required


def test_independent_and_grouped_execution_kinds_are_declared() -> None:
    specs = list_v3_benchmark_scenarios()
    independent = [
        spec
        for spec in specs
        if spec.execution_kind is V3BenchmarkExecutionKind.INDEPENDENT
    ]
    grouped = [
        spec
        for spec in specs
        if spec.execution_kind is V3BenchmarkExecutionKind.GROUPED
    ]
    assert len(independent) == 28
    assert [spec.scenario_id for spec in grouped] == [
        V3_BENCHMARK_SCENARIO_IDS[28],
        V3_BENCHMARK_SCENARIO_IDS[29],
    ]
    for spec in independent:
        assert spec.recipe.arm_count == 1
        assert spec.recipe.treatment_scope is V3BenchmarkTreatmentScope.NONE
        assert spec.recipe.contrast_kind is V3BenchmarkContrastKind.NONE
    for spec in grouped:
        assert spec.recipe.arm_count >= 2
        assert spec.recipe.treatment_scope is V3BenchmarkTreatmentScope.RUN_OPPORTUNITY
        assert spec.recipe.contrast_kind is V3BenchmarkContrastKind.SINGLE_FACTOR
        assert spec.required_capture_lanes.count("path_dependence_artifacts") == 1


def test_v2_registry_is_unchanged() -> None:
    assert BENCHMARK_SCENARIO_COUNT == 16
    assert len(BENCHMARK_SCENARIO_IDS) == 16
    assert not any(item.startswith("v3-bench-") for item in BENCHMARK_SCENARIO_IDS)


def test_mandate_language_is_absent_from_registry_text() -> None:
    for spec in list_v3_benchmark_scenarios():
        texts = " ".join((spec.title, *spec.non_goals)).lower()
        for phrase in _FORBIDDEN_MANDATE_PHRASES:
            assert phrase not in texts


def test_unknown_scenario_is_rejected() -> None:
    with pytest.raises(V3BenchmarkError) as excinfo:
        get_v3_benchmark_scenario("v3-bench-99-unknown")
    assert excinfo.value.code == "unknown_scenario"
    with pytest.raises(V3BenchmarkError) as excinfo:
        get_v3_benchmark_scenario("bench-01-seasonal-planning")
    assert excinfo.value.code == "unknown_scenario"
    with pytest.raises(V3BenchmarkError):
        get_v3_benchmark_scenario(1)  # type: ignore[arg-type]


def test_registry_values_are_immutable_and_detached() -> None:
    spec = _first_spec()
    with pytest.raises(FrozenInstanceError):
        spec.request_number = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        spec.recipe.seeds = (1,)  # type: ignore[misc]
    assert isinstance(spec.recipe.seeds, tuple)
    assert isinstance(spec.required_specs, tuple)
    assert isinstance(spec.evidence_selectors, tuple)

    detached = V3BenchmarkRecipe(
        profile=V3BenchmarkProfile.SMOKE,
        schedule_id="v3-bench-smoke-v1",
        schedule_version=1,
        horizon_ticks=96,
        seeds=[23, 11],  # type: ignore[arg-type]
        arm_count=1,
    )
    assert detached.seeds == (23, 11)


def test_invalid_profiles_and_budgets_are_rejected() -> None:
    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkRecipe(
            profile="smoke",  # type: ignore[arg-type]
            schedule_id="v3-bench-smoke-v1",
            schedule_version=1,
            horizon_ticks=96,
            seeds=(23,),
            arm_count=1,
        )
    assert excinfo.value.code == "invalid_profile"

    with pytest.raises(V3BenchmarkError):
        V3BenchmarkRecipe(
            profile=V3BenchmarkProfile.SMOKE,
            schedule_id="v3-bench-smoke-v1",
            schedule_version=1,
            horizon_ticks=0,
            seeds=(23,),
            arm_count=1,
        )

    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkRecipe(
            profile=V3BenchmarkProfile.SMOKE,
            schedule_id="v3-bench-smoke-v1",
            schedule_version=1,
            horizon_ticks=96,
            seeds={23, 11},  # type: ignore[arg-type]
            arm_count=1,
        )
    assert excinfo.value.code == "unordered_seeds"

    with pytest.raises(V3BenchmarkError):
        V3BenchmarkRecipe(
            profile=V3BenchmarkProfile.SMOKE,
            schedule_id="v3-bench-smoke-v1",
            schedule_version=1,
            horizon_ticks=96,
            seeds=(23.5,),  # type: ignore[arg-type]
            arm_count=1,
        )


def test_contrast_scope_consistency_is_enforced() -> None:
    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkRecipe(
            profile=V3BenchmarkProfile.RESEARCH,
            schedule_id="v3-bench-research-v1",
            schedule_version=1,
            horizon_ticks=192,
            seeds=(11,),
            arm_count=2,
            treatment_scope=V3BenchmarkTreatmentScope.INITIALIZER_PROFILE,
            contrast_kind=V3BenchmarkContrastKind.SINGLE_FACTOR,
        )
    assert excinfo.value.code == "contrast_scope_mismatch"

    with pytest.raises(V3BenchmarkError):
        V3BenchmarkRecipe(
            profile=V3BenchmarkProfile.RESEARCH,
            schedule_id="v3-bench-research-v1",
            schedule_version=1,
            horizon_ticks=192,
            seeds=(11,),
            arm_count=2,
            treatment_scope=V3BenchmarkTreatmentScope.RUN_OPPORTUNITY,
            contrast_kind=V3BenchmarkContrastKind.NONE,
        )


def test_unsupported_lane_and_execution_combinations_are_rejected() -> None:
    spec = _first_spec()
    with pytest.raises(V3BenchmarkError) as excinfo:
        replace(spec, lanes=(V3BenchmarkLane.RESEARCH,))
    assert excinfo.value.code == "unsupported_lane_combination"

    with pytest.raises(V3BenchmarkError) as excinfo:
        replace(
            spec,
            recipe=replace(spec.recipe, arm_count=2),
        )
    assert excinfo.value.code == "unsupported_lane_combination"

    grouped = list_v3_benchmark_scenarios()[-1]
    with pytest.raises(V3BenchmarkError) as excinfo:
        replace(
            grouped,
            recipe=replace(
                grouped.recipe,
                treatment_scope=V3BenchmarkTreatmentScope.NONE,
                contrast_kind=V3BenchmarkContrastKind.NONE,
            ),
        )
    assert excinfo.value.code == "unsupported_lane_combination"


def test_unknown_specs_modes_and_selector_versions_are_rejected() -> None:
    spec = _first_spec()
    with pytest.raises(V3BenchmarkError):
        replace(spec, required_specs=("global_technology_registry",))
    with pytest.raises(V3BenchmarkError):
        replace(spec, required_modes=("institutional_economy",))
    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkEvidenceSelector(selector_id="unknown_selector", selector_version=1)
    assert excinfo.value.code == "unknown_selector"
    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkEvidenceSelector(
            selector_id="population_lifecycle_evidence", selector_version=2
        )
    assert excinfo.value.code == "unknown_selector_version"
    with pytest.raises(V3BenchmarkError):
        replace(spec, required_capture_lanes=("private_truth_backchannel",))


def test_duplicate_and_unordered_collections_are_rejected() -> None:
    spec = _first_spec()
    with pytest.raises(V3BenchmarkError):
        replace(spec, non_goals=("same note", "same note"))
    with pytest.raises(V3BenchmarkError):
        replace(spec, required_specs={"population_lifecycle"})  # type: ignore[arg-type]
    with pytest.raises(V3BenchmarkError):
        replace(spec, off_v1_gate=False)


def test_null_phenomenon_with_complete_evidence_passes() -> None:
    check = _check(
        status=V3BenchmarkCheckStatus.PASS,
        numerator=0,
        denominator=4,
    )
    run = V3BenchmarkRunResult(
        scenario_id=V3_BENCH_01_BLANK_SLATE,
        lane=V3BenchmarkLane.RESEARCH,
        execution_status=V3BenchmarkExecutionStatus.COMPLETED,
        declared_horizon=8,
        ticks_committed=8,
        coverage=V3BenchmarkCoverage.EXERCISED,
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        phenomenon=V3BenchmarkPhenomenon.NOT_DETECTED,
        checks=(check,),
    )
    assert run.phenomenon is V3BenchmarkPhenomenon.NOT_DETECTED
    suite = V3BenchmarkSuiteResult(profile=V3BenchmarkProfile.SMOKE, runs=(run,))
    assert suite.scenario_ids() == (V3_BENCH_01_BLANK_SLATE,)


def test_unavailable_evidence_cannot_pass_a_check() -> None:
    with pytest.raises(V3BenchmarkError) as excinfo:
        _check(evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE)
    assert excinfo.value.code == "pass_requires_complete_evidence"

    with pytest.raises(V3BenchmarkError) as excinfo:
        _check(coverage=V3BenchmarkCoverage.NOT_EXERCISED)
    assert excinfo.value.code == "pass_requires_exercised_coverage"

    with pytest.raises(V3BenchmarkError):
        _check(source_references=())

    unexecuted = _check(
        status=V3BenchmarkCheckStatus.UNEXECUTED,
        evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
        coverage=V3BenchmarkCoverage.NOT_EXERCISED,
        numerator=None,
        denominator=None,
        source_references=(),
    )
    assert unexecuted.status is V3BenchmarkCheckStatus.UNEXECUTED


def test_complete_evidence_requires_the_full_declared_horizon() -> None:
    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkRunResult(
            scenario_id=V3_BENCH_01_BLANK_SLATE,
            lane=V3BenchmarkLane.RESEARCH,
            execution_status=V3BenchmarkExecutionStatus.COMPLETED,
            declared_horizon=96,
            ticks_committed=64,
            coverage=V3BenchmarkCoverage.EXERCISED,
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            phenomenon=V3BenchmarkPhenomenon.UNKNOWN,
            checks=(),
        )
    assert excinfo.value.code == "incomplete_horizon"

    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkRunResult(
            scenario_id=V3_BENCH_01_BLANK_SLATE,
            lane=V3BenchmarkLane.RESEARCH,
            execution_status=V3BenchmarkExecutionStatus.TIMED_OUT,
            declared_horizon=96,
            ticks_committed=64,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            phenomenon=V3BenchmarkPhenomenon.UNKNOWN,
            checks=(),
        )
    assert excinfo.value.code == "complete_evidence_requires_completion"

    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkRunResult(
            scenario_id=V3_BENCH_01_BLANK_SLATE,
            lane=V3BenchmarkLane.RESEARCH,
            execution_status=V3BenchmarkExecutionStatus.TIMED_OUT,
            declared_horizon=96,
            ticks_committed=64,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            phenomenon=V3BenchmarkPhenomenon.NOT_DETECTED,
            checks=(),
        )
    assert excinfo.value.code == "phenomenon_requires_complete_evidence"


def test_suite_result_rejects_duplicate_runs_and_publication_values() -> None:
    run = V3BenchmarkRunResult(
        scenario_id=V3_BENCH_01_BLANK_SLATE,
        lane=V3BenchmarkLane.MECHANISM,
        execution_status=V3BenchmarkExecutionStatus.NOT_RUN,
        declared_horizon=96,
        ticks_committed=0,
        coverage=V3BenchmarkCoverage.NOT_EXERCISED,
        evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
        phenomenon=V3BenchmarkPhenomenon.UNKNOWN,
        checks=(),
    )
    with pytest.raises(V3BenchmarkError) as excinfo:
        V3BenchmarkSuiteResult(
            profile=V3BenchmarkProfile.SMOKE, runs=(run, run)
        )
    assert excinfo.value.code == "duplicate_run"

    with pytest.raises(V3BenchmarkError) as excinfo:
        replace(run, publication_status="private_truth_dump")
    assert excinfo.value.code == "invalid_publication_status"
