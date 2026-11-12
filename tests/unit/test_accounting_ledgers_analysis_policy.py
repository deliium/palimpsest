"""Locked accounting analysis policy tests."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from analysis.accounting_ledgers_contract import AccountingAnalysisError
from analysis.accounting_ledgers_policy import (
    ACCOUNTING_LEDGERS_ANALYSIS_LOCKED_POLICY,
    AccountingLedgersAnalysisPolicy,
    default_accounting_ledgers_analysis_policy,
    window_bounds,
    window_index_for_tick,
)


def test_policy_defaults_and_locked_map() -> None:
    policy = default_accounting_ledgers_analysis_policy()
    assert policy is default_accounting_ledgers_analysis_policy()
    assert policy.window_ticks == 32
    assert policy.max_windows == 512
    assert policy.min_distribution_samples == 4
    assert policy.max_quantity == 64
    for name, value in ACCOUNTING_LEDGERS_ANALYSIS_LOCKED_POLICY.items():
        assert getattr(policy, name) == value


def test_defaults_match_the_documented_caps() -> None:
    policy = AccountingLedgersAnalysisPolicy()
    assert policy.max_record_events == 200_000
    assert policy.max_transfer_events == 200_000
    assert policy.max_contribution_events == 200_000
    assert policy.max_claim_events == 200_000
    assert policy.max_owner_rows == 4_096
    assert policy.max_entry_rows == 4_096
    assert policy.max_record_rows == 2_048
    assert policy.max_counterparty_rows == 1_024
    assert policy.max_flow_rows == 4_096
    assert policy.max_alignment_rows == 4_096
    assert policy.max_condition_rows == 1_024
    assert policy.max_owners == 4_096
    assert policy.max_item_kinds == 1_024
    assert policy.max_valuation_milli == 64_000
    assert policy.alignment_consistent_milli == 250
    assert policy.alignment_inconsistent_milli == 750


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("window_ticks", 0),
        ("max_windows", 0),
        ("max_record_events", 0),
        ("max_quantity", 0),
        ("max_valuation_milli", 0),
        ("min_distribution_samples", 0),
        ("alignment_consistent_milli", 1_001),
        ("alignment_inconsistent_milli", -1),
    ],
)
def test_out_of_range_values_are_rejected(name: str, value: int) -> None:
    with pytest.raises(AccountingAnalysisError):
        AccountingLedgersAnalysisPolicy(**{name: value})


def test_bool_and_float_are_rejected() -> None:
    with pytest.raises(AccountingAnalysisError):
        AccountingLedgersAnalysisPolicy(window_ticks=True)  # type: ignore[arg-type]
    with pytest.raises(AccountingAnalysisError):
        AccountingLedgersAnalysisPolicy(window_ticks=32.0)  # type: ignore[arg-type]


def test_alignment_threshold_order_is_enforced() -> None:
    with pytest.raises(AccountingAnalysisError):
        AccountingLedgersAnalysisPolicy(
            alignment_consistent_milli=750,
            alignment_inconsistent_milli=750,
        )


def test_window_index_and_bounds() -> None:
    assert window_index_for_tick(0) == 0
    assert window_index_for_tick(31) == 0
    assert window_index_for_tick(32) == 1
    assert window_index_for_tick(511) == 15
    assert window_bounds(0) == (0, 32)
    assert window_bounds(1) == (32, 64)
    assert window_bounds(15) == (480, 512)
    with pytest.raises(AccountingAnalysisError):
        window_index_for_tick(512 * 32)
    with pytest.raises(AccountingAnalysisError):
        window_bounds(512)
    with pytest.raises(AccountingAnalysisError):
        window_index_for_tick(-1)
    with pytest.raises(AccountingAnalysisError):
        window_index_for_tick(True)  # type: ignore[arg-type]
