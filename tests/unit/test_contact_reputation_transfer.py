"""Cross-community reputation transfer excludes first-hand evidence."""

from __future__ import annotations

from analysis.contact_reputation_transfer import (
    ContactReputationEvidenceRow,
    compute_contact_reputation_transfer,
)
from analysis.society_emergence import CandidateCommunityRow


def _communities() -> tuple[CandidateCommunityRow, ...]:
    return (
        CandidateCommunityRow.from_members(
            person_ids=("a-1",), lane_coverage=("interaction",)
        ),
        CandidateCommunityRow.from_members(
            person_ids=("b-1", "b-2"), lane_coverage=("interaction",)
        ),
    )


def _row(**overrides: object) -> ContactReputationEvidenceRow:
    values: dict[str, object] = {
        "owner_id": "b-1",
        "target_id": "b-2",
        "source_id": "a-1",
        "dimension": "trust",
        "channel": "communication",
        "trust_band": "high",
        "tick": 3,
    }
    values.update(overrides)
    return ContactReputationEvidenceRow(**values)  # type: ignore[arg-type]


def test_cross_community_communication_is_transfer() -> None:
    result = compute_contact_reputation_transfer(_communities(), (_row(),))
    assert result.transfer_event_count == 1
    assert result.target_count == 1


def test_same_community_and_direct_are_not_transfer() -> None:
    result = compute_contact_reputation_transfer(
        _communities(),
        (
            _row(source_id="b-2"),
            _row(channel="direct_observation", source_id=None),
            _row(channel="remembered_interaction", source_id=None),
        ),
    )
    assert result.transfer_event_count == 0
    assert result.direct_observation_coverage_count == 1
    assert result.remembered_interaction_coverage_count == 1


def test_source_equal_target_rejected_from_transfer() -> None:
    result = compute_contact_reputation_transfer(
        _communities(), (_row(source_id="b-2", target_id="b-2"),)
    )
    assert result.transfer_event_count == 0


def test_unknown_source_is_unresolved() -> None:
    result = compute_contact_reputation_transfer(
        _communities(), (_row(source_id="ghost"),)
    )
    assert result.unresolved_source_count == 1


def test_dimension_and_trust_band_counts_exposed() -> None:
    from analysis.contact_reputation_transfer import (
        compute_contact_reputation_transfer_metric,
    )

    result = compute_contact_reputation_transfer(
        _communities(), (_row(dimension="generosity", trust_band="low"),)
    )
    document = compute_contact_reputation_transfer_metric(
        result, run_id="run", input_revision="rev"
    )
    assert document.values["dimension_generosity_count"] == 1
    assert document.values["trust_band_low_count"] == 1
