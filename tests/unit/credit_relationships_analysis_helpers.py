"""Shared builders for detached credit analysis tests."""

from __future__ import annotations

from types import SimpleNamespace

from world.credit_relationships import (
    CreditClaimFrame,
    CreditFrameAct,
    CreditFrameDirection,
    credit_claim_relation,
)
from world.events import (
    ExchangeCompleted,
    Fed,
    Given,
    Talked,
    Told,
)
from world.identifiers import EntityId, EventId

ANCHOR = "crd-0123456789abcdef"
ACTOR = "body-a"
RECIPIENT = "body-b"


def frame(
    *,
    act: CreditFrameAct = CreditFrameAct.PROPOSE,
    direction: CreditFrameDirection = CreditFrameDirection.OWNER_DEBTOR,
    anchor: str = ANCHOR,
    principal_kind: str = "food",
    principal_quantity: int = 2,
    repayment_kind: str = "water",
    repayment_quantity: int = 3,
    paid_quantity: int = 0,
    opened_tick: int = 0,
    due_tick: int | None = 10,
    confidence_milli: int = 500,
) -> CreditClaimFrame:
    return CreditClaimFrame(
        act=act,
        direction=direction,
        anchor=anchor,
        principal_kind_token=principal_kind,
        principal_quantity=principal_quantity,
        repayment_kind_token=repayment_kind,
        repayment_quantity=repayment_quantity,
        paid_quantity=paid_quantity,
        opened_tick=opened_tick,
        due_tick=due_tick,
        condition="by_deadline" if due_tick is not None else "on_receipt",
        collateral_kind="none",
        collateral_item_token=None,
        collateral_quantity=0,
        confidence_milli=confidence_milli,
    )


def event(
    token: str,
    details: object,
    *,
    tick: int = 0,
    sequence: int = 0,
    actor: str = ACTOR,
) -> SimpleNamespace:
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=sequence,
        actor_id=EntityId(actor),
        target_id=None,
        details=details,
        occurrence=None,
    )


def talked(
    token: str,
    *frames: CreditClaimFrame,
    tick: int = 0,
    sequence: int = 0,
    told: bool = False,
) -> SimpleNamespace:
    from world.communications import origin_utterance

    utterance = origin_utterance(
        text="credit",
        speaker_id=EntityId(ACTOR),
        relations=tuple(credit_claim_relation(item) for item in frames),
    )
    details_type = Told if told else Talked
    return event(
        token,
        details_type(recipient_id=EntityId(RECIPIENT), utterance=utterance),
        tick=tick,
        sequence=sequence,
    )


def given(
    token: str,
    *,
    item_id: str,
    tick: int = 0,
    sequence: int = 0,
    actor: str = ACTOR,
    recipient: str = RECIPIENT,
) -> SimpleNamespace:
    return event(
        token,
        Given(recipient_id=EntityId(recipient), item_id=EntityId(item_id)),
        tick=tick,
        sequence=sequence,
        actor=actor,
    )


def completed(
    token: str,
    *,
    give_ids: tuple[str, ...] = ("item-1",),
    give_kinds: tuple[str, ...] = ("food",),
    tick: int = 0,
) -> SimpleNamespace:
    return event(
        token,
        ExchangeCompleted(
            actor_id=EntityId(ACTOR),
            counterparty_id=EntityId(RECIPIENT),
            act="accept",
            give_item_ids=tuple(EntityId(value) for value in give_ids),
            take_item_ids=(EntityId("item-take"),),
            give_item_kinds=give_kinds,
            take_item_kinds=("material",),
        ),
        tick=tick,
    )


def fed(
    token: str,
    *,
    item_id: str = "item-2",
    item_kind: str = "water",
    tick: int = 0,
) -> SimpleNamespace:
    return event(
        token,
        Fed(
            target_id=EntityId(RECIPIENT),
            item_id=EntityId(item_id),
            item_kind=item_kind,
        ),
        tick=tick,
    )
