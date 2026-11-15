"""Locked detached social-mobility analysis policy and window helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final

from analysis.social_mobility_contract import SocialMobilityError

__all__ = [
    "SOCIAL_MOBILITY_ANALYSIS_LOCKED_POLICY",
    "SocialMobilityAnalysisPolicy",
    "default_social_mobility_analysis_policy",
    "validate_window_index",
    "window_bounds",
    "window_index_for_tick",
    "with_window_end",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.policy")

_INT_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "window_ticks": (1, 512),
        "max_windows": (1, 512),
        "min_mobility_pairs": (2, 64),
        "rank_bins": (2, 10),
        "max_generation_lag": (1, 4),
        "max_lineage_depth": (1, 8),
        "max_generation_index": (0, 32),
        "max_event_rows": (0, 1_000_000),
        "max_owners": (0, 1_000_000),
        "max_pairs": (0, 1_000_000),
        "max_domain_rows": (0, 1_000_000),
        "max_generation_rows": (0, 1_000_000),
        "max_lag_rows": (0, 1_000_000),
        "max_coverage_rows": (0, 1_000_000),
        "max_notices": (0, 1_000_000),
        "persistence_share_milli": (0, 1_000),
    }
)


@dataclass(frozen=True, slots=True)
class SocialMobilityAnalysisPolicy:
    """Validated detached social-mobility policy."""

    window_ticks: int = 32
    max_windows: int = 512
    min_mobility_pairs: int = 8
    rank_bins: int = 5
    max_generation_lag: int = 4
    max_lineage_depth: int = 8
    max_generation_index: int = 32
    max_event_rows: int = 200_000
    max_owners: int = 4_096
    max_pairs: int = 4_096
    max_domain_rows: int = 4_096
    max_generation_rows: int = 1_024
    max_lag_rows: int = 2_048
    max_coverage_rows: int = 1_024
    max_notices: int = 8
    persistence_share_milli: int = 500

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or type(value) is not int
                or not minimum <= value <= maximum
            ):
                _LOG.warning("social_mobility_policy_range field=%s", name)
                raise SocialMobilityError(f"social_mobility_policy_{name}")


_DEFAULT_POLICY: Final[SocialMobilityAnalysisPolicy] = SocialMobilityAnalysisPolicy()

SOCIAL_MOBILITY_ANALYSIS_LOCKED_POLICY: Final[Mapping[str, int]] = MappingProxyType(
    {name: getattr(_DEFAULT_POLICY, name) for name in _INT_RANGES}
)


def default_social_mobility_analysis_policy() -> SocialMobilityAnalysisPolicy:
    """Return the one locked analysis policy value."""

    return _DEFAULT_POLICY


def _require_policy(policy: object) -> SocialMobilityAnalysisPolicy:
    if type(policy) is not SocialMobilityAnalysisPolicy:
        raise SocialMobilityError("social_mobility_invalid_policy")
    return policy


def with_window_end(
    window_end: int,
    policy: SocialMobilityAnalysisPolicy | None = None,
) -> SocialMobilityAnalysisPolicy:
    """Return the policy truncated to the last observed window."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if isinstance(window_end, bool) or type(window_end) is not int:
        raise SocialMobilityError("social_mobility_window_out_of_range")
    if window_end < 0:
        raise SocialMobilityError("social_mobility_window_out_of_range")
    windows = window_end // active.window_ticks + 1
    if windows > active.max_windows:
        raise SocialMobilityError("social_mobility_window_out_of_range")
    return replace(active, max_windows=windows)


def window_index_for_tick(
    tick: int, policy: SocialMobilityAnalysisPolicy | None = None
) -> int:
    """Return the locked policy window index for ``tick``."""

    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise SocialMobilityError("social_mobility_window_out_of_range")
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    index = tick // active.window_ticks
    if index >= active.max_windows:
        raise SocialMobilityError("social_mobility_window_out_of_range")
    return index


def validate_window_index(
    window_index: int, policy: SocialMobilityAnalysisPolicy | None = None
) -> int:
    """Validate one window index against the locked policy."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or window_index < 0
        or window_index >= active.max_windows
    ):
        raise SocialMobilityError("social_mobility_window_out_of_range")
    return window_index


def window_bounds(
    window_index: int, policy: SocialMobilityAnalysisPolicy | None = None
) -> tuple[int, int]:
    """Return inclusive-exclusive tick bounds for one policy window."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    validate_window_index(window_index, active)
    start = window_index * active.window_ticks
    return start, start + active.window_ticks
