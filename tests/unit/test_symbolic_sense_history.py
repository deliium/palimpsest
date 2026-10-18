"""Bounded symbolic sense history records promotions and shifts."""

from __future__ import annotations

from agents.cognition.semantic_naming import (
    LabelBinding,
    NamingCandidate,
    NamingReferentKind,
    NamingStatus,
    label_binding_id,
)
from agents.cognition.symbolic_language import (
    _MAX_SENSE_HISTORY,
    SymbolicCompositionKind,
    SymbolicReferentHypothesis,
    SymbolicSenseRecord,
    SymbolicSenseTrigger,
    SymbolicStatus,
    _append_sense,
    _CompositionDraft,
    _meaning_shift,
    _promote,
    default_symbolic_language_policy,
)
from agents.models import AgentId

OWNER = AgentId("owner-a")
POLICY = default_symbolic_language_policy()
PARTS = ("alpha", "beta")


def _binding(token: str, entity: str) -> LabelBinding:
    return LabelBinding(
        binding_id=label_binding_id(OWNER, NamingReferentKind.LOCATION, token),
        owner_id=OWNER,
        label_token=token,
        referent_kind=NamingReferentKind.LOCATION,
        status=NamingStatus.ACTIVE,
        strength=0.5,
        candidates=(
            NamingCandidate(
                kind=NamingReferentKind.LOCATION,
                entity_id=entity,
                confidence=0.5,
            ),
        ),
        evidence_count=3,
    )


def _draft(
    *,
    status: SymbolicStatus = SymbolicStatus.CANDIDATE,
    hypothesis: SymbolicReferentHypothesis | None = None,
) -> _CompositionDraft:
    return _CompositionDraft(
        kind=SymbolicCompositionKind.RELATIONAL,
        parts=PARTS,
        referent_hypothesis=hypothesis,
        status=status,
        strength=0.5,
        evidence_count=3,
        usage_count=0,
        first_tick=1,
        last_tick=1,
        last_utterance_tick=None,
        sense_revision=0,
        evidence=[],
    )


def test_symbolic_promotion_records_referent_and_associations() -> None:
    draft = _draft(
        hypothesis=SymbolicReferentHypothesis(
            referent_kind=NamingReferentKind.LOCATION, confidence=0.5
        )
    )
    bindings = {"alpha": _binding("alpha", "loc-a"), "beta": _binding("beta", "loc-b")}
    _promote([draft], OWNER, 4, POLICY, [], bindings)
    assert draft.status is SymbolicStatus.ACTIVE
    assert len(draft.sense_history) == 1
    record = draft.sense_history[0]
    assert record.trigger is SymbolicSenseTrigger.PROMOTED
    assert record.referent_kind is NamingReferentKind.LOCATION
    assert record.associated_ids == ("loc-a", "loc-b")


def test_symbolic_promotion_without_senses_records_empty_associations() -> None:
    draft = _draft(
        hypothesis=SymbolicReferentHypothesis(
            referent_kind=NamingReferentKind.AGENT, confidence=0.5
        )
    )
    _promote([draft], OWNER, 4, POLICY, [], {})
    record = draft.sense_history[0]
    assert record.referent_kind is NamingReferentKind.AGENT
    assert record.associated_ids == ()


def test_symbolic_shift_records_increment_and_remain_monotonic() -> None:
    draft = _draft(
        status=SymbolicStatus.ACTIVE,
        hypothesis=SymbolicReferentHypothesis(
            referent_kind=NamingReferentKind.LOCATION, confidence=0.5
        ),
    )
    draft.pending_referent_kind = NamingReferentKind.AGENT
    draft.meaning_shift_streak = POLICY.meaning_shift_ticks - 1
    _meaning_shift([draft], OWNER, 8, POLICY, {})
    assert draft.sense_revision == 1
    assert draft.sense_history[-1].trigger is SymbolicSenseTrigger.SHIFTED
    assert draft.sense_history[-1].referent_kind is NamingReferentKind.LOCATION


def test_symbolic_sense_history_caps_without_raising() -> None:
    draft = _draft()
    for tick in range(_MAX_SENSE_HISTORY + 6):
        _append_sense(
            draft,
            owner_id=OWNER,
            tick=tick,
            trigger=SymbolicSenseTrigger.PROMOTED,
            referent_kind=NamingReferentKind.LOCATION,
            confidence=0.5,
            associated_ids=(),
        )
    assert len(draft.sense_history) == _MAX_SENSE_HISTORY
    ordinals = [item.ordinal for item in draft.sense_history]
    assert ordinals == sorted(ordinals)
    assert len(set(ordinals)) == len(ordinals)


def test_symbolic_sense_record_rejects_duplicate_associations() -> None:
    try:
        SymbolicSenseRecord(
            ordinal=0,
            tick=1,
            trigger=SymbolicSenseTrigger.PROMOTED,
            referent_kind=NamingReferentKind.LOCATION,
            confidence=0.5,
            associated_ids=("loc-a", "loc-a"),
        )
    except ValueError as error:
        assert "duplicate_associated" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("duplicate associations must be rejected")
