"""Token-only owner export for detached accounting analysis."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final

from agents.cognition.accounting_ledgers import AccountingLedger
from agents.models import AgentId

__all__ = [
    "AccountingOwnerRow",
    "accounting_owner_export",
]

_HEX: Final[int] = 16


def _token(prefix: str, material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:_HEX]
    return f"{prefix}{digest}"


@dataclass(frozen=True, slots=True)
class AccountingOwnerRow:
    owner_token: str
    entry_token: str
    record_token: str
    entry_kind: str
    direction: str
    item_kind: str
    quantity: int
    assessment: str
    confidence_milli: int
    first_tick: int
    last_tick: int
    window_index: int

    def __post_init__(self) -> None:
        for name in (
            "owner_token",
            "entry_token",
            "record_token",
            "entry_kind",
            "direction",
            "item_kind",
            "assessment",
        ):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise ValueError("accounting_owner_export_invalid")
        for name in (
            "quantity",
            "confidence_milli",
            "first_tick",
            "last_tick",
            "window_index",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise ValueError("accounting_owner_export_invalid")
        if self.last_tick < self.first_tick:
            raise ValueError("accounting_owner_export_invalid")


def accounting_owner_export(
    ledgers: tuple[AccountingLedger, ...],
) -> tuple[AccountingOwnerRow, ...]:
    """Project owner ledgers to token-only rows without analysis imports."""

    rows: list[AccountingOwnerRow] = []
    for ledger in ledgers:
        if type(ledger) is not AccountingLedger:
            raise TypeError("ledgers entries must be AccountingLedger")
        owner = ledger.owner_id
        if type(owner) is not AgentId:
            raise TypeError("ledger owner must be AgentId")
        owner_token = _token("acco-", owner.value)
        for entry in ledger.entries:
            record_token = entry.record_token or _token(
                "accrec-", entry.entry_id
            )
            rows.append(
                AccountingOwnerRow(
                    owner_token=owner_token,
                    entry_token=entry.entry_id,
                    record_token=record_token,
                    entry_kind=entry.terms.entry_kind.value,
                    direction=entry.terms.direction.value,
                    item_kind=entry.terms.item_kind,
                    quantity=entry.terms.quantity,
                    assessment=entry.assessment.value,
                    confidence_milli=entry.confidence_milli,
                    first_tick=entry.first_tick,
                    last_tick=entry.last_tick,
                    window_index=entry.last_tick // 32,
                )
            )
    rows.sort(key=lambda row: (row.owner_token, row.window_index, row.entry_token))
    return tuple(rows)
