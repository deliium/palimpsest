"""Bounded ``crd_v1`` speech attachment for owner credit beliefs.

A credit relation travels only inside an existing ``Talk`` or ``Tell``
utterance. The frame is testimony, never a contract, bank record, or authority
to give or collect. The selector never creates or replaces a command; it may
attach at most one relation to an already-selected utterance.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from agents.cognition.credit_relationships import (
    CreditAct,
    CreditDirection,
    CreditRelationshipLedger,
    CreditRelationshipPolicy,
    CreditRelationshipRow,
    CreditStatus,
    CreditTerms,
    default_credit_relationship_policy,
)
from agents.models import AgentId
from world.credit_relationships import (
    CREDIT_ACT_PREDICATES,
    CREDIT_FRAME_MAX_RELATIONS,
    CREDIT_FRAME_SUBJECT,
    CreditClaimFrame,
    CreditFrameAct,
    CreditFrameDirection,
    credit_claim_relation,
    encode_credit_claim_frame,
)

__all__ = [
    "CREDIT_COMMUNICATION_POLICY_VERSION",
    "credit_communicate_utterance",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.credit_relationships_communication"
)

CREDIT_COMMUNICATION_POLICY_VERSION: Final[str] = (
    "credit-relationships-communication.v1"
)

_FRAME_ACTS: Final[dict[CreditAct, CreditFrameAct]] = {
    CreditAct.PROPOSE: CreditFrameAct.PROPOSE,
    CreditAct.ACCEPT: CreditFrameAct.ACCEPT,
    CreditAct.DECLINE: CreditFrameAct.DECLINE,
    CreditAct.REPAY: CreditFrameAct.REPAY,
    CreditAct.DEFAULT: CreditFrameAct.DEFAULT,
    CreditAct.RENEGOTIATE: CreditFrameAct.RENEGOTIATE,
    CreditAct.FORGIVE: CreditFrameAct.FORGIVE,
    CreditAct.DISPUTE: CreditFrameAct.DISPUTE,
    CreditAct.WITHDRAW: CreditFrameAct.WITHDRAW,
}
_FRAME_DIRECTIONS: Final[dict[CreditDirection, CreditFrameDirection]] = {
    CreditDirection.OWNER_DEBTOR: CreditFrameDirection.OWNER_DEBTOR,
    CreditDirection.OWNER_CREDITOR: CreditFrameDirection.OWNER_CREDITOR,
}


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _terms_with_due(terms: CreditTerms, due_tick: int) -> CreditTerms:
    return replace(terms, due_tick=due_tick)


def _select(
    ledger: CreditRelationshipLedger,
    *,
    tick: int,
    policy: CreditRelationshipPolicy,
) -> tuple[CreditAct, CreditRelationshipRow, CreditTerms] | None:
    received = [
        row
        for row in ledger.rows
        if row.status is CreditStatus.PROPOSED and not row.proposed_by_owner
    ]
    if received:
        received.sort(
            key=lambda row: (
                -row.expectation_milli,
                row.first_tick,
                row.anchor,
            )
        )
        row = received[0]
        act = (
            CreditAct.ACCEPT
            if row.expectation_milli >= policy.accept_min_willingness_milli
            else CreditAct.DECLINE
        )
        return act, row, row.terms

    repaid = [
        row
        for row in ledger.rows
        if row.direction is CreditDirection.OWNER_DEBTOR
        and row.status
        in {CreditStatus.PARTIALLY_REPAID, CreditStatus.REPAID}
        and row.last_repayment_tick == tick
    ]
    if repaid:
        repaid.sort(key=lambda row: (row.last_tick, row.anchor))
        return CreditAct.REPAY, repaid[0], repaid[0].terms

    overdue_debtor = [
        row
        for row in ledger.rows
        if row.direction is CreditDirection.OWNER_DEBTOR
        and row.status in {CreditStatus.OPEN, CreditStatus.PARTIALLY_REPAID}
        and row.terms.due_tick is not None
        and tick >= row.terms.due_tick
    ]
    if overdue_debtor:
        overdue_debtor.sort(key=lambda row: (row.terms.due_tick or 0, row.anchor))
        row = overdue_debtor[0]
        if row.expectation_milli < 250:
            return CreditAct.DEFAULT, row, row.terms
        return (
            CreditAct.RENEGOTIATE,
            row,
            _terms_with_due(row.terms, tick + 8),
        )

    overdue_creditor = [
        row
        for row in ledger.rows
        if row.direction is CreditDirection.OWNER_CREDITOR
        and row.status in {CreditStatus.OPEN, CreditStatus.PARTIALLY_REPAID}
        and row.terms.due_tick is not None
        and tick >= row.terms.due_tick + policy.grace_ticks
    ]
    if overdue_creditor:
        overdue_creditor.sort(key=lambda row: (row.terms.due_tick or 0, row.anchor))
        return CreditAct.DISPUTE, overdue_creditor[0], overdue_creditor[0].terms

    forgiven = [
        row
        for row in ledger.rows
        if row.direction is CreditDirection.OWNER_CREDITOR
        and row.status in {CreditStatus.DEFAULTED, CreditStatus.EXPIRED}
        and row.trust_milli >= 750
    ]
    if forgiven:
        forgiven.sort(key=lambda row: (-row.trust_milli, row.anchor))
        return CreditAct.FORGIVE, forgiven[0], forgiven[0].terms

    withdrawn = [
        row
        for row in ledger.rows
        if row.status is CreditStatus.PROPOSED
        and row.proposed_by_owner
        and tick - row.first_tick >= 8
    ]
    if withdrawn:
        withdrawn.sort(key=lambda row: (row.first_tick, row.anchor))
        return CreditAct.WITHDRAW, withdrawn[0], withdrawn[0].terms
    return None


def _frame_for(
    act: CreditAct,
    row: CreditRelationshipRow,
    terms: CreditTerms,
    *,
    paid_quantity: int = 0,
) -> CreditClaimFrame:
    collateral_item = terms.collateral_item_kind
    return CreditClaimFrame(
        act=_FRAME_ACTS[act],
        direction=_FRAME_DIRECTIONS[row.direction],
        anchor=row.anchor,
        principal_kind_token=terms.principal_kind.value,
        principal_quantity=terms.principal_quantity,
        repayment_kind_token=terms.repayment_kind.value,
        repayment_quantity=terms.repayment_quantity,
        paid_quantity=min(16, max(0, paid_quantity)),
        opened_tick=row.first_tick,
        due_tick=terms.due_tick,
        condition=terms.condition.value,
        collateral_kind=terms.collateral_kind.value,
        collateral_item_token=(
            None if collateral_item is None else collateral_item.value
        ),
        collateral_quantity=terms.collateral_quantity,
        confidence_milli=row.confidence_milli,
    )


def credit_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    ledger: object | None,
    tick: int,
    policy: CreditRelationshipPolicy | None = None,
) -> object:
    """Attach at most one ``crd_v1`` relation to an already-selected utterance."""

    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if type(ledger) is not CreditRelationshipLedger:
        return command
    if ledger.owner_id != owner_id or not ledger.rows:
        return command
    if not _is_expressible(command):
        return command
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise TypeError("tick must be a non-negative int")
    active = (
        default_credit_relationship_policy() if policy is None else policy
    )
    if type(active) is not CreditRelationshipPolicy:
        raise TypeError("policy must be CreditRelationshipPolicy or None")
    selected = _select(ledger, tick=tick, policy=active)
    if selected is None:
        return command
    act, row, terms = selected
    paid = (
        row.paid_quantity
        if act is CreditAct.REPAY
        else 0
    )
    frame = _frame_for(act, row, terms, paid_quantity=paid)
    utterance = getattr(command, "utterance", None)
    if utterance is None:
        return command
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = tuple(getattr(content, "relations", ()))
    if any(
        relation.subject == CREDIT_FRAME_SUBJECT
        or relation.predicate in CREDIT_ACT_PREDICATES.values()
        for relation in relations
    ):
        return command
    if len(relations) >= CREDIT_FRAME_MAX_RELATIONS:
        _LOG.warning("credit_frame_dropped reason_code=relation_cap")
        return command
    try:
        relation = credit_claim_relation(frame)
    except ValueError:
        _LOG.warning("credit_frame_dropped reason_code=malformed")
        return command
    if len(encode_credit_claim_frame(frame)) > 320:
        _LOG.warning("credit_frame_dropped reason_code=oversize")
        return command
    updated_content = replace(content, relations=(*relations, relation))
    updated_utterance = replace(utterance, content=updated_content)
    _LOG.debug("credit_frame_attached act=%s", act.value)
    from typing import Any, cast

    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated_utterance,
    )
