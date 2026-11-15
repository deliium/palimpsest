"""Locked detached economic-cascade analysis policy and window helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final

from analysis.economic_cascades_contract import EconomicCascadesError

__all__ = [
    "ECONOMIC_CASCADES_LOCKED_POLICY",
    "EconomicCascadesPolicy",
    "default_policy",
    "policy_with",
    "window_bounds",
    "window_bounds_for_tick",
    "window_index",
    "window_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.economic_cascades.policy")

_INT_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "window_ticks": (1, 4_096),
        "max_windows": (1, 65_536),
        "max_events": (1, 1_000_000),
        "max_disruptions": (1, 65_536),
        "max_stages": (1, 65_536),
        "max_dependency_edges": (1, 65_536),
        "max_chains": (1, 65_536),
        "max_propagation_rows": (1, 65_536),
        "max_coverage_rows": (1, 65_536),
        "max_notices": (1, 1_024),
        "max_chain_depth": (1, 64),
        "max_propagation_lag_windows": (0, 64),
        "min_linked_chains": (1, 1_000),
        "shortfall_share_milli": (1, 1_000),
    }
)


@dataclass(frozen=True, slots=True)
class EconomicCascadesPolicy:
    """Validated detached economic-cascade policy."""

    window_ticks: int = 32
    max_windows: int = 512
    max_events: int = 200_000
    max_disruptions: int = 4_096
    max_stages: int = 4_096
    max_dependency_edges: int = 4_096
    max_chains: int = 2_048
    max_propagation_rows: int = 1_024
    max_coverage_rows: int = 1_024
    max_notices: int = 8
    max_chain_depth: int = 6
    max_propagation_lag_windows: int = 2
    min_linked_chains: int = 3
    shortfall_share_milli: int = 250

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or type(value) is not int
                or not minimum <= value <= maximum
            ):
                _LOG.warning(
                    "economic_cascades_policy_invalid field=%s", name
                )
                raise EconomicCascadesError("economic_cascades_invalid_policy")
        if self.max_propagation_lag_windows > self.max_windows:
            raise EconomicCascadesError("economic_cascades_invalid_policy")

    def window_index(self, tick: int) -> int:
        """Return the policy window index for ``tick``."""

        return window_index(tick, self)

    def window_tick(self, index: int) -> int:
        """Return the first tick of window ``index``."""

        return window_tick(index, self)

    def window_bounds(self, tick: int) -> tuple[int, int]:
        """Return inclusive-exclusive bounds for the window containing ``tick``."""

        return window_bounds(tick, self)


_DEFAULT_POLICY: Final[EconomicCascadesPolicy] = EconomicCascadesPolicy()

ECONOMIC_CASCADES_LOCKED_POLICY: Final[Mapping[str, int]] = MappingProxyType(
    {name: getattr(_DEFAULT_POLICY, name) for name in _INT_RANGES}
)


def _require_policy(policy: object) -> EconomicCascadesPolicy:
    if type(policy) is not EconomicCascadesPolicy:
        raise EconomicCascadesError("economic_cascades_invalid_policy")
    return policy


def default_policy() -> EconomicCascadesPolicy:
    """Return the one locked analysis policy value."""

    return _DEFAULT_POLICY


def policy_with(**overrides: int) -> EconomicCascadesPolicy:
    """Return a validated copy with ``overrides`` applied."""

    unknown = set(overrides) - set(_INT_RANGES)
    if unknown:
        raise EconomicCascadesError("economic_cascades_invalid_policy")
    return replace(_DEFAULT_POLICY, **overrides)


def _require_tick(tick: object, policy: EconomicCascadesPolicy) -> int:
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    if tick // policy.window_ticks >= policy.max_windows:
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    return tick


def window_index(
    tick: int, policy: EconomicCascadesPolicy | None = None
) -> int:
    """Return the locked policy window index for ``tick``."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    value = _require_tick(tick, active)
    return value // active.window_ticks


def window_tick(
    index: int, policy: EconomicCascadesPolicy | None = None
) -> int:
    """Return the first tick of window ``index``."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if (
        isinstance(index, bool)
        or type(index) is not int
        or index < 0
        or index >= active.max_windows
    ):
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    return index * active.window_ticks


def window_bounds(
    tick: int, policy: EconomicCascadesPolicy | None = None
) -> tuple[int, int]:
    """Return inclusive-exclusive tick bounds for the window containing ``tick``."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    start = window_tick(window_index(tick, active), active)
    return start, start + active.window_ticks


def window_index_for_tick(
    tick: int, policy: EconomicCascadesPolicy | None = None
) -> int:
    """Alias retained for symmetry with sibling analysis policies."""

    return window_index(tick, policy)


def window_bounds_for_tick(
    tick: int, policy: EconomicCascadesPolicy | None = None
) -> tuple[int, int]:
    """Alias retained for symmetry with sibling analysis policies."""

    return window_bounds(tick, policy)
