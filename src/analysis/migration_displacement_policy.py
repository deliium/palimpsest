"""Locked detached-analysis thresholds for migration displacement.

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
    "MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VALUES",
    "MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION",
    "MigrationDisplacementAnalysisPolicy",
    "MigrationDisplacementAnalysisPolicyError",
    "default_migration_displacement_analysis_policy",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.migration_displacement.policy"
)

MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION: Final[str] = (
    "migration-displacement-analysis.v1"
)

MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VALUES: Final[Mapping[str, object]] = (
    MappingProxyType(
        {
            "wave_window_ticks": 12,
            "max_wave_gap_ticks": 6,
            "min_wave_participants": 2,
            "min_wave_distinct_origins": 1,
            "min_wave_route_overlap": 1,
            "cause_window_ticks": 16,
            "min_cause_evidence": 1,
            "displacement_min_independent_causes": 1,
            "mixed_min_displacement_causes": 1,
            "mixed_min_opportunity_causes": 1,
            "integration_window_ticks": 32,
            "min_residence_ticks": 4,
            "cluster_window_ticks": 32,
            "min_cluster_members": 2,
            "max_candidates_per_run": 512,
            "max_pairs_per_run": 4096,
            "max_rows_per_family": 5000,
            "quantum": 0.000001,
        }
    )
)


class MigrationDisplacementAnalysisPolicyError(ValueError):
    """Stable-code analysis policy violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class MigrationDisplacementAnalysisPolicy:
    """Locked detached migration-displacement analysis policy."""

    version: str = MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION
    wave_window_ticks: int = 12
    max_wave_gap_ticks: int = 6
    min_wave_participants: int = 2
    min_wave_distinct_origins: int = 1
    min_wave_route_overlap: int = 1
    cause_window_ticks: int = 16
    min_cause_evidence: int = 1
    displacement_min_independent_causes: int = 1
    mixed_min_displacement_causes: int = 1
    mixed_min_opportunity_causes: int = 1
    integration_window_ticks: int = 32
    min_residence_ticks: int = 4
    cluster_window_ticks: int = 32
    min_cluster_members: int = 2
    max_candidates_per_run: int = 512
    max_pairs_per_run: int = 4096
    max_rows_per_family: int = 5000
    quantum: float = 0.000001

    def __post_init__(self) -> None:
        if self.version != MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION:
            _LOG.error(
                "migration_displacement_analysis_policy_rejected field=version "
                "reason_code=unsupported_policy"
            )
            raise MigrationDisplacementAnalysisPolicyError("unsupported_policy")
        for item in fields(type(self)):
            if item.name == "version":
                continue
            expected = MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VALUES[item.name]
            actual = getattr(self, item.name)
            if isinstance(expected, float):
                accepted = type(actual) is float and actual == expected
            else:
                accepted = type(actual) is int and actual == expected
            if not accepted:
                _LOG.error(
                    "migration_displacement_analysis_policy_rejected field=%s "
                    "reason_code=unsupported_policy",
                    item.name,
                )
                raise MigrationDisplacementAnalysisPolicyError("unsupported_policy")


def default_migration_displacement_analysis_policy() -> (
    MigrationDisplacementAnalysisPolicy
):
    """Return the one locked analysis policy value."""
    _LOG.debug(
        "migration_displacement_analysis_policy_loaded policy_version=%s "
        "wave_window_ticks=%s",
        MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION,
        MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VALUES["wave_window_ticks"],
    )
    return MigrationDisplacementAnalysisPolicy()
