"""Frozen detached rows for market-like institution analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.market_institutions_contract import (
    MARKET_FORBIDDEN_KEYS,
    MarketAlignment,
    MarketCoverage,
    MarketGatheringStatus,
    MarketInstitutionsError,
    MarketLineageStatus,
    MarketVenueStatus,
    require_market_candidate_token,
    require_market_venue_token,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MarketCandidateRow",
    "MarketExpectationRow",
    "MarketGatheringRow",
    "MarketLineageRow",
    "MarketOwnerExpectationInput",
    "MarketOwnerRecordInput",
    "MarketOwnerRoleInput",
    "MarketParticipationRow",
    "MarketRecordRow",
    "MarketRoleRow",
    "MarketVenueRow",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.rows"
)


def _forbid_keys(cls: type[object]) -> None:
    if set(getattr(cls, "__dataclass_fields__", {})) & MARKET_FORBIDDEN_KEYS:
        raise MarketInstitutionsError("market_institutions_layer_leak")


def _count(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except (TypeError, ValueError) as exc:
        raise MarketInstitutionsError("market_institutions_invalid_input") from exc


def _token(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise MarketInstitutionsError("market_institutions_invalid_input")
    try:
        return require_stable_id(name, value)
    except (TypeError, ValueError) as exc:
        raise MarketInstitutionsError("market_institutions_invalid_input") from exc


@dataclass(frozen=True, slots=True)
class MarketGatheringRow:
    """Per-window gathering evidence at one logical location."""

    venue_id: str
    window_index: int
    location_token: str
    exchange_count: int
    proposal_count: int
    withdrawn_count: int
    distinct_party_count: int
    distinct_actor_count: int
    status: MarketGatheringStatus
    coverage: MarketCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "venue_id", require_market_venue_token(self.venue_id))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(
            self, "location_token", _token("location_token", self.location_token)
        )
        for name in (
            "exchange_count",
            "proposal_count",
            "withdrawn_count",
            "distinct_party_count",
            "distinct_actor_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if type(self.status) is not MarketGatheringStatus:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")


@dataclass(frozen=True, slots=True)
class MarketVenueRow:
    """One active or dormant venue window with objective persistence status."""

    venue_id: str
    window_index: int
    location_token: str
    exchange_count: int
    proposal_count: int
    withdrawn_count: int
    distinct_party_count: int
    distinct_actor_count: int
    active_window_count: int
    recurrence_milli: int
    status: MarketVenueStatus
    market_like: bool
    coverage: MarketCoverage
    participant_tokens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "venue_id", require_market_venue_token(self.venue_id))
        for name in (
            "window_index",
            "exchange_count",
            "proposal_count",
            "withdrawn_count",
            "distinct_party_count",
            "distinct_actor_count",
            "active_window_count",
            "recurrence_milli",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.recurrence_milli > 1_000:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(
            self, "location_token", _token("location_token", self.location_token)
        )
        if type(self.status) is not MarketVenueStatus:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.market_like) is not bool:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.market_like is not (
            self.status is MarketVenueStatus.MARKET_LIKE_PERSISTENT
        ):
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        participants = tuple(self.participant_tokens)
        for participant in participants:
            _token("participant_token", participant)
        if tuple(sorted(set(participants))) != participants:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(self, "participant_tokens", participants)


@dataclass(frozen=True, slots=True)
class MarketCandidateRow:
    """One contemporaneous market candidate over connected venues."""

    market_token: str
    window_index: int
    venue_ids: tuple[str, ...]
    exchange_count: int
    distinct_party_count: int
    coverage: MarketCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "market_token", require_market_candidate_token(self.market_token)
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        venue_ids = tuple(sorted(set(self.venue_ids)))
        if not venue_ids:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        for venue_id in venue_ids:
            require_market_venue_token(venue_id)
        object.__setattr__(self, "venue_ids", venue_ids)
        object.__setattr__(
            self, "exchange_count", _count("exchange_count", self.exchange_count)
        )
        object.__setattr__(
            self,
            "distinct_party_count",
            _count("distinct_party_count", self.distinct_party_count),
        )
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")


@dataclass(frozen=True, slots=True)
class MarketParticipationRow:
    """Broker-like participation counts for one actor at one venue window."""

    venue_id: str
    window_index: int
    actor_token: str
    exchange_count: int
    counterparty_count: int
    active_window_count: int
    broker_like: bool
    coverage: MarketCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "venue_id", require_market_venue_token(self.venue_id))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(self, "actor_token", _token("actor_token", self.actor_token))
        for name in (
            "exchange_count",
            "counterparty_count",
            "active_window_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if type(self.broker_like) is not bool:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")


@dataclass(frozen=True, slots=True)
class MarketOwnerExpectationInput:
    """Analysis boundary row for one owner expectation and schedule."""

    owner_token: str
    venue_token: str
    expectation: str
    cadence: str
    interval_ticks: int | None
    phase_tick: int | None
    schedule_window_index: int | None
    confidence_milli: int
    evidence_count: int
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token("owner_token", self.owner_token))
        object.__setattr__(
            self, "venue_token", require_market_venue_token(self.venue_token)
        )
        if self.expectation not in {"none", "weak", "expected", "strong"}:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.cadence not in {
            "single_occurrence",
            "recurring_interval",
            "periodic_window",
            "unknown",
        }:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        for name in ("interval_ticks", "phase_tick", "schedule_window_index"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _count(name, value))
        object.__setattr__(
            self, "confidence_milli", _count("confidence_milli", self.confidence_milli)
        )
        if self.confidence_milli > 1_000:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(
            self, "evidence_count", _count("evidence_count", self.evidence_count)
        )
        first = _count("first_tick", self.first_tick)
        last = _count("last_tick", self.last_tick)
        if last < first:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MarketOwnerRoleInput:
    """Analysis boundary row for one owner role claim."""

    owner_token: str
    venue_token: str
    role_kind: str
    role_basis: str
    recognized: bool
    actor_token: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token("owner_token", self.owner_token))
        object.__setattr__(
            self, "venue_token", require_market_venue_token(self.venue_token)
        )
        if self.role_kind not in {"broker", "host", "organizer", "unknown"}:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.role_basis not in {
            "observed_participation",
            "claimed",
            "office",
            "organization",
        }:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.recognized) is not bool:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(
            self, "actor_token", _token("actor_token", self.actor_token)
        )
        first = _count("first_tick", self.first_tick)
        last = _count("last_tick", self.last_tick)
        if last < first:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MarketOwnerRecordInput:
    """Analysis boundary row for one opaque owner record anchor."""

    owner_token: str
    venue_token: str
    record_kind: str
    anchor_token: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token("owner_token", self.owner_token))
        object.__setattr__(
            self, "venue_token", require_market_venue_token(self.venue_token)
        )
        if self.record_kind not in {
            "exchange_record",
            "attendance_record",
            "agreement_record",
            "unknown",
        }:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(
            self, "anchor_token", _token("anchor_token", self.anchor_token)
        )
        first = _count("first_tick", self.first_tick)
        last = _count("last_tick", self.last_tick)
        if last < first:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MarketExpectationRow:
    """Detached owner expectation row joined to an objective venue."""

    venue_id: str
    window_index: int
    owner_token: str
    expectation: str
    cadence: str
    interval_ticks: int | None
    phase_tick: int | None
    schedule_window_index: int | None
    confidence_milli: int
    evidence_count: int
    alignment: MarketAlignment
    coverage: MarketCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "venue_id", require_market_venue_token(self.venue_id))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(self, "owner_token", _token("owner_token", self.owner_token))
        if self.expectation not in {"none", "weak", "expected", "strong"}:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.cadence not in {
            "single_occurrence",
            "recurring_interval",
            "periodic_window",
            "unknown",
        }:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        for name in ("interval_ticks", "phase_tick", "schedule_window_index"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _count(name, value))
        object.__setattr__(
            self, "confidence_milli", _count("confidence_milli", self.confidence_milli)
        )
        if self.confidence_milli > 1_000:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(
            self, "evidence_count", _count("evidence_count", self.evidence_count)
        )
        if type(self.alignment) is not MarketAlignment:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")


@dataclass(frozen=True, slots=True)
class MarketRoleRow:
    """Detached owner role claim joined to an objective venue."""

    venue_id: str
    window_index: int
    actor_token: str
    role_kind: str
    role_basis: str
    recognized: bool
    exchange_count: int
    counterparty_count: int
    active_window_count: int
    coverage: MarketCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "venue_id", require_market_venue_token(self.venue_id))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(self, "actor_token", _token("actor_token", self.actor_token))
        if self.role_kind not in {"broker", "host", "organizer", "unknown"}:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.role_basis not in {
            "observed_participation",
            "claimed",
            "office",
            "organization",
        }:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.recognized) is not bool:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.recognized and self.role_basis not in {"office", "organization"}:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        for name in ("exchange_count", "counterparty_count", "active_window_count"):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")


@dataclass(frozen=True, slots=True)
class MarketRecordRow:
    """Detached opaque record-anchor reference joined to an objective venue."""

    venue_id: str
    window_index: int
    record_kind: str
    anchor_token: str
    owner_row_count: int
    coverage: MarketCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "venue_id", require_market_venue_token(self.venue_id))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        if self.record_kind not in {
            "exchange_record",
            "attendance_record",
            "agreement_record",
            "unknown",
        }:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        object.__setattr__(
            self, "anchor_token", _token("anchor_token", self.anchor_token)
        )
        object.__setattr__(
            self, "owner_row_count", _count("owner_row_count", self.owner_row_count)
        )
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")


@dataclass(frozen=True, slots=True)
class MarketLineageRow:
    """Forward-only market lineage relation across consecutive windows."""

    window_index: int
    market_token: str
    venue_ids: tuple[str, ...]
    party_count: int
    status: MarketLineageStatus
    previous_market_tokens: tuple[str, ...]
    next_market_tokens: tuple[str, ...]
    rerouted: bool
    sustained: bool
    coverage: MarketCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(
            self, "market_token", require_market_candidate_token(self.market_token)
        )
        venue_ids = tuple(sorted(set(self.venue_ids)))
        if not venue_ids:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        for venue_id in venue_ids:
            require_market_venue_token(venue_id)
        object.__setattr__(self, "venue_ids", venue_ids)
        object.__setattr__(
            self, "party_count", _count("party_count", self.party_count)
        )
        if type(self.status) is not MarketLineageStatus:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        for name in ("previous_market_tokens", "next_market_tokens"):
            tokens = tuple(sorted(set(getattr(self, name))))
            for token in tokens:
                require_market_candidate_token(token)
            object.__setattr__(self, name, tokens)
        if type(self.rerouted) is not bool or type(self.sustained) is not bool:
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.rerouted is not (
            self.status is MarketLineageStatus.TRANSFORMED
        ):
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if self.sustained is not (
            self.status
            in {MarketLineageStatus.CONTINUED, MarketLineageStatus.TRANSFORMED}
        ):
            raise MarketInstitutionsError("market_institutions_invalid_input")
        if type(self.coverage) is not MarketCoverage:
            raise MarketInstitutionsError("market_institutions_invalid_input")
