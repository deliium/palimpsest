"""Dependency-care analysis metric family tests."""

from __future__ import annotations

from analysis.dependency_care_metrics import (
    CAREGIVER_DIVERSITY_METRIC_VERSION,
    CAREGIVING_BURDEN_METRIC_VERSION,
    DEPENDENT_SURVIVAL_METRIC_VERSION,
    INTERGENERATIONAL_COOPERATION_METRIC_VERSION,
    CareActRow,
    DependencyAgentRow,
    compute_caregiver_diversity,
    compute_caregiving_burden,
    compute_dependency_survival,
    compute_intergenerational_cooperation,
)
from analysis.models import MetricAvailability
from analysis.specifications import (
    COOPERATION_ACTION_KINDS,
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
)


def test_catalog_includes_dependency_care_families() -> None:
    specs = all_metric_specifications()
    assert len(specs) == METRIC_FAMILY_COUNT == 71
    assert frozenset(spec.family_id for spec in specs) == frozenset(MetricFamilyId)
    validate_metric_catalog()
    assert "feed" in COOPERATION_ACTION_KINDS
    assert "transport" in COOPERATION_ACTION_KINDS


def test_versions_match_spec() -> None:
    assert (
        metric_specification(MetricFamilyId.DEPENDENCY_SURVIVAL).version_identifier
        == DEPENDENT_SURVIVAL_METRIC_VERSION
    )
    assert (
        metric_specification(MetricFamilyId.CAREGIVER_DIVERSITY).version_identifier
        == CAREGIVER_DIVERSITY_METRIC_VERSION
    )
    assert (
        metric_specification(MetricFamilyId.CAREGIVING_BURDEN).version_identifier
        == CAREGIVING_BURDEN_METRIC_VERSION
    )
    assert (
        metric_specification(
            MetricFamilyId.INTERGENERATIONAL_COOPERATION
        ).version_identifier
        == INTERGENERATIONAL_COOPERATION_METRIC_VERSION
    )


def test_dependency_survival_rates() -> None:
    document = compute_dependency_survival(
        (
            DependencyAgentRow("dep-1", "dependent", True, 10, 0),
            DependencyAgentRow("dep-2", "dependent", False, 4, 0),
            DependencyAgentRow("ind-1", "independent", True, 20, 1),
        ),
        run_id="run-dep-surv",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["dependent_count"] == 2
    assert document.values["dependent_survival_rate"] == 0.5
    assert document.values["independent_survival_rate"] == 1.0


def test_caregiver_diversity_and_burden() -> None:
    acts = (
        CareActRow("care-a", "dep-1", "feed", 1, fatigue_delta=0.1),
        CareActRow("care-b", "dep-1", "help", 2, fatigue_delta=0.2),
        CareActRow("care-a", "dep-2", "transport", 3, fatigue_delta=0.3),
    )
    diversity = compute_caregiver_diversity(
        acts, run_id="run-div", input_revision="rev-1"
    )
    assert diversity.availability is MetricAvailability.PRESENT
    assert diversity.values["dependent_count"] == 2
    assert diversity.values["mean_unique_caregivers"] == 1.5
    burden = compute_caregiving_burden(
        acts, run_id="run-burden", input_revision="rev-1"
    )
    assert burden.availability is MetricAvailability.PRESENT
    assert burden.values["caregiver_count"] == 2
    assert burden.values["care_act_count"] == 3


def test_intergenerational_cooperation_rate() -> None:
    acts = (
        CareActRow(
            "care-a",
            "dep-1",
            "feed",
            1,
            caregiver_generation_index=1,
            dependent_generation_index=0,
        ),
        CareActRow(
            "care-b",
            "dep-2",
            "help",
            2,
            caregiver_generation_index=0,
            dependent_generation_index=0,
        ),
    )
    document = compute_intergenerational_cooperation(
        acts, run_id="run-igen", input_revision="rev-1"
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["cross_generation_act_count"] == 1
    assert document.values["cross_generation_rate"] == 0.5


def test_empty_rows_absent() -> None:
    assert (
        compute_dependency_survival((), run_id="r", input_revision="v").availability
        is MetricAvailability.ABSENT
    )
    assert (
        compute_caregiver_diversity((), run_id="r", input_revision="v").availability
        is MetricAvailability.ABSENT
    )
