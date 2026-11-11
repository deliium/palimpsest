"""Locked detached market-like institution analysis policy and window helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from analysis.market_institutions_contract import (
    MarketInstitutionsError,
)

__all__ = [
    "MARKET_INSTITUTION_ANALYSIS_LOCKED_POLICY",
    "MarketInstitutionsAnalysisPolicy",
    "default_market_institutions_analysis_policy",
    "window_bounds",
    "window_index_for_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.policy"
)

_INT_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "window_ticks": (1, 4_096),
        "max_windows": (1, 65_536),
        "max_exchange_events": (1, 1_000_000),
        "max_attempt_rows": (1, 1_000_000),
        "max_venue_rows": (1, 65_536),
        "max_gathering_rows": (1, 65_536),
        "max_participation_rows": (1, 65_536),
        "max_expectation_rows": (1, 16_384),
        "max_role_rows": (1, 16_384),
        "max_record_rows": (1, 16_384),
        "max_markets": (1, 16_384),
        "max_locations": (1, 16_384),
        "max_lineage_edges": (1, 65_536),
        "max_dormant_windows_per_venue": (0, 16),
        "min_gathering_exchanges": (1, 16),
        "min_gathering_participants": (1, 64),
        "min_recurring_windows": (1, 16),
        "min_persistent_windows": (1, 16),
        "persistent_recurrence_milli": (1, 1_000),
        "expectation_min_evidence": (1, 16),
        "broker_min_exchanges": (1, 16),
        "broker_min_counterparties": (1, 16),
        "broker_min_windows": (1, 16),
        "alignment_high_milli": (1, 1_000),
        "alignment_low_milli": (0, 1_000),
        "lineage_overlap_milli": (1, 1_000),
    }
)


@dataclass(frozen=True, slots=True)
class MarketInstitutionsAnalysisPolicy:
    """Validated detached market-like institution analysis policy."""

    window_ticks: int = 32
    max_windows: int = 512
    max_exchange_events: int = 200_000
    max_attempt_rows: int = 200_000
    max_venue_rows: int = 8_192
    max_gathering_rows: int = 8_192
    max_participation_rows: int = 8_192
    max_expectation_rows: int = 4_096
    max_role_rows: int = 4_096
    max_record_rows: int = 4_096
    max_markets: int = 1_024
    max_locations: int = 4_096
    max_lineage_edges: int = 16_384
    max_dormant_windows_per_venue: int = 1
    min_gathering_exchanges: int = 2
    min_gathering_participants: int = 2
    min_recurring_windows: int = 2
    min_persistent_windows: int = 3
    persistent_recurrence_milli: int = 500
    expectation_min_evidence: int = 2
    broker_min_exchanges: int = 3
    broker_min_counterparties: int = 2
    broker_min_windows: int = 2
    alignment_high_milli: int = 750
    alignment_low_milli: int = 250
    lineage_overlap_milli: int = 500

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int:
                _LOG.warning(
                    "market_institutions_policy_invalid field=%s", name
                )
                raise MarketInstitutionsError(
                    "market_institutions_invalid_policy"
                )
            if value < minimum or value > maximum:
                _LOG.warning(
                    "market_institutions_policy_invalid field=%s", name
                )
                raise MarketInstitutionsError(
                    "market_institutions_invalid_policy"
                )
        if self.min_persistent_windows < self.min_recurring_windows:
            raise MarketInstitutionsError("market_institutions_invalid_policy")
        if self.alignment_low_milli >= self.alignment_high_milli:
            raise MarketInstitutionsError("market_institutions_invalid_policy")


MARKET_INSTITUTION_ANALYSIS_LOCKED_POLICY: Final[Mapping[str, int]] = (
    MappingProxyType(
        {
            name: getattr(MarketInstitutionsAnalysisPolicy, name)
            for name in _INT_RANGES
        }
    )
)

_DEFAULT_POLICY: Final[MarketInstitutionsAnalysisPolicy] = (
    MarketInstitutionsAnalysisPolicy()
)


def default_market_institutions_analysis_policy() -> (
    MarketInstitutionsAnalysisPolicy
):
    """Return the one locked analysis policy value."""

    return _DEFAULT_POLICY


def window_index_for_tick(
    tick: int, policy: MarketInstitutionsAnalysisPolicy | None = None
) -> int:
    """Return the locked policy window index for ``tick``."""

    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise MarketInstitutionsError("market_institutions_invalid_window")
    active = _DEFAULT_POLICY if policy is None else policy
    if type(active) is not MarketInstitutionsAnalysisPolicy:
        raise MarketInstitutionsError("market_institutions_invalid_policy")
    index = tick // active.window_ticks
    if index >= active.max_windows:
        raise MarketInstitutionsError("market_institutions_invalid_window")
    return index


def window_bounds(
    window_index: int, policy: MarketInstitutionsAnalysisPolicy
) -> tuple[int, int]:
    """Return inclusive-exclusive tick bounds for one policy window."""

    if type(policy) is not MarketInstitutionsAnalysisPolicy:
        raise MarketInstitutionsError("market_institutions_invalid_policy")
    if (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or window_index < 0
        or window_index >= policy.max_windows
    ):
        raise MarketInstitutionsError("market_institutions_invalid_window")
    start = window_index * policy.window_ticks
    return start, start + policy.window_ticks
