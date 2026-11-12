"""Property bounds for accounting detection."""

# mypy: ignore-errors

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.accounting_ledgers_contract import (
    AccountingCoverage,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
)
from analysis.accounting_ledgers_detection import (
    accounting_distribution_summary,
    detect_accounting_entries,
    detect_record_conditions,
)
from analysis.accounting_ledgers_rows import (
    AccountingClaimEvidenceRow,
    AccountingEvidenceHarvest,
)


def _claim(
    index: int, kind: str, direction: str, quantity: int
) -> AccountingClaimEvidenceRow:
    return AccountingClaimEvidenceRow(
        claim_token=f"accc-{index:016x}",
        record_token=f"accrec-{index:016x}",
        entry_kind=AccountingEntryKindToken(kind),
        direction=AccountingEntryDirection(direction),
        item_kind="generic",
        quantity=quantity,
        assessment=AccountingRecordAssessmentToken.CONSISTENT,
        confidence_milli=500,
        speaker_token="body-a",
        tick=index,
        event_ordinal=index,
    )


@settings(max_examples=40, deadline=None)
@given(st.lists(st.integers(min_value=1, max_value=64), max_size=30))
def test_detected_counts_and_shares_stay_bounded(values) -> None:
    claims = tuple(
        _claim(
            index,
            list(AccountingEntryKindToken)[index % 5].value,
            list(AccountingEntryDirection)[index % 6].value,
            value,
        )
        for index, value in enumerate(values)
    )
    entries = detect_accounting_entries(
        AccountingEvidenceHarvest(claims=claims, coverage=AccountingCoverage.COMPLETE)
    )
    assert len(entries) <= 4_096
    conditions = detect_record_conditions(entries)
    assert all(0 <= row.share_milli <= 1_000 for row in conditions)
    summary = accounting_distribution_summary(values)
    assert summary.sample_count <= len(values)
    assert all(0 <= share <= 1_000 for share in summary.bin_shares_milli)
