"""Locked detached scientific-hypothesis analysis policy and window helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final

from analysis.scientific_hypotheses_contract import ScientificHypothesesError

__all__ = [
    "SCIENTIFIC_HYPOTHESES_LOCKED_POLICY",
    "ScientificHypothesesPolicy",
    "default_policy",
    "policy_with",
    "window_bounds",
    "window_index",
    "window_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.scientific_hypotheses.policy"
)

_INT_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "window_ticks": (1, 4_096),
        "max_windows": (1, 65_536),
        "max_events": (1, 1_000_000),
        "max_owners": (1, 4_096),
        "max_hypotheses": (1, 65_536),
        "max_conditions": (1, 65_536),
        "max_revisions": (1, 65_536),
        "max_trials": (1, 65_536),
        "max_summary_rows": (1, 65_536),
        "max_notices": (1, 1_024),
        "min_samples": (1, 1_000),
        "confidence_prior": (1, 1_000),
    }
)


@dataclass(frozen=True, slots=True)
class ScientificHypothesesPolicy:
    """Validated detached scientific-hypothesis policy."""

    window_ticks: int = 32
    max_windows: int = 512
    max_events: int = 200_000
    max_owners: int = 64
    max_hypotheses: int = 4_096
    max_conditions: int = 8_192
    max_revisions: int = 8_192
    max_trials: int = 4_096
    max_summary_rows: int = 1_024
    max_notices: int = 8
    min_samples: int = 3
    confidence_prior: int = 1

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or type(value) is not int
                or not minimum <= value <= maximum
            ):
                _LOG.warning("scientific_hypotheses_policy_invalid field=%s", name)
                raise ScientificHypothesesError(
                    "scientific_hypotheses_invalid_policy"
                )

    def window_index(self, tick: int) -> int:
        """Return the policy window index for ``tick``."""

        return window_index(tick, self)

    def window_tick(self, index: int) -> int:
        """Return the first tick of window ``index``."""

        return window_tick(index, self)

    def window_bounds(self, tick: int) -> tuple[int, int]:
        """Return inclusive-exclusive bounds for the window containing ``tick``."""

        return window_bounds(tick, self)


_DEFAULT_POLICY: Final[ScientificHypothesesPolicy] = ScientificHypothesesPolicy()

SCIENTIFIC_HYPOTHESES_LOCKED_POLICY: Final[Mapping[str, int]] = MappingProxyType(
    {name: getattr(_DEFAULT_POLICY, name) for name in _INT_RANGES}
)


def _require_policy(policy: object) -> ScientificHypothesesPolicy:
    if type(policy) is not ScientificHypothesesPolicy:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_policy")
    return policy


def default_policy() -> ScientificHypothesesPolicy:
    """Return the one locked analysis policy value."""

    return _DEFAULT_POLICY


def policy_with(**overrides: int) -> ScientificHypothesesPolicy:
    """Return a validated copy with ``overrides`` applied."""

    unknown = set(overrides) - set(_INT_RANGES)
    if unknown:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_policy")
    return replace(_DEFAULT_POLICY, **overrides)


def _require_tick(tick: object, policy: ScientificHypothesesPolicy) -> int:
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_policy")
    if tick // policy.window_ticks >= policy.max_windows:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_policy")
    return tick


def window_index(
    tick: int, policy: ScientificHypothesesPolicy | None = None
) -> int:
    """Return the locked policy window index for ``tick``."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    value = _require_tick(tick, active)
    return value // active.window_ticks


def window_tick(
    index: int, policy: ScientificHypothesesPolicy | None = None
) -> int:
    """Return the first tick of window ``index``."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if (
        isinstance(index, bool)
        or type(index) is not int
        or index < 0
        or index >= active.max_windows
    ):
        raise ScientificHypothesesError("scientific_hypotheses_invalid_policy")
    return index * active.window_ticks


def window_bounds(
    tick: int, policy: ScientificHypothesesPolicy | None = None
) -> tuple[int, int]:
    """Return inclusive-exclusive tick bounds for the window containing ``tick``."""

    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    start = window_tick(window_index(tick, active), active)
    return start, start + active.window_ticks
