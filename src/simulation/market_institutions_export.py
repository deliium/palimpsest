"""Token-only owner projection of market institution ledgers for analysis.

The export boundary accepts only owner ledgers and emits sorted rows that carry
no objective event tokens, payload text, item ids, prices, or valuations.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from agents.cognition.market_institutions import (
    MarketInstitutionLedger,
    MarketScheduleBelief,
)
from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MarketOwnerExportRow",
    "market_institution_export_digest",
    "market_institution_export_notices",
    "market_institution_owner_export",
    "market_owner_venue_token",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.market_institutions_export"
)

_EXPECTATION_FAMILY: Final[str] = "expectation"
_ROLE_FAMILY: Final[str] = "role"
_RECORD_FAMILY: Final[str] = "record"
_COVERAGE: Final[str] = "complete"
_HEX_LEN: Final[int] = 16
_VENUE_PREFIX: Final[str] = "mkt-ven-"


def market_owner_venue_token(location_token: str) -> str:
    """Mirror the analysis content address without importing analysis."""

    if type(location_token) is not str or not location_token:
        raise ValueError("market_institutions_invalid_identity")
    digest = hashlib.sha256(f"venue\x1f{location_token}".encode()).hexdigest()
    return f"{_VENUE_PREFIX}{digest[:_HEX_LEN]}"


def _tick(value: object) -> int:
    return require_exact_nonneg_int("tick", value)


@dataclass(frozen=True, slots=True)
class MarketOwnerExportRow:
    """One token-only owner market row for detached analysis."""

    owner_token: str
    venue_token: str
    family: str
    expectation: str | None
    cadence: str | None
    interval_ticks: int | None
    phase_tick: int | None
    schedule_window_index: int | None
    confidence_milli: int | None
    evidence_count: int | None
    role_kind: str | None
    role_basis: str | None
    recognized: bool | None
    actor_token: str | None
    record_kind: str | None
    anchor_token: str | None
    first_tick: int
    last_tick: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_token", require_stable_id("owner_token", self.owner_token)
        )
        if type(self.venue_token) is not str or not self.venue_token:
            raise ValueError("market_institutions_invalid_identity")
        if self.family not in {
            _EXPECTATION_FAMILY,
            _ROLE_FAMILY,
            _RECORD_FAMILY,
        }:
            raise ValueError("market_institutions_invalid_input")
        first = _tick(self.first_tick)
        last = _tick(self.last_tick)
        if last < first:
            raise ValueError("market_institutions_invalid_input")
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


def _best_schedule(
    schedules: Sequence[MarketScheduleBelief],
) -> MarketScheduleBelief | None:
    if not schedules:
        return None
    return max(schedules, key=lambda item: (item.last_tick, item.confidence_milli))


def market_institution_owner_export(
    ledgers: Sequence[object],
    *,
    allowed_owner_ids: Sequence[AgentId] | None = None,
) -> tuple[MarketOwnerExportRow, ...]:
    """Project owner ledgers into sorted token-only rows."""

    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise ValueError("market_institutions_invalid_input")
    allowed = None
    if allowed_owner_ids is not None:
        allowed = {owner.value for owner in allowed_owner_ids}
    rows: list[MarketOwnerExportRow] = []
    seen: set[str] = set()
    for ledger in ledgers:
        if type(ledger) is not MarketInstitutionLedger:
            raise ValueError("market_institutions_invalid_item")
        if ledger.owner_id.value in seen:
            raise ValueError("market_institutions_duplicate_owner")
        if allowed is not None and ledger.owner_id.value not in allowed:
            raise ValueError("market_institutions_foreign_owner")
        seen.add(ledger.owner_id.value)
        owner_token = ledger.owner_id.value
        for venue in sorted(ledger.venues, key=lambda item: item.venue_id):
            venue_token = market_owner_venue_token(venue.location_id.value)
            schedule = _best_schedule(venue.schedules)
            rows.append(
                MarketOwnerExportRow(
                    owner_token=owner_token,
                    venue_token=venue_token,
                    family=_EXPECTATION_FAMILY,
                    expectation=venue.expectation.level.value,
                    cadence=(
                        "unknown" if schedule is None else schedule.cadence.value
                    ),
                    interval_ticks=(
                        None if schedule is None else schedule.interval_ticks
                    ),
                    phase_tick=None if schedule is None else schedule.phase_tick,
                    schedule_window_index=(
                        None if schedule is None else schedule.window_index
                    ),
                    confidence_milli=(
                        0 if schedule is None else schedule.confidence_milli
                    ),
                    evidence_count=venue.expectation.evidence_count,
                    role_kind=None,
                    role_basis=None,
                    recognized=None,
                    actor_token=None,
                    record_kind=None,
                    anchor_token=None,
                    first_tick=venue.first_tick,
                    last_tick=venue.last_tick,
                    coverage=_COVERAGE,
                )
            )
            for role in sorted(
                venue.roles,
                key=lambda item: (item.actor_id.value, item.role_kind.value),
            ):
                rows.append(
                    MarketOwnerExportRow(
                        owner_token=owner_token,
                        venue_token=venue_token,
                        family=_ROLE_FAMILY,
                        expectation=None,
                        cadence=None,
                        interval_ticks=None,
                        phase_tick=None,
                        schedule_window_index=None,
                        confidence_milli=None,
                        evidence_count=None,
                        role_kind=role.role_kind.value,
                        role_basis=role.basis.value,
                        recognized=role.recognized,
                        actor_token=role.actor_id.value,
                        record_kind=None,
                        anchor_token=None,
                        first_tick=role.first_tick,
                        last_tick=role.last_tick,
                        coverage=_COVERAGE,
                    )
                )
            for record in sorted(
                venue.records,
                key=lambda item: (item.record_kind.value, item.anchor),
            ):
                rows.append(
                    MarketOwnerExportRow(
                        owner_token=owner_token,
                        venue_token=venue_token,
                        family=_RECORD_FAMILY,
                        expectation=None,
                        cadence=None,
                        interval_ticks=None,
                        phase_tick=None,
                        schedule_window_index=None,
                        confidence_milli=None,
                        evidence_count=None,
                        role_kind=None,
                        role_basis=None,
                        recognized=None,
                        actor_token=None,
                        record_kind=record.record_kind.value,
                        anchor_token=record.anchor,
                        first_tick=record.first_tick,
                        last_tick=record.last_tick,
                        coverage=_COVERAGE,
                    )
                )
    rows.sort(
        key=lambda row: (
            row.owner_token,
            row.venue_token,
            row.family,
            row.first_tick,
            row.last_tick,
        )
    )
    _LOG.debug(
        "market_institution_owner_export owners=%s rows=%s",
        len(seen),
        len(rows),
    )
    return tuple(rows)


def market_institution_export_notices(
    rows: Sequence[MarketOwnerExportRow],
) -> tuple[str, ...]:
    """Return bounded notices for an owner export."""

    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValueError("market_institutions_invalid_input")
    if any(type(row) is not MarketOwnerExportRow for row in rows):
        raise ValueError("market_institutions_invalid_input")
    return ()


def market_institution_export_digest(
    rows: Sequence[MarketOwnerExportRow],
) -> str:
    """Return a deterministic digest over canonical owner export rows."""

    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValueError("market_institutions_invalid_input")
    material = []
    for row in rows:
        if type(row) is not MarketOwnerExportRow:
            raise ValueError("market_institutions_invalid_input")
        material.append(
            "\x1f".join(
                (
                    row.owner_token,
                    row.venue_token,
                    row.family,
                    row.expectation or "",
                    row.cadence or "",
                    (
                        str(row.confidence_milli)
                        if row.confidence_milli is not None
                        else ""
                    ),
                    row.role_kind or "",
                    row.role_basis or "",
                    row.actor_token or "",
                    row.record_kind or "",
                    row.anchor_token or "",
                    str(row.first_tick),
                    str(row.last_tick),
                )
            )
        )
    return hashlib.sha256("\x1e".join(material).encode("utf-8")).hexdigest()
