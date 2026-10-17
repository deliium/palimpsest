"""Candidate-society contracts reject malformed or content-bearing rows."""

from __future__ import annotations

import dataclasses

import pytest

from analysis.models import MetricCoverage
from analysis.society_emergence import (
    CandidateCommunityRow,
    SocietyEmergenceError,
    SocietyEmissionResult,
    derive_community_id,
)


def _community(person_ids: tuple[str, ...]) -> CandidateCommunityRow:
    return CandidateCommunityRow.from_members(
        person_ids=person_ids,
        lane_coverage=("interaction",),
        residence_region_ids=("north",),
        tick_start=1,
        tick_end=5,
    )


def test_community_id_is_content_derived_and_order_independent() -> None:
    first = derive_community_id(("b", "a"))
    second = derive_community_id(("a", "b"))
    assert first == second
    assert first.startswith("community-")
    digest = first.removeprefix("community-")
    assert len(digest) == 16
    assert all(char in "0123456789abcdef" for char in digest)


def test_row_sorts_persons_and_rejects_empty_set() -> None:
    row = _community(("b", "a"))
    assert row.person_ids == ("a", "b")
    with pytest.raises(SocietyEmergenceError, match="empty_person_set"):
        CandidateCommunityRow.from_members(
            person_ids=(),
            lane_coverage=("interaction",),
        )


def test_row_rejects_content_payloads_and_bad_lanes() -> None:
    with pytest.raises(SocietyEmergenceError, match="content_payload_rejected"):
        CandidateCommunityRow(
            community_id="community-0000000000000000",
            person_ids=({"text": "narrative"},),  # type: ignore[arg-type]
            lane_coverage=frozenset({"interaction"}),
            residence_region_ids=(),
            tick_start=0,
            tick_end=1,
        )
    with pytest.raises(SocietyEmergenceError, match="unknown_lane"):
        CandidateCommunityRow.from_members(
            person_ids=("a",),
            lane_coverage=("rumor",),
        )


def test_row_rejects_forged_community_id() -> None:
    with pytest.raises(SocietyEmergenceError, match="community_id_mismatch"):
        CandidateCommunityRow(
            community_id="community-forged",
            person_ids=("a", "b"),
            lane_coverage=frozenset({"interaction"}),
            residence_region_ids=(),
            tick_start=0,
            tick_end=1,
        )


def test_result_rejects_duplicate_members_and_unknown_persons() -> None:
    a = _community(("a", "b"))
    b = _community(("b", "c"))
    with pytest.raises(
        SocietyEmergenceError, match="duplicate_person_across_communities"
    ):
        SocietyEmissionResult(
            communities=(a, b),
            singleton_person_ids=(),
            coverage=MetricCoverage(observed=3, expected=3),
            known_person_ids=("a", "b", "c"),
        )
    single = _community(("a", "b"))
    with pytest.raises(SocietyEmergenceError, match="unknown_person"):
        SocietyEmissionResult(
            communities=(single,),
            singleton_person_ids=(),
            coverage=MetricCoverage(observed=2, expected=2),
            known_person_ids=("a",),
        )


def test_result_canonical_order_round_trips_and_is_frozen() -> None:
    b = _community(("c", "d"))
    a = _community(("a", "b"))
    result = SocietyEmissionResult(
        communities=(b, a),
        singleton_person_ids=("e",),
        coverage=MetricCoverage(observed=4, expected=5),
        known_person_ids=("e", "d", "c", "b", "a"),
    )
    assert result.communities == tuple(
        sorted(result.communities, key=lambda item: item.community_id)
    )
    assert result.singleton_person_ids == ("e",)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.communities = ()  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.communities[0].person_ids = ()  # type: ignore[misc]
