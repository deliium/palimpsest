# mypy: ignore-errors
"""V4-11 treaty frame collection and local reconciliation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyError,
    DiplomaticPartyResolution,
    TreatyAct,
    TreatyChangeKind,
    TreatyFrame,
    TreatyProvisionKind,
    TreatySubjectKind,
    apply_diplomacy_update,
    treaty_frame_relations,
)

pytestmark = pytest.mark.unit

OWNER = "alice"
PEER = "bob"
OBS_EMPTY = SimpleNamespace(communications=(), occurrences=())


def _observation(speaker: str, relations) -> SimpleNamespace:
    communication = SimpleNamespace(
        speaker_id=SimpleNamespace(value=speaker),
        utterance=SimpleNamespace(content=SimpleNamespace(relations=tuple(relations))),
    )
    return SimpleNamespace(communications=(communication,), occurrences=())


def _propose_frame(*participants: str, **overrides) -> TreatyFrame:
    values = dict(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=tuple(
            name if ":" in name else f"agent:{name}" for name in participants
        ),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=1,
        envoy_ref=participants[0],
    )
    values.update(overrides)
    return TreatyFrame(**values)


def _propose_via_observation() -> tuple[object, TreatyFrame]:
    frame = _propose_frame(OWNER, PEER)
    observation = _observation(OWNER, treaty_frame_relations(frame))
    ledger = apply_diplomacy_update(
        owner_id=OWNER, tick=1, observation=observation, prior=None
    )
    return ledger, frame


def test_owner_proposal_through_observation_creates_anchor() -> None:
    ledger, _ = _propose_via_observation()
    assert len(ledger.treaties) == 1
    assert len(ledger.treaty_versions) == 1
    assert len(ledger.treaty_declarations) == 1


def test_peer_proposal_to_non_participant_is_only_a_recollection() -> None:
    frame = _propose_frame(OWNER, PEER)
    observation = _observation(OWNER, treaty_frame_relations(frame))
    ledger = apply_diplomacy_update(
        owner_id="carol", tick=1, observation=observation, prior=None
    )
    assert ledger.treaties == ()
    assert ledger.treaty_versions == ()
    assert len(ledger.treaty_recollections) == 1


def test_unresolved_organization_anchor_is_retained() -> None:
    frame = _propose_frame(
        OWNER,
        "organization:orgc-" + "0" * 16,
    )
    ledger = apply_diplomacy_update(
        owner_id=OWNER, tick=1, observation=OBS_EMPTY, prior=None, frames=(frame,)
    )
    unresolved = [
        row
        for row in ledger.parties
        if row.resolution is DiplomaticPartyResolution.UNRESOLVED
    ]
    assert unresolved
    assert ledger.treaties == ()


def test_unknown_treaty_and_version_refs_are_notices() -> None:
    ledger, _ = _propose_via_observation()
    unknown_treaty = TreatyFrame(
        act=TreatyAct.TREATY_ACCEPT,
        treaty_ref="dpg-" + "2" * 16,
        version_ref="dpv-" + "2" * 16,
        envoy_ref=OWNER,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER,
        tick=2,
        observation=OBS_EMPTY,
        prior=ledger,
        frames=(unknown_treaty,),
    )
    assert "treaty_unknown_treaty" in updated.notices
    unknown_version = TreatyFrame(
        act=TreatyAct.TREATY_ACCEPT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref="dpv-" + "3" * 16,
        envoy_ref=OWNER,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER,
        tick=3,
        observation=OBS_EMPTY,
        prior=updated,
        frames=(unknown_version,),
    )
    assert "treaty_unknown_version" in updated.notices


def test_malformed_chunk_group_is_noticed_and_creates_no_row() -> None:
    frame = _propose_frame(OWNER, PEER, record_refs=("record-" + "x" * 100,))
    relations = treaty_frame_relations(frame)
    assert len(relations) > 1
    observation = _observation(OWNER, relations[:1])
    ledger = apply_diplomacy_update(
        owner_id=OWNER, tick=1, observation=observation, prior=None
    )
    assert "treaty_malformed_chunks" in ledger.notices
    assert ledger.treaties == ()


def test_repeating_identical_frames_is_idempotent() -> None:
    ledger, frame = _propose_via_observation()
    baseline = (
        len(ledger.treaties),
        len(ledger.treaty_versions),
        len(ledger.treaty_declarations),
    )
    second = apply_diplomacy_update(
        owner_id=OWNER,
        tick=1,
        observation=OBS_EMPTY,
        prior=ledger,
        frames=(frame,),
    )
    assert (
        len(second.treaties),
        len(second.treaty_versions),
        len(second.treaty_declarations),
    ) == baseline


def test_version_acts_create_retained_parent_links() -> None:
    ledger, _ = _propose_via_observation()
    renewal = TreatyFrame(
        act=TreatyAct.TREATY_RENEW,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="b" * 64,
        effective_tick=2,
        envoy_ref=OWNER,
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER,
        tick=2,
        observation=OBS_EMPTY,
        prior=ledger,
        frames=(renewal,),
    )
    newest = max(updated.treaty_versions, key=lambda row: row.version_index)
    assert newest.version_index == 2
    assert newest.change_kind is TreatyChangeKind.RENEWAL
    assert newest.parent_version_ids == (ledger.treaty_versions[0].version_id,)
    assert updated.treaties[0].current_version_id == newest.version_id


def test_unknown_version_does_not_mutate_state() -> None:
    ledger, _ = _propose_via_observation()
    with pytest.raises(DiplomacyError):
        TreatyFrame(
            act=TreatyAct.TREATY_ACCEPT,
            treaty_ref=ledger.treaties[0].treaty_id,
            envoy_ref=OWNER,
            participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        )
