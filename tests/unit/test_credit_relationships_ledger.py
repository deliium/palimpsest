"""Owner-scoped credit relationship ledger behaviour."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from agents.cognition.credit_relationships import (
    CREDIT_NOTICE_CODES,
    CreditAct,
    CreditClaim,
    CreditClaimSource,
    CreditDirection,
    CreditRelationshipLedger,
    CreditRepaymentObservation,
    CreditStatus,
    CreditTermsRevision,
    apply_credit_relationship_update,
    credit_row_id,
    empty_credit_relationships,
)
from agents.models import AgentId
from tests.unit.test_credit_relationships_helpers import (
    OWNER,
    OWNER_VALUE,
    PEER,
    anchor,
    claim,
    commitment,
    prices,
    signal,
    terms,
)
from world.values import ItemKind

pytestmark = pytest.mark.unit


def _apply(**kwargs):  # type: ignore[no-untyped-def]
    return apply_credit_relationship_update(owner_id=OWNER, **kwargs)


def _row(ledger: CreditRelationshipLedger):  # type: ignore[no-untyped-def]
    assert len(ledger.rows) == 1
    return ledger.rows[0]


def test_self_authored_proposal_creates_proposed_row() -> None:
    ledger = _apply(tick=2, claims=(claim(),))
    row = _row(ledger)
    assert row.status is CreditStatus.PROPOSED
    assert row.direction is CreditDirection.OWNER_DEBTOR
    assert row.proposed_by_owner is True
    assert row.terms == terms()
    assert row.own_claim_count == 1
    assert row.row_id == credit_row_id(OWNER, row.anchor)


def test_received_proposal_inverts_direction_and_is_not_owner_proposed() -> None:
    received = claim(source=CreditClaimSource.COMMUNICATED, source_tick=2)
    ledger = _apply(tick=2, claims=(received,))
    row = _row(ledger)
    assert row.direction is CreditDirection.OWNER_CREDITOR
    assert row.proposed_by_owner is False
    assert row.received_claim_count == 1


def test_accept_decline_and_withdraw_transitions() -> None:
    proposed = _apply(tick=1, claims=(claim(),))
    accepted = _apply(
        tick=2,
        claims=(claim(act=CreditAct.ACCEPT, source_tick=2),),
        prior=proposed,
    )
    assert _row(accepted).status is CreditStatus.ACCEPTED
    declined = _apply(
        tick=2,
        claims=(claim(act=CreditAct.DECLINE, source_tick=2),),
        prior=proposed,
    )
    assert _row(declined).status is CreditStatus.DECLINED
    withdrawn = _apply(
        tick=2,
        claims=(claim(act=CreditAct.WITHDRAW, source_tick=2),),
        prior=proposed,
    )
    assert _row(withdrawn).status is CreditStatus.WITHDRAWN


def test_accept_on_decided_row_is_rejected() -> None:
    proposed = _apply(tick=1, claims=(claim(),))
    accepted = _apply(
        tick=2,
        claims=(claim(act=CreditAct.ACCEPT, source_tick=2),),
        prior=proposed,
    )
    again = _apply(
        tick=3,
        claims=(claim(act=CreditAct.ACCEPT, source_tick=3),),
        prior=accepted,
    )
    assert _row(again).status is CreditStatus.ACCEPTED
    assert "credit_claim_rejected" in again.notices


def test_partial_then_full_repayment_claim() -> None:
    active = terms(repayment_quantity=3)
    proposed = _apply(tick=1, claims=(claim(active_terms=active),))
    accepted = _apply(
        tick=2,
        claims=(claim(act=CreditAct.ACCEPT, active_terms=active, source_tick=2),),
        prior=proposed,
    )
    partial = _apply(
        tick=3,
        claims=(
            claim(
                act=CreditAct.REPAY,
                active_terms=active,
                paid_quantity=1,
                source_tick=3,
            ),
        ),
        prior=accepted,
    )
    assert _row(partial).status is CreditStatus.PARTIALLY_REPAID
    assert _row(partial).paid_quantity == 1
    full = _apply(
        tick=4,
        claims=(
            claim(
                act=CreditAct.REPAY,
                active_terms=active,
                paid_quantity=2,
                source_tick=4,
            ),
        ),
        prior=partial,
    )
    assert _row(full).status is CreditStatus.REPAID
    assert _row(full).paid_quantity == 3


def test_repayment_claim_on_terminal_row_is_rejected() -> None:
    proposed = _apply(tick=1, claims=(claim(),))
    forgiven = _apply(
        tick=2,
        claims=(claim(act=CreditAct.FORGIVE, source_tick=2),),
        prior=proposed,
    )
    repaid = _apply(
        tick=3,
        claims=(
            claim(act=CreditAct.REPAY, paid_quantity=1, source_tick=3),
        ),
        prior=forgiven,
    )
    assert _row(repaid).status is CreditStatus.FORGIVEN
    assert "credit_claim_rejected" in repaid.notices


def test_default_requires_due_tick_or_debtor_self_declaration() -> None:
    early = terms(due_tick=10)
    proposed = _apply(tick=1, claims=(claim(active_terms=early),))
    self_declared = _apply(
        tick=2,
        claims=(claim(act=CreditAct.DEFAULT, active_terms=early, source_tick=2),),
        prior=proposed,
    )
    assert _row(self_declared).status is CreditStatus.DEFAULTED

    remote = _apply(
        tick=2,
        claims=(
            claim(
                act=CreditAct.DEFAULT,
                direction=CreditDirection.OWNER_CREDITOR,
                source=CreditClaimSource.COMMUNICATED,
                source_tick=2,
            ),
        ),
        prior=proposed,
    )
    assert _row(remote).status is CreditStatus.PROPOSED
    assert "credit_claim_rejected" in remote.notices

    on_time = _apply(
        tick=10,
        claims=(
            claim(
                act=CreditAct.DEFAULT,
                direction=CreditDirection.OWNER_CREDITOR,
                source=CreditClaimSource.COMMUNICATED,
                source_tick=10,
            ),
        ),
        prior=proposed,
    )
    assert _row(on_time).status is CreditStatus.DEFAULTED


def test_forgive_and_dispute_are_owner_beliefs() -> None:
    proposed = _apply(tick=1, claims=(claim(),))
    forgiven = _apply(
        tick=2,
        claims=(claim(act=CreditAct.FORGIVE, source_tick=2),),
        prior=proposed,
    )
    disputed = _apply(
        tick=2,
        claims=(claim(act=CreditAct.DISPUTE, source_tick=2),),
        prior=proposed,
    )
    assert _row(forgiven).status is CreditStatus.FORGIVEN
    assert _row(disputed).status is CreditStatus.DISPUTED


def test_renegotiation_retains_prior_terms_and_resets_paid_quantity() -> None:
    original = terms(repayment_quantity=2)
    revised = terms(repayment_quantity=4)
    proposed = _apply(tick=1, claims=(claim(active_terms=original),))
    accepted = _apply(
        tick=2,
        claims=(claim(act=CreditAct.ACCEPT, active_terms=original, source_tick=2),),
        prior=proposed,
    )
    partial = _apply(
        tick=3,
        claims=(
            claim(
                act=CreditAct.REPAY,
                active_terms=original,
                paid_quantity=1,
                source_tick=3,
            ),
        ),
        prior=accepted,
    )
    renegotiated = _apply(
        tick=4,
        claims=(
            claim(act=CreditAct.RENEGOTIATE, active_terms=revised, source_tick=4),
        ),
        prior=partial,
    )
    row = _row(renegotiated)
    assert row.terms == revised
    assert row.paid_quantity == 0
    assert row.status is CreditStatus.OPEN
    assert row.revisions == (
        CreditTermsRevision(tick=4, terms=original, reason="renegotiated"),
    )


def test_repeated_fold_is_a_byte_identical_no_op() -> None:
    first = _apply(tick=2, claims=(claim(),))
    second = _apply(tick=2, claims=(claim(),), prior=first)
    assert second == first
    assert second.notices == first.notices
    assert _row(second).confidence_milli == _row(first).confidence_milli


def test_accept_with_mismatched_terms_is_rejected() -> None:
    proposed = _apply(tick=1, claims=(claim(),))
    mismatched = terms(repayment_quantity=5)
    result = _apply(
        tick=2,
        claims=(claim(act=CreditAct.ACCEPT, active_terms=mismatched, source_tick=2),),
        prior=proposed,
    )
    assert _row(result).status is CreditStatus.PROPOSED
    assert "credit_terms_mismatch" in result.notices


def test_missing_trust_and_price_defaults() -> None:
    row = _row(_apply(tick=2, claims=(claim(),)))
    assert row.trust_milli == 500
    assert row.trust_confidence_milli == 200
    assert row.price_confidence_milli == 500
    assert row.expectation_milli == 500


def test_willingness_formula_uses_trust_history_and_price_confidence() -> None:
    trusted = _row(
        _apply(tick=2, claims=(claim(),), signals=(signal(trust_milli=1_000),))
    )
    assert trusted.expectation_milli == 750
    priced = _row(
        _apply(
            tick=2,
            claims=(claim(),),
            signals=(signal(trust_milli=1_000),),
            prices=prices(confidence_milli=1_000),
        )
    )
    assert priced.expectation_milli == 850


def test_repaid_history_contributes_to_willingness() -> None:
    first_terms = terms(repayment_quantity=1)
    second_terms = terms(repayment_quantity=1)
    first = claim(active_terms=first_terms, opened_tick=1)
    second = claim(active_terms=second_terms, opened_tick=2, source_tick=2)
    ledger = _apply(tick=2, claims=(first, second))
    assert len(ledger.rows) == 2
    accepted = _apply(
        tick=3,
        claims=(
            claim(
                act=CreditAct.ACCEPT,
                active_terms=first_terms,
                opened_tick=1,
                source_tick=3,
            ),
        ),
        prior=ledger,
    )
    repaid = _apply(
        tick=4,
        claims=(
            claim(
                act=CreditAct.REPAY,
                active_terms=first_terms,
                opened_tick=1,
                paid_quantity=1,
                source_tick=4,
            ),
        ),
        prior=accepted,
    )
    for row in repaid.rows:
        assert row.expectation_milli == 650


def test_commitment_seeds_open_creditor_candidate() -> None:
    ledger = _apply(tick=2, commitments=commitment())
    row = _row(ledger)
    assert row.direction is CreditDirection.OWNER_CREDITOR
    assert row.status is CreditStatus.OPEN
    assert row.proposed_by_owner is False
    assert row.promise_count == 1
    assert row.terms.principal_kind is ItemKind.FOOD
    assert row.terms.repayment_kind is ItemKind.WATER


def test_commitment_seeds_owner_debtor_candidate() -> None:
    ledger = _apply(tick=2, commitments=commitment(owner_is_debtor=True))
    row = _row(ledger)
    assert row.direction is CreditDirection.OWNER_DEBTOR
    assert row.proposed_by_owner is True
    assert row.promise_count == 1


def test_commitment_fold_is_idempotent() -> None:
    first = _apply(tick=2, commitments=commitment())
    second = _apply(tick=2, commitments=commitment(), prior=first)
    assert second == first
    assert _row(second).promise_count == 1


def test_non_credit_commitment_kind_is_ignored() -> None:
    ledger = _apply(tick=2, commitments=commitment(kind="promise"))
    assert ledger.rows == ()


def test_repayment_observation_folds_into_open_debtor_row() -> None:
    ledger = _apply(tick=2, commitments=commitment(owner_is_debtor=True))
    observed = _apply(
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
    row = _row(observed)
    assert row.status is CreditStatus.PARTIALLY_REPAID
    assert row.paid_quantity == 1
    assert row.last_repayment_tick == 3


def test_ambiguous_repayment_observation_changes_nothing() -> None:
    first = claim(active_terms=terms(repayment_quantity=3), opened_tick=1)
    second = claim(
        active_terms=terms(repayment_quantity=3), opened_tick=2, source_tick=2
    )
    ledger = _apply(tick=2, claims=(first, second))
    ledger = _apply(
        tick=3,
        claims=(
            claim(
                act=CreditAct.ACCEPT,
                active_terms=terms(repayment_quantity=3),
                opened_tick=1,
                source_tick=3,
            ),
            claim(
                act=CreditAct.ACCEPT,
                active_terms=terms(repayment_quantity=3),
                opened_tick=2,
                source_tick=3,
            ),
        ),
        prior=ledger,
    )
    assert all(row.status is CreditStatus.ACCEPTED for row in ledger.rows)
    observed = _apply(
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
    assert all(row.paid_quantity == 0 for row in observed.rows)
    assert "credit_repayment_ambiguous" in observed.notices


def test_unmatched_repayment_observation_is_noted() -> None:
    ledger = _apply(
        tick=2,
        repayments=(
            CreditRepaymentObservation(
                counterparty_id=PEER,
                item_kind=ItemKind.WATER,
                quantity=1,
                tick=2,
            ),
        ),
    )
    assert ledger.rows == ()
    assert "credit_repayment_unmatched" in ledger.notices


def test_row_cap_truncates_with_notice() -> None:
    claims = tuple(
        claim(opened_tick=index, source_tick=index) for index in range(1, 34)
    )
    ledger = _apply(tick=34, claims=claims)
    assert len(ledger.rows) == 32
    assert "credit_ledger_truncated" in ledger.notices


def test_claims_per_row_cap_truncates_with_notice() -> None:
    claims = tuple(
        claim(source_tick=index) for index in range(1, 18)
    )
    ledger = _apply(tick=18, claims=claims)
    row = _row(ledger)
    assert len(row.claims) == 16
    assert "credit_ledger_truncated" in ledger.notices


def test_notice_bounds_keep_a_deterministic_prefix() -> None:
    ledger = CreditRelationshipLedger(OWNER, notices=tuple(CREDIT_NOTICE_CODES))
    assert len(ledger.notices) == 8
    assert ledger.notices == tuple(sorted(CREDIT_NOTICE_CODES))[:8]


def test_two_owners_never_share_row_ids_or_beliefs() -> None:
    first = _apply(tick=2, claims=(claim(),))
    other_owner = AgentId("agent-9")
    second = apply_credit_relationship_update(
        owner_id=other_owner,
        tick=2,
        claims=(claim(owner_value=other_owner.value),),
    )
    assert first.owner_id != second.owner_id
    assert _row(first).row_id != _row(second).row_id


def test_same_counterparty_two_anchors_are_independent() -> None:
    first = _row(
        _apply(
            tick=2,
            claims=(claim(active_terms=terms(repayment_kind=ItemKind.WATER)),),
        )
    )
    second = _row(
        _apply(
            tick=2,
            claims=(claim(active_terms=terms(repayment_kind=ItemKind.TOOL)),),
        )
    )
    assert first.anchor != second.anchor
    ledger = _apply(
        tick=3,
        claims=(
            claim(active_terms=terms(repayment_kind=ItemKind.WATER)),
            claim(
                active_terms=terms(repayment_kind=ItemKind.TOOL),
                source_tick=2,
            ),
        ),
    )
    assert len(ledger.rows) == 2


def test_empty_ledger_is_owner_local() -> None:
    ledger = empty_credit_relationships(OWNER)
    assert ledger.owner_id == OWNER
    assert ledger.rows == ()
    assert ledger.owner_id.value == OWNER_VALUE


def test_claim_anchor_forgery_is_ignored() -> None:
    forged_terms = terms()
    forged = CreditClaim(
        act=CreditAct.PROPOSE,
        direction=CreditDirection.OWNER_DEBTOR,
        anchor=anchor(party_b="someone-else"),
        terms=forged_terms,
        paid_quantity=0,
        opened_tick=1,
        confidence_milli=500,
        counterparty_id=PEER,
        source=CreditClaimSource.SELF_AUTHORED,
        source_tick=1,
    )
    ledger = _apply(tick=2, claims=(forged,))
    assert ledger.rows == ()
    assert "credit_anchor_ambiguous" in ledger.notices
