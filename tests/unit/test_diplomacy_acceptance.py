"""V4-10 envoy standing, agreement acceptance, and misrepresentation tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyError,
    DiplomacyLedger,
    DiplomaticAcceptanceBasis,
    DiplomaticDeclaration,
    DiplomaticDeclarationAct,
    DiplomaticEnvoy,
    DiplomaticEnvoyStatus,
    DiplomaticInstrument,
    DiplomaticInstrumentKind,
    DiplomaticInstrumentStatus,
    DiplomaticMisrepresentationKind,
    DiplomaticParty,
    DiplomaticPartyKind,
    DiplomaticPartyResolution,
    DiplomaticProvenance,
    DiplomaticRelation,
    DiplomaticTermKind,
    RepresentationDurationKind,
    RepresentationScopeKind,
    RepresentationStatus,
    default_diplomacy_policy,
    detect_diplomatic_misrepresentation,
    diplomacy_declaration_id,
    diplomacy_envoy_id,
    diplomacy_envoy_status,
    diplomacy_instrument_id,
    diplomacy_instrument_status,
    diplomacy_party_id,
    diplomacy_relation_id,
    is_agreement_view,
)

pytestmark = pytest.mark.unit

OWNER = "owner-a"
OTHER = "agent-b"
ENVOY = "envoy-e"
MANDATE = "rmd-" + "1" * 16
POLICY = default_diplomacy_policy()


def _mandate(
    *,
    scope_kind: RepresentationScopeKind = RepresentationScopeKind.NEGOTIATE,
    duration_kind: RepresentationDurationKind = (
        RepresentationDurationKind.UNTIL_REVOKED
    ),
    scope_subject: str | None = "trade",
    status: RepresentationStatus = RepresentationStatus.RECOGNIZED,
    end_tick: int | None = None,
    revoked: bool = False,
    superseded: bool = False,
    expired: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        mandate_id=MANDATE,
        scope_kind=scope_kind,
        duration_kind=duration_kind,
        scope_subject=scope_subject,
        status=status,
        end_tick=end_tick,
        revoked=revoked,
        superseded=superseded,
        expired=expired,
    )


def _representation(*mandates: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(mandates=tuple(mandates))


def _parties() -> tuple[str, str, tuple[DiplomaticParty, ...]]:
    self_id = diplomacy_party_id(OWNER, DiplomaticPartyKind.AGENT, OWNER)
    other_id = diplomacy_party_id(OWNER, DiplomaticPartyKind.AGENT, OTHER)
    rows = (
        DiplomaticParty(
            party_id=self_id,
            kind=DiplomaticPartyKind.AGENT,
            anchor_ref=OWNER,
            resolution=DiplomaticPartyResolution.RESOLVED,
            first_seen_tick=0,
            provenance=DiplomaticProvenance.SELF_DECLARED,
        ),
        DiplomaticParty(
            party_id=other_id,
            kind=DiplomaticPartyKind.AGENT,
            anchor_ref=OTHER,
            resolution=DiplomaticPartyResolution.RESOLVED,
            first_seen_tick=0,
            provenance=DiplomaticProvenance.COMMUNICATED,
        ),
    )
    return self_id, other_id, tuple(sorted(rows, key=lambda row: row.party_id))


def _relation() -> DiplomaticRelation:
    self_id, other_id, _ = _parties()
    return DiplomaticRelation(
        relation_id=diplomacy_relation_id(OWNER, (OWNER, OTHER)),
        party_ids=(self_id, other_id),
        opened_tick=0,
        last_tick=0,
        provenance=DiplomaticProvenance.SELF_DECLARED,
    )


def _envoy(
    *,
    party_id: str,
    mandate_ref: str | None = MANDATE,
    end_tick: int | None = None,
) -> DiplomaticEnvoy:
    relation = _relation()
    envoy_id = diplomacy_envoy_id(OWNER, relation.relation_id, party_id, ENVOY, 0, 0)
    return DiplomaticEnvoy(
        envoy_id=envoy_id,
        relation_id=relation.relation_id,
        party_id=party_id,
        envoy_ref=ENVOY,
        mandate_ref=mandate_ref,
        status=DiplomaticEnvoyStatus.CLAIMED,
        accredited_tick=0,
        end_tick=end_tick,
        revision=0,
        provenance=DiplomaticProvenance.COMMUNICATED,
    )


def _instrument(
    *,
    kind: DiplomaticInstrumentKind = DiplomaticInstrumentKind.PROPOSAL,
    topic: str = "trade",
    end_tick: int | None = None,
) -> DiplomaticInstrument:
    relation = _relation()
    return DiplomaticInstrument(
        instrument_id=diplomacy_instrument_id(
            OWNER, relation.relation_id, kind, topic, 1
        ),
        relation_id=relation.relation_id,
        party_ids=relation.party_ids,
        kind=kind,
        term_kind=DiplomaticTermKind.MATERIAL_EXCHANGE,
        topic_subject=topic,
        opener_envoy_ref=None,
        opened_tick=1,
        end_tick=end_tick,
        anchor_refs=(),
        revision=0,
        provenance=DiplomaticProvenance.SELF_DECLARED,
    )


def _declaration(
    instrument: DiplomaticInstrument,
    party_id: str,
    act: DiplomaticDeclarationAct,
    *,
    envoy_ref: str | None = None,
    tick: int = 1,
    revision: int = 0,
) -> DiplomaticDeclaration:
    return DiplomaticDeclaration(
        declaration_id=diplomacy_declaration_id(
            OWNER, instrument.instrument_id, party_id, act, tick, revision
        ),
        instrument_id=instrument.instrument_id,
        declarer_party_id=party_id,
        envoy_ref=envoy_ref,
        act=act,
        declared_tick=tick,
        provenance=(
            DiplomaticProvenance.COMMUNICATED
            if envoy_ref is not None
            else DiplomaticProvenance.SELF_DECLARED
        ),
        independence_ref=None,
        revision=revision,
    )


def _ledger(
    instrument: DiplomaticInstrument,
    declarations: tuple[DiplomaticDeclaration, ...],
    *,
    envoys: tuple[DiplomaticEnvoy, ...] = (),
) -> DiplomacyLedger:
    _, _, parties = _parties()
    return DiplomacyLedger(
        owner_id=OWNER,
        tick=max((row.declared_tick for row in declarations), default=1),
        relations=(_relation(),),
        parties=parties,
        envoys=tuple(
            sorted(envoys, key=lambda row: (row.accredited_tick, row.envoy_id))
        ),
        instruments=(instrument,),
        declarations=tuple(
            sorted(
                declarations, key=lambda row: (row.declared_tick, row.declaration_id)
            )
        ),
    )


def test_self_claim_stays_claimed_and_missing_mandate_is_not_recognized() -> None:
    self_id, _, _ = _parties()
    envoy = _envoy(party_id=self_id, mandate_ref=None)
    assert (
        diplomacy_envoy_status(envoy, None, tick=1, policy=POLICY)
        is DiplomaticEnvoyStatus.CLAIMED
    )

    with_ref = _envoy(party_id=self_id)
    assert (
        diplomacy_envoy_status(with_ref, None, tick=1, policy=POLICY)
        is DiplomaticEnvoyStatus.UNKNOWN
    )
    assert (
        diplomacy_envoy_status(with_ref, _representation(), tick=1, policy=POLICY)
        is DiplomaticEnvoyStatus.UNKNOWN
    )


def test_recognized_mandate_drives_standing_and_supersession() -> None:
    self_id, _, _ = _parties()
    envoy = _envoy(party_id=self_id)
    assert (
        diplomacy_envoy_status(
            envoy,
            _representation(_mandate()),
            tick=1,
            policy=POLICY,
        )
        is DiplomaticEnvoyStatus.RECOGNIZED
    )
    assert (
        diplomacy_envoy_status(
            envoy,
            _representation(_mandate(status=RepresentationStatus.SUPERSEDED)),
            tick=1,
            policy=POLICY,
        )
        is DiplomaticEnvoyStatus.SUPERSEDED
    )
    assert (
        diplomacy_envoy_status(
            envoy,
            _representation(_mandate(revoked=True)),
            tick=1,
            policy=POLICY,
        )
        is DiplomaticEnvoyStatus.REVOKED
    )
    assert (
        diplomacy_envoy_status(
            envoy,
            _representation(_mandate(status=RepresentationStatus.CONTESTED)),
            tick=1,
            policy=POLICY,
        )
        is DiplomaticEnvoyStatus.CONTESTED
    )
    assert (
        diplomacy_envoy_status(
            envoy,
            _representation(_mandate(end_tick=2)),
            tick=2,
            policy=POLICY,
        )
        is DiplomaticEnvoyStatus.EXPIRED
    )


def test_every_party_acceptance_is_required_for_agreement_view() -> None:
    self_id, other_id, _ = _parties()
    instrument = _instrument()
    opener = _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE)
    one_accept = _declaration(instrument, other_id, DiplomaticDeclarationAct.ACCEPT)
    status, basis = diplomacy_instrument_status(
        instrument, (opener, one_accept), tick=2, policy=POLICY
    )
    assert status is DiplomaticInstrumentStatus.PROPOSED

    both = _declaration(instrument, self_id, DiplomaticDeclarationAct.ACCEPT, tick=2)
    status, basis = diplomacy_instrument_status(
        instrument, (opener, one_accept, both), tick=2, policy=POLICY
    )
    assert status is DiplomaticInstrumentStatus.APPARENTLY_ACCEPTED
    assert basis is DiplomaticAcceptanceBasis.ALL_PARTIES_DECLARED
    assert is_agreement_view(
        instrument, (opener, one_accept, both), tick=2, policy=POLICY
    )


def test_unrecognized_envoy_accept_does_not_complete_a_party() -> None:
    self_id, other_id, _ = _parties()
    instrument = _instrument()
    declarations = (
        _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE),
        _declaration(
            instrument,
            other_id,
            DiplomaticDeclarationAct.ACCEPT,
            envoy_ref=ENVOY,
        ),
    )
    envoy = _envoy(party_id=other_id)
    status, _ = diplomacy_instrument_status(
        instrument,
        declarations,
        tick=2,
        policy=POLICY,
        representation=_representation(_mandate(status=RepresentationStatus.CLAIMED)),
        envoys=(envoy,),
    )
    assert status is DiplomaticInstrumentStatus.PROPOSED


def test_recognized_envoy_with_covering_scope_completes_a_party() -> None:
    self_id, other_id, _ = _parties()
    instrument = _instrument()
    declarations = (
        _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE),
        _declaration(instrument, self_id, DiplomaticDeclarationAct.ACCEPT, tick=2),
        _declaration(
            instrument,
            other_id,
            DiplomaticDeclarationAct.ACCEPT,
            envoy_ref=ENVOY,
            tick=2,
        ),
    )
    status, _ = diplomacy_instrument_status(
        instrument,
        declarations,
        tick=2,
        policy=POLICY,
        representation=_representation(_mandate()),
        envoys=(_envoy(party_id=other_id),),
    )
    assert status is DiplomaticInstrumentStatus.APPARENTLY_ACCEPTED


def test_principal_accept_counts_without_any_envoy() -> None:
    self_id, other_id, _ = _parties()
    instrument = _instrument()
    declarations = (
        _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE),
        _declaration(instrument, self_id, DiplomaticDeclarationAct.ACCEPT, tick=2),
        _declaration(instrument, other_id, DiplomaticDeclarationAct.ACCEPT, tick=2),
    )
    status, _ = diplomacy_instrument_status(
        instrument, declarations, tick=2, policy=POLICY
    )
    assert status is DiplomaticInstrumentStatus.APPARENTLY_ACCEPTED


def test_single_act_mandate_never_accepts_a_long_running_instrument() -> None:
    self_id, other_id, _ = _parties()
    instrument = _instrument(kind=DiplomaticInstrumentKind.PROMISE)
    declarations = (
        _declaration(instrument, self_id, DiplomaticDeclarationAct.PROMISE),
        _declaration(
            instrument,
            self_id,
            DiplomaticDeclarationAct.ACCEPT,
            envoy_ref=ENVOY,
            tick=2,
        ),
        _declaration(instrument, other_id, DiplomaticDeclarationAct.ACCEPT, tick=2),
    )
    status, _ = diplomacy_instrument_status(
        instrument,
        declarations,
        tick=2,
        policy=POLICY,
        representation=_representation(
            _mandate(duration_kind=RepresentationDurationKind.SINGLE_ACT)
        ),
        envoys=(_envoy(party_id=self_id),),
    )
    assert status is not DiplomaticInstrumentStatus.APPARENTLY_ACCEPTED


def test_reject_withdraw_and_dispute_transitions() -> None:
    self_id, other_id, _ = _parties()
    instrument = _instrument()
    opener = _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE)
    reject = _declaration(instrument, other_id, DiplomaticDeclarationAct.REJECT, tick=2)
    status, basis = diplomacy_instrument_status(
        instrument, (opener, reject), tick=2, policy=POLICY
    )
    assert status is DiplomaticInstrumentStatus.REJECTED
    assert basis is DiplomaticAcceptanceBasis.REJECTED

    withdraw = _declaration(
        instrument, self_id, DiplomaticDeclarationAct.WITHDRAW, tick=2
    )
    status, basis = diplomacy_instrument_status(
        instrument, (opener, withdraw), tick=2, policy=POLICY
    )
    assert status is DiplomaticInstrumentStatus.WITHDRAWN

    dispute = _declaration(
        instrument, other_id, DiplomaticDeclarationAct.DISPUTE, tick=2
    )
    status, basis = diplomacy_instrument_status(
        instrument, (opener, dispute), tick=2, policy=POLICY
    )
    assert status is DiplomaticInstrumentStatus.UNRESOLVED
    assert basis is DiplomaticAcceptanceBasis.DISPUTED


def test_expiry_boundary_is_exclusive() -> None:
    self_id, _, _ = _parties()
    instrument = _instrument(end_tick=3)
    opener = _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE)
    status, _ = diplomacy_instrument_status(
        instrument, (opener,), tick=2, policy=POLICY
    )
    assert status is DiplomaticInstrumentStatus.PROPOSED
    status, basis = diplomacy_instrument_status(
        instrument, (opener,), tick=3, policy=POLICY
    )
    assert status is DiplomaticInstrumentStatus.EXPIRED
    assert basis is DiplomaticAcceptanceBasis.EXPIRED


def test_scope_exceeded_is_retained_for_a_mismatched_subject() -> None:
    self_id, other_id, _ = _parties()
    instrument = _instrument(topic="passage")
    declarations = (
        _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE),
        _declaration(
            instrument,
            other_id,
            DiplomaticDeclarationAct.ACCEPT,
            envoy_ref=ENVOY,
            tick=2,
        ),
    )
    ledger = _ledger(
        instrument,
        declarations,
        envoys=(_envoy(party_id=other_id),),
    )
    updated = detect_diplomatic_misrepresentation(
        ledger,
        _representation(_mandate(scope_subject="trade")),
        tick=2,
        policy=POLICY,
    )
    kinds = {row.kind for row in updated.misrepresentations}
    assert DiplomaticMisrepresentationKind.SCOPE_EXCEEDED in kinds


def test_all_four_misrepresentation_kinds_are_retained_once() -> None:
    self_id, other_id, _ = _parties()
    instrument = _instrument()
    declarations = (
        _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE),
        _declaration(
            instrument,
            other_id,
            DiplomaticDeclarationAct.ACCEPT,
            envoy_ref=ENVOY,
            tick=2,
        ),
        # principal contradiction
        _declaration(instrument, other_id, DiplomaticDeclarationAct.REJECT, tick=3),
        # member contest by the other principal
        _declaration(instrument, self_id, DiplomaticDeclarationAct.REJECT, tick=3),
    )
    ledger = _ledger(
        instrument,
        declarations,
        envoys=(_envoy(party_id=other_id),),
    )
    first = detect_diplomatic_misrepresentation(
        ledger,
        _representation(_mandate(status=RepresentationStatus.CLAIMED)),
        tick=3,
        policy=POLICY,
    )
    kinds = {row.kind for row in first.misrepresentations}
    assert DiplomaticMisrepresentationKind.MANDATE_UNRECOGNIZED in kinds
    assert DiplomaticMisrepresentationKind.CONTRADICTED_BY_PRINCIPAL in kinds
    assert DiplomaticMisrepresentationKind.CONTESTED_BY_MEMBER in kinds
    second = detect_diplomatic_misrepresentation(
        first,
        _representation(_mandate(status=RepresentationStatus.CLAIMED)),
        tick=3,
        policy=POLICY,
    )
    assert [row.misrepresentation_id for row in first.misrepresentations] == [
        row.misrepresentation_id for row in second.misrepresentations
    ]


def test_actor_cannot_satisfy_two_parties() -> None:
    self_id, _, _ = _parties()
    instrument = _instrument()
    outsider_id = diplomacy_party_id(OWNER, DiplomaticPartyKind.AGENT, "agent-z")
    with pytest.raises(DiplomacyError) as excinfo:
        _ledger(
            instrument,
            (
                _declaration(instrument, self_id, DiplomaticDeclarationAct.PROPOSE),
                _declaration(
                    instrument, outsider_id, DiplomaticDeclarationAct.ACCEPT, tick=2
                ),
            ),
        )
    assert excinfo.value.code == "diplomacy_party_set_invalid"
