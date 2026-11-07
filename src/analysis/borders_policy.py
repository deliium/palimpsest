"""Locked detached-analysis thresholds for border claims.

Every value is fixed. Analysis never reads runner configuration, owner belief
policy, wall-clock state, or random state.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Final

__all__ = [
    "BORDERS_ANALYSIS_POLICY_VALUES",
    "BORDERS_ANALYSIS_POLICY_VERSION",
    "BordersAnalysisPolicy",
    "BordersAnalysisPolicyError",
    "default_borders_analysis_policy",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.borders.policy")

BORDERS_ANALYSIS_POLICY_VERSION: Final[str] = "borders-analysis.v1"

BORDERS_ANALYSIS_POLICY_VALUES: Final[Mapping[str, object]] = MappingProxyType(
    {
        "physical_window_ticks": 6,
        "min_use_actions": 2,
        "min_distinct_actors": 2,
        "hostile_window_ticks": 6,
        "overlap_min_claim_strength": 0.40,
        "recognition_min_declarations": 1,
        "agreement_consistency_min_parties": 2,
        "control_pattern_window_ticks": 12,
        "control_pattern_min_physical_actions": 2,
        "max_pairs_per_run": 4096,
        "max_rows_per_family": 5000,
        "quantum": 0.000001,
    }
)


class BordersAnalysisPolicyError(ValueError):
    """Stable-code analysis policy violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BordersAnalysisPolicy:
    """Locked detached border analysis policy."""

    version: str = BORDERS_ANALYSIS_POLICY_VERSION
    physical_window_ticks: int = 6
    min_use_actions: int = 2
    min_distinct_actors: int = 2
    hostile_window_ticks: int = 6
    overlap_min_claim_strength: float = 0.40
    recognition_min_declarations: int = 1
    agreement_consistency_min_parties: int = 2
    control_pattern_window_ticks: int = 12
    control_pattern_min_physical_actions: int = 2
    max_pairs_per_run: int = 4096
    max_rows_per_family: int = 5000
    quantum: float = 0.000001

    def __post_init__(self) -> None:
        if self.version != BORDERS_ANALYSIS_POLICY_VERSION:
            raise BordersAnalysisPolicyError("borders_analysis_policy_not_locked")
        for item in fields(type(self)):
            if item.name == "version":
                continue
            expected = BORDERS_ANALYSIS_POLICY_VALUES[item.name]
            actual = getattr(self, item.name)
            if isinstance(expected, float):
                if type(actual) is not float or actual != expected:
                    raise BordersAnalysisPolicyError(
                        "borders_analysis_policy_not_locked"
                    )
            elif type(actual) is not int or actual != expected:
                raise BordersAnalysisPolicyError("borders_analysis_policy_not_locked")


def default_borders_analysis_policy() -> BordersAnalysisPolicy:
    """Return the one locked analysis policy value."""
    _LOG.debug(
        "borders_analysis_policy_loaded policy_version=%s window_ticks=%s",
        BORDERS_ANALYSIS_POLICY_VERSION,
        BORDERS_ANALYSIS_POLICY_VALUES["physical_window_ticks"],
    )
    return BordersAnalysisPolicy()
