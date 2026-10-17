"""Isolation audit classifies cross-community transfer by physical journeys."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.society_emergence import CandidateCommunityRow
from analysis.society_isolation import (
    SocietyEvidenceEdge,
    SocietyIsolationError,
    SocietyJourneyRow,
    compute_society_isolation,
    compute_society_isolation_metric,
)


def _communities() -> tuple[CandidateCommunityRow, CandidateCommunityRow]:
    north = CandidateCommunityRow.from_members(
        person_ids=("a", "b"),
        lane_coverage=("interaction",),
        residence_region_ids=("north",),
    )
    south = CandidateCommunityRow.from_members(
        person_ids=("c", "d"),
        lane_coverage=("interaction",),
        residence_region_ids=("south",),
    )
    return north, south


def _edge(edge_id: str, source: str, target: str, tick: int) -> SocietyEvidenceEdge:
    return SocietyEvidenceEdge(
        edge_id=edge_id,
        kind="communication",
        source_person_id=source,
        target_person_id=target,
        tick=tick,
    )


def test_travel_then_contact_is_explained() -> None:
    north, south = _communities()
    journeys = (
        SocietyJourneyRow(
            person_id="a",
            origin_region_id="north",
            destination_region_id="south",
            arrival_tick=3,
        ),
    )
    result = compute_society_isolation(
        (north, south), (_edge("e1", "a", "c", 5),), journeys
    )
    assert result.explained_count == 1
    assert result.unexplained_count == 0
    assert result.rows[0].reason_code == "arrival_precedes_edge"


def test_edge_before_arrival_is_flagged() -> None:
    north, south = _communities()
    journeys = (
        SocietyJourneyRow(
            person_id="a",
            origin_region_id="north",
            destination_region_id="south",
            arrival_tick=6,
        ),
    )
    result = compute_society_isolation(
        (north, south), (_edge("e1", "a", "c", 5),), journeys
    )
    assert result.explained_count == 0
    assert result.unexplained_count == 1
    assert result.rows[0].reason_code == "no_prior_arrival"


def test_no_journey_evidence_is_unexplained_finding() -> None:
    north, south = _communities()
    result = compute_society_isolation((north, south), (_edge("e1", "b", "d", 2),), ())
    assert result.unexplained_count == 1
    assert result.rows[0].reason_code == "no_journey_evidence"


def test_same_community_edges_are_not_audited() -> None:
    north, south = _communities()
    result = compute_society_isolation((north, south), (_edge("e1", "a", "b", 2),), ())
    assert result.rows == ()


def test_metric_marks_unexplained_as_partial_finding() -> None:
    north, south = _communities()
    result = compute_society_isolation((north, south), (_edge("e1", "b", "d", 2),), ())
    doc = compute_society_isolation_metric(
        result,
        run_id="run-i",
        input_revision="rev-i",
        community_count=2,
    )
    assert doc.availability is MetricAvailability.PARTIAL
    assert doc.values["unexplained_count"] == 1
    assert doc.values["explained_count"] == 0
    assert doc.provenance.notes_code == "unexplained_edges"


def test_empty_audit_is_absent() -> None:
    north, south = _communities()
    result = compute_society_isolation((north, south), (), ())
    doc = compute_society_isolation_metric(
        result,
        run_id="run-i",
        input_revision="rev-i",
        community_count=2,
    )
    assert doc.availability is MetricAvailability.ABSENT


def test_unknown_kind_rejected() -> None:
    try:
        SocietyEvidenceEdge(
            edge_id="e1",
            kind="telepathy",
            source_person_id="a",
            target_person_id="c",
            tick=1,
        )
    except SocietyIsolationError as error:
        assert error.reason_code == "unknown_evidence_kind"
    else:  # pragma: no cover
        raise AssertionError("unknown kind accepted")
