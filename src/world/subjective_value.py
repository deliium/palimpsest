"""Objective barter gate. Carries horizon and bundle size, never a ledger."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from world.identifiers import EntityId

_LOG = logging.getLogger(__name__)


def exchange_party_ids(left: EntityId, right: EntityId) -> tuple[EntityId, EntityId]:
    """Canonical unordered pair. The lower id is first."""
    if type(left) is not EntityId or type(right) is not EntityId:
        raise TypeError("exchange parties must be EntityId")
    if left == right:
        raise ValueError("exchange parties must be distinct")
    if left.value <= right.value:
        return (left, right)
    return (right, left)


@dataclass(frozen=True, slots=True)
class ExchangeOffer:
    """Live proposal. Parties, item ids, and tick. No reservation integer."""

    party_ids: tuple[EntityId, EntityId]
    proposer_id: EntityId
    give_item_ids: tuple[EntityId, ...]
    take_item_ids: tuple[EntityId, ...]
    tick: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.party_ids, tuple)
            or len(self.party_ids) != 2
            or any(type(party) is not EntityId for party in self.party_ids)
        ):
            raise TypeError("ExchangeOffer.party_ids must be two EntityIds")
        ordered = exchange_party_ids(self.party_ids[0], self.party_ids[1])
        if ordered != self.party_ids:
            raise ValueError("ExchangeOffer.party_ids must be ordered")
        if type(self.proposer_id) is not EntityId or self.proposer_id not in self.party_ids:
            raise ValueError("ExchangeOffer.proposer_id must be one party")
        give = _distinct_ids("ExchangeOffer.give_item_ids", self.give_item_ids)
        take = _distinct_ids("ExchangeOffer.take_item_ids", self.take_item_ids)
        if not give or not take:
            raise ValueError("ExchangeOffer sides must be non-empty")
        if set(give) & set(take):
            raise ValueError("ExchangeOffer item ids must be disjoint")
        if type(self.tick) is not int or isinstance(self.tick, bool) or self.tick < 0:
            raise ValueError("ExchangeOffer.tick must be a non-negative int")
        object.__setattr__(self, "give_item_ids", give)
        object.__setattr__(self, "take_item_ids", take)
        _LOG.debug(
            "exchange_offer_stored pair=%s,%s tick=%s give_len=%s take_len=%s",
            self.party_ids[0].value,
            self.party_ids[1].value,
            self.tick,
            len(give),
            len(take),
        )


def _distinct_ids(name: str, value: object) -> tuple[EntityId, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple of EntityId")
    seen: set[str] = set()
    copied: list[EntityId] = []
    for item in value:
        if type(item) is not EntityId:
            raise TypeError(f"{name} entries must be EntityId")
        if item.value in seen:
            raise ValueError(f"duplicate {name}")
        seen.add(item.value)
        copied.append(item)
    return tuple(copied)


@dataclass(frozen=True, slots=True)
class SubjectiveValuationRuleContext:
    """Admission context for ``NegotiateExchange``.

    The engine reads ``horizon_ticks`` and ``max_bundle`` only. A valuation
    ledger is not a field of this context.
    """

    allow_negotiate: bool
    horizon_ticks: int
    max_bundle: int

    def __post_init__(self) -> None:
        if type(self.allow_negotiate) is not bool:
            raise TypeError("allow_negotiate must be bool")
        if type(self.horizon_ticks) is not int or isinstance(self.horizon_ticks, bool):
            raise TypeError("horizon_ticks must be int")
        if type(self.max_bundle) is not int or isinstance(self.max_bundle, bool):
            raise TypeError("max_bundle must be int")
        if self.horizon_ticks < 1 or self.horizon_ticks > 64:
            raise ValueError("horizon_ticks must be in [1, 64]")
        if self.max_bundle < 1 or self.max_bundle > 8:
            raise ValueError("max_bundle must be in [1, 8]")
        _LOG.debug(
            "subjective_valuation_rule_context allow_negotiate=%s "
            "horizon_ticks=%s max_bundle=%s",
            self.allow_negotiate,
            self.horizon_ticks,
            self.max_bundle,
        )
