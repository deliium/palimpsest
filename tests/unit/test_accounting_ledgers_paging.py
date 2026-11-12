"""Accounting snapshot paging tests."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from simulation.accounting_ledgers_models import AccountingSnapshotEntry
from simulation.accounting_ledgers_paging import (
    ACCOUNTING_LEDGERS_PAGE_DEFAULT,
    ACCOUNTING_LEDGERS_PAGE_MAX,
    page_accounting_ledgers,
)


def _entry(index: int, window: int) -> AccountingSnapshotEntry:
    return AccountingSnapshotEntry(
        entry_token=f"acce-{index:016x}",
        record_token=f"accrec-{index:016x}",
        entry_kind="exchange",
        direction="inflow",
        item_kind="food",
        quantity=1,
        assessment="consistent",
        confidence_milli=500,
        first_tick=window * 32,
        last_tick=window * 32,
        window_index=window,
    )


def test_page_filters_sorts_and_returns_next_key() -> None:
    rows = (_entry(3, 1), _entry(1, 0), _entry(2, 0))
    page, next_key = page_accounting_ledgers(rows, purpose="entries", limit=2)
    assert [row.entry_token for row in page] == [
        "acce-0000000000000001",
        "acce-0000000000000002",
    ]
    assert next_key == "000:acce-0000000000000002"
    rest, next_key = page_accounting_ledgers(
        rows, purpose="entries", limit=2, after_key=next_key
    )
    assert [row.entry_token for row in rest] == ["acce-0000000000000003"]
    assert next_key == ""


def test_window_filter_and_boundaries() -> None:
    rows = (_entry(1, 0), _entry(2, 1))
    page, _ = page_accounting_ledgers(
        rows, purpose="entries", window_index=1
    )
    assert len(page) == 1
    assert page[0].window_index == 1
    page, _ = page_accounting_ledgers(rows, purpose="entries", window_index=511)
    assert page == ()
    assert ACCOUNTING_LEDGERS_PAGE_DEFAULT == 100
    assert ACCOUNTING_LEDGERS_PAGE_MAX == 500
    with pytest.raises(ValueError):
        page_accounting_ledgers(rows, purpose="entries", limit=501)
    with pytest.raises(ValueError):
        page_accounting_ledgers(rows, purpose="entries", window_index=512)
    with pytest.raises(ValueError):
        page_accounting_ledgers(rows, purpose="unknown")
