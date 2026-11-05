# mypy: ignore-errors
"""V4-11 treaty expiry, supersession, misrepresentation, and conflicts."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomaticConflictKind,
    DiplomaticMisrepresentationKind,
    DiplomaticTerminationKind,
    RepresentationDurationKind,
    RepresentationScopeKind,
    RepresentationStatus,
    TreatyAct,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatyRecollectionBasis,
    TreatyRecollectionStance,
    TreatyStatus,
    TreatySubjectKind,
    apply_diplomacy_update,
    default_diplomacy_policy,
    default_treaty_policy,
    diplomacy_treaty_statuses,
)
from agents.cognition.diplomacy_communication import TreatyFrame

pytestmark = pytest.mark.unit

OWNER = "alice"
PEER = "bob"
ENVOY = "envoy-e"
MANDATE = "rmd-" + "1" * 16
OBS = SimpleNamespace(communications=(), occurrences=())


def _mandate(**overrides) -> SimpleNamespace:
    values = dict(
        mandate_id=MANDATE,
        scope_kind=RepresentationScopeKind.NEGOTIATE,
        duration_kind=RepresentationDurationKind.UNTIL_REVOKED,
        scope_subject="ceasefire",
        status=RepresentationStatus.RECOGNIZED,
        end_tick=None,
        revoked=False,
        superseded=False,
        expired=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _representation(*mandates: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(mandates=tuple(mandates))


def _propose(*, end_tick: int | None = None, tick: int = 1):
    frame = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=tick,
        end_tick=end_tick,
        envoy_ref=OWNER,
    )
    return apply_diplomacy_update(
        owner_id=OWNER, tick=tick, observation=OBS, prior=None, frames=(frame,)
    )


def _accept(ledger, *, party: str, tick: int, envoy: str | None = None, mandate=None):
    frame = TreatyFrame(
        act=TreatyAct.TREATY_ACCEPT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=max(
            ledger.treaty_versions, key=lambda row: row.version_index
        ).version_id,
        party_ref=party,
        envoy_ref=envoy or party,
        mandate_ref=mandate,
        actor_ref=envoy,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
    )
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=OBS,
        prior=ledger,
        frames=(frame,),
        representation=_representation(_mandate(end_tick=None)) if envoy else None,
    )


def test_envoy_misrepresentation_is_retained_once() -> None:
    ledger = _propose()
    ledger = _accept(ledger, party=PEER, tick=2, envoy=ENVOY)  # no mandate
    kinds = {row.kind for row in ledger.treaty_misrepresentations}
    assert DiplomaticMisrepresentationKind.MANDATE_UNRECOGNIZED in kinds
    second = _accept(ledger, party=PEER, tick=2, envoy=ENVOY)
    assert len(second.treaty_misrepresentations) == len(
        ledger.treaty_misrepresentations
    )


def test_principal_declarations_never_create_misrepresentation_rows() -> None:
    ledger = _propose()
    ledger = _accept(ledger, party=PEER, tick=2)
    assert ledger.treaty_misrepresentations == ()


def test_expiry_boundary_appends_one_termination() -> None:
    ledger = _propose(end_tick=5)
    for index, party in enumerate((OWNER, PEER)):
        ledger = _accept(ledger, party=party, tick=2 + index)
    before = [
        row
        for row in ledger.terminations
        if row.kind is DiplomaticTerminationKind.EXPIRED
    ]
    assert before == []
    expired = apply_diplomacy_update(
        owner_id=OWNER, tick=5, observation=OBS, prior=ledger
    )
    rows = [
        row
        for row in expired.terminations
        if row.kind is DiplomaticTerminationKind.EXPIRED
        and row.target_kind == "treaty_version"
    ]
    assert len(rows) == 1
    repeated = apply_diplomacy_update(
        owner_id=OWNER, tick=5, observation=OBS, prior=expired
    )
    assert (
        len(
            [
                row
                for row in repeated.terminations
                if row.kind is DiplomaticTerminationKind.EXPIRED
                and row.target_kind == "treaty_version"
            ]
        )
        == 1
    )


def test_rejected_renewal_does_not_supersede_accepted_version() -> None:
    ledger = _propose()
    for index, party in enumerate((OWNER, PEER)):
        ledger = _accept(ledger, party=party, tick=2 + index)
    renewal = TreatyFrame(
        act=TreatyAct.TREATY_RENEW,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="b" * 64,
        effective_tick=5,
        envoy_ref=OWNER,
    )
    proposed = apply_diplomacy_update(
        owner_id=OWNER, tick=4, observation=OBS, prior=ledger, frames=(renewal,)
    )
    rejected = TreatyFrame(
        act=TreatyAct.TREATY_REJECT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=max(
            proposed.treaty_versions, key=lambda row: row.version_index
        ).version_id,
        party_ref=PEER,
        envoy_ref=PEER,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER, tick=5, observation=OBS, prior=proposed, frames=(rejected,)
    )
    statuses = diplomacy_treaty_statuses(
        updated.treaties[0],
        updated.treaty_versions,
        updated.treaty_declarations,
        tick=5,
        policy=default_diplomacy_policy(),
        treaty_policy=default_treaty_policy(),
        envoys=updated.envoys,
    )
    assert statuses[0][1] is TreatyStatus.APPARENTLY_ACCEPTED
    assert statuses[1][1] is TreatyStatus.PROPOSED


def test_recollection_digest_mismatch_is_not_classified_in_cognition() -> None:
    ledger = _propose()
    version = ledger.treaty_versions[0]
    frame = TreatyFrame(
        act=TreatyAct.TREATY_RECOLLECT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=version.version_id,
        subject_kind=TreatySubjectKind.CEASEFIRE,
        basis=TreatyRecollectionBasis.DURABLE_RECORD,
        stance=TreatyRecollectionStance.REMEMBER,
        confidence=0.5,
        terms_digest="b" * 64,
        envoy_ref=OWNER,
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER, tick=2, observation=OBS, prior=ledger, frames=(frame,)
    )
    assert len(updated.treaty_recollections) == 1
    assert not any(
        row.kind is DiplomaticConflictKind.TREATY_RECOLLECTION_CONFLICT
        for row in updated.conflicts
    )


def test_recollection_subject_mismatch_and_record_conflict_are_retained() -> None:
    ledger = _propose()
    recollection = TreatyFrame(
        act=TreatyAct.TREATY_RECOLLECT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        subject_kind=TreatySubjectKind.TRADE,
        basis=TreatyRecollectionBasis.DURABLE_RECORD,
        stance=TreatyRecollectionStance.REMEMBER,
        confidence=0.5,
        envoy_ref=OWNER,
    )
    updated = apply_diplomacy_update(
        owner_id=OWNER, tick=2, observation=OBS, prior=ledger, frames=(recollection,)
    )
    assert any(
        row.kind is DiplomaticConflictKind.TREATY_RECOLLECTION_CONFLICT
        for row in updated.conflicts
    )
    version = updated.treaty_versions[0]
    conflicting = replace(
        updated,
        treaty_versions=(
            replace(
                version,
                version_id="dpv-" + "9" * 16,
                version_index=2,
                parent_version_ids=(version.version_id,),
                change_kind=TreatyChangeKind.RENEWAL,
                record_refs=("shared-record",),
                terms_digest="b" * 64,
            ),
            replace(version, record_refs=("shared-record",), terms_digest="c" * 64),
        ),
        treaties=(
            replace(
                updated.treaties[0],
                current_version_id="dpv-" + "9" * 16,
            ),
        ),
    )
    detected = apply_diplomacy_update(
        owner_id=OWNER, tick=3, observation=OBS, prior=conflicting
    )
    assert any(
        row.kind is DiplomaticConflictKind.TREATY_RECORD_CONFLICT
        for row in detected.conflicts
    )
