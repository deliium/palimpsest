"""Four organization metric families: keys, availability, and counts."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from analysis import (
    MetricAvailability,
    MetricDocument,
    OrganizationAnalysis,
    OrganizationCandidate,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    OrganizationDetectionResult,
    OrganizationMembershipStatus,
    OrganizationTemporalScope,
    OrganizationWindowResult,
    assign_organization_identities,
    compute_organization_formation_metric,
    compute_organization_lineage_metric,
    compute_organization_membership_metric,
    compute_organization_structure_metric,
    derive_organization_lineage,
    metric_specification,
)
from analysis.specifications import MetricFamilyId

pytestmark = pytest.mark.unit


def _candidate(
    key: str,
    window: int,
    members: tuple[str, ...],
    *,
    status: OrganizationCandidateStatus = OrganizationCandidateStatus.RECOGNIZED,
    goals: tuple[str, ...] = ("p1",),
    roles: tuple[str, ...] = ("r1",),
    records: tuple[str, ...] = (),
    identity: tuple[str, ...] = ("water-carriers",),
) -> OrganizationCandidate:
    claims = tuple(
        __import__("analysis").OrganizationMemberClaim(
            member_id=member,
            status=OrganizationMembershipStatus.EXPLICIT,
            basis="self_identification",
            temporal_scope=OrganizationTemporalScope.ONGOING,
            owner_ids=("ada",),
            channels=("communicated",),
        )
        for member in members
    )
    return OrganizationCandidate(
        candidate_key=key,
        window_index=window,
        member_ids=tuple(sorted(members)),
        member_claims=claims,
        role_anchor_ids=roles,
        goal_anchor_ids=goals,
        resource_anchor_ids=(),
        procedure_anchor_ids=(),
        record_anchor_ids=records,
        commitment_ids=(),
        identity_tokens=identity,
        status=status,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        self_identified=True,
        owner_ids=("ada",),
        first_tick=window * 10,
        last_tick=window * 10 + 9,
        overlap_member_ids=("a",) if len(members) > 2 else (),
    )


def _analysis(
    candidates: tuple[OrganizationCandidate, ...],
    windows: tuple[int, ...] = (0,),
) -> OrganizationAnalysis:
    detection = OrganizationDetectionResult(
        windows=tuple(
            OrganizationWindowResult(
                window_index=index,
                start_tick=index * 10,
                end_tick=index * 10 + 9,
                candidate_keys=tuple(
                    candidate.candidate_key
                    for candidate in candidates
                    if candidate.window_index == index
                ),
                lane_presence=(
                    ("roles", True),
                    ("goals", True),
                    ("resources", False),
                    ("procedures", False),
                    ("records", True),
                    ("commitments", False),
                    ("identities", True),
                ),
            )
            for index in windows
        ),
        candidates=tuple(candidates),
        coverage=OrganizationCoverage.of(4, 7),
    )
    return derive_organization_lineage(assign_organization_identities(detection))


def _empty_analysis() -> OrganizationAnalysis:
    return derive_organization_lineage(
        assign_organization_identities(OrganizationDetectionResult())
    )


@pytest.mark.parametrize(
    ("compute", "family"),
    (
        (compute_organization_formation_metric, MetricFamilyId.ORGANIZATION_FORMATION),
        (
            compute_organization_membership_metric,
            MetricFamilyId.ORGANIZATION_MEMBERSHIP,
        ),
        (compute_organization_structure_metric, MetricFamilyId.ORGANIZATION_STRUCTURE),
        (compute_organization_lineage_metric, MetricFamilyId.ORGANIZATION_LINEAGE),
    ),
)
def test_empty_analysis_is_absent_with_no_values(
    compute: Callable[..., MetricDocument], family: MetricFamilyId
) -> None:
    analysis = _empty_analysis()
    document = compute(analysis, run_id="run-1", input_revision="rev-1")
    assert document.metric_family == family.value
    assert document.availability is MetricAvailability.ABSENT
    assert document.values == {}
    assert set(document.evidence_stages) == set(
        metric_specification(family).evidence_inputs
    )


@pytest.mark.parametrize(
    ("compute", "family"),
    (
        (compute_organization_formation_metric, MetricFamilyId.ORGANIZATION_FORMATION),
        (
            compute_organization_membership_metric,
            MetricFamilyId.ORGANIZATION_MEMBERSHIP,
        ),
        (compute_organization_structure_metric, MetricFamilyId.ORGANIZATION_STRUCTURE),
        (compute_organization_lineage_metric, MetricFamilyId.ORGANIZATION_LINEAGE),
    ),
)
def test_partial_coverage_is_partial(
    compute: Callable[..., MetricDocument], family: MetricFamilyId
) -> None:
    analysis = _analysis((_candidate("c1", 0, ("a", "b", "c")),))
    document = compute(analysis, run_id="run-1", input_revision="rev-1")
    assert document.availability is MetricAvailability.PARTIAL
    assert set(document.values) == set(metric_specification(family).value_keys)


def test_counts_match_the_fixture() -> None:
    analysis = _analysis((_candidate("c1", 0, ("a", "b", "c"), records=("rec-1",)),))
    formation = compute_organization_formation_metric(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert formation.values["candidate_count"] == 1
    assert formation.values["recognized_count"] == 1
    assert formation.values["multi_channel_candidate_count"] == 1
    assert formation.values["window_count"] == 1

    membership = compute_organization_membership_metric(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert membership.values["member_belief_count"] == 3
    assert membership.values["explicit_count"] == 3
    assert membership.values["overlap_member_count"] == 1

    structure = compute_organization_structure_metric(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert structure.values["role_count"] == 1
    assert structure.values["goal_count"] == 1
    assert structure.values["record_count"] == 1
    assert structure.values["identity_count"] == 1
    assert structure.values["candidates_with_roles"] == 1

    lineage = compute_organization_lineage_metric(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert lineage.values["emergence_count"] == 1
    assert lineage.values["continuation_count"] == 0
    assert lineage.values["lineage_window_count"] == 1
