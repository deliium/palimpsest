"""Committed-event reconstruction of bounded exchange-gathering evidence.

This module is the only market-analysis module that knows world event shapes. It
never reads ``WorldState``, cognition ledgers, or observers, and it retains no
item ids, item kinds, bundles, prices, or valuations.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.market_institutions_contract import (
    MarketAttemptKind,
    MarketCoverage,
    MarketInstitutionsError,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
    default_market_institutions_analysis_policy,
    window_index_for_tick,
)
from world.events import (
    ExchangeCompleted,
    ExchangeProposed,
    ExchangeWithdrawn,
    WorldEvent,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MarketAttemptRow",
    "MarketEvidenceHarvest",
    "MarketExchangeRow",
    "market_evidence_digest",
    "market_evidence_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.events"
)


def _require_token(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise MarketInstitutionsError("market_institutions_invalid_input")
    return require_stable_id(name, value)


@dataclass(frozen=True, slots=True)
class MarketExchangeRow:
    """One completed exchange attributed to its authoritative origin location."""

    tick: int
    window_index: int
    location_token: str
    event_token: str
    actor_token: str
    counterparty_token: str
    party_tokens: tuple[str, str]
    source_kind: str = "exchange"

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self,
            "window_index",
            require_exact_nonneg_int("window_index", self.window_index),
        )
        location = _require_token("location_token", self.location_token)
        event = _require_token("event_token", self.event_token)
        actor = _require_token("actor_token", self.actor_token)
        counterparty = _require_token("counterparty_token", self.counterparty_token)
        if actor == counterparty:
            raise MarketInstitutionsError("market_institutions_invalid_exchange")
        object.__setattr__(self, "location_token", location)
        object.__setattr__(self, "event_token", event)
        object.__setattr__(self, "actor_token", actor)
        object.__setattr__(self, "counterparty_token", counterparty)
        expected = tuple(sorted((actor, counterparty)))
        if tuple(self.party_tokens) != expected:
            raise MarketInstitutionsError("market_institutions_invalid_exchange")
        if self.source_kind != "exchange":
            raise MarketInstitutionsError("market_institutions_invalid_input")


@dataclass(frozen=True, slots=True)
class MarketAttemptRow:
    """One exchange offer, counteroffer, or withdrawal attempt."""

    tick: int
    window_index: int
    location_token: str
    event_token: str
    actor_token: str
    counterparty_token: str
    attempt_kind: MarketAttemptKind

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))
        object.__setattr__(
            self,
            "window_index",
            require_exact_nonneg_int("window_index", self.window_index),
        )
        object.__setattr__(
            self,
            "location_token",
            _require_token("location_token", self.location_token),
        )
        object.__setattr__(
            self, "event_token", _require_token("event_token", self.event_token)
        )
        object.__setattr__(
            self, "actor_token", _require_token("actor_token", self.actor_token)
        )
        object.__setattr__(
            self,
            "counterparty_token",
            _require_token("counterparty_token", self.counterparty_token),
        )
        if type(self.attempt_kind) is not MarketAttemptKind:
            raise MarketInstitutionsError("market_institutions_invalid_input")


@dataclass(frozen=True, slots=True)
class MarketEvidenceHarvest:
    """Bounded, token-only exchange evidence with explicit coverage."""

    exchanges: tuple[MarketExchangeRow, ...]
    attempts: tuple[MarketAttemptRow, ...]
    coverage: MarketCoverage
    notices: tuple[str, ...]
    exchange_count: int
    attempt_count: int

    def __post_init__(self) -> None:
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        for row in self.exchanges:
            if type(row) is not MarketExchangeRow:
                raise MarketInstitutionsError("market_institutions_invalid_input")
        for attempt in self.attempts:
            if type(attempt) is not MarketAttemptRow:
                raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.exchange_count != len(self.exchanges):
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.attempt_count != len(self.attempts):
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))


def _event_token(event: WorldEvent) -> str:
    return event.event_id.value


def _origin_token(event: WorldEvent) -> str | None:
    occurrence = event.occurrence
    if occurrence is None or occurrence.origin_location_id is None:
        return None
    value = occurrence.origin_location_id.value
    return value if value else None


def market_evidence_rows_from_events(
    events: Sequence[object],
    *,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
) -> MarketEvidenceHarvest:
    """Reconstruct bounded exchange rows from committed events only."""

    active = (
        default_market_institutions_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not MarketInstitutionsAnalysisPolicy:
        raise MarketInstitutionsError("market_institutions_invalid_policy")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise MarketInstitutionsError("market_institutions_invalid_input")

    ordered = sorted(
        cast(Sequence[WorldEvent], events), key=lambda item: (item.tick, item.sequence)
    )
    seen: set[str] = set()
    for event in ordered:
        token = _event_token(event)
        if token in seen:
            raise MarketInstitutionsError("market_institutions_duplicate_event")
        seen.add(token)

    notices: set[str] = set()
    exchanges: list[MarketExchangeRow] = []
    attempts: list[MarketAttemptRow] = []
    ignored = 0
    missing_attempt_locations = 0

    for event in ordered:
        details = event.details
        if isinstance(details, ExchangeCompleted):
            if details.act != "accept" or details.actor_id == details.counterparty_id:
                raise MarketInstitutionsError(
                    "market_institutions_invalid_exchange"
                )
            location = _origin_token(event)
            if location is None:
                raise MarketInstitutionsError(
                    "market_institutions_unknown_location"
                )
            actor = details.actor_id.value
            counterparty = details.counterparty_id.value
            exchanges.append(
                MarketExchangeRow(
                    tick=event.tick,
                    window_index=window_index_for_tick(event.tick, active),
                    location_token=location,
                    event_token=_event_token(event),
                    actor_token=actor,
                    counterparty_token=counterparty,
                    party_tokens=cast(
                        tuple[str, str], tuple(sorted((actor, counterparty)))
                    ),
                )
            )
        elif isinstance(details, (ExchangeProposed, ExchangeWithdrawn)):
            location = _origin_token(event)
            if location is None:
                missing_attempt_locations += 1
                notices.add("market_institutions_attempt_location_unresolved")
                continue
            if details.actor_id == details.counterparty_id:
                raise MarketInstitutionsError(
                    "market_institutions_invalid_exchange"
                )
            if isinstance(details, ExchangeWithdrawn):
                kind = MarketAttemptKind.WITHDRAW
            else:
                kind = MarketAttemptKind(details.act)
            attempts.append(
                MarketAttemptRow(
                    tick=event.tick,
                    window_index=window_index_for_tick(event.tick, active),
                    location_token=location,
                    event_token=_event_token(event),
                    actor_token=details.actor_id.value,
                    counterparty_token=details.counterparty_id.value,
                    attempt_kind=kind,
                )
            )
        else:
            ignored += 1

    exchanges.sort(
        key=lambda row: (
            row.tick,
            row.event_token,
            row.actor_token,
            row.counterparty_token,
        )
    )
    attempts.sort(
        key=lambda row: (
            row.tick,
            row.event_token,
            row.actor_token,
            row.attempt_kind.value,
        )
    )

    if len(exchanges) > active.max_exchange_events:
        exchanges = exchanges[: active.max_exchange_events]
        notices.add("market_institutions_exchange_truncated")
        _LOG.warning(
            "market_events_truncated exchanges=%s cap=%s",
            len(exchanges),
            active.max_exchange_events,
        )
    if len(attempts) > active.max_attempt_rows:
        attempts = attempts[: active.max_attempt_rows]
        notices.add("market_institutions_attempt_truncated")
        _LOG.warning(
            "market_events_truncated attempts=%s cap=%s",
            len(attempts),
            active.max_attempt_rows,
        )
    if missing_attempt_locations:
        _LOG.warning(
            "market_events_location_missing attempts=%s",
            missing_attempt_locations,
        )
    if ignored:
        _LOG.debug("market_events_ignored_kind=%s", ignored)

    if not exchanges and not attempts:
        coverage = MarketCoverage.MISSING
    elif notices:
        coverage = MarketCoverage.PARTIAL
    else:
        coverage = MarketCoverage.COMPLETE

    _LOG.debug(
        "market_events_parsed exchanges=%s attempts=%s notices=%s",
        len(exchanges),
        len(attempts),
        len(notices),
    )
    return MarketEvidenceHarvest(
        exchanges=tuple(exchanges),
        attempts=tuple(attempts),
        coverage=coverage,
        notices=tuple(sorted(notices)),
        exchange_count=len(exchanges),
        attempt_count=len(attempts),
    )


def market_evidence_digest(harvest: MarketEvidenceHarvest) -> str:
    """Return a deterministic digest over canonical evidence rows."""

    if type(harvest) is not MarketEvidenceHarvest:
        raise MarketInstitutionsError("market_institutions_invalid_input")
    material = [
        "\x1f".join(
            (
                "exchange",
                str(row.tick),
                str(row.window_index),
                row.location_token,
                row.event_token,
                row.actor_token,
                row.counterparty_token,
            )
        )
        for row in harvest.exchanges
    ]
    material.extend(
        "\x1f".join(
            (
                "attempt",
                str(row.tick),
                str(row.window_index),
                row.location_token,
                row.event_token,
                row.actor_token,
                row.counterparty_token,
                row.attempt_kind.value,
            )
        )
        for row in harvest.attempts
    )
    return hashlib.sha256("\x1e".join(material).encode("utf-8")).hexdigest()
