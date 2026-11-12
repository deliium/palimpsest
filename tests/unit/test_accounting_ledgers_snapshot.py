"""Accounting snapshot model tests."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from simulation.accounting_ledgers_models import (
    ACCOUNTING_LEDGERS_MAX_ENTRIES,
    ACCOUNTING_LEDGERS_SNAPSHOT_VERSION,
    AccountingLedgersSnapshot,
    AccountingLedgersSummary,
    AccountingSnapshotEntry,
    empty_accounting_ledgers_snapshot,
)


def _entry(index: int, window: int = 0) -> AccountingSnapshotEntry:
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


def test_empty_snapshot_has_no_wall_clock_field() -> None:
    snapshot = empty_accounting_ledgers_snapshot("run-1")
    assert snapshot.schema_version == ACCOUNTING_LEDGERS_SNAPSHOT_VERSION
    assert not any(
        "time" in name or "clock" in name
        for name in snapshot.__dataclass_fields__
    )


def test_snapshot_caps_and_duplicate_ids_rejected() -> None:
    summary = AccountingLedgersSummary(
        entry_count=2,
        record_count=0,
        condition_count=0,
        flow_count=0,
        counterparty_count=0,
        alignment_count=0,
        window_count=1,
        entry_coverage="complete",
        record_coverage="missing",
        alignment_coverage="missing",
        truncated=False,
    )
    with pytest.raises(ValueError):
        AccountingLedgersSnapshot(
            run_id="run-1",
            schema_version=ACCOUNTING_LEDGERS_SNAPSHOT_VERSION,
            policy_version="accounting-ledgers.v1",
            summary=summary,
            entries=(_entry(1), _entry(1)),
        )
    with pytest.raises(ValueError):
        AccountingLedgersSnapshot(
            run_id="run-1",
            schema_version=ACCOUNTING_LEDGERS_SNAPSHOT_VERSION,
            policy_version="accounting-ledgers.v1",
            summary=summary,
            entries=tuple(_entry(i) for i in range(ACCOUNTING_LEDGERS_MAX_ENTRIES + 1)),
        )


def test_snapshot_accepts_bounded_rows() -> None:
    summary = AccountingLedgersSummary(
        entry_count=2,
        record_count=0,
        condition_count=0,
        flow_count=0,
        counterparty_count=0,
        alignment_count=0,
        window_count=2,
        entry_coverage="complete",
        record_coverage="missing",
        alignment_coverage="missing",
        truncated=False,
    )
    snapshot = AccountingLedgersSnapshot(
        run_id="run-1",
        schema_version=ACCOUNTING_LEDGERS_SNAPSHOT_VERSION,
        policy_version="accounting-ledgers.v1",
        summary=summary,
        entries=(_entry(1), _entry(2, window=1)),
    )
    assert len(snapshot.entries) == 2
