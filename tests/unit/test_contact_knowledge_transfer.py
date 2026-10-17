"""Cross-community practical-knowledge transfer counting."""

from __future__ import annotations

from analysis.contact_knowledge_transfer import (
    ContactPracticalKnowledgeAuditRow,
    compute_contact_knowledge_transfer,
    compute_contact_knowledge_transfer_metric,
)
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


def test_cross_community_teaching_transfer_counted() -> None:
    result = compute_contact_knowledge_transfer(
        _communities(),
        rows=(
            ContactPracticalKnowledgeAuditRow(
                "b-1", "teaching", "a-1", "a-1", 1, False, None, 3
            ),
        ),
    )
    assert result.total_transfer_count == 1
    assert result.channel_count("teaching") == 1
    assert result.donor_recipient_pairs == (
        (_communities()[0].community_id, _communities()[1].community_id),
    )


def test_same_community_transfer_excluded() -> None:
    result = compute_contact_knowledge_transfer(
        _communities(),
        rows=(
            ContactPracticalKnowledgeAuditRow(
                "a-1", "imitation", "a-1", None, 1, False, None, 3
            ),
        ),
    )
    assert result.total_transfer_count == 0


def test_unknown_donor_is_unresolved_not_zero() -> None:
    result = compute_contact_knowledge_transfer(
        _communities(),
        rows=(
            ContactPracticalKnowledgeAuditRow(
                "b-1", "teaching", "ghost", "ghost", 1, False, None, 3
            ),
        ),
    )
    assert result.unresolved_donor_count == 1
    assert result.total_transfer_count == 0


def test_mutated_and_mean_hop_aggregates() -> None:
    result = compute_contact_knowledge_transfer(
        _communities(),
        rows=(
            ContactPracticalKnowledgeAuditRow(
                "b-1", "teaching", "a-1", "a-1", 1, True, 0.25, 3
            ),
            ContactPracticalKnowledgeAuditRow(
                "b-1", "written_record", "a-1", None, 3, False, 0.75, 4
            ),
        ),
    )
    assert result.mutated_transfer_count == 1
    assert result.mean_hop == 2.0
    assert result.fingerprint_distance_mean == 0.5


def test_metric_reports_channels_and_rate() -> None:
    result = compute_contact_knowledge_transfer(
        _communities(),
        rows=(
            ContactPracticalKnowledgeAuditRow(
                "b-1", "combination", "a-1", None, 0, False, None, 3
            ),
        ),
    )
    document = compute_contact_knowledge_transfer_metric(
        result, run_id="run", input_revision="rev"
    )
    assert document.values["total_transfer_count"] == 1
    assert document.values["combination_count"] == 1
    assert document.availability.value == "present"


def test_rows_before_onset_are_excluded() -> None:
    result = compute_contact_knowledge_transfer(
        _communities(),
        rows=(
            ContactPracticalKnowledgeAuditRow(
                "b-1", "teaching", "a-1", "a-1", 1, False, None, 1
            ),
            ContactPracticalKnowledgeAuditRow(
                "b-1", "teaching", "a-1", "a-1", 1, False, None, 4
            ),
        ),
        onset_tick_by_person={"b-1": 3},
    )
    assert result.total_transfer_count == 1
