"""Bounded ``crd_v1`` frames round-trip and stay testimony-only."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from agents.cognition.credit_relationships import (
    CreditClaimSource,
    apply_credit_relationship_update,
)
from agents.cognition.credit_relationships_communication import (
    credit_communicate_utterance,
)
from tests.unit.test_credit_relationships_helpers import (
    OWNER,
    PEER,
    claim,
    commitment,
    prices,
    signal,
    terms,
)
from world.actions import Give, Move, NegotiateExchange, Talk, Tell, Wait
from world.communications import CommunicationRelation, origin_utterance
from world.credit_relationships import (
    CREDIT_FRAME_MAX_RELATIONS,
    CreditClaimFrame,
    CreditFrameAct,
    CreditFrameDirection,
    credit_claim_relation,
    encode_credit_claim_frame,
    parse_credit_claim_frame,
    parse_credit_claim_relation,
)
from world.identifiers import EntityId
from world.values import ItemKind

pytestmark = pytest.mark.unit

OWNER_ENTITY = EntityId("body-1")


def _talk() -> Talk:
    return Talk(
        recipient_id=PEER,
        utterance=origin_utterance(text="hello", speaker_id=OWNER_ENTITY),
    )


def _frame(act: CreditFrameAct = CreditFrameAct.PROPOSE) -> CreditClaimFrame:
    return CreditClaimFrame(
        act=act,
        direction=CreditFrameDirection.OWNER_DEBTOR,
        anchor="crd-0123456789abcdef",
        principal_kind_token="food",
        principal_quantity=2,
        repayment_kind_token="water",
        repayment_quantity=3,
        paid_quantity=1 if act is CreditFrameAct.REPAY else 0,
        opened_tick=1,
        due_tick=10,
        condition="by_deadline",
        collateral_kind="none",
        collateral_item_token=None,
        collateral_quantity=0,
        confidence_milli=500,
    )


@pytest.mark.parametrize("act", tuple(CreditFrameAct))
def test_every_act_round_trips(act: CreditFrameAct) -> None:
    frame = _frame(act)
    assert parse_credit_claim_frame(encode_credit_claim_frame(frame)) == frame


def test_frame_has_exactly_sixteen_parts() -> None:
    assert len(encode_credit_claim_frame(_frame()).split(":")) == 16


@pytest.mark.parametrize(
    "text",
    (
        "crd_v1:crd_propose:owner_debtor",
        "other:crd_propose:owner_debtor:crd-0123456789abcdef:food:2:water:3:0:1:10:by_deadline:none:none:0:500",
        "crd_v1:crd_unknown:owner_debtor:crd-0123456789abcdef:food:2:water:3:0:1:10:by_deadline:none:none:0:500",
        "crd_v1:crd_propose:unknown:crd-0123456789abcdef:food:2:water:3:0:1:10:by_deadline:none:none:0:500",
        "crd_v1:crd_propose:owner_debtor:not-an-anchor:food:2:water:3:0:1:10:by_deadline:none:none:0:500",
        "crd_v1:crd_propose:owner_debtor:crd-0123456789abcdef:food:0:water:3:0:1:10:by_deadline:none:none:0:500",
        "crd_v1:crd_propose:owner_debtor:crd-0123456789abcdef:food:2:water:3:0:1:10:by_deadline:none:none:0:1001",
        "crd_v1:crd_propose:owner_debtor:crd-0123456789abcdef:food:2:water:3:0:1:10:by_deadline:item_pledge:none:0:500",
        "crd_v1:crd_propose:owner_debtor:crd-0123456789abcdef:food:2:water:3:0:1:10:by_deadline:none:water:0:500",
        "crd_v1:crd_propose:owner_debtor:crd-0123456789abcdef:food:2:water:3:0:1:10:unknown:none:none:0:500",
    ),
)
def test_malformed_frames_fail_closed(text: str) -> None:
    with pytest.raises(ValueError):
        parse_credit_claim_frame(text)


def test_oversize_frame_fails_closed() -> None:
    frame = _frame()
    text = encode_credit_claim_frame(frame) + "0" * 400
    with pytest.raises(ValueError):
        parse_credit_claim_frame(text)


def test_unrelated_relation_returns_none() -> None:
    relation = CommunicationRelation(
        subject="prc_v1", predicate="prc_quote", object="food:water"
    )
    assert parse_credit_claim_relation(relation) is None
    other = CommunicationRelation(
        subject="crd_v1", predicate="unrelated", object="x"
    )
    assert parse_credit_claim_relation(other) is None


def test_relation_round_trips() -> None:
    frame = _frame()
    relation = credit_claim_relation(frame)
    assert relation.subject == "crd_v1"
    assert parse_credit_claim_relation(relation) == frame


def _received_proposal_ledger(*, trust_milli: int = 500):
    return apply_credit_relationship_update(
        owner_id=OWNER,
        tick=2,
        claims=(
            claim(
                source=CreditClaimSource.COMMUNICATED,
                source_tick=2,
            ),
        ),
        signals=(signal(trust_milli=trust_milli),),
    )


def test_received_proposal_accepts_or_declines_by_willingness() -> None:
    accepted = credit_communicate_utterance(
        _talk(),
        owner_id=OWNER,
        ledger=_received_proposal_ledger(trust_milli=800),
        tick=3,
    )
    assert type(accepted) is Talk
    relation = accepted.utterance.content.relations[-1]
    assert relation.predicate == "crd_accept"
    declined = credit_communicate_utterance(
        _talk(),
        owner_id=OWNER,
        ledger=_received_proposal_ledger(trust_milli=0),
        tick=3,
    )
    assert declined.utterance.content.relations[-1].predicate == "crd_decline"


def test_owner_proposed_row_is_never_auto_accepted() -> None:
    ledger = apply_credit_relationship_update(
        owner_id=OWNER, tick=2, claims=(claim(),)
    )
    updated = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=ledger, tick=3
    )
    assert len(updated.utterance.content.relations) == 0


def test_debtor_renegotiates_or_defaults_at_the_deadline() -> None:
    ledger = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=2,
        commitments=commitment(
            owner_is_debtor=True,
            due_tick=10,
        ),
    )
    renegotiated = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=ledger, tick=10
    )
    assert (
        renegotiated.utterance.content.relations[-1].predicate
        == "crd_renegotiate"
    )
    low_trust = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=2,
        commitments=commitment(owner_is_debtor=True, due_tick=10),
        signals=(signal(trust_milli=0),),
        prices=prices(confidence_milli=0),
    )
    defaulted = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=low_trust, tick=10
    )
    assert defaulted.utterance.content.relations[-1].predicate == "crd_default"


def test_creditor_disputes_after_the_grace_window() -> None:
    ledger = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=2,
        commitments=commitment(due_tick=10),
    )
    before = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=ledger, tick=17
    )
    assert len(before.utterance.content.relations) == 0
    after = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=ledger, tick=18
    )
    assert after.utterance.content.relations[-1].predicate == "crd_dispute"


def test_creditor_forgives_a_trusted_expired_row() -> None:
    ledger = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=20,
        commitments=commitment(due_tick=10),
        signals=(signal(trust_milli=900),),
    )
    assert ledger.rows[0].status.value == "expired"
    updated = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=ledger, tick=20
    )
    assert updated.utterance.content.relations[-1].predicate == "crd_forgive"


def test_proposer_withdraws_after_eight_ticks() -> None:
    ledger = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=2,
        claims=(claim(active_terms=terms(due_tick=None)),),
    )
    before = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=ledger, tick=8
    )
    assert len(before.utterance.content.relations) == 0
    after = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=ledger, tick=9
    )
    assert after.utterance.content.relations[-1].predicate == "crd_withdraw"


def test_debtor_declares_observed_repayment() -> None:
    ledger = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=2,
        commitments=commitment(owner_is_debtor=True, due_tick=10),
    )
    observed = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=3,
        repayments=tuple(),
        prior=ledger,
    )
    assert observed.rows[0].status.value == "open"
    from agents.cognition.credit_relationships import (
        CreditRepaymentObservation,
    )

    observed = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=3,
        repayments=(
            CreditRepaymentObservation(
                counterparty_id=PEER,
                item_kind=ItemKind.WATER,
                quantity=1,
                tick=3,
            ),
        ),
        prior=ledger,
    )
    updated = credit_communicate_utterance(
        _talk(), owner_id=OWNER, ledger=observed, tick=3
    )
    relation = updated.utterance.content.relations[-1]
    assert relation.predicate == "crd_repay"
    assert parse_credit_claim_relation(relation).paid_quantity == 1


def test_existing_credit_relation_blocks_a_second_one() -> None:
    ledger = _received_proposal_ledger(trust_milli=800)
    relation = credit_claim_relation(_frame())
    command = Talk(
        recipient_id=PEER,
        utterance=origin_utterance(
            text="hello",
            speaker_id=OWNER_ENTITY,
            relations=(relation,),
        ),
    )
    updated = credit_communicate_utterance(
        command, owner_id=OWNER, ledger=ledger, tick=3
    )
    assert len(updated.utterance.content.relations) == 1


def test_relation_cap_is_respected() -> None:
    ledger = _received_proposal_ledger(trust_milli=800)
    relations = tuple(
        CommunicationRelation(subject="note", predicate=f"p{index}", object="x")
        for index in range(CREDIT_FRAME_MAX_RELATIONS)
    )
    command = Talk(
        recipient_id=PEER,
        utterance=origin_utterance(
            text="hello", speaker_id=OWNER_ENTITY, relations=relations
        ),
    )
    updated = credit_communicate_utterance(
        command, owner_id=OWNER, ledger=ledger, tick=3
    )
    assert updated is command


def test_only_talk_and_tell_are_expressible() -> None:
    ledger = _received_proposal_ledger(trust_milli=800)
    tell = Tell(
        recipient_id=PEER,
        utterance=origin_utterance(text="hello", speaker_id=OWNER_ENTITY),
    )
    assert type(
        credit_communicate_utterance(
            tell, owner_id=OWNER, ledger=ledger, tick=3
        )
    ) is Tell
    for command in (
        Wait(),
        Move(destination_id=EntityId("loc-b")),
        Give(recipient_id=PEER, item_id=EntityId("item-1")),
        NegotiateExchange(
            counterparty_id=PEER,
            act="offer",
            give_item_ids=(EntityId("item-1"),),
            take_item_ids=(EntityId("item-2"),),
        ),
    ):
        assert (
            credit_communicate_utterance(
                command, owner_id=OWNER, ledger=ledger, tick=3
            )
            is command
        )


def test_disabled_or_empty_ledger_is_a_noop() -> None:
    command = _talk()
    assert (
        credit_communicate_utterance(
            command, owner_id=OWNER, ledger=None, tick=3
        )
        is command
    )
