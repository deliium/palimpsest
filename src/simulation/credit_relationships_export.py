"""Token-only owner export rows for detached credit analysis.

The export reads completed owner ledgers and emits neutral strings and integers.
It never includes counterparty ids, item ids, raw claims, or digest content, and
it never imports ``analysis``.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, NoReturn

from agents.cognition.credit_relationships import (
    CreditRelationshipError,
    CreditRelationshipLedger,
)

__all__ = [
    "CreditOwnerRow",
    "credit_owner_export",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.credit_relationships_export"
)

_CREDIT_EXPORT_WINDOW_TICKS: Final[int] = 32


def _fail(code: str) -> NoReturn:
    _LOG.error("credit_relationships_export_invalid reason_code=%s", code)
    raise CreditRelationshipError(code)


def _token(name: str, value: object) -> str:
    if type(value) is not str or not value:
        _fail("credit_invalid_identifier")
    return value


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail("credit_invalid_identifier")
    return value


def _peer_token(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"credpeer-{digest[:16]}"


@dataclass(frozen=True, slots=True)
class CreditOwnerRow:
    """One neutral exported owner credit row."""

    owner_token: str
    window_index: int
    anchor_token: str
    counterparty_token: str
    direction: str
    principal_kind_token: str
    principal_quantity: int
    repayment_kind_token: str
    repayment_quantity: int
    paid_quantity: int
    due_tick: int | None
    condition: str
    collateral_kind: str
    collateral_quantity: int
    status: str
    confidence_milli: int
    level: str
    trust_milli: int
    expectation_milli: int
    claim_count: int
    promise_count: int
    renegotiate_count: int
    first_tick: int
    last_tick: int
    coverage: str

    def __post_init__(self) -> None:
        for name in (
            "owner_token",
            "anchor_token",
            "counterparty_token",
            "direction",
            "principal_kind_token",
            "repayment_kind_token",
            "condition",
            "collateral_kind",
            "status",
            "level",
            "coverage",
        ):
            _token(name, getattr(self, name))
        if not self.counterparty_token.startswith("credpeer-"):
            _fail("credit_invalid_identifier")
        for name in (
            "window_index",
            "principal_quantity",
            "repayment_quantity",
            "paid_quantity",
            "collateral_quantity",
            "confidence_milli",
            "trust_milli",
            "expectation_milli",
            "claim_count",
            "promise_count",
            "renegotiate_count",
            "first_tick",
            "last_tick",
        ):
            _count(name, getattr(self, name))
        if self.due_tick is not None:
            _count("due_tick", self.due_tick)
        if self.last_tick < self.first_tick:
            _fail("credit_invalid_identifier")
        if self.paid_quantity > self.repayment_quantity:
            _fail("credit_invalid_identifier")


def credit_owner_export(ledgers: Iterable[object]) -> tuple[CreditOwnerRow, ...]:
    """Project owner credit ledgers into neutral analysis input rows."""

    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Iterable):
        _fail("credit_invalid_identifier")
    values = tuple(ledgers)
    rows: list[CreditOwnerRow] = []
    for ledger in values:
        if type(ledger) is not CreditRelationshipLedger:
            _fail("credit_invalid_identifier")
        coverage = "partial" if ledger.notices else "complete"
        for row in ledger.rows:
            window_index = row.last_tick // _CREDIT_EXPORT_WINDOW_TICKS
            rows.append(
                CreditOwnerRow(
                    owner_token=ledger.owner_id.value,
                    window_index=window_index,
                    anchor_token=row.anchor,
                    counterparty_token=_peer_token(row.counterparty_id.value),
                    direction=row.direction.value,
                    principal_kind_token=row.terms.principal_kind.value,
                    principal_quantity=row.terms.principal_quantity,
                    repayment_kind_token=row.terms.repayment_kind.value,
                    repayment_quantity=row.terms.repayment_quantity,
                    paid_quantity=row.paid_quantity,
                    due_tick=row.terms.due_tick,
                    condition=row.terms.condition.value,
                    collateral_kind=row.terms.collateral_kind.value,
                    collateral_quantity=row.terms.collateral_quantity,
                    status=row.status.value,
                    confidence_milli=row.confidence_milli,
                    level=row.level.value,
                    trust_milli=row.trust_milli,
                    expectation_milli=row.expectation_milli,
                    claim_count=len(row.claims),
                    promise_count=row.promise_count,
                    renegotiate_count=sum(
                        1
                        for revision in row.revisions
                        if revision.reason == "renegotiated"
                    ),
                    first_tick=row.first_tick,
                    last_tick=row.last_tick,
                    coverage=coverage,
                )
            )
    rows.sort(key=lambda row: (row.owner_token, row.window_index, row.anchor_token))
    _LOG.debug("credit_owner_export rows=%s owners=%s", len(rows), len(values))
    return tuple(rows)
