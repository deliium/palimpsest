"""Forward-only organization lineage: all six kinds and acyclicity."""

from __future__ import annotations

import pytest

from analysis import (
    OrganizationAnalysis,
    OrganizationAnalysisError,
    OrganizationCandidate,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    OrganizationDetectionResult,
    OrganizationLineageEdge,
    OrganizationLineageKind,
    OrganizationTemporalScope,
    OrganizationWindowResult,
    assign_organization_identities,
    derive_organization_lineage,
    validate_organization_lineage,
)

pytestmark = pytest.mark.unit


def _candidate(
    key: str,
    window: int,
    members: tuple[str, ...],
    anchors: tuple[str, ...],
) -> OrganizationCandidate:
    return OrganizationCandidate(
        candidate_key=key,
        window_index=window,
        member_ids=tuple(sorted(members)),
        member_claims=(),
        role_anchor_ids=(),
        goal_anchor_ids=tuple(item.partition(":")[2] for item in anchors),
        resource_anchor_ids=(),
        procedure_anchor_ids=(),
        record_anchor_ids=(),
        commitment_ids=(),
        identity_tokens=(),
        status=OrganizationCandidateStatus.PARTIAL,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        self_identified=False,
        owner_ids=("ada",),
        first_tick=window * 10,
        last_tick=window * 10 + 9,
    )


def _analysis(
    candidates: tuple[OrganizationCandidate, ...],
    windows: tuple[int, ...],
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
                lane_presence=(("goals", True),),
            )
            for index in windows
        ),
        candidates=tuple(candidates),
        coverage=OrganizationCoverage.of(1, 7),
    )
    return derive_organization_lineage(assign_organization_identities(detection))


def _kinds(analysis: OrganizationAnalysis) -> set[OrganizationLineageKind]:
    return {edge.kind for edge in analysis.edges}


def test_continuation_and_transformation_are_distinguished() -> None:
    analysis = _analysis(
        (
            _candidate("w0", 0, ("a", "b", "c", "d"), ("goal:p1",)),
            _candidate("w1", 1, ("a", "b", "c", "d"), ("goal:p1",)),
            _candidate("w2", 2, ("a", "b", "c", "d"), ("goal:p2",)),
        ),
        (0, 1, 2),
    )
    kinds = _kinds(analysis)
    assert OrganizationLineageKind.CONTINUED in kinds
    assert OrganizationLineageKind.TRANSFORMED in kinds


def test_split_merge_dissolution_and_emergence() -> None:
    analysis = _analysis(
        (
            _candidate("parent", 0, ("a", "b", "c", "d"), ("goal:p1",)),
            _candidate("child1", 1, ("a", "b"), ("goal:p1",)),
            _candidate("child2", 1, ("c", "d"), ("goal:p1",)),
            _candidate("merged", 2, ("a", "b", "c", "d"), ("goal:p1",)),
            _candidate("new", 2, ("x", "y"), ("goal:p9",)),
            _candidate("gone", 3, ("q", "r"), ("goal:p8",)),
        ),
        (0, 1, 2, 3),
    )
    kinds = _kinds(analysis)
    assert {
        OrganizationLineageKind.SPLIT,
        OrganizationLineageKind.MERGE,
        OrganizationLineageKind.DISSOLVED,
        OrganizationLineageKind.EMERGED,
    } <= kinds


def test_edges_are_monotone_and_records_are_known() -> None:
    analysis = _analysis(
        (
            _candidate("w0", 0, ("a", "b"), ("goal:p1",)),
            _candidate("w1", 1, ("a", "b"), ("goal:p1",)),
        ),
        (0, 1),
    )
    ticks = [edge.tick for edge in analysis.edges]
    assert ticks == sorted(ticks)
    validate_organization_lineage(
        analysis.edges,
        known_ids=tuple(record.organization_id for record in analysis.records),
    )
    assert len(analysis.determinism_digest) == 64


def test_backward_edge_is_rejected() -> None:
    first = "org-0000000000000001"
    second = "org-0000000000000002"
    edges = (
        OrganizationLineageEdge(
            kind=OrganizationLineageKind.CONTINUED,
            from_id=first,
            to_id=second,
            tick=5,
        ),
        OrganizationLineageEdge(
            kind=OrganizationLineageKind.CONTINUED,
            from_id=second,
            to_id=first,
            tick=4,
        ),
    )
    with pytest.raises(OrganizationAnalysisError) as excinfo:
        validate_organization_lineage(edges, known_ids=(first, second))
    assert excinfo.value.reason_code == "organization_lineage_tick"


def test_cycle_is_rejected() -> None:
    first = "org-0000000000000001"
    second = "org-0000000000000002"
    edges = (
        OrganizationLineageEdge(
            kind=OrganizationLineageKind.TRANSFORMED,
            from_id=first,
            to_id=second,
            tick=5,
        ),
        OrganizationLineageEdge(
            kind=OrganizationLineageKind.TRANSFORMED,
            from_id=second,
            to_id=first,
            tick=6,
        ),
    )
    with pytest.raises(OrganizationAnalysisError) as excinfo:
        validate_organization_lineage(edges, known_ids=(first, second))
    assert excinfo.value.reason_code == "organization_lineage_cycle"


def test_missing_windows_are_not_zero_counts() -> None:
    analysis = _analysis((_candidate("w0", 0, ("a", "b"), ("goal:p1",)),), (0,))
    assert analysis.coverage.ratio is not None
    assert analysis.coverage.ratio < 1.0
    assert analysis.windows
