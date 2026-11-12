"""Locked detached credit relationship analysis policy and window helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from analysis.credit_relationships_contract import (
    CreditRelationshipAnalysisError,
)

__all__ = [
    "CREDIT_RELATIONSHIPS_ANALYSIS_LOCKED_POLICY",
    "CreditRelationshipsAnalysisPolicy",
    "default_credit_relationships_analysis_policy",
    "window_bounds",
    "window_index_for_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.credit_relationships.policy"
)

_INT_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "window_ticks": (1, 4_096),
        "max_windows": (1, 65_536),
        "max_claim_events": (1, 1_000_000),
        "max_transfer_events": (1, 1_000_000),
        "max_owner_rows": (1, 16_384),
        "max_claim_rows": (1, 16_384),
        "max_relationship_rows": (1, 65_536),
        "max_performance_rows": (1, 65_536),
        "max_distribution_rows": (1, 65_536),
        "max_counterparty_rows": (1, 16_384),
        "max_alignment_rows": (1, 65_536),
        "max_owners": (1, 16_384),
        "max_item_kinds": (1, 1_024),
        "min_distribution_samples": (1, 1_000),
        "max_ratio_milli": (1, 1_000_000),
        "alignment_high_milli": (1, 1_000),
        "alignment_low_milli": (0, 1_000),
    }
)


@dataclass(frozen=True, slots=True)
class CreditRelationshipsAnalysisPolicy:
    """Validated detached credit analysis policy."""

    window_ticks: int = 32
    max_windows: int = 512
    max_claim_events: int = 200_000
    max_transfer_events: int = 200_000
    max_owner_rows: int = 4_096
    max_claim_rows: int = 4_096
    max_relationship_rows: int = 8_192
    max_performance_rows: int = 8_192
    max_distribution_rows: int = 8_192
    max_counterparty_rows: int = 1_024
    max_alignment_rows: int = 4_096
    max_owners: int = 4_096
    max_item_kinds: int = 1_024
    min_distribution_samples: int = 4
    max_ratio_milli: int = 64_000
    alignment_high_milli: int = 750
    alignment_low_milli: int = 250

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int:
                _LOG.warning("credit_relationships_policy_invalid field=%s", name)
                raise CreditRelationshipAnalysisError(
                    "credit_analysis_invalid_policy"
                )
            if value < minimum or value > maximum:
                _LOG.warning("credit_relationships_policy_invalid field=%s", name)
                raise CreditRelationshipAnalysisError(
                    "credit_analysis_invalid_policy"
                )
        if self.alignment_low_milli >= self.alignment_high_milli:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_policy")


_DEFAULT_POLICY: Final[CreditRelationshipsAnalysisPolicy] = (
    CreditRelationshipsAnalysisPolicy()
)

CREDIT_RELATIONSHIPS_ANALYSIS_LOCKED_POLICY: Final[Mapping[str, int]] = (
    MappingProxyType(
        {name: getattr(_DEFAULT_POLICY, name) for name in _INT_RANGES}
    )
)


def default_credit_relationships_analysis_policy() -> (
    CreditRelationshipsAnalysisPolicy
):
    """Return the one locked analysis policy value."""

    return _DEFAULT_POLICY


def window_index_for_tick(
    tick: int, policy: CreditRelationshipsAnalysisPolicy | None = None
) -> int:
    """Return the locked policy window index for ``tick``."""

    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_window")
    active = _DEFAULT_POLICY if policy is None else policy
    if type(active) is not CreditRelationshipsAnalysisPolicy:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_policy")
    index = tick // active.window_ticks
    if index >= active.max_windows:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_window")
    return index


def window_bounds(
    window_index: int, policy: CreditRelationshipsAnalysisPolicy
) -> tuple[int, int]:
    """Return inclusive-exclusive tick bounds for one policy window."""

    if type(policy) is not CreditRelationshipsAnalysisPolicy:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_policy")
    if (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or window_index < 0
        or window_index >= policy.max_windows
    ):
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_window")
    start = window_index * policy.window_ticks
    return start, start + policy.window_ticks
