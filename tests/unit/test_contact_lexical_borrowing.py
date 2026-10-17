"""Cross-community lexical borrowing is communicated and owner-scoped."""

from __future__ import annotations

from analysis.contact_lexical_borrowing import (
    ContactNamingEvidenceRow,
    compute_contact_lexical_borrowing,
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


def _row(**overrides: object) -> ContactNamingEvidenceRow:
    values: dict[str, object] = {
        "owner_id": "b-1",
        "label_token": "tok-a",
        "referent_kind": "food",
        "actor_id": "a-1",
        "channel": "communication",
        "first_tick": 3,
        "last_tick": 3,
        "evidence_tick": 3,
        "strength": 0.8,
        "transmission": "communicated",
    }
    values.update(overrides)
    return ContactNamingEvidenceRow(**values)  # type: ignore[arg-type]


def test_cross_community_communication_is_borrowing() -> None:
    result = compute_contact_lexical_borrowing(_communities(), (_row(),))
    assert result.borrowing_event_count == 1
    assert result.borrowed_label_count == 1
    assert result.new_adoption_count == 1


def test_same_community_and_observed_only_not_borrowing() -> None:
    result = compute_contact_lexical_borrowing(
        _communities(),
        (
            _row(actor_id="b-1"),
            _row(channel="observation", actor_id=None),
            _row(channel="direct", actor_id=None),
        ),
    )
    assert result.borrowing_event_count == 0


def test_unknown_actor_is_unresolved() -> None:
    result = compute_contact_lexical_borrowing(
        _communities(), (_row(actor_id="ghost"),)
    )
    assert result.unresolved_actor_count == 1


def test_reinforcement_distinguished_from_new_adoption() -> None:
    result = compute_contact_lexical_borrowing(
        _communities(), (_row(evidence_tick=4, last_tick=4),)
    )
    assert result.new_adoption_count == 0
    assert result.reinforcement_count == 1


def test_merge_and_competition_are_distinguished() -> None:
    communities = (
        *_communities(),
        CandidateCommunityRow.from_members(
            person_ids=("c-1",), lane_coverage=("interaction",)
        ),
    )
    result = compute_contact_lexical_borrowing(
        communities,
        (
            _row(first_tick=1, last_tick=1, evidence_tick=3, label_token="tok-a"),
            _row(first_tick=1, last_tick=1, evidence_tick=4, label_token="tok-b"),
            _row(
                first_tick=1,
                last_tick=1,
                evidence_tick=5,
                label_token="tok-a",
                actor_id="c-1",
            ),
        ),
    )
    assert result.competition_count == 1
    assert result.merge_count == 1
