"""Stable analytical organization identities across windows."""

from __future__ import annotations

import pytest

from analysis import (
    OrganizationCandidate,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    OrganizationDetectionResult,
    OrganizationTemporalScope,
    OrganizationWindowResult,
    assign_organization_identities,
    derive_organization_id,
)

pytestmark = pytest.mark.unit


def _candidate(
    key: str,
    window: int,
    members: tuple[str, ...],
    anchors: tuple[str, ...],
    *,
    status: OrganizationCandidateStatus = OrganizationCandidateStatus.PARTIAL,
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
        status=status,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        self_identified=False,
        owner_ids=("ada",),
        first_tick=window * 10,
        last_tick=window * 10 + 9,
    )


def _detection(
    candidates: tuple[OrganizationCandidate, ...], windows: tuple[int, ...]
) -> OrganizationDetectionResult:
    window_results = tuple(
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
    )
    return OrganizationDetectionResult(
        windows=window_results,
        candidates=candidates,
        coverage=OrganizationCoverage.of(1, 7),
    )


def test_identity_is_permutation_invariant() -> None:
    first = derive_organization_id(
        creation_tick=0,
        founding_member_ids=("a", "b"),
        structural_anchors=("goal:p1", "role:r1"),
    )
    second = derive_organization_id(
        creation_tick=0,
        founding_member_ids=("b", "a"),
        structural_anchors=("role:r1", "goal:p1"),
    )
    assert first == second
    assert first.startswith("org-")
    assert len(first) == 20


def test_small_churn_keeps_the_id_and_large_churn_mints_a_new_one() -> None:
    members = ("a", "b", "c", "d", "e")
    detection = _detection(
        (
            _candidate("w0", 0, members, ("goal:p1",)),
            _candidate("w1", 1, ("a", "b", "c", "d", "z"), ("goal:p1",)),
            _candidate("w2", 2, ("q", "r", "s", "t", "u"), ("goal:p1",)),
        ),
        (0, 1, 2),
    )
    assignment = assign_organization_identities(detection)
    ids = {candidate_id for _, candidate_id in assignment.candidate_ids}
    mapping = dict(assignment.candidate_ids)
    assert mapping["w0"] == mapping["w1"]
    assert mapping["w2"] != mapping["w0"]
    assert len(ids) == 2


def test_split_and_merge_mint_new_ids() -> None:
    detection = _detection(
        (
            _candidate("parent", 0, ("a", "b", "c", "d"), ("goal:p1",)),
            _candidate("child1", 1, ("a", "b"), ("goal:p1",)),
            _candidate("child2", 1, ("c", "d"), ("goal:p1",)),
            _candidate("merged", 2, ("a", "b", "c", "d"), ("goal:p1",)),
        ),
        (0, 1, 2),
    )
    assignment = assign_organization_identities(detection)
    mapping = dict(assignment.candidate_ids)
    assert mapping["child1"] != mapping["parent"]
    assert mapping["child2"] != mapping["parent"]
    assert mapping["merged"] != mapping["child1"]
    assert mapping["merged"] != mapping["child2"]


def test_empty_and_single_window_inputs_are_valid() -> None:
    empty = assign_organization_identities(OrganizationDetectionResult())
    assert empty.records == ()
    assert empty.transitions == ()

    single = assign_organization_identities(
        _detection((_candidate("w0", 0, ("a", "b"), ("goal:p1",)),), (0,))
    )
    assert len(single.records) == 1
    assert single.records[0].window_indexes == (0,)


def test_records_are_ordered_and_typed() -> None:
    assignment = assign_organization_identities(
        _detection(
            (
                _candidate("w1", 1, ("c", "d"), ("goal:p2",)),
                _candidate("w0", 0, ("a", "b"), ("goal:p1",)),
            ),
            (0, 1),
        )
    )
    assert [record.organization_id for record in assignment.records] == sorted(
        record.organization_id for record in assignment.records
    )
    for record in assignment.records:
        assert record.status is OrganizationCandidateStatus.PARTIAL
        assert record.member_ids == tuple(sorted(record.member_ids))
