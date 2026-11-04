"""V4-10 instrument collection tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    DiplomacyError,
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticDeclarationAct,
    DiplomaticInstrumentKind,
    DiplomaticNegotiationStatus,
    DiplomaticPartyKind,
    DiplomaticTermKind,
    apply_diplomacy_update,
    default_diplomacy_policy,
    diplomacy_instrument_status,
    is_agreement_view,
)
from agents.cognition.diplomacy import DiplomacyLedger

pytestmark = pytest.mark.unit

OWNER = "owner-a"
OTHER = "agent-b"


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(),
        communications=(),
        regional_context=None,
        self_body=None,
        exits=(),
    )


def _update(
    prior: DiplomacyLedger | None, frames: tuple[object, ...], *, tick: int = 1
) -> DiplomacyLedger:
    return apply_diplomacy_update(
        owner_id=OWNER,
        tick=tick,
        observation=_observation(),
        prior=prior,
        frames=frames,
    )


def _opening(
    act: DiplomaticAct,
    *,
    topic: str = "trade",
    term: DiplomaticTermKind = DiplomaticTermKind.MATERIAL_EXCHANGE,
    envoy_ref: str = OWNER,
    actor_ref: str = OWNER,
    party_ref: str = OTHER,
    revision: int = 0,
) -> DiplomacyFrame:
    return DiplomacyFrame(
        act=act,
        envoy_ref=envoy_ref,
        actor_ref=actor_ref,
        party_kind=DiplomaticPartyKind.AGENT,
        party_ref=party_ref,
        topic_subject=topic,
        term_kind=term,
        revision=revision,
    )


@pytest.mark.parametrize(
    ("act", "kind", "declaration_act"),
    (
        (
            DiplomaticAct.PROPOSE,
            DiplomaticInstrumentKind.PROPOSAL,
            DiplomaticDeclarationAct.PROPOSE,
        ),
        (
            DiplomaticAct.PROMISE,
            DiplomaticInstrumentKind.PROMISE,
            DiplomaticDeclarationAct.PROMISE,
        ),
        (
            DiplomaticAct.DISPUTE,
            DiplomaticInstrumentKind.DISPUTE,
            DiplomaticDeclarationAct.DISPUTE,
        ),
        (
            DiplomaticAct.SHARED_PROJECT,
            DiplomaticInstrumentKind.SHARED_PROJECT,
            DiplomaticDeclarationAct.SHARED_PROJECT,
        ),
    ),
)
def test_each_opening_kind_is_collected(
    act: DiplomaticAct,
    kind: DiplomaticInstrumentKind,
    declaration_act: DiplomaticDeclarationAct,
) -> None:
    ledger = _update(None, (_opening(act),))
    assert len(ledger.instruments) == 1
    instrument = ledger.instruments[0]
    assert instrument.kind is kind
    assert instrument.term_kind is DiplomaticTermKind.MATERIAL_EXCHANGE
    assert ledger.declarations[0].act is declaration_act


def test_promise_retains_commitment_anchor_but_never_enforces_it() -> None:
    without = _update(None, (_opening(DiplomaticAct.PROMISE),))
    assert without.instruments[0].anchor_refs == ()

    with_anchor = apply_diplomacy_update(
        owner_id=OWNER,
        tick=1,
        observation=_observation(),
        prior=None,
        frames=(_opening(DiplomaticAct.PROMISE),),
        anchor_refs=("commitment-1",),
    )
    assert with_anchor.instruments[0].anchor_refs == ("commitment-1",)


def test_shared_project_and_dispute_link_owner_anchors() -> None:
    ledger = apply_diplomacy_update(
        owner_id=OWNER,
        tick=1,
        observation=_observation(),
        prior=None,
        frames=(
            _opening(DiplomaticAct.SHARED_PROJECT),
            _opening(DiplomaticAct.DISPUTE),
        ),
        anchor_refs=("project-1", "dispute-1"),
    )
    kinds = {row.kind for row in ledger.instruments}
    assert kinds == {
        DiplomaticInstrumentKind.SHARED_PROJECT,
        DiplomaticInstrumentKind.DISPUTE,
    }
    assert all(row.anchor_refs for row in ledger.instruments)


def test_report_changes_no_instrument_status() -> None:
    first = _update(None, (_opening(DiplomaticAct.PROPOSE),))
    instrument = first.instruments[0]
    report = DiplomacyFrame(
        act=DiplomaticAct.REPORT,
        envoy_ref=OTHER,
        actor_ref=OTHER,
        instrument_ref=instrument.instrument_id,
        revision=1,
    )
    second = _update(first, (report,), tick=2)
    status, _ = diplomacy_instrument_status(
        second.instruments[0],
        second.declarations,
        tick=2,
        policy=default_diplomacy_policy(),
    )
    assert status.value == "proposed"


def test_free_form_terms_are_rejected() -> None:
    with pytest.raises(DiplomacyError):
        DiplomacyFrame(
            act=DiplomaticAct.PROPOSE,
            envoy_ref=OWNER,
            topic_subject="trade",
            term_kind="free-form obligation",  # type: ignore[arg-type]
        )


def test_agreement_view_reuses_one_instrument() -> None:
    first = _update(None, (_opening(DiplomaticAct.PROPOSE),))
    instrument = first.instruments[0]
    accepts = (
        DiplomacyFrame(
            act=DiplomaticAct.ACCEPT,
            envoy_ref=OTHER,
            actor_ref=OTHER,
            instrument_ref=instrument.instrument_id,
            revision=1,
        ),
        DiplomacyFrame(
            act=DiplomaticAct.ACCEPT,
            envoy_ref=OWNER,
            actor_ref=OWNER,
            instrument_ref=instrument.instrument_id,
            revision=2,
        ),
    )
    second = _update(first, accepts, tick=2)
    assert len(second.instruments) == 1
    assert is_agreement_view(
        second.instruments[0],
        second.declarations,
        tick=2,
        policy=default_diplomacy_policy(),
    )


def test_declaration_outside_the_party_set_is_rejected() -> None:
    first = _update(None, (_opening(DiplomaticAct.PROPOSE),))
    instrument = first.instruments[0]
    outsider = DiplomacyFrame(
        act=DiplomaticAct.ACCEPT,
        envoy_ref="agent-z",
        actor_ref="agent-z",
        instrument_ref=instrument.instrument_id,
        revision=1,
    )
    with pytest.raises(DiplomacyError) as excinfo:
        _update(first, (outsider,), tick=2)
    assert excinfo.value.code == "diplomacy_party_set_invalid"


def test_unknown_instrument_reference_is_retained_as_a_notice() -> None:
    frame = DiplomacyFrame(
        act=DiplomaticAct.ACCEPT,
        envoy_ref=OTHER,
        actor_ref=OTHER,
        instrument_ref="dpi-" + "0" * 16,
        revision=1,
    )
    ledger = _update(None, (frame,))
    assert ledger.instruments == ()
    assert "diplomacy_unknown_instrument" in ledger.notices


def test_negotiation_does_not_create_an_instrument() -> None:
    ledger = _update(
        None,
        (
            _opening(
                DiplomaticAct.OPEN_NEGOTIATION,
                term=DiplomaticTermKind.PASSAGE,
            ),
        ),
    )
    assert ledger.instruments == ()
    assert ledger.negotiations[0].status is DiplomaticNegotiationStatus.OPENED
    assert ledger.negotiations[0].term_kind is DiplomaticTermKind.PASSAGE
