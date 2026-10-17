"""Contact exposure, cross-community interaction mix, and kinship boundary."""

from __future__ import annotations

from analysis.society_contact import (
    ContactEpisodeRow,
    ContactInteractionRow,
    ContactKinshipRow,
    ContactPresenceRow,
    compute_society_contact,
    compute_society_contact_metric,
)
from analysis.society_emergence import CandidateCommunityRow


def _communities() -> tuple[CandidateCommunityRow, ...]:
    return (
        CandidateCommunityRow.from_members(
            person_ids=("a-1", "a-2"), lane_coverage=("interaction",)
        ),
        CandidateCommunityRow.from_members(
            person_ids=("b-1", "b-2"), lane_coverage=("interaction",)
        ),
    )


def test_separated_communities_have_no_contact_pair() -> None:
    result = compute_society_contact(
        _communities(),
        presence=(
            ContactPresenceRow("a-1", "loc-a", 0),
            ContactPresenceRow("b-1", "loc-b", 0),
        ),
    )
    assert result.pairs == ()
    assert (
        compute_society_contact_metric(
            result, run_id="run", input_revision="rev"
        ).availability.value
        == "absent"
    )


def test_co_presence_derives_onset_and_person_ticks() -> None:
    result = compute_society_contact(
        _communities(),
        presence=(
            ContactPresenceRow("a-1", "loc-x", 2),
            ContactPresenceRow("b-1", "loc-x", 2),
            ContactPresenceRow("a-1", "loc-x", 3),
            ContactPresenceRow("b-1", "loc-x", 3),
        ),
    )
    assert len(result.pairs) == 1
    pair = result.pairs[0]
    assert pair.onset_tick == 2
    assert pair.location_tick_count == 2
    assert pair.cross_community_person_ticks == 4


def test_observed_episode_counts_and_onset() -> None:
    result = compute_society_contact(
        _communities(),
        episodes=(
            ContactEpisodeRow(
                participant_ids=("a-1",),
                present_ids=("b-1",),
                location_id="loc-x",
                tick=4,
            ),
        ),
    )
    assert result.pairs[0].contact_event_count == 1
    assert result.pairs[0].onset_tick == 4


def test_cross_interactions_counted_same_community_and_collective_excluded() -> None:
    result = compute_society_contact(
        _communities(),
        interactions=(
            ContactInteractionRow("communication", "a-1", "b-1", 1),
            ContactInteractionRow("exchange", "a-1", "b-2", 1),
            ContactInteractionRow("teaching", "a-1", "a-2", 1),
            ContactInteractionRow("conflict", "a-1", "b-1", 1),
            ContactInteractionRow("cooperation", "a-1", None, 1),
            ContactInteractionRow("collective_project_contribution", "a-1", None, 1),
        ),
    )
    pair = result.pairs[0]
    assert pair.interaction_count("communication") == 1
    assert pair.interaction_count("exchange") == 1
    assert pair.interaction_count("teaching") == 0
    assert pair.interaction_count("conflict") == 1
    assert pair.interaction_count("cooperation") == 0


def test_cross_community_kinship_edge_counted() -> None:
    result = compute_society_contact(
        _communities(),
        kinship=(ContactKinshipRow("a-1", "b-1", 5),),
    )
    assert result.pairs[0].cross_community_kinship_edge_count == 1


def test_same_community_kinship_and_unassigned_are_excluded() -> None:
    result = compute_society_contact(
        _communities(),
        kinship=(
            ContactKinshipRow("a-1", "a-2", 5),
            ContactKinshipRow("a-1", "unknown", 5),
        ),
        presence=(ContactPresenceRow("unknown", "loc-x", 1),),
    )
    assert result.pairs == ()
    assert result.unassigned_person_count == 1


def test_metric_document_reports_present_pair_with_coverage() -> None:
    result = compute_society_contact(
        _communities(),
        episodes=(
            ContactEpisodeRow(
                participant_ids=("a-1",),
                present_ids=("b-1",),
                location_id="loc-x",
                tick=4,
            ),
        ),
        presence=(
            ContactPresenceRow("a-1", "loc-x", 4),
            ContactPresenceRow("b-1", "loc-x", 4),
        ),
    )
    document = compute_society_contact_metric(
        result, run_id="run", input_revision="rev"
    )
    assert document.availability.value == "present"
    assert document.values["contact_pair_count"] == 1
    assert document.values["contact_event_count"] == 1
    assert document.provenance.notes_code == "descriptive_contact_association"


def test_collective_contribution_counts_only_when_spanning_communities() -> None:
    result = compute_society_contact(
        _communities(),
        interactions=(
            ContactInteractionRow(
                "collective_project_contribution",
                "a-1",
                None,
                1,
                participant_person_ids=("a-1", "b-1"),
            ),
            ContactInteractionRow(
                "public_good_maintenance",
                "a-1",
                None,
                1,
                participant_person_ids=("a-1", "a-2"),
            ),
        ),
    )
    assert result.collective_project_contribution_count == 1
    assert result.public_good_maintenance_count == 0
