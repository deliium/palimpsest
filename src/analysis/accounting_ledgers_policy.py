"""Locked detached accounting analysis policy and window helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from analysis.accounting_ledgers_contract import AccountingAnalysisError

__all__ = [
    "ACCOUNTING_LEDGERS_ANALYSIS_LOCKED_POLICY",
    "AccountingLedgersAnalysisPolicy",
    "default_accounting_ledgers_analysis_policy",
    "window_bounds",
    "window_index_for_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.accounting_ledgers.policy"
)

_INT_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "window_ticks": (1, 4_096),
        "max_windows": (1, 65_536),
        "max_record_events": (1, 1_000_000),
        "max_transfer_events": (1, 1_000_000),
        "max_contribution_events": (1, 1_000_000),
        "max_claim_events": (1, 1_000_000),
        "max_owner_rows": (1, 16_384),
        "max_entry_rows": (1, 65_536),
        "max_record_rows": (1, 65_536),
        "max_counterparty_rows": (1, 16_384),
        "max_flow_rows": (1, 65_536),
        "max_alignment_rows": (1, 65_536),
        "max_condition_rows": (1, 16_384),
        "max_owners": (1, 16_384),
        "max_item_kinds": (1, 1_024),
        "min_distribution_samples": (1, 1_000),
        "max_quantity": (1, 1_000_000),
        "max_valuation_milli": (1, 1_000_000),
        "alignment_consistent_milli": (0, 1_000),
        "alignment_inconsistent_milli": (0, 1_000),
    }
)


@dataclass(frozen=True, slots=True)
class AccountingLedgersAnalysisPolicy:
    """Validated detached accounting analysis policy."""

    window_ticks: int = 32
    max_windows: int = 512
    max_record_events: int = 200_000
    max_transfer_events: int = 200_000
    max_contribution_events: int = 200_000
    max_claim_events: int = 200_000
    max_owner_rows: int = 4_096
    max_entry_rows: int = 4_096
    max_record_rows: int = 2_048
    max_counterparty_rows: int = 1_024
    max_flow_rows: int = 4_096
    max_alignment_rows: int = 4_096
    max_condition_rows: int = 1_024
    max_owners: int = 4_096
    max_item_kinds: int = 1_024
    min_distribution_samples: int = 4
    max_quantity: int = 64
    max_valuation_milli: int = 64_000
    alignment_consistent_milli: int = 250
    alignment_inconsistent_milli: int = 750

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or type(value) is not int
                or not minimum <= value <= maximum
            ):
                _LOG.warning("accounting_ledgers_policy_invalid field=%s", name)
                raise AccountingAnalysisError(
                    "accounting_analysis_invalid_policy"
                )
        if (
            self.alignment_consistent_milli
            >= self.alignment_inconsistent_milli
        ):
            raise AccountingAnalysisError("accounting_analysis_invalid_policy")


_DEFAULT_POLICY: Final[AccountingLedgersAnalysisPolicy] = (
    AccountingLedgersAnalysisPolicy()
)

ACCOUNTING_LEDGERS_ANALYSIS_LOCKED_POLICY: Final[Mapping[str, int]] = (
    MappingProxyType(
        {name: getattr(_DEFAULT_POLICY, name) for name in _INT_RANGES}
    )
)


def default_accounting_ledgers_analysis_policy() -> AccountingLedgersAnalysisPolicy:
    """Return the one locked analysis policy value."""

    return _DEFAULT_POLICY


def _require_policy(
    policy: object,
) -> AccountingLedgersAnalysisPolicy:
    if type(policy) is not AccountingLedgersAnalysisPolicy:
        raise AccountingAnalysisError("accounting_analysis_invalid_policy")
    return policy


def window_index_for_tick(
    tick: int, policy: AccountingLedgersAnalysisPolicy | None = None
) -> int:
    """Return the locked policy window index for ``tick``."""

    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise AccountingAnalysisError("accounting_analysis_invalid_window")
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    index = tick // active.window_ticks
    if index >= active.max_windows:
        raise AccountingAnalysisError("accounting_analysis_invalid_window")
    return index


def window_bounds(
    window_index: int, policy: AccountingLedgersAnalysisPolicy | None = None
) -> tuple[int, int]:
    """Return inclusive-exclusive tick bounds for one policy window."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or window_index < 0
        or window_index >= active.max_windows
    ):
        raise AccountingAnalysisError("accounting_analysis_invalid_window")
    start = window_index * active.window_ticks
    return start, start + active.window_ticks
