"""Locked detached detection thresholds for organized conflict.

The policy distinguishes individual violence from coordinated conflict and
persistent inter-group conflict. Every threshold is fixed, deterministic, and
independent of environment, wall clock, random state, runner configuration, and
owner belief.

Classification rules
--------------------
``individual_violence``
    One attacker and one target, no shared co-participation, and no recurrence
    across the configured window.

``coordinated_conflict``
    At least ``min_side_actors`` actors on one side and at least
    ``min_hostile_events`` hostile events inside ``window_ticks``, recurring in
    at least ``min_windows`` windows.

``persistent_inter_group_conflict``
    At least ``inter_group_min_sides`` sides, each with at least
    ``inter_group_min_actors_per_side`` actors, reciprocal hostile windows at
    least ``reciprocal_min_windows`` times, and the sustained span/event/active
    tick thresholds.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Final

__all__ = [
    "ORGANIZED_CONFLICT_ANALYSIS_POLICY_VALUES",
    "ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION",
    "OrganizedConflictAnalysisError",
    "OrganizedConflictAnalysisPolicy",
    "default_organized_conflict_analysis_policy",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organized_conflict.policy")

ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION: Final[str] = (
    "organized-conflict-analysis.v1"
)

ORGANIZED_CONFLICT_ANALYSIS_POLICY_VALUES: Final[Mapping[str, int]] = MappingProxyType(
    {
        "window_ticks": 6,
        "min_side_actors": 2,
        "min_hostile_events": 2,
        "min_coordinated_windows": 2,
        "min_windows": 3,
        "sustained_span_ticks": 24,
        "sustained_min_hostile_events": 6,
        "sustained_min_active_ticks": 3,
        "inter_group_min_sides": 2,
        "inter_group_min_actors_per_side": 2,
        "reciprocal_min_windows": 2,
        "max_episodes": 2048,
        "max_windows": 4096,
        "max_participants_per_episode": 64,
    }
)

CONFIDENCE_BANDS: Final[tuple[float, ...]] = (0.25, 0.5, 0.75)


class OrganizedConflictAnalysisError(ValueError):
    """Stable-code analysis policy violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OrganizedConflictAnalysisPolicy:
    """Locked analytical detection policy."""

    window_ticks: int = 6
    min_side_actors: int = 2
    min_hostile_events: int = 2
    min_coordinated_windows: int = 2
    min_windows: int = 3
    sustained_span_ticks: int = 24
    sustained_min_hostile_events: int = 6
    sustained_min_active_ticks: int = 3
    inter_group_min_sides: int = 2
    inter_group_min_actors_per_side: int = 2
    reciprocal_min_windows: int = 2
    max_episodes: int = 2048
    max_windows: int = 4096
    max_participants_per_episode: int = 64
    confidence_bands: tuple[float, ...] = CONFIDENCE_BANDS

    def __post_init__(self) -> None:
        for field in fields(type(self)):
            if field.name == "confidence_bands":
                if self.confidence_bands != CONFIDENCE_BANDS:
                    raise OrganizedConflictAnalysisError(
                        "organized_conflict_analysis_policy_not_locked"
                    )
                continue
            expected = ORGANIZED_CONFLICT_ANALYSIS_POLICY_VALUES[field.name]
            actual = getattr(self, field.name)
            if type(actual) is not int or actual != expected:
                raise OrganizedConflictAnalysisError(
                    "organized_conflict_analysis_policy_not_locked"
                )


def default_organized_conflict_analysis_policy() -> OrganizedConflictAnalysisPolicy:
    """Return the one locked analysis policy value."""

    _LOG.info(
        "organized_conflict_analysis_policy_loaded policy_version=%s window_ticks=%s",
        ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION,
        ORGANIZED_CONFLICT_ANALYSIS_POLICY_VALUES["window_ticks"],
    )
    return OrganizedConflictAnalysisPolicy()
