"""Shared builders for credit-relationship unit tests."""

# mypy: ignore-errors


from __future__ import annotations

from agents.cognition.credit_relationships import (
    CreditAct,
    CreditClaim,
    CreditClaimSource,
    CreditCollateralKind,
    CreditCondition,
    CreditCounterpartySignal,
    CreditDirection,
    CreditTerms,
    credit_anchor,
)
from agents.cognition.emergent_prices import (
    EmergentPriceLedger,
    PriceExpectationLevel,
    PriceExpectationRow,
    PriceUnitSource,
    price_belief_id,
)
from agents.cognition.structured_commitments import (
    CommitmentInterpretation,
    StructuredCommitmentLedger,
)
from agents.models import AgentId
from world.identifiers import EntityId
from world.values import ItemKind

OWNER = AgentId("agent-1")
OWNER_VALUE = "agent-1"
PEER_AGENT = "agent-2"
PEER = EntityId(PEER_AGENT)


def terms(
    *,
    principal_kind: ItemKind = ItemKind.FOOD,
    principal_quantity: int = 2,
    repayment_kind: ItemKind = ItemKind.WATER,
    repayment_quantity: int = 2,
    due_tick: int | None = 10,
    condition: CreditCondition = CreditCondition.BY_DEADLINE,
    collateral_kind: CreditCollateralKind = CreditCollateralKind.NONE,
    collateral_item_kind: ItemKind | None = None,
    collateral_quantity: int = 0,
) -> CreditTerms:
    return CreditTerms(
        principal_kind=principal_kind,
        principal_quantity=principal_quantity,
        repayment_kind=repayment_kind,
        repayment_quantity=repayment_quantity,
        due_tick=due_tick,
        condition=condition,
        collateral_kind=collateral_kind,
        collateral_item_kind=collateral_item_kind,
        collateral_quantity=collateral_quantity,
    )


def anchor(
    *,
    opened_tick: int = 1,
    principal_kind: ItemKind = ItemKind.FOOD,
    repayment_kind: ItemKind = ItemKind.WATER,
    party_a: str = OWNER_VALUE,
    party_b: str = PEER_AGENT,
) -> str:
    return credit_anchor(
        party_a=party_a,
        party_b=party_b,
        principal_kind=principal_kind,
        repayment_kind=repayment_kind,
        opened_tick=opened_tick,
    )


def claim(
    *,
    act: CreditAct = CreditAct.PROPOSE,
    direction: CreditDirection = CreditDirection.OWNER_DEBTOR,
    active_terms: CreditTerms | None = None,
    opened_tick: int = 1,
    paid_quantity: int = 0,
    confidence_milli: int = 500,
    source: CreditClaimSource = CreditClaimSource.SELF_AUTHORED,
    source_tick: int = 1,
    counterparty: EntityId = PEER,
    owner_value: str = OWNER_VALUE,
) -> CreditClaim:
    terms_value = active_terms if active_terms is not None else terms()
    return CreditClaim(
        act=act,
        direction=direction,
        anchor=anchor(
            opened_tick=opened_tick,
            principal_kind=terms_value.principal_kind,
            repayment_kind=terms_value.repayment_kind,
            party_a=owner_value,
            party_b=counterparty.value,
        ),
        terms=terms_value,
        paid_quantity=paid_quantity,
        opened_tick=opened_tick,
        confidence_milli=confidence_milli,
        counterparty_id=counterparty,
        source=source,
        source_tick=source_tick,
    )


def signal(
    *,
    trust_milli: int = 500,
    confidence_milli: int = 500,
    counterparty: EntityId = PEER,
) -> CreditCounterpartySignal:
    return CreditCounterpartySignal(
        counterparty_id=counterparty,
        trust_milli=trust_milli,
        confidence_milli=confidence_milli,
    )


def prices(
    *,
    item_kind: ItemKind = ItemKind.FOOD,
    unit_kind: ItemKind = ItemKind.WATER,
    confidence_milli: int = 750,
) -> EmergentPriceLedger:
    return EmergentPriceLedger(
        OWNER,
        rows=(
            PriceExpectationRow(
                item_kind=item_kind,
                unit_kind=unit_kind,
                unit_source=PriceUnitSource.OWNER_REFERENCE,
                expected_ratio_milli=1_000,
                confidence_milli=confidence_milli,
                level=PriceExpectationLevel.EXPECTED,
                valuation_reservation=0,
                observation_count=0,
                quote_count=0,
                first_tick=1,
                last_tick=1,
                observations=(),
                quotes=(),
                row_id=price_belief_id(OWNER, item_kind, unit_kind.value),
            ),
        ),
    )


def commitment(
    *,
    local_id: int = 1,
    kind: str = "debt",
    owed_by: str = "self",
    item_kind: str = "water",
    now_item_kind: str = "food",
    quantity: int = 2,
    due_tick: int | None = 10,
    created_tick: int = 1,
    status: str = "open",
    confidence: float = 0.6,
    owner_is_debtor: bool = False,
) -> StructuredCommitmentLedger:
    debtor = OWNER_VALUE if owner_is_debtor else PEER_AGENT
    creditor = PEER_AGENT if owner_is_debtor else OWNER_VALUE
    interpretation = CommitmentInterpretation(
        local_id=local_id,
        source_event_ids=("event-1",),
        parties=tuple(sorted((debtor, creditor))),
        debtor_id=debtor,
        creditor_id=creditor,
        kind=kind,
        owed_by=owed_by,
        item_kind=item_kind,
        service="none",
        quantity=quantity,
        now_item_kind=now_item_kind,
        due_kind="by_tick" if due_tick is not None else "none",
        due_tick=due_tick,
        created_tick=created_tick,
        status=status,
        now_matched=False,
        matched_quantity=0,
        confidence=confidence,
    )
    return StructuredCommitmentLedger(
        OWNER,
        max_open_interpretations=8,
        interpretations=(interpretation,),
    )
