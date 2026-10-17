"""Deterministic candidate-community clustering over detached lanes."""

from __future__ import annotations

from analysis.models import MetricAvailability, MetricCoverage
from analysis.society_emergence import (
    SocietyEdgeRow,
    SocietyEmissionResult,
    SocietyResidenceRow,
    compute_candidate_communities,
    compute_society_emergence,
)


def _edge(source: str, target: str, tick: int = 1) -> SocietyEdgeRow:
    return SocietyEdgeRow(
        source_person_id=source,
        target_person_id=target,
        tick=tick,
        lane="interaction",
    )


def test_two_disconnected_region_separated_populations() -> None:
    residence = (
        SocietyResidenceRow("a", "north", 0, 10),
        SocietyResidenceRow("b", "north", 0, 10),
        SocietyResidenceRow("c", "south", 0, 10),
        SocietyResidenceRow("d", "south", 0, 10),
    )
    result = compute_candidate_communities(
        residence,
        (_edge("a", "b"), _edge("c", "d")),
        (),
        ("a", "b", "c", "d"),
        10,
    )
    assert len(result.communities) == 2
    assert {frozenset(item.person_ids) for item in result.communities} == {
        frozenset({"a", "b"}),
        frozenset({"c", "d"}),
    }
    regions = sorted(item.residence_region_ids for item in result.communities)
    assert regions == [("north",), ("south",)]
    assert result.singleton_person_ids == ()
    assert result.coverage.observed == 4


def test_single_bridge_merges_populations() -> None:
    result = compute_candidate_communities(
        (),
        (
            _edge("a", "b"),
            _edge("a", "c"),
            _edge("a", "d"),
            _edge("b", "c"),
            _edge("b", "d"),
            _edge("c", "d"),
        ),
        (),
        ("a", "b", "c", "d"),
        3,
    )
    assert len(result.communities) == 1
    assert set(result.communities[0].person_ids) == {"a", "b", "c", "d"}


def test_empty_lanes_yield_singletons_with_coverage_gap() -> None:
    result = compute_candidate_communities((), (), (), ("a", "b"), 0)
    assert result.communities == ()
    assert result.singleton_person_ids == ("a", "b")
    assert result.coverage.observed == 0
    assert result.coverage.expected == 2
    assert result.coverage.ratio == 0.0


def test_lane_membership_deduplicates_persons() -> None:
    residence = (SocietyResidenceRow("a", "north", 0, 4),)
    interaction = (_edge("a", "b"),)
    trust = (
        SocietyEdgeRow(
            source_person_id="b",
            target_person_id="a",
            tick=2,
            lane="trust",
            weight=0.5,
        ),
    )
    result = compute_candidate_communities(residence, interaction, trust, ("a", "b"), 4)
    assert len(result.communities) == 1
    community = result.communities[0]
    assert community.person_ids == ("a", "b")
    assert community.lane_coverage == frozenset({"interaction", "residence", "trust"})


def test_unknown_and_dead_persons_fail_closed() -> None:
    from analysis.society_emergence import SocietyEmergenceError

    try:
        compute_candidate_communities((), (_edge("a", "ghost"),), (), ("a",), 1)
    except SocietyEmergenceError as error:
        assert error.reason_code == "unknown_person"
    else:  # pragma: no cover - defensive
        raise AssertionError("unknown person was accepted")


def test_labels_are_stable_across_calls() -> None:
    edges = (_edge("a", "b"), _edge("c", "d"))
    first = compute_candidate_communities((), edges, (), ("a", "b", "c", "d"), 1)
    second = compute_candidate_communities((), edges, (), ("a", "b", "c", "d"), 1)
    assert [item.community_id for item in first.communities] == [
        item.community_id for item in second.communities
    ]


def test_empty_emission_document_is_absent_and_stable() -> None:
    result = SocietyEmissionResult(
        communities=(),
        singleton_person_ids=(),
        coverage=MetricCoverage(observed=0, expected=0),
    )
    first = compute_society_emergence(result, run_id="run-s", input_revision="rev-s")
    second = compute_society_emergence(result, run_id="run-s", input_revision="rev-s")
    assert first.availability is MetricAvailability.ABSENT
    assert first.values["community_count"] == 0
    assert first == second
