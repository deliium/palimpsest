"""Committed-event reconstruction of bounded exchange-implied ratio evidence.

This module is the only price-analysis module that knows world event shapes. It
never reads ``WorldState``, cognition ledgers, stores, or observers, and it
retains no item ids, inventories, prices, or valuations.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from collections.abc import Sequence
from typing import Final, cast

from analysis.emergent_prices_contract import (
    EmergentPriceAnalysisError,
    PriceCoverage,
    PricePairing,
    PriceQuoteDirection,
)
from analysis.emergent_prices_policy import (
    EmergentPricesAnalysisPolicy,
    default_emergent_prices_analysis_policy,
    window_index_for_tick,
)
from analysis.emergent_prices_rows import (
    ExchangePriceEvidenceRow,
    PriceEvidenceHarvest,
    PriceQuoteEvidenceRow,
)
from analysis.market_institutions_contract import market_venue_token
from world.events import (
    ExchangeCompleted,
    ExchangeProposed,
    ExchangeWithdrawn,
    Fed,
    WorldEvent,
)

__all__ = [
    "price_evidence_digest",
    "price_evidence_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.emergent_prices.events")

_MAX_NOTICES: Final[int] = 8


def _event_token(event: WorldEvent) -> str:
    return event.event_id.value


def _origin_token(event: WorldEvent) -> str | None:
    occurrence = event.occurrence
    if occurrence is None or occurrence.origin_location_id is None:
        return None
    value = occurrence.origin_location_id.value
    return value if value else None


def _kind_index(events: Sequence[WorldEvent]) -> dict[str, str]:
    found: dict[str, str] = {}
    for event in events:
        details = event.details
        if type(details) is ExchangeCompleted:
            for item_id, kind in zip(
                details.give_item_ids, details.give_item_kinds, strict=True
            ):
                found[item_id.value] = kind
            for item_id, kind in zip(
                details.take_item_ids, details.take_item_kinds, strict=True
            ):
                found[item_id.value] = kind
        elif type(details) is Fed:
            found[details.item_id.value] = details.item_kind
    return found


def _resolve(
    item_ids: Sequence[object], kind_of: dict[str, str]
) -> tuple[str, ...] | None:
    kinds: list[str] = []
    for item_id in item_ids:
        key = getattr(item_id, "value", None)
        if type(key) is not str:
            return None
        kind = kind_of.get(key)
        if kind is None:
            return None
        kinds.append(kind)
    return tuple(kinds)


def _side_kinds(value: object) -> tuple[str, ...] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        return None
    kinds: list[str] = []
    for kind in value:
        if type(kind) is not str or not kind:
            return None
        kinds.append(kind)
    return tuple(kinds)


def _pairing(
    give_kinds: tuple[str, ...], take_kinds: tuple[str, ...]
) -> tuple[PricePairing, str, str, int, int, int | None]:
    """Return pairing, canonical item/unit kinds, counts, and optional ratio."""

    if not give_kinds or not take_kinds:
        return PricePairing.HETEROGENEOUS, "", "", 0, 0, None
    give = Counter(give_kinds)
    take = Counter(take_kinds)
    if len(give) > 1 or len(take) > 1:
        all_kinds = sorted(set(give_kinds) | set(take_kinds))
        return (
            PricePairing.HETEROGENEOUS,
            all_kinds[0],
            all_kinds[-1],
            len(give_kinds),
            len(take_kinds),
            None,
        )
    give_kind = next(iter(give))
    take_kind = next(iter(take))
    if give_kind == take_kind:
        return (
            PricePairing.SAME_KIND,
            give_kind,
            take_kind,
            len(give_kinds),
            len(take_kinds),
            None,
        )
    item_kind = min(give_kind, take_kind)
    unit_kind = max(give_kind, take_kind)
    item_count = give[item_kind] + take[item_kind]
    unit_count = give[unit_kind] + take[unit_kind]
    if item_count <= 0:
        return PricePairing.HETEROGENEOUS, item_kind, unit_kind, 0, unit_count, None
    ratio = unit_count * 1_000 // item_count
    return PricePairing.PAIRED, item_kind, unit_kind, item_count, unit_count, ratio


def _direction(
    *, item_kind: str, give_kinds: tuple[str, ...]
) -> PriceQuoteDirection:
    if item_kind in give_kinds:
        return PriceQuoteDirection.GIVE_FOR_UNIT
    return PriceQuoteDirection.UNIT_FOR_GIVE


def price_evidence_rows_from_events(
    events: Sequence[object],
    *,
    policy: EmergentPricesAnalysisPolicy | None = None,
) -> PriceEvidenceHarvest:
    """Reconstruct bounded ratio evidence from committed events only."""

    active = (
        default_emergent_prices_analysis_policy() if policy is None else policy
    )
    if type(active) is not EmergentPricesAnalysisPolicy:
        raise EmergentPriceAnalysisError("price_analysis_invalid_policy")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise EmergentPriceAnalysisError("price_analysis_missing_input")
    ordered = sorted(
        cast(Sequence[WorldEvent], events), key=lambda item: (item.tick, item.sequence)
    )
    seen: set[str] = set()
    for event in ordered:
        token = _event_token(event)
        if token in seen:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        seen.add(token)

    kind_of = _kind_index(ordered)
    notices: set[str] = set()
    exchanges: list[ExchangePriceEvidenceRow] = []
    quotes: list[PriceQuoteEvidenceRow] = []
    skipped = 0

    for event in ordered:
        details = event.details
        if type(details) is ExchangeCompleted:
            give_kinds = _side_kinds(details.give_item_kinds)
            take_kinds = _side_kinds(details.take_item_kinds)
            if give_kinds is None or take_kinds is None:
                skipped += 1
                continue
            origin = _origin_token(event)
            venue = market_venue_token(origin) if origin is not None else "none"
            coverage = (
                PriceCoverage.PARTIAL
                if origin is None
                else PriceCoverage.COMPLETE
            )
            if origin is None:
                notices.add("price_venue_unresolved")
            pairing, item_kind, unit_kind, item_count, unit_count, ratio = _pairing(
                give_kinds, take_kinds
            )
            if ratio is not None and ratio > active.max_ratio_milli:
                pairing = PricePairing.OUT_OF_RANGE
                ratio = None
            exchanges.append(
                ExchangePriceEvidenceRow(
                    tick=event.tick,
                    window_index=window_index_for_tick(event.tick, active),
                    venue_token=venue,
                    event_token=_event_token(event),
                    event_kind="completed",
                    actor_token=details.actor_id.value,
                    counterparty_token=details.counterparty_id.value,
                    item_kind=item_kind,
                    unit_kind=unit_kind,
                    item_count=item_count,
                    unit_count=unit_count,
                    ratio_milli=ratio,
                    pairing=pairing,
                    coverage=coverage,
                )
            )
        elif isinstance(details, (ExchangeProposed, ExchangeWithdrawn)):
            assert isinstance(details, (ExchangeProposed, ExchangeWithdrawn))
            origin = _origin_token(event)
            venue = market_venue_token(origin) if origin is not None else "none"
            coverage = (
                PriceCoverage.PARTIAL
                if origin is None
                else PriceCoverage.COMPLETE
            )
            if origin is None:
                notices.add("price_venue_unresolved")
            give_kinds_raw = _resolve(details.give_item_ids, kind_of)
            take_kinds_raw = _resolve(details.take_item_ids, kind_of)
            if give_kinds_raw is None or take_kinds_raw is None:
                skipped += 1
                continue
            give_kinds = give_kinds_raw
            take_kinds = take_kinds_raw
            if not give_kinds or not take_kinds:
                skipped += 1
                continue
            pairing, item_kind, unit_kind, _item_count, _unit_count, ratio = _pairing(
                give_kinds, take_kinds
            )
            if ratio is not None and ratio > active.max_ratio_milli:
                pairing = PricePairing.OUT_OF_RANGE
                ratio = None
            quotes.append(
                PriceQuoteEvidenceRow(
                    tick=event.tick,
                    window_index=window_index_for_tick(event.tick, active),
                    venue_token=venue,
                    event_token=_event_token(event),
                    actor_token=details.actor_id.value,
                    counterparty_token=details.counterparty_id.value,
                    item_kind=item_kind,
                    unit_kind=unit_kind,
                    direction=_direction(item_kind=item_kind, give_kinds=give_kinds),
                    ratio_milli=ratio,
                    pairing=pairing,
                    coverage=coverage,
                )
            )

    unique_quotes: dict[tuple[str, str, str, str], PriceQuoteEvidenceRow] = {}
    for row in quotes:
        key = (row.event_token, row.item_kind, row.unit_kind, row.direction.value)
        unique_quotes.setdefault(key, row)
    quotes = list(unique_quotes.values())
    quotes.sort(
        key=lambda row: (
            row.tick,
            row.event_token,
            row.item_kind,
            row.unit_kind,
            row.direction.value,
        )
    )
    exchanges.sort(
        key=lambda row: (
            row.tick,
            row.event_token,
            row.item_kind,
            row.unit_kind,
        )
    )

    if len(exchanges) > active.max_exchange_events:
        exchanges = exchanges[: active.max_exchange_events]
        notices.add("price_evidence_truncated")
        _LOG.warning(
            "price_evidence_truncated family=exchanges cap=%s",
            active.max_exchange_events,
        )
    if len(quotes) > active.max_quote_events:
        quotes = quotes[: active.max_quote_events]
        notices.add("price_evidence_truncated")
        _LOG.warning(
            "price_evidence_truncated family=quotes cap=%s",
            active.max_quote_events,
        )
    if skipped:
        notices.add("price_evidence_skipped")
        _LOG.warning("price_evidence_skipped count=%s", skipped)

    if not exchanges and not quotes:
        coverage = PriceCoverage.MISSING
    elif notices:
        coverage = PriceCoverage.PARTIAL
    else:
        coverage = PriceCoverage.COMPLETE

    _LOG.debug(
        "price_evidence_harvested exchanges=%s quotes=%s coverage=%s",
        len(exchanges),
        len(quotes),
        coverage.value,
    )
    return PriceEvidenceHarvest(
        exchanges=tuple(exchanges),
        quotes=tuple(quotes),
        coverage=coverage,
        notices=tuple(sorted(notices)[:_MAX_NOTICES]),
        exchange_count=len(exchanges),
        quote_count=len(quotes),
    )


def price_evidence_digest(harvest: PriceEvidenceHarvest) -> str:
    """Return a deterministic digest over canonical evidence rows."""

    if type(harvest) is not PriceEvidenceHarvest:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    material: list[str] = []
    for row in harvest.exchanges:
        material.append(
            "\x1f".join(
                (
                    "exchange",
                    str(row.tick),
                    str(row.window_index),
                    row.venue_token,
                    row.event_token,
                    row.actor_token,
                    row.counterparty_token,
                    row.item_kind,
                    row.unit_kind,
                    str(row.item_count),
                    str(row.unit_count),
                    "none" if row.ratio_milli is None else str(row.ratio_milli),
                    row.pairing.value,
                )
            )
        )
    for quote in harvest.quotes:
        material.append(
            "\x1f".join(
                (
                    "quote",
                    str(quote.tick),
                    str(quote.window_index),
                    quote.venue_token,
                    quote.event_token,
                    quote.actor_token,
                    quote.counterparty_token,
                    quote.item_kind,
                    quote.unit_kind,
                    quote.direction.value,
                    "none" if quote.ratio_milli is None else str(quote.ratio_milli),
                    quote.pairing.value,
                )
            )
        )
    return hashlib.sha256("\x1e".join(material).encode("utf-8")).hexdigest()
