"""Shared builders for emergent-price unit tests."""

# mypy: ignore-errors


from __future__ import annotations

from agents.cognition.acceptance_memory import (
    AcceptanceMemoryLedger,
    AcceptanceMemoryRow,
)
from agents.cognition.emergent_prices import (
    PriceQuote,
    PriceQuoteDirection,
    PriceQuoteSource,
    make_price_observation,
)
from agents.cognition.subjective_value import (
    SubjectiveValuationLedger,
    ValuationRow,
)
from agents.models import AgentId
from world.identifiers import EntityId
from world.values import ItemKind

OWNER = AgentId("agent-1")
PEER = AgentId("agent-2")
OWNER_ENTITY = EntityId("body-1")
PEER_ENTITY = EntityId("body-2")
VENUE = "mkt-ven-0123456789abcdef"


def valuations(
    *rows: tuple[ItemKind, ItemKind, int],
    tick: int = 1,
) -> SubjectiveValuationLedger:
    return SubjectiveValuationLedger(
        OWNER,
        kind_rows=tuple(
            ValuationRow(item, reference, reservation, (), tick)
            for item, reference, reservation in rows
        ),
    )


def acceptance(*rows: tuple[ItemKind, int], tick: int = 1) -> AcceptanceMemoryLedger:
    return AcceptanceMemoryLedger(
        OWNER,
        rows=tuple(
            AcceptanceMemoryRow(kind, count, ("giver-1",), tick)
            for kind, count in rows
        ),
    )


def observation(
    *,
    source_tick: int = 1,
    item_kind: ItemKind = ItemKind.FOOD,
    unit_kind: ItemKind = ItemKind.WATER,
    exchange_count: int = 1,
    proposed_count: int = 0,
    withdrawn_count: int = 0,
    ratio: int | None = 1_000,
    counterparties: tuple[EntityId, ...] = (PEER_ENTITY,),
):
    return make_price_observation(
        source_tick=source_tick,
        item_kind=item_kind,
        unit_kind=unit_kind,
        counterparty_ids=counterparties,
        exchange_count=exchange_count,
        proposed_count=proposed_count,
        withdrawn_count=withdrawn_count,
        observed_ratio_milli=ratio,
    )


def quote(
    *,
    item_kind: ItemKind = ItemKind.FOOD,
    unit_kind: ItemKind = ItemKind.WATER,
    direction: PriceQuoteDirection = PriceQuoteDirection.GIVE_FOR_UNIT,
    ratio: int = 2_000,
    confidence: int = 500,
    source: PriceQuoteSource = PriceQuoteSource.OBSERVED_OFFER,
    source_tick: int = 1,
) -> PriceQuote:
    return PriceQuote(
        item_kind=item_kind,
        unit_kind=unit_kind,
        venue_id=VENUE,
        direction=direction,
        counterparty_id=PEER_ENTITY,
        ratio_milli=ratio,
        confidence_milli=confidence,
        source=source,
        source_tick=source_tick,
        first_tick=source_tick,
        last_tick=source_tick,
    )
