# mypy: ignore-errors
"""V4-11 treaty status, representative acceptance, and supersession."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomaticTerminationKind,
    RepresentationDurationKind,
    RepresentationScopeKind,
    RepresentationStatus,
    TreatyAcceptanceBasis,
    TreatyChangeKind,
    TreatyProvisionKind,
    TreatyStatus,
    TreatySubjectKind,
    apply_diplomacy_update,
    default_diplomacy_policy,
    default_treaty_policy,
    diplomacy_treaty_statuses,
    diplomacy_treaty_version_status,
    expire_treaty_records,
    treaty_participant_union,
)
from agents.cognition.diplomacy_communication import TreatyAct, TreatyFrame

pytestmark = pytest.mark.unit

OWNER = "alice"
PEER = "bob"
THIRD = "carol"
ENVOY = "envoy-e"
MANDATE = "rmd-" + "1" * 16
OBS = SimpleNamespace(communications=(), occurrences=())


def _mandate(
    *,
    scope_kind: RepresentationScopeKind = RepresentationScopeKind.NEGOTIATE,
    duration_kind: RepresentationDurationKind = (
        RepresentationDurationKind.UNTIL_REVOKED
    ),
    scope_subject: str | None = "ceasefire",
    status: RepresentationStatus = RepresentationStatus.RECOGNIZED,
) -> SimpleNamespace:
    return SimpleNamespace(
        mandate_id=MANDATE,
        scope_kind=scope_kind,
        duration_kind=duration_kind,
        scope_subject=scope_subject,
        status=status,
        end_tick=None,
        revoked=False,
        superseded=False,
        expired=False,
    )


def _representation(*mandates: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(mandates=tuple(mandates))


def _propose(
    *,
    peers: tuple[str, ...] = (PEER,),
    end_tick: int | None = None,
    tick: int = 1,
    prior=None,
):
    frame = TreatyFrame(
        act=TreatyAct.TREATY_PROPOSE,
        participant_refs=(f"agent:{OWNER}", *(f"agent:{peer}" for peer in peers)),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=tick,
        end_tick=end_tick,
        envoy_ref=OWNER,
    )
    return apply_diplomacy_update(
        owner_id=OWNER, tick=tick, observation=OBS, prior=prior, frames=(frame,)
    )


def _accept_frame(ledger, *, party: str, tick: int, envoy: str | None = None):
    return TreatyFrame(
        act=TreatyAct.TREATY_ACCEPT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[-1].version_id,
        party_ref=party,
        envoy_ref=envoy or party,
        participant_refs=tuple(f"agent:{name}" for name in (OWNER, PEER, THIRD)),
    )


def _apply(ledger, frame, *, tick: int, representation=None):
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=OBS,
        prior=ledger,
        frames=(frame,),
        representation=representation,
    )


def _status(ledger, *, tick: int, representation=None):
    return diplomacy_treaty_statuses(
        ledger.treaties[0],
        ledger.treaty_versions,
        ledger.treaty_declarations,
        tick=tick,
        policy=default_diplomacy_policy(),
        treaty_policy=default_treaty_policy(),
        representation=representation,
        envoys=ledger.envoys,
    )


def test_all_principals_accept_three_party_treaty() -> None:
    ledger = _propose(peers=(PEER, THIRD))
    for index, party in enumerate((OWNER, PEER, THIRD)):
        ledger = _apply(
            ledger,
            _accept_frame(ledger, party=party, tick=2 + index),
            tick=2 + index,
        )
    assert _status(ledger, tick=5) == (
        (
            ledger.treaty_versions[0].version_id,
            TreatyStatus.APPARENTLY_ACCEPTED,
            TreatyAcceptanceBasis.ALL_PARTICIPANTS_DECLARED,
        ),
    )


def test_one_missing_participant_stays_proposed() -> None:
    ledger = _propose(peers=(PEER, THIRD))
    ledger = _apply(ledger, _accept_frame(ledger, party=OWNER, tick=2), tick=2)
    ledger = _apply(ledger, _accept_frame(ledger, party=PEER, tick=3), tick=3)
    status, basis = diplomacy_treaty_version_status(
        ledger.treaty_versions[0],
        ledger.treaty_declarations,
        tick=3,
        policy=default_diplomacy_policy(),
        envoys=ledger.envoys,
    )
    assert status is TreatyStatus.PROPOSED
    assert basis is TreatyAcceptanceBasis.PROPOSER_ONLY


def test_recognized_envoy_with_covering_scope_counts() -> None:
    ledger = _propose()
    ledger = _apply(ledger, _accept_frame(ledger, party=OWNER, tick=2), tick=2)
    frame = _accept_frame(ledger, party=PEER, tick=3, envoy=ENVOY)
    frame = replace(frame, mandate_ref=MANDATE, actor_ref=ENVOY)
    representation = _representation(_mandate())
    ledger = _apply(ledger, frame, tick=3, representation=representation)
    status, basis = diplomacy_treaty_version_status(
        ledger.treaty_versions[0],
        ledger.treaty_declarations,
        tick=3,
        policy=default_diplomacy_policy(),
        representation=representation,
        envoys=ledger.envoys,
        subject_kind=TreatySubjectKind.CEASEFIRE,
    )
    assert status is TreatyStatus.APPARENTLY_ACCEPTED
    assert basis is TreatyAcceptanceBasis.ALL_PARTICIPANTS_DECLARED


@pytest.mark.parametrize(
    ("duration", "scope"),
    (
        (RepresentationDurationKind.SINGLE_ACT, RepresentationScopeKind.NEGOTIATE),
        (RepresentationDurationKind.OCCASION, RepresentationScopeKind.NEGOTIATE),
        (RepresentationDurationKind.UNTIL_REVOKED, RepresentationScopeKind.SPEAK_FOR),
    ),
)
def test_non_covering_mandates_do_not_complete_a_party(
    duration: RepresentationDurationKind, scope: RepresentationScopeKind
) -> None:
    ledger = _propose()
    ledger = _apply(ledger, _accept_frame(ledger, party=OWNER, tick=2), tick=2)
    frame = _accept_frame(ledger, party=PEER, tick=3, envoy=ENVOY)
    frame = replace(frame, mandate_ref=MANDATE, actor_ref=ENVOY)
    representation = _representation(_mandate(duration_kind=duration, scope_kind=scope))
    ledger = _apply(ledger, frame, tick=3, representation=representation)
    status, _ = diplomacy_treaty_version_status(
        ledger.treaty_versions[0],
        ledger.treaty_declarations,
        tick=3,
        policy=default_diplomacy_policy(),
        representation=representation,
        envoys=ledger.envoys,
        subject_kind=TreatySubjectKind.CEASEFIRE,
    )
    assert status is not TreatyStatus.APPARENTLY_ACCEPTED


def test_self_claim_envoy_never_counts() -> None:
    ledger = _propose()
    ledger = _apply(ledger, _accept_frame(ledger, party=OWNER, tick=2), tick=2)
    frame = _accept_frame(ledger, party=PEER, tick=3, envoy=ENVOY)
    frame = replace(frame, mandate_ref=None, actor_ref=ENVOY)
    ledger = _apply(ledger, frame, tick=3)
    status, _ = diplomacy_treaty_version_status(
        ledger.treaty_versions[0],
        ledger.treaty_declarations,
        tick=3,
        policy=default_diplomacy_policy(),
        envoys=ledger.envoys,
    )
    assert status is not TreatyStatus.APPARENTLY_ACCEPTED


def test_reject_and_termination_and_suspension_versions() -> None:
    ledger = _propose()
    reject = TreatyFrame(
        act=TreatyAct.TREATY_REJECT,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        party_ref=PEER,
        envoy_ref=PEER,
        participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
    )
    rejected = _apply(ledger, reject, tick=2)
    status, basis = diplomacy_treaty_version_status(
        rejected.treaty_versions[0],
        rejected.treaty_declarations,
        tick=2,
        policy=default_diplomacy_policy(),
    )
    assert status is TreatyStatus.PROPOSED
    assert basis is TreatyAcceptanceBasis.REJECTED

    for act, tick, expected, declaration_act in (
        (
            TreatyAct.TREATY_SUSPEND,
            3,
            TreatyStatus.SUSPENDED,
            "suspend",
        ),
        (
            TreatyAct.TREATY_TERMINATE,
            4,
            TreatyStatus.TERMINATED,
            "terminate",
        ),
    ):
        frame = TreatyFrame(
            act=act,
            treaty_ref=ledger.treaties[0].treaty_id,
            version_ref=ledger.treaty_versions[-1].version_id,
            participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
            subject_kind=TreatySubjectKind.CEASEFIRE,
            provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
            terms_digest="a" * 64,
            effective_tick=1,
            envoy_ref=OWNER,
        )
        updated = _apply(ledger, frame, tick=tick)
        newest = max(
            updated.treaty_versions,
            key=lambda version: version.version_index,
        )
        status = diplomacy_treaty_version_status(
            newest,
            updated.treaty_declarations,
            tick=tick,
            policy=default_diplomacy_policy(),
        )
        assert status[0] is TreatyStatus.PROPOSED
        assert any(
            row.act.value == declaration_act
            and row.declarer_party_id == updated.parties[0].party_id
            for row in updated.treaty_declarations
        )
        peer = TreatyFrame(
            act=act,
            treaty_ref=updated.treaties[0].treaty_id,
            version_ref=newest.version_id,
            party_ref=PEER,
            envoy_ref=PEER,
            participant_refs=(f"agent:{OWNER}", f"agent:{PEER}"),
            subject_kind=TreatySubjectKind.CEASEFIRE,
            provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
            terms_digest="a" * 64,
            effective_tick=1,
        )
        updated = _apply(updated, peer, tick=tick + 1)
        assert (
            diplomacy_treaty_version_status(
                max(
                    updated.treaty_versions,
                    key=lambda version: version.version_index,
                ),
                updated.treaty_declarations,
                tick=tick + 1,
                policy=default_diplomacy_policy(),
            )[0]
            is expected
        )


def test_expiry_boundary_is_exclusive() -> None:
    ledger = _propose(end_tick=5)
    for index, party in enumerate((OWNER, PEER)):
        ledger = _apply(
            ledger,
            _accept_frame(ledger, party=party, tick=2 + index),
            tick=2 + index,
        )
    before = diplomacy_treaty_version_status(
        ledger.treaty_versions[0],
        ledger.treaty_declarations,
        tick=4,
        policy=default_diplomacy_policy(),
    )
    assert before[0] is TreatyStatus.APPARENTLY_ACCEPTED
    expired = expire_treaty_records(ledger, tick=5, policy=default_diplomacy_policy())
    assert any(
        row.target_kind == "treaty_version"
        and row.kind is DiplomaticTerminationKind.EXPIRED
        for row in expired.terminations
    )


def test_renewal_supersedes_only_after_acceptance() -> None:
    ledger = _propose()
    for index, party in enumerate((OWNER, PEER)):
        ledger = _apply(
            ledger,
            _accept_frame(ledger, party=party, tick=2 + index),
            tick=2 + index,
        )
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
    proposed = _apply(ledger, renewal, tick=4)
    statuses = _status(proposed, tick=4)
    assert statuses[0][1] is TreatyStatus.APPARENTLY_ACCEPTED
    assert statuses[1][1] is TreatyStatus.PROPOSED
    for index, party in enumerate((OWNER, PEER)):
        proposed = _apply(
            proposed,
            _accept_frame(proposed, party=party, tick=5 + index),
            tick=5 + index,
        )
    statuses = _status(proposed, tick=7)
    assert statuses[0][1] is TreatyStatus.SUPERSEDED
    assert statuses[1][1] is TreatyStatus.APPARENTLY_ACCEPTED


def test_accession_and_withdrawal_update_the_anchor_union() -> None:
    ledger = _propose()
    accession = TreatyFrame(
        act=TreatyAct.TREATY_ACCEDE,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=ledger.treaty_versions[0].version_id,
        participant_refs=(
            f"agent:{OWNER}",
            f"agent:{PEER}",
            f"agent:{THIRD}",
        ),
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="c" * 64,
        effective_tick=2,
        envoy_ref=OWNER,
    )
    updated = _apply(ledger, accession, tick=2)
    assert len(updated.treaty_versions[-1].participant_party_ids) == 3
    assert len(updated.treaties[0].participant_party_ids) == 3
    assert (
        treaty_participant_union(updated.treaties[0], updated.treaty_versions)
        == updated.treaties[0].participant_party_ids
    )


def test_withdrawal_terminates_when_fewer_than_two_non_owner_parties_remain() -> None:
    ledger = _propose(peers=(PEER, THIRD))
    version = ledger.treaty_versions[0]
    frame = TreatyFrame(
        act=TreatyAct.TREATY_WITHDRAW,
        treaty_ref=ledger.treaties[0].treaty_id,
        version_ref=version.version_id,
        party_ref=PEER,
        envoy_ref=PEER,
        subject_kind=TreatySubjectKind.CEASEFIRE,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        participant_refs=tuple(f"agent:{name}" for name in (OWNER, PEER, THIRD)),
    )
    updated = _apply(ledger, frame, tick=2)
    latest = updated.treaty_versions[-1]
    assert latest.change_kind is TreatyChangeKind.TERMINATION
    assert latest.participant_party_ids == version.participant_party_ids


def test_two_treaties_on_same_relation_and_subject_coexist() -> None:
    first = _propose()
    second = _propose(tick=2, prior=first)
    assert first.treaties[0].treaty_id != second.treaties[-1].treaty_id
    assert len(second.treaties) == 2


def test_one_envoy_cannot_satisfy_two_parties() -> None:
    ledger = _propose()
    ledger = _apply(ledger, _accept_frame(ledger, party=OWNER, tick=2), tick=2)
    for index, party in enumerate((OWNER, PEER)):
        frame = _accept_frame(ledger, party=party, tick=3 + index, envoy=ENVOY)
        frame = replace(frame, mandate_ref=MANDATE, actor_ref=ENVOY)
        ledger = _apply(
            ledger, frame, tick=3 + index, representation=_representation(_mandate())
        )
    status, _ = diplomacy_treaty_version_status(
        ledger.treaty_versions[0],
        ledger.treaty_declarations,
        tick=5,
        policy=default_diplomacy_policy(),
        representation=_representation(_mandate()),
        envoys=ledger.envoys,
    )
    assert status is not TreatyStatus.APPARENTLY_ACCEPTED
