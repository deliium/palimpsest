"""Purpose-bound cursors and read/publication ports for accounting snapshots."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final, Protocol

__all__ = [
    "ACCOUNTING_LEDGERS_CURSOR_TOKEN",
    "AccountingLedgersCursor",
    "AccountingLedgersPublisher",
    "AccountingLedgersReader",
    "accounting_ledgers_query_fingerprint",
]

ACCOUNTING_LEDGERS_CURSOR_TOKEN: Final[str] = (
    "palimpsest.accounting_ledgers.cursor.v1"
)
ACCOUNTING_LEDGERS_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "entries",
    "records",
    "conditions",
    "flows",
    "counterparties",
    "alignment",
)


@dataclass(frozen=True, slots=True)
class AccountingLedgersCursor:
    purpose: str
    fingerprint: str
    after_key: str
    window_index: int | None

    def __post_init__(self) -> None:
        if self.purpose not in ACCOUNTING_LEDGERS_PURPOSES:
            raise ValueError("accounting_ledgers_cursor_invalid")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("accounting_ledgers_cursor_invalid")
        if type(self.after_key) is not str:
            raise ValueError("accounting_ledgers_cursor_invalid")
        if self.window_index is not None and (
            isinstance(self.window_index, bool)
            or type(self.window_index) is not int
            or not 0 <= self.window_index <= 511
        ):
            raise ValueError("accounting_ledgers_cursor_invalid")


def accounting_ledgers_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    limit: int,
    window_index: int | None,
) -> str:
    """Bind the cursor to the exact query and window filter."""

    material = "\x1f".join(
        (
            run_id,
            publication_id,
            digest,
            purpose,
            str(limit),
            "-" if window_index is None else str(window_index),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AccountingLedgersReader(Protocol):
    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> object: ...


class AccountingLedgersPublisher(Protocol):
    def publish(self, snapshot: object) -> object: ...
