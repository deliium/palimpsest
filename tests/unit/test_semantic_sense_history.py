"""Bounded naming sense history records promotions, shifts, and merges."""

from __future__ import annotations

import pytest

from agents.cognition.semantic_naming import (
    _MAX_SENSE_HISTORY,
    NamingCandidate,
    NamingReferentKind,
    NamingSenseRecord,
    NamingSenseTrigger,
    NamingStatus,
    NamingTransmission,
    _BindingDraft,
    _meaning_shift,
    _merge,
    _promote,
    default_semantic_naming_policy,
    label_binding_id,
)
from agents.models import AgentId

OWNER = AgentId("owner-a")
POLICY = default_semantic_naming_policy()


def _candidate(entity: str, confidence: float) -> NamingCandidate:
    return NamingCandidate(
        kind=NamingReferentKind.LOCATION,
        entity_id=entity,
        confidence=confidence,
    )


def _draft(
    *,
    status: NamingStatus = NamingStatus.CANDIDATE,
    strength: float = 0.5,
    candidates: tuple[NamingCandidate, ...],
    evidence_count: int = 3,
) -> _BindingDraft:
    return _BindingDraft(
        label_token="place_alpha",
        referent_kind=NamingReferentKind.LOCATION,
        strength=strength,
        status=status,
        candidates=list(candidates),
        evidence_count=evidence_count,
        first_tick=1,
        last_tick=1,
        transmission=NamingTransmission.OBSERVED,
        sense_revision=0,
        merged_into=None,
        competing_label_ids=[],
        evidence=[],
        last_utterance_tick=None,
        meaning_shift_streak=0,
    )


def test_promotion_appends_one_promoted_record() -> None:
    draft = _draft(candidates=(_candidate("loc-a", 0.6), _candidate("loc-b", 0.5)))
    _promote([draft], OWNER, 3, POLICY, [])
    assert draft.status is NamingStatus.ACTIVE
    assert len(draft.sense_history) == 1
    record = draft.sense_history[0]
    assert record.ordinal == 0
    assert record.tick == 3
    assert record.trigger is NamingSenseTrigger.PROMOTED
    assert record.referent_id == "loc-a"
    assert record.associated_ids == ("loc-b",)
    assert record.confidence == 0.6


def test_meaning_shift_appends_shifted_record_only_on_increment() -> None:
    draft = _draft(
        status=NamingStatus.ACTIVE,
        candidates=(_candidate("loc-b", 0.9), _candidate("loc-a", 0.5)),
    )
    draft.pending_top_id = "loc-a"
    draft.meaning_shift_streak = POLICY.meaning_shift_ticks - 1
    _meaning_shift([draft], OWNER, 7, POLICY)
    assert draft.sense_revision == 1
    assert [item.trigger for item in draft.sense_history] == [
        NamingSenseTrigger.SHIFTED
    ]
    assert draft.sense_history[0].referent_id == "loc-b"
    assert draft.sense_history[0].tick == 7


def test_sense_history_ordinals_are_monotonic_after_trimming() -> None:
    draft = _draft(
        status=NamingStatus.ACTIVE,
        candidates=(_candidate("loc-b", 0.9), _candidate("loc-a", 0.5)),
    )
    for _ in range(_MAX_SENSE_HISTORY + 4):
        draft.pending_top_id = "loc-a"
        draft.meaning_shift_streak = POLICY.meaning_shift_ticks - 1
        _meaning_shift([draft], OWNER, 7, POLICY)
    assert len(draft.sense_history) == _MAX_SENSE_HISTORY
    ordinals = [item.ordinal for item in draft.sense_history]
    assert ordinals == sorted(ordinals)
    assert len(set(ordinals)) == len(ordinals)


def test_merge_records_absorption_on_surviving_binding() -> None:
    stronger = _draft(
        status=NamingStatus.ACTIVE,
        strength=0.7,
        candidates=(
            _candidate("loc-c", 0.9),
            _candidate("loc-a", 0.6),
            _candidate("loc-b", 0.5),
        ),
    )
    weaker = _draft(
        status=NamingStatus.ACTIVE,
        strength=0.5,
        candidates=(_candidate("loc-a", 0.6), _candidate("loc-b", 0.5)),
    )
    weaker.label_token = "place_beta"
    _merge([stronger, weaker], OWNER, 9, POLICY)
    assert weaker.merged_into == label_binding_id(
        OWNER, NamingReferentKind.LOCATION, "place_alpha"
    )
    assert len(stronger.sense_history) == 1
    record = stronger.sense_history[0]
    assert record.trigger is NamingSenseTrigger.MERGED
    assert record.referent_id == "loc-c"
    assert record.associated_ids == ("loc-a", "loc-b")


def test_sense_record_rejects_duplicates_and_bad_ids() -> None:
    with pytest.raises(ValueError, match="duplicate_associated"):
        NamingSenseRecord(
            ordinal=0,
            tick=1,
            trigger=NamingSenseTrigger.PROMOTED,
            referent_kind=NamingReferentKind.LOCATION,
            referent_id="loc-a",
            associated_ids=("loc-b", "loc-b"),
        )
    with pytest.raises(ValueError, match="referent_included"):
        NamingSenseRecord(
            ordinal=0,
            tick=1,
            trigger=NamingSenseTrigger.PROMOTED,
            referent_kind=NamingReferentKind.LOCATION,
            referent_id="loc-a",
            associated_ids=("loc-a",),
        )
