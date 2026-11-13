"""Locked detached economic-inequality analysis policy and window helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final

from analysis.economic_inequality_contract import EconomicInequalityError

__all__ = [
    "ECONOMIC_INEQUALITY_ANALYSIS_LOCKED_POLICY",
    "EconomicInequalityAnalysisPolicy",
    "default_economic_inequality_analysis_policy",
    "validate_window_index",
    "window_bounds",
    "window_index_for_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.policy"
)

_INT_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "window_ticks": (1, 4_096),
        "max_windows": (1, 65_536),
        "min_distribution_samples": (1, 1_000),
        "max_event_rows": (1, 1_000_000),
        "max_owners": (1, 65_536),
        "max_dimension_rows": (1, 65_536),
        "max_comparison_rows": (1, 65_536),
        "max_cohorts": (1, 4_096),
        "max_societies": (1, 65_536),
        "max_notices": (1, 1_024),
        "trend_threshold_milli": (0, 1_000),
    }
)


@dataclass(frozen=True, slots=True)
class EconomicInequalityAnalysisPolicy:
    """Validated detached economic-inequality policy."""

    window_ticks: int = 32
    max_windows: int = 512
    min_distribution_samples: int = 4
    max_event_rows: int = 200_000
    max_owners: int = 4_096
    max_dimension_rows: int = 4_096
    max_comparison_rows: int = 4_096
    max_cohorts: int = 32
    max_societies: int = 2_048
    max_notices: int = 8
    trend_threshold_milli: int = 50

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or type(value) is not int
                or not minimum <= value <= maximum
            ):
                _LOG.warning(
                    "economic_inequality_policy_invalid field=%s", name
                )
                raise EconomicInequalityError(
                    "economic_inequality_invalid_policy"
                )


_DEFAULT_POLICY: Final[EconomicInequalityAnalysisPolicy] = (
    EconomicInequalityAnalysisPolicy()
)

ECONOMIC_INEQUALITY_ANALYSIS_LOCKED_POLICY: Final[Mapping[str, int]] = (
    MappingProxyType(
        {name: getattr(_DEFAULT_POLICY, name) for name in _INT_RANGES}
    )
)


def default_economic_inequality_analysis_policy() -> (
    EconomicInequalityAnalysisPolicy
):
    """Return the one locked analysis policy value."""

    return _DEFAULT_POLICY


def _require_policy(
    policy: object,
) -> EconomicInequalityAnalysisPolicy:
    if type(policy) is not EconomicInequalityAnalysisPolicy:
        raise EconomicInequalityError("economic_inequality_invalid_policy")
    return policy


def with_window_end(
    window_end: int,
    policy: EconomicInequalityAnalysisPolicy | None = None,
) -> EconomicInequalityAnalysisPolicy:
    """Return the policy truncated to the last observed window."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if isinstance(window_end, bool) or type(window_end) is not int:
        raise EconomicInequalityError("economic_inequality_invalid_window")
    if window_end < 0:
        raise EconomicInequalityError("economic_inequality_invalid_window")
    windows = window_end // active.window_ticks + 1
    if windows > active.max_windows:
        raise EconomicInequalityError("economic_inequality_invalid_window")
    return replace(active, max_windows=windows)


def window_index_for_tick(
    tick: int, policy: EconomicInequalityAnalysisPolicy | None = None
) -> int:
    """Return the locked policy window index for ``tick``."""

    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise EconomicInequalityError("economic_inequality_invalid_window")
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    index = tick // active.window_ticks
    if index >= active.max_windows:
        raise EconomicInequalityError("economic_inequality_invalid_window")
    return index


def validate_window_index(
    window_index: int, policy: EconomicInequalityAnalysisPolicy | None = None
) -> int:
    """Validate one window index against the locked policy."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or window_index < 0
        or window_index >= active.max_windows
    ):
        raise EconomicInequalityError("economic_inequality_invalid_window")
    return window_index


def window_bounds(
    window_index: int, policy: EconomicInequalityAnalysisPolicy | None = None
) -> tuple[int, int]:
    """Return inclusive-exclusive tick bounds for one policy window."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    validate_window_index(window_index, active)
    start = window_index * active.window_ticks
    return start, start + active.window_ticks
