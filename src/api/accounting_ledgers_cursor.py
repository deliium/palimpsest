"""Purpose-bound cursor codec alias for accounting ledger reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "ACCOUNTING_LEDGERS_CURSOR_TTL_SECONDS",
    "AccountingLedgersCursorCodec",
    "AccountingLedgersCursorError",
]

AccountingLedgersCursorCodec = DiplomacyCursorCodec
AccountingLedgersCursorError = DiplomacyCursorError
ACCOUNTING_LEDGERS_CURSOR_TTL_SECONDS: Final[int] = 900
