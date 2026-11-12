"""Accounting snapshot composition and publication tests."""

# mypy: ignore-errors

from __future__ import annotations

from pathlib import Path

from analysis.accounting_ledgers_analysis import (
    empty_accounting_ledgers_analysis,
    harvest_accounting_ledgers_analysis,
)
from experiments.accounting_ledgers_publication import (
    build_accounting_ledgers_harvest_result,
    compose_accounting_ledgers_snapshot,
    publish_accounting_ledgers_snapshot,
)
from persistence.accounting_ledgers_filesystem import (
    create_accounting_ledgers_publisher,
)
from tests.unit.test_accounting_ledgers_events import _talked


class FakePublisher:
    def __init__(self) -> None:
        self.snapshots = []

    def publish(self, snapshot):
        self.snapshots.append(snapshot)
        return type(
            "Receipt",
            (),
            {"stored": True, "notices": ()},
        )()


def test_missing_analysis_is_not_published() -> None:
    analysis = empty_accounting_ledgers_analysis("run-1")
    snapshot = compose_accounting_ledgers_snapshot(analysis, run_id="run-1")
    receipt = publish_accounting_ledgers_snapshot(snapshot, FakePublisher())
    assert receipt.reason_code == "publication_missing"
    assert receipt.stored is False


def test_disabled_publisher_writes_nothing() -> None:
    analysis = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=(_talked("ev-a", tick=1),)
    )
    snapshot = compose_accounting_ledgers_snapshot(analysis, run_id="run-1")
    receipt = publish_accounting_ledgers_snapshot(snapshot, None)
    assert receipt.reason_code == "publication_disabled"
    assert receipt.stored is False


def test_complete_analysis_publishes() -> None:
    analysis = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=(_talked("ev-a", tick=1),)
    )
    fake = FakePublisher()
    result = build_accounting_ledgers_harvest_result(analysis, publisher=fake)
    assert result.receipt.reason_code == "published"
    assert result.receipt.stored is True
    assert len(fake.snapshots) == 1
    assert result.snapshot.publication_id.startswith("acct-pub-")


def test_store_quota_and_corruption_map_to_receipts() -> None:
    class QuotaPublisher:
        def publish(self, snapshot):
            raise ValueError("accounting_ledgers_store_quota")

    class CorruptPublisher:
        def publish(self, snapshot):
            raise ValueError("accounting_ledgers_store_corrupt")

    analysis = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=(_talked("ev-a", tick=1),)
    )
    snapshot = compose_accounting_ledgers_snapshot(analysis, run_id="run-1")
    quota = publish_accounting_ledgers_snapshot(snapshot, QuotaPublisher())
    assert quota.reason_code == "store_quota_exceeded"
    corrupt = publish_accounting_ledgers_snapshot(snapshot, CorruptPublisher())
    assert corrupt.reason_code == "store_corrupt"


def test_idempotent_republish_through_the_store(tmp_path: Path) -> None:
    analysis = harvest_accounting_ledgers_analysis(
        run_id="run-1", events=(_talked("ev-a", tick=1),)
    )
    publisher = create_accounting_ledgers_publisher(tmp_path)
    first = build_accounting_ledgers_harvest_result(analysis, publisher=publisher)
    second = build_accounting_ledgers_harvest_result(analysis, publisher=publisher)
    assert first.receipt.stored is True
    assert second.receipt.stored is False
