"""Owner join and researcher-only alignment tests."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from analysis.accounting_ledgers_contract import (
    AccountingAlignment,
    AccountingCoverage,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
    AccountingRecordIntegrityToken,
)
from analysis.accounting_ledgers_expectations import (
    AccountingOwnerRowInput,
    join_accounting_owners,
)
from analysis.accounting_ledgers_policy import AccountingLedgersAnalysisPolicy
from analysis.accounting_ledgers_rows import (
    AccountingRecordEvidenceRow,
    AccountingTransferEvidenceRow,
)


def _owner(
    quantity: int = 4, *, token: str = "acce-0123456789abcdef"
) -> AccountingOwnerRowInput:
    return AccountingOwnerRowInput(
        owner_token="acco-0123456789abcdef",
        entry_token=token,
        record_token="accrec-0123456789abcdef",
        entry_kind=AccountingEntryKindToken.EXCHANGE,
        direction=AccountingEntryDirection.INFLOW,
        item_kind="food",
        quantity=quantity,
        assessment=AccountingRecordAssessmentToken.CONSISTENT,
        confidence_milli=700,
        first_tick=1,
        last_tick=2,
        window_index=0,
    )


def _record() -> AccountingRecordEvidenceRow:
    return AccountingRecordEvidenceRow(
        record_token="accrec-0123456789abcdef",
        record_genre="agreement",
        observed_integrity=AccountingRecordIntegrityToken.INTACT,
        content_revision=0,
        author_token="body-a",
        tick=1,
        event_ordinal=0,
        copy_generation=0,
        tombstoned=False,
    )


def _transfer(quantity: int) -> AccountingTransferEvidenceRow:
    return AccountingTransferEvidenceRow(
        transfer_token="accf-0123456789abcdef",
        giver_token="body-a",
        receiver_token="body-b",
        item_kind="food",
        quantity=quantity,
        tick=1,
        event_ordinal=0,
    )


def test_all_four_alignment_values() -> None:
    consistent = join_accounting_owners(
        owner_rows=(_owner(4),),
        record_rows=(_record(),),
        transfer_rows=(_transfer(4),),
    )
    assert consistent.alignments[0].alignment is AccountingAlignment.CONSISTENT
    not_applicable = join_accounting_owners(
        owner_rows=(_owner(4),),
        record_rows=(),
        transfer_rows=(),
    )
    assert (
        not_applicable.alignments[0].alignment
        is AccountingAlignment.NOT_APPLICABLE
    )
    unresolved = join_accounting_owners(
        owner_rows=(_owner(4),),
        record_rows=(_record(),),
        transfer_rows=(_transfer(6),),
    )
    assert unresolved.alignments[0].alignment is AccountingAlignment.UNRESOLVED
    inconsistent = join_accounting_owners(
        owner_rows=(_owner(4),),
        record_rows=(_record(),),
        transfer_rows=(_transfer(20),),
    )
    assert inconsistent.alignments[0].alignment is AccountingAlignment.INCONSISTENT


def test_gap_thresholds() -> None:
    for evidence, expected in (
        (4, AccountingAlignment.CONSISTENT),
        (6, AccountingAlignment.UNRESOLVED),
        (20, AccountingAlignment.INCONSISTENT),
    ):
        result = join_accounting_owners(
            owner_rows=(_owner(4),),
            record_rows=(_record(),),
            transfer_rows=(_transfer(evidence),),
        )
        assert result.alignments[0].alignment is expected
        assert 0 <= result.alignments[0].gap_milli <= 1_000


def test_missing_owner_rows_and_no_synthetic_alignment() -> None:
    result = join_accounting_owners(
        owner_rows=(),
        record_rows=(_record(),),
        transfer_rows=(_transfer(4),),
    )
    assert result.coverage is AccountingCoverage.MISSING
    assert result.alignments == ()
    assert result.owner_rows == ()


def test_owner_row_without_evidence_is_not_applicable() -> None:
    result = join_accounting_owners(
        owner_rows=(_owner(),),
        record_rows=(),
        transfer_rows=(),
    )
    assert result.alignments[0].alignment is AccountingAlignment.NOT_APPLICABLE
    assert result.alignments[0].gap_milli == 0


def test_duplicate_rows_and_cap_truncation() -> None:
    duplicate = join_accounting_owners(
        owner_rows=(_owner(), _owner()),
        record_rows=(_record(),),
        transfer_rows=(_transfer(4),),
    )
    assert duplicate.duplicate_owner_rows == 1
    assert duplicate.coverage is AccountingCoverage.PARTIAL
    policy = AccountingLedgersAnalysisPolicy(max_owner_rows=1)
    truncated = join_accounting_owners(
        owner_rows=(
            _owner(token="acce-0123456789abcdef"),
            _owner(token="acce-0123456789abcdee"),
        ),
        record_rows=(_record(),),
        transfer_rows=(_transfer(4),),
        policy=policy,
    )
    assert len(truncated.owner_rows) == 1
    assert truncated.coverage is AccountingCoverage.PARTIAL
    assert "accounting_owner_truncated" in truncated.notices


def test_invalid_policy_fails_closed() -> None:
    from analysis.accounting_ledgers_contract import AccountingAnalysisError

    with pytest.raises(AccountingAnalysisError):
        join_accounting_owners(
            owner_rows=(_owner(),),
            record_rows=(),
            transfer_rows=(),
            policy=object(),  # type: ignore[arg-type]
        )
