"""Token-only owner export rows for detached price analysis.

The export reads completed owner ledgers and emits neutral strings and integers.
It never includes counterparty ids, item ids, raw observations, valuations, or
digest content, and it never imports ``analysis``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, NoReturn

from agents.cognition.emergent_prices import (
    PRICE_WINDOW_TICKS,
    EmergentPriceError,
    EmergentPriceLedger,
)
from agents.models import AgentId

__all__ = [
    "EmergentPriceOwnerQuoteRow",
    "EmergentPriceOwnerRow",
    "price_owner_export",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.emergent_prices_export")

_NONE_TOKEN: Final[str] = "none"


def _fail(code: str) -> NoReturn:
    _LOG.error("emergent_prices_export_invalid reason_code=%s", code)
    raise EmergentPriceError(code)


def _token(name: str, value: object) -> str:
    if type(value) is not str or not value:
        _fail("price_invalid_identifier")
    return value


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail("price_invalid_identifier")
    return value


@dataclass(frozen=True, slots=True)
class EmergentPriceOwnerRow:
    """One neutral exported owner expectation row."""

    owner_token: str
    venue_token: str
    window_index: int
    item_kind_token: str
    unit_token: str
    unit_source: str
    expected_ratio_milli: int
    confidence_milli: int
    level: str
    valuation_reservation: int
    observation_count: int
    quote_count: int
    first_tick: int
    last_tick: int
    coverage: str

    def __post_init__(self) -> None:
        _token("owner_token", self.owner_token)
        _token("venue_token", self.venue_token)
        _token("item_kind_token", self.item_kind_token)
        _token("unit_token", self.unit_token)
        _token("unit_source", self.unit_source)
        _token("level", self.level)
        if self.coverage not in {"complete", "partial", "missing"}:
            _fail("price_invalid_identifier")
        for name in (
            "window_index",
            "expected_ratio_milli",
            "confidence_milli",
            "valuation_reservation",
            "observation_count",
            "quote_count",
            "first_tick",
            "last_tick",
        ):
            _count(name, getattr(self, name))
        if self.last_tick < self.first_tick:
            _fail("price_invalid_identifier")


@dataclass(frozen=True, slots=True)
class EmergentPriceOwnerQuoteRow:
    """One neutral exported owner quote row."""

    owner_token: str
    venue_token: str
    window_index: int
    item_kind_token: str
    unit_token: str
    direction: str
    ratio_milli: int
    confidence_milli: int
    source: str
    source_tick: int
    first_tick: int
    last_tick: int
    coverage: str

    def __post_init__(self) -> None:
        for name in (
            "owner_token",
            "venue_token",
            "item_kind_token",
            "unit_token",
            "direction",
            "source",
            "coverage",
        ):
            _token(name, getattr(self, name))
        for name in (
            "window_index",
            "ratio_milli",
            "confidence_milli",
            "source_tick",
            "first_tick",
            "last_tick",
        ):
            _count(name, getattr(self, name))
        if self.last_tick < self.first_tick:
            _fail("price_invalid_identifier")


def _require_ledger(value: object) -> EmergentPriceLedger:
    if type(value) is not EmergentPriceLedger:
        _fail("price_invalid_identifier")
    return value


def price_owner_export(
    ledgers: Iterable[object],
    *,
    allowed_owner_ids: Sequence[AgentId] | None = None,
) -> tuple[EmergentPriceOwnerRow | EmergentPriceOwnerQuoteRow, ...]:
    """Project owner ledgers into neutral analysis input rows."""

    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Iterable):
        _fail("price_invalid_identifier")
    values = tuple(ledgers)
    allowed = None
    if allowed_owner_ids is not None:
        allowed = set()
        for owner in allowed_owner_ids:
            if type(owner) is not AgentId:
                _fail("price_invalid_identifier")
            allowed.add(owner)
    rows: list[EmergentPriceOwnerRow | EmergentPriceOwnerQuoteRow] = []
    for ledger_value in values:
        ledger = _require_ledger(ledger_value)
        if allowed is not None and ledger.owner_id not in allowed:
            _fail("price_invalid_identifier")
        coverage = "complete" if not ledger.notices else "partial"
        for row in ledger.rows:
            units = tuple(
                quote.venue_id
                for quote in row.quotes
                if quote.source_tick == max(
                    (item.source_tick for item in row.quotes), default=-1
                )
            )
            venue_token = "none" if not units else sorted(units)[0]
            window_index = row.last_tick // PRICE_WINDOW_TICKS
            rows.append(
                EmergentPriceOwnerRow(
                    owner_token=ledger.owner_id.value,
                    venue_token=venue_token,
                    window_index=window_index,
                    item_kind_token=row.item_kind.value,
                    unit_token=_NONE_TOKEN
                    if row.unit_kind is None
                    else row.unit_kind.value,
                    unit_source=row.unit_source.value,
                    expected_ratio_milli=row.expected_ratio_milli,
                    confidence_milli=row.confidence_milli,
                    level=row.level.value,
                    valuation_reservation=row.valuation_reservation,
                    observation_count=row.observation_count,
                    quote_count=row.quote_count,
                    first_tick=row.first_tick,
                    last_tick=row.last_tick,
                    coverage=coverage,
                )
            )
            for quote in row.quotes:
                rows.append(
                    EmergentPriceOwnerQuoteRow(
                        owner_token=ledger.owner_id.value,
                        venue_token=quote.venue_id,
                        window_index=quote.source_tick // PRICE_WINDOW_TICKS,
                        item_kind_token=row.item_kind.value,
                        unit_token=_NONE_TOKEN
                        if row.unit_kind is None
                        else row.unit_kind.value,
                        direction=quote.direction.value,
                        ratio_milli=quote.ratio_milli,
                        confidence_milli=quote.confidence_milli,
                        source=quote.source.value,
                        source_tick=quote.source_tick,
                        first_tick=quote.first_tick,
                        last_tick=quote.last_tick,
                        coverage=coverage,
                    )
                )
    rows.sort(key=_row_sort_key)
    _LOG.debug("price_owner_export rows=%s ledgers=%s", len(rows), len(values))
    return tuple(rows)


def _row_sort_key(row: EmergentPriceOwnerRow | EmergentPriceOwnerQuoteRow) -> tuple[
    int, str, int, str, str, str
]:
    if type(row) is EmergentPriceOwnerQuoteRow:
        return (
            1,
            row.owner_token,
            row.window_index,
            row.item_kind_token,
            row.unit_token,
            row.direction,
        )
    assert type(row) is EmergentPriceOwnerRow
    return (
        0,
        row.owner_token,
        row.window_index,
        row.item_kind_token,
        row.unit_token,
        row.unit_source,
    )
