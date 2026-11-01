"""Two detached metric families over organization operation beliefs."""

from __future__ import annotations

import pytest

from analysis import (
    OrganizationCandidateOperations,
    OrganizationOperationSummary,
    compute_organization_operation_authority_metric,
    compute_organization_operations_metric,
    metric_specification,
)
from analysis.models import MetricAvailability
from analysis.specifications import MetricFamilyId

pytestmark = pytest.mark.unit

ORG = f"org-{'a' * 16}"
AUTHORITY_COUNTS = (
    ("decision_belief", 1),
    ("observation", 1),
    ("procedure_belief", 1),
    ("role_belief", 1),
    ("self_authored", 2),
    ("unknown", 1),
)


def _candidate(
    *,
    operation_count: int = 8,
    contested: tuple[str, ...] = ("resource_control",),
) -> OrganizationCandidateOperations:
    return OrganizationCandidateOperations(
        organization_id=ORG,
        control_counts=(("resource_control", 1), ("storage", 2)),
        admission_count=1,
        departure_count=1,
        assignment_count=1,
        procedure_action_count=1,
        commitment_count=1,
        decision_count=1,
        action_count=1,
        contested_domains=contested,
        authority_counts=AUTHORITY_COUNTS,
        provenance_counts=(("observed_effect", 1),),
        orphaned_count=0,
        mean_owner_support=1.5,
        coverage_ratio=0.25 if operation_count else None,
    )


def _summary(
    *,
    coverage: float | None = 1.0,
    orphaned: int = 0,
    history_truncated: bool = False,
    contested_operation_count: int = 2,
) -> OrganizationOperationSummary:
    candidate = _candidate()
    return OrganizationOperationSummary(
        candidates=(candidate,),
        as_of_tick=9,
        control_counts=(("resource_control", 1), ("storage", 2)),
        admission_count=1,
        departure_count=1,
        assignment_count=1,
        procedure_action_count=1,
        commitment_count=1,
        decision_count=1,
        action_count=1,
        contested_domain_counts=(("resource_control", 2), ("procedure_action", 1)),
        contested_operation_count=contested_operation_count,
        authority_contest_count=1,
        authority_counts=AUTHORITY_COUNTS,
        provenance_counts=(("observed_effect", 1),),
        provenance_known_count=1,
        orphaned_count=orphaned,
        mean_owner_support=1.5,
        coverage_ratio=coverage,
        history_truncated=history_truncated,
    )


def test_operation_families_register_at_version_one() -> None:
    operations = metric_specification(MetricFamilyId.ORGANIZATION_OPERATIONS)
    authority = metric_specification(
        MetricFamilyId.ORGANIZATION_OPERATION_AUTHORITY
    )
    assert operations.family_id.value == "organization_operations"
    assert operations.algorithm_version == "1"
    assert authority.family_id.value == "organization_operation_authority"
    assert authority.algorithm_version == "1"


def test_operation_metric_reports_exact_keys_and_counts() -> None:
    summary = _summary()
    document = compute_organization_operations_metric(
        summary, run_id="run-1", input_revision="rev-1"
    )
    spec = metric_specification(MetricFamilyId.ORGANIZATION_OPERATIONS)
    assert document.availability is MetricAvailability.PRESENT
    assert set(document.values) == set(spec.value_keys)
    assert document.values["control_count"] == 1
    assert document.values["storage_count"] == 2
    assert document.values["record_keeping_count"] == 0
    assert document.values["admission_count"] == 1
    assert document.values["departure_count"] == 1
    assert document.values["assignment_count"] == 1
    assert document.values["procedure_action_count"] == 1
    assert document.values["commitment_count"] == 1
    assert document.values["decision_count"] == 1
    assert document.values["action_count"] == 1
    assert document.values["contested_operation_count"] == 2
    assert document.values["orphaned_operation_count"] == 0
    assert document.values["provenance_known_count"] == 1
    assert document.values["operation_coverage_ratio"] == 1.0
    assert document.values["as_of_tick"] == 9


def test_authority_metric_reports_basis_and_contest_keys() -> None:
    summary = _summary()
    document = compute_organization_operation_authority_metric(
        summary, run_id="run-1", input_revision="rev-1"
    )
    spec = metric_specification(MetricFamilyId.ORGANIZATION_OPERATION_AUTHORITY)
    assert document.availability is MetricAvailability.PRESENT
    assert set(document.values) == set(spec.value_keys)
    assert document.values["authority_self_authored_count"] == 2
    assert document.values["authority_role_count"] == 1
    assert document.values["authority_decision_count"] == 1
    assert document.values["authority_procedure_count"] == 1
    assert document.values["authority_observation_count"] == 1
    assert document.values["authority_unknown_count"] == 1
    assert document.values["resource_contest_count"] == 2
    assert document.values["membership_contest_count"] == 0
    assert document.values["authority_contest_count"] == 1
    assert document.values["procedure_contest_count"] == 1
    assert document.values["orphaned_count"] == 0
    assert document.values["mean_owner_support"] == 1.5


def test_missing_summary_is_absent() -> None:
    for compute in (
        compute_organization_operations_metric,
        compute_organization_operation_authority_metric,
    ):
        document = compute(None, run_id="run-1", input_revision="rev-1")
        assert document.availability is MetricAvailability.ABSENT
        assert document.values == {}


def test_truncated_or_orphaned_evidence_is_partial() -> None:
    truncated = _summary(history_truncated=True)
    orphaned = _summary(orphaned=2, coverage=0.5)
    for summary in (truncated, orphaned):
        for compute in (
            compute_organization_operations_metric,
            compute_organization_operation_authority_metric,
        ):
            document = compute(summary, run_id="run-1", input_revision="rev-1")
            assert document.availability is MetricAvailability.PARTIAL


def test_no_composite_score_or_capacity_key_exists() -> None:
    summary = _summary()
    for compute in (
        compute_organization_operations_metric,
        compute_organization_operation_authority_metric,
    ):
        document = compute(summary, run_id="run-1", input_revision="rev-1")
        for key in document.values:
            assert "score" not in key
            assert "capacity" not in key
            assert "prevalence" not in key
            assert "probability" not in key
