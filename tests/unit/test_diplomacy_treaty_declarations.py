# mypy: ignore-errors
"""V4-11 treaty declarations, recollections, terminations, and conflicts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyError,
    DiplomaticConflictKind,
    DiplomaticProvenance,
    DiplomaticTermination,
    DiplomaticTerminationKind,
    TreatyDeclarationAct,
    TreatyProvisionKind,
    TreatyRecollectionBasis,
    TreatyRecollectionStance,
    TreatySubjectKind,
    apply_diplomacy_termination,
    apply_diplomacy_update,
    diplomacy_ledger_digest,
)
from agents.cognition.diplomacy_communication import TreatyAct, TreatyFrame

pytestmark = pytest.mark.unit

OWNER = "alice"
PEER = "bob"
OBS = SimpleNamespace(communications=(), occurrences=())


def _propose():
    frame = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=1,
        envoy_ref=OWNER,
    )
    return apply_diplomacy_update(
        owner_id=OWNER, tick=1, observation=OBS, prior=None, frames=(frame,)
    )


def _accept(ledger, *, tick: int = 2, party: str = OWNER, envoy: str | None = None):
    frame = TreatyFrame(
        act=TreatyAct.TREATY_ACCEPT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        envoy_ref=envoy or party,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
    )
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=OBS,
        prior=ledger,
        frames=(frame,),
    )


def test_every_declaration_act_is_retained() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    for act in (
        TreatyAct.TREATY_ACCEPT,
        TreatyAct.TREATY_REJECT,
        TreatyAct.TREATY_INTERPRET,
        TreatyAct.TREATY_IGNORE,
    ):
        frame = TreatyFrame(
            act=act,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=version.version_id,
            envoy_ref=OWNER,
            participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        )
        updated = apply_diplomacy_update(
            owner_id=OWNER,
            tick=2 + len(ledger.treaty_declarations),
            observation=OBS,
            prior=ledger,
            frames=(frame,),
        )
        assert len(updated.treaty_declarations) == 2
        assert updated.treaty_declarations[-1].act in {
            TreatyDeclarationAct.ACCEPT,
            TreatyDeclarationAct.REJECT,
            TreatyDeclarationAct.INTERPRET,
            TreatyDeclarationAct.IGNORE,
        }


def test_declaration_party_must_be_a_version_participant() -> None:
    ledger = _propose()
    frame = TreatyFrame(
        act=TreatyAct.TREATY_ACCEPT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        envoy_ref="carol",
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER, tick=2, observation=OBS, prior=ledger, frames=(frame,)
    )
    assert len(updated.treaty_declarations) == 1


def test_recollection_accepts_absent_local_refs_and_creates_nothing() -> None:
    ledger = _propose()
    frame = TreatyFrame(
        act=TreatyAct.TREATY_RECOLLECT,
        treaty_ref="dpg-" + "1" * 16,
        version_ref="dpv-" + "1" * 16,
        subject_kind=TreatySubjectKind.TRADE,
        basis=TreatyRecollectionBasis.DURABLE_RECORD,
        stance=TreatyRecollectionStance.REMEMBER,
        confidence=0.5,
        envoy_ref=OWNER,
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER, tick=2, observation=OBS, prior=ledger, frames=(frame,)
    )
    assert len(updated.treaties) == len(ledger.treaties)
    assert len(updated.treaty_versions) == len(ledger.treaty_versions)
    assert len(updated.treaty_recollections) == 1
    recollection = updated.treaty_recollections[0]
    assert recollection.basis is TreatyRecollectionBasis.DURABLE_RECORD
    assert recollection.stance is TreatyRecollectionStance.REMEMBER


def test_recollection_stances_are_closed_and_quantized() -> None:
    ledger = _propose()
    for stance in (
        TreatyRecollectionStance.REINTERPRET,
        TreatyRecollectionStance.IGNORE,
        TreatyRecollectionStance.RENEW,
    ):
        frame = TreatyFrame(
            act=TreatyAct.TREATY_RECOLLECT,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=ledger.treaty_versions[0].version_id,
            subject_kind=TreatySubjectKind.CEASEFIRE,
            basis=TreatyRecollectionBasis.INSTITUTIONAL_MEMORY,
            stance=stance,
            confidence=0.33337,
            envoy_ref=OWNER,
        )
        updated = apply_diplomacy_update(
            owner_id=OWNER,
            tick=2,
            observation=OBS,
            prior=ledger,
            frames=(frame,),
        )
        assert updated.treaty_recollections[-1].confidence == pytest.approx(0.3334)
    with pytest.raises(DiplomacyError):
        TreatyFrame(
            act=TreatyAct.TREATY_RECOLLECT,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=ledger.treaty_versions[0].version_id,
            subject_kind=TreatySubjectKind.CEASEFIRE,
            basis=TreatyRecollectionBasis.INSTITUTIONAL_MEMORY,
            stance=TreatyRecollectionStance.REMEMBER,
            confidence=1.5,
            envoy_ref=OWNER,
        )


def test_no_truth_or_misremember_field_exists() -> None:
    ledger = _propose()
    frame = TreatyFrame(
        act=TreatyAct.TREATY_RECOLLECT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        subject_kind=TreatySubjectKind.CEASEFIRE,
        basis=TreatyRecollectionBasis.DIRECT_PARTICIPATION,
        stance=TreatyRecollectionStance.REMEMBER,
        confidence=1.0,
        envoy_ref=OWNER,
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER, tick=2, observation=OBS, prior=ledger, frames=(frame,)
    )
    recollection = updated.treaty_recollections[0]
    assert not hasattr(recollection, "misremembered")
    assert not hasattr(recollection, "truth_value")
    assert not hasattr(recollection, "false_belief")


def test_treaty_termination_targets_and_kinds() -> None:
    ledger = _propose()
    treaty = ledger.treaties[0]
    for kind in (
        DiplomaticTerminationKind.PARTY_WITHDREW,
        DiplomaticTerminationKind.TREATY_TERMINATED,
        DiplomaticTerminationKind.SUPERSEDED,
        DiplomaticTerminationKind.EXPIRED,
    ):
        updated = apply_diplomacy_termination(
            ledger,
            target_kind="treaty",
            target_ref=treaty.treaty_id,
            kind=kind,
            tick=2,
            provenance=DiplomaticProvenance.COMMUNICATED,
        )
        assert updated.terminations
    with pytest.raises(DiplomacyError):
        DiplomaticTermination(
            termination_id="dpt-" + "0" * 16,
            target_kind="treaty",
            target_ref=treaty.treaty_id,
            kind=DiplomaticTerminationKind.ENVOY_RECALLED,
            tick=2,
            provenance=DiplomaticProvenance.COMMUNICATED,
        )


def test_treaty_conflict_kinds_coexist() -> None:
    assert {
        DiplomaticConflictKind.TREATY_PARTICIPANT_CONFLICT,
        DiplomaticConflictKind.TREATY_RECORD_CONFLICT,
        DiplomaticConflictKind.TREATY_RECOLLECTION_CONFLICT,
    }.issubset(set(DiplomaticConflictKind))


def test_digest_covers_declarations_and_recollections() -> None:
    ledger = _propose()
    baseline = diplomacy_ledger_digest(ledger)
    accepted = _accept(ledger)
    assert diplomacy_ledger_digest(accepted) != baseline
    frame = TreatyFrame(
        act=TreatyAct.TREATY_RECOLLECT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        subject_kind=TreatySubjectKind.CEASEFIRE,
        basis=TreatyRecollectionBasis.COMMUNICATED_TESTIMONY,
        stance=TreatyRecollectionStance.REINTERPRET,
        confidence=0.25,
        envoy_ref=OWNER,
    )
    recollected = apply_diplomacy_update(
        owner_id=OWNER, tick=2, observation=OBS, prior=ledger, frames=(frame,)
    )
    assert diplomacy_ledger_digest(recollected) != baseline
