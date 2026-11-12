"""Descriptive accounting detection tests."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from analysis.accounting_ledgers_contract import (
    AccountingAnalysisError,
    AccountingCoverage,
    AccountingDistributionStatus,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
    assert_accounting_layer_separation,
)
from analysis.accounting_ledgers_detection import (
    accounting_distribution_summary,
    detect_accounting_counterparties,
    detect_accounting_entries,
    detect_accounting_flows,
    detect_record_conditions,
)
from analysis.accounting_ledgers_rows import (
    AccountingClaimEvidenceRow,
    AccountingEvidenceHarvest,
)

KINDS = list(AccountingEntryKindToken)
DIRECTIONS = list(AccountingEntryDirection)


def _claim(
    index: int,
    *,
    kind: AccountingEntryKindToken = AccountingEntryKindToken.EXCHANGE,
    direction: AccountingEntryDirection = AccountingEntryDirection.INFLOW,
    tick: int = 1,
    quantity: int = 2,
    assessment: AccountingRecordAssessmentToken = (
        AccountingRecordAssessmentToken.CONSISTENT
    ),
    speaker: str = "body-a",
) -> AccountingClaimEvidenceRow:
    return AccountingClaimEvidenceRow(
        claim_token=f"accc-{index:016x}",
        record_token=f"accrec-{index:016x}",
        entry_kind=kind,
        direction=direction,
        item_kind="food",
        quantity=quantity,
        assessment=assessment,
        confidence_milli=700,
        speaker_token=speaker,
        tick=tick,
        event_ordinal=index,
    )


def _harvest(claims) -> AccountingEvidenceHarvest:
    return AccountingEvidenceHarvest(
        claims=tuple(claims),
        coverage=AccountingCoverage.COMPLETE,
    )


def test_all_five_kinds_and_six_directions_detected() -> None:
    claims = [
        _claim(index, kind=kind, direction=direction)
        for index, (kind, direction) in enumerate(
            zip(KINDS * 2, DIRECTIONS, strict=False)
        )
    ]
    entries = detect_accounting_entries(_harvest(claims))
    assert {entry.entry_kind for entry in entries} == set(KINDS)
    assert len(entries) >= len(DIRECTIONS)


def test_condition_histograms_and_shares() -> None:
    claims = [
        _claim(
            index,
            assessment=(
                AccountingRecordAssessmentToken.DAMAGED
                if index % 2
                else AccountingRecordAssessmentToken.CONSISTENT
            ),
        )
        for index in range(6)
    ]
    entries = detect_accounting_entries(_harvest(claims))
    conditions = detect_record_conditions(entries)
    assert sum(row.record_count for row in conditions) == len(entries)
    assert all(0 <= row.share_milli <= 1_000 for row in conditions)
    assert all(row.quantity_histogram for row in conditions)


def test_flows_and_counterparties_are_descriptive() -> None:
    entries = detect_accounting_entries(
        _harvest([_claim(index, speaker=f"body-{index % 2}") for index in range(4)])
    )
    flows = detect_accounting_flows(entries)
    assert flows
    assert all(row.quantity_sum >= 0 for row in flows)
    counterparties = detect_accounting_counterparties(
        [_claim(index, speaker=f"body-{index % 3}") for index in range(6)]
    )
    assert len(counterparties) == 3
    assert all(row.entry_count > 0 for row in counterparties)


def test_distribution_insufficient_below_four_and_available_at_four() -> None:
    insufficient = accounting_distribution_summary([1, 2, 3])
    assert insufficient.status is AccountingDistributionStatus.INSUFFICIENT_SAMPLES
    assert insufficient.median is None
    assert insufficient.bin_shares_milli == ()
    available = accounting_distribution_summary([1, 2, 3, 4])
    assert available.status is AccountingDistributionStatus.AVAILABLE
    assert available.sample_count == 4
    assert available.minimum == 1
    assert available.maximum == 4
    assert available.median is not None
    assert len(available.bin_shares_milli) == 5
    assert all(0 <= share <= 1_000 for share in available.bin_shares_milli)


def test_out_of_range_values_are_excluded_and_counted() -> None:
    summary = accounting_distribution_summary([1, 2, 3, 4, 65, -1, True])
    assert summary.sample_count == 4
    assert summary.maximum == 4


def test_layer_separation_rejects_mixed_rows() -> None:
    claim = _claim(1)
    entry = detect_accounting_entries(_harvest([claim]))[0]
    with pytest.raises(AccountingAnalysisError):
        assert_accounting_layer_separation(claim, entry)


def test_hypothesis_counts_and_shares_are_bounded() -> None:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @settings(max_examples=50, deadline=None)
    @given(
        st.lists(st.integers(min_value=1, max_value=64), min_size=0, max_size=40),
    )
    def _check(values) -> None:
        summary = accounting_distribution_summary(values)
        assert summary.sample_count <= len(values)
        assert all(0 <= share <= 1_000 for share in summary.bin_shares_milli)

    _check()
