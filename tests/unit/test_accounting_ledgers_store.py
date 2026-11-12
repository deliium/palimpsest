"""Atomic accounting snapshot store tests."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

import pytest

from persistence.accounting_ledgers_filesystem import (
    ACCOUNTING_LEDGERS_STORE_VERSION,
    AccountingLedgersPublisherOptions,
    create_accounting_ledgers_publisher,
    create_accounting_ledgers_reader,
)
from simulation.accounting_ledgers_codec import (
    finalize_accounting_ledgers_snapshot,
)
from simulation.accounting_ledgers_models import (
    AccountingLedgersSnapshot,
    AccountingLedgersSummary,
    AccountingSnapshotEntry,
    empty_accounting_ledgers_snapshot,
)


def _snapshot(run_id: str = "run-1") -> AccountingLedgersSnapshot:
    return finalize_accounting_ledgers_snapshot(
        empty_accounting_ledgers_snapshot(run_id)
    )


def _variant(run_id: str) -> AccountingLedgersSnapshot:
    entry = AccountingSnapshotEntry(
        entry_token="acce-0000000000000001",
        record_token="accrec-0000000000000001",
        entry_kind="exchange",
        direction="inflow",
        item_kind="food",
        quantity=1,
        assessment="consistent",
        confidence_milli=500,
        first_tick=0,
        last_tick=0,
        window_index=0,
    )
    return finalize_accounting_ledgers_snapshot(
        AccountingLedgersSnapshot(
            run_id=run_id,
            schema_version="accounting-ledgers-snapshot-v1",
            policy_version="accounting-ledgers.v1",
            summary=AccountingLedgersSummary(
                entry_count=1,
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
            ),
            entries=(entry,),
        )
    )


def test_publish_read_and_idempotent_republish(tmp_path: Path) -> None:
    publisher = create_accounting_ledgers_publisher(tmp_path)
    reader = create_accounting_ledgers_reader(tmp_path)
    snapshot = _snapshot()
    first = publisher.publish(snapshot)
    assert first.stored is True
    second = publisher.publish(snapshot)
    assert second.stored is False
    assert reader.read_snapshot("run-1") == snapshot
    assert ACCOUNTING_LEDGERS_STORE_VERSION == "accounting-ledgers-store-v1"


def test_conflicting_bytes_and_quota(tmp_path: Path) -> None:
    publisher = create_accounting_ledgers_publisher(
        tmp_path, options=AccountingLedgersPublisherOptions(max_publications=1)
    )
    first = _snapshot("run-1")
    publisher.publish(first)
    same_id_different = first
    assert publisher.publish(same_id_different).stored is False
    second = _variant("run-1")
    with pytest.raises(ValueError) as quota:
        publisher.publish(second)
    assert "quota" in str(quota.value)


def test_corrupt_state_and_interrupted_temp_file(tmp_path: Path) -> None:
    publisher = create_accounting_ledgers_publisher(tmp_path)
    publisher.publish(_snapshot())
    state = tmp_path / "run-1" / "state.json"
    state.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError) as corrupt:
        create_accounting_ledgers_reader(tmp_path).read_snapshot("run-1")
    assert "corrupt" in str(corrupt.value)
    state.write_text(
        '{"store_version":"accounting-ledgers-store-v1","publications":{}}',
        encoding="utf-8",
    )
    (tmp_path / "run-1" / ".tmp-leftover").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        create_accounting_ledgers_reader(tmp_path).read_snapshot("run-1")
