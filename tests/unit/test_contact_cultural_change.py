"""Pre/post-contact cultural divergence windows and membership stability."""

from __future__ import annotations

from analysis.contact_cultural_change import (
    ContactDigestRow,
    compute_contact_cultural_change,
    compute_contact_cultural_change_metric,
)
from analysis.society_contact import ContactPairRow
from analysis.society_emergence import CandidateCommunityRow


def _communities() -> tuple[CandidateCommunityRow, ...]:
    return (
        CandidateCommunityRow.from_members(
            person_ids=("a-1",), lane_coverage=("interaction",)
        ),
        CandidateCommunityRow.from_members(
            person_ids=("b-1",), lane_coverage=("interaction",)
        ),
    )


def _pair(onset: int = 5) -> ContactPairRow:
    communities = _communities()
    return ContactPairRow(
        community_a_id=communities[0].community_id,
        community_b_id=communities[1].community_id,
        onset_tick=onset,
        contact_event_count=1,
        location_tick_count=1,
        cross_community_person_ticks=2,
        interaction_counts=(),
        cross_community_kinship_edge_count=0,
    )


def _dimension(offset: int) -> str:
    from analysis.society_divergence import SOCIETY_DIMENSIONS

    return SOCIETY_DIMENSIONS[offset % len(SOCIETY_DIMENSIONS)]


def test_identical_distributions_yield_zero_divergence() -> None:
    dimension = _dimension(0)
    rows = []
    for tick in (1, 2, 6, 7):
        rows.append(ContactDigestRow(dimension, "a-1", "tok-x", tick))
        rows.append(ContactDigestRow(dimension, "b-1", "tok-x", tick))
    result = compute_contact_cultural_change(
        _communities(), (_pair(),), rows, final_tick=10
    )
    row = next(item for item in result.rows if item.dimension == dimension)
    assert row.pre_divergence == 0.0
    assert row.post_divergence == 0.0
    assert row.convergence_delta == 0.0


def test_disjoint_pre_to_shared_post_is_positive_convergence() -> None:
    dimension = _dimension(1)
    rows = (
        ContactDigestRow(dimension, "a-1", "tok-a", 1),
        ContactDigestRow(dimension, "b-1", "tok-b", 1),
        ContactDigestRow(dimension, "a-1", "tok-a", 6),
        ContactDigestRow(dimension, "b-1", "tok-a", 6),
    )
    result = compute_contact_cultural_change(
        _communities(), (_pair(),), rows, final_tick=10
    )
    row = next(item for item in result.rows if item.dimension == dimension)
    assert row.convergence_delta is not None
    assert row.convergence_delta > 0.0


def test_missing_post_window_is_partial_never_zero() -> None:
    dimension = _dimension(2)
    rows = (
        ContactDigestRow(dimension, "a-1", "tok-a", 1),
        ContactDigestRow(dimension, "b-1", "tok-b", 1),
    )
    result = compute_contact_cultural_change(
        _communities(), (_pair(),), rows, final_tick=10
    )
    row = next(item for item in result.rows if item.dimension == dimension)
    assert row.reason_code == "missing_window"
    document = compute_contact_cultural_change_metric(
        result, run_id="run", input_revision="rev"
    )
    assert document.availability.value in {"partial", "absent"}


def test_membership_stability_is_exposed() -> None:
    result = compute_contact_cultural_change(
        _communities(),
        (_pair(),),
        (),
        final_tick=10,
        pre_community_by_person={"a-1": _communities()[0].community_id},
    )
    assert result.membership_stability == 0.5
