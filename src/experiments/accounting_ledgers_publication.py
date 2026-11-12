"""Programmatic post-completion publication for accounting snapshots."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.accounting_ledgers_analysis import AccountingLedgersAnalysis
from analysis.accounting_ledgers_contract import AccountingCoverage
from simulation.accounting_ledgers_codec import (
    finalize_accounting_ledgers_snapshot,
)
from simulation.accounting_ledgers_models import (
    ACCOUNTING_LEDGERS_MAX_WINDOWS,
    AccountingLedgersSnapshot,
    AccountingLedgersSummary,
    AccountingSnapshotAlignment,
    AccountingSnapshotCondition,
    AccountingSnapshotCounterparty,
    AccountingSnapshotEntry,
    AccountingSnapshotFlow,
    AccountingSnapshotRecord,
)
from simulation.accounting_ledgers_ports import AccountingLedgersPublisher

__all__ = [
    "AccountingLedgersHarvest",
    "AccountingLedgersReceipt",
    "build_accounting_ledgers_harvest_result",
    "compose_accounting_ledgers_snapshot",
    "publish_accounting_ledgers_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.accounting_ledgers_publication"
)

_REASON_CODES: Final[frozenset[str]] = frozenset(
    {
        "published",
        "publication_disabled",
        "publication_missing",
        "store_quota_exceeded",
        "store_corrupt",
    }
)


@dataclass(frozen=True, slots=True)
class AccountingLedgersReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason_code not in _REASON_CODES:
            raise ValueError("accounting_ledgers_receipt_invalid")
        if type(self.stored) is not bool:
            raise ValueError("accounting_ledgers_receipt_invalid")


@dataclass(frozen=True, slots=True)
class AccountingLedgersHarvest:
    run_id: str
    analysis: AccountingLedgersAnalysis
    snapshot: AccountingLedgersSnapshot
    receipt: AccountingLedgersReceipt


def _window(rows: Sequence[object]) -> int:
    return min(
        ACCOUNTING_LEDGERS_MAX_WINDOWS - 1,
        len(
            {
                getattr(row, "window_index", 0)
                for row in rows
            }
        ),
    )


def compose_accounting_ledgers_snapshot(
    analysis: AccountingLedgersAnalysis, *, run_id: str
) -> AccountingLedgersSnapshot:
    """Map one analysis harvest into the canonical sibling snapshot."""

    if type(analysis) is not AccountingLedgersAnalysis:
        raise TypeError("analysis must be AccountingLedgersAnalysis")
    if analysis.run_id != run_id:
        raise ValueError("accounting_ledgers_run_mismatch")
    entries = tuple(
        AccountingSnapshotEntry(
            entry_token=row.entry_token,
            record_token=row.record_token,
            entry_kind=row.entry_kind.value,
            direction=row.direction.value,
            item_kind=row.item_kind,
            quantity=row.quantity,
            assessment=row.assessment.value,
            confidence_milli=row.confidence_milli,
            first_tick=row.first_tick,
            last_tick=row.last_tick,
            window_index=row.window_index,
        )
        for row in analysis.entries
    )
    records = tuple(
        AccountingSnapshotRecord(
            record_token=row.record_token,
            record_genre=row.record_genre,
            observed_integrity=row.observed_integrity.value,
            content_revision=row.content_revision,
            author_token=row.author_token,
            tick=row.tick,
            event_ordinal=row.event_ordinal,
            copy_generation=row.copy_generation,
            tombstoned=row.tombstoned,
            window_index=row.tick // 32,
        )
        for row in analysis.records
    )
    conditions = tuple(
        AccountingSnapshotCondition(
            condition=row.condition,
            record_count=row.record_count,
            share_milli=row.share_milli,
            window_index=row.window_index,
            availability=row.availability,
        )
        for row in analysis.conditions
    )
    flows = tuple(
        AccountingSnapshotFlow(
            flow_token=row.entry_kind.value + "-" + row.direction.value,
            entry_kind=row.entry_kind.value,
            direction=row.direction.value,
            event_count=row.event_count,
            quantity_sum=row.quantity_sum,
            owner_count=row.owner_count,
            counterparty_count=row.counterparty_count,
            window_index=row.window_index,
        )
        for row in analysis.flows
    )
    counterparties = tuple(
        AccountingSnapshotCounterparty(
            counterparty_token=row.counterparty_token,
            entry_count=row.entry_count,
            kinds=row.kinds,
            first_tick=row.first_tick,
            last_tick=row.last_tick,
            window_index=row.first_tick // 32,
        )
        for row in analysis.counterparties
    )
    alignments = tuple(
        AccountingSnapshotAlignment(
            alignment_token=row.entry_token,
            entry_token=row.entry_token,
            alignment=row.alignment.value,
            gap_milli=row.gap_milli,
            record_token=row.record_token,
            window_index=0,
        )
        for row in analysis.alignments
    )
    summary = AccountingLedgersSummary(
        entry_count=len(entries),
        record_count=len(records),
        condition_count=len(conditions),
        flow_count=len(flows),
        counterparty_count=len(counterparties),
        alignment_count=len(alignments),
        window_count=_window((*entries, *records, *conditions, *flows)),
        entry_coverage=analysis.coverage["entries"].value,
        record_coverage=analysis.coverage["records"].value,
        alignment_coverage=analysis.coverage["alignments"].value,
        condition_coverage=analysis.coverage["conditions"].value,
        flow_coverage=analysis.coverage["flows"].value,
        counterparty_coverage=analysis.coverage["counterparties"].value,
        truncated=analysis.truncated,
    )
    return finalize_accounting_ledgers_snapshot(
        AccountingLedgersSnapshot(
            run_id=run_id,
            schema_version="accounting-ledgers-snapshot-v1",
            policy_version="accounting-ledgers.v1",
            summary=summary,
            entries=entries,
            records=records,
            conditions=conditions,
            flows=flows,
            counterparties=counterparties,
            alignments=alignments,
        )
    )


def publish_accounting_ledgers_snapshot(
    snapshot: AccountingLedgersSnapshot,
    publisher: AccountingLedgersPublisher | None,
) -> AccountingLedgersReceipt:
    """Publish programmatically; map disabled/missing/quota/corruption."""

    if type(snapshot) is not AccountingLedgersSnapshot:
        raise TypeError("snapshot must be AccountingLedgersSnapshot")
    if snapshot.summary.entry_coverage == AccountingCoverage.MISSING.value:
        return AccountingLedgersReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_missing",
            coverage="missing",
        )
    if publisher is None:
        return AccountingLedgersReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_disabled",
            coverage=snapshot.summary.entry_coverage,
        )
    try:
        receipt = publisher.publish(snapshot)
    except ValueError as error:
        message = str(error)
        code = (
            "store_quota_exceeded" if "quota" in message else "store_corrupt"
        )
        _LOG.warning("accounting_ledgers_published stored=%s reason=%s", False, code)
        return AccountingLedgersReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code=code,
            coverage=snapshot.summary.entry_coverage,
        )
    stored = bool(getattr(receipt, "stored", True))
    _LOG.info(
        "accounting_ledgers_published stored=%s reason=%s", stored, "published"
    )
    return AccountingLedgersReceipt(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        stored=stored,
        reason_code="published",
        coverage=snapshot.summary.entry_coverage,
        notices=tuple(getattr(receipt, "notices", ())),
    )


def build_accounting_ledgers_harvest_result(
    analysis: AccountingLedgersAnalysis,
    *,
    publisher: AccountingLedgersPublisher | None,
) -> AccountingLedgersHarvest:
    """Compose and publish one completed-run harvest programmatically."""

    snapshot = compose_accounting_ledgers_snapshot(
        analysis, run_id=analysis.run_id
    )
    receipt = publish_accounting_ledgers_snapshot(snapshot, publisher)
    return AccountingLedgersHarvest(
        run_id=analysis.run_id,
        analysis=analysis,
        snapshot=snapshot,
        receipt=receipt,
    )
