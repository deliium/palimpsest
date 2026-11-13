"""Cohort and detached-society comparisons over possession distributions.

Each stratum keeps its own distribution and Gini. Comparisons report distribution
statistics and a closed longitudinal direction; they never rank strata, label a
best or worst, or produce a composite score.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.economic_inequality_contract import (
    EconomicInequalityAvailability,
    EconomicInequalityCoverage,
    EconomicInequalityError,
    EconomicInequalityTrend,
    economic_inequality_cohort_token,
)
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
    default_economic_inequality_analysis_policy,
)
from analysis.economic_inequality_rows import (
    EconomicCohortMembership,
    EconomicCohortRow,
    EconomicPossessionRow,
    EconomicSocietyMembership,
    EconomicSocietyRow,
)
from analysis.inequality_indices import (
    inequality_distribution_summary,
    quantized_gini,
)

__all__ = [
    "EconomicComparisonResult",
    "compare_economic_inequality_strata",
    "trend_direction",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.comparisons"
)


@dataclass(frozen=True, slots=True)
class EconomicComparisonResult:
    """Bounded cohort and society comparison rows with coverage."""

    cohort_rows: tuple[EconomicCohortRow, ...] = ()
    society_rows: tuple[EconomicSocietyRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: EconomicInequalityCoverage = EconomicInequalityCoverage.MISSING
    overlap_member_count: int = 0
    comparable_cohort_count: int = 0
    comparable_society_count: int = 0

    def __post_init__(self) -> None:
        for name in ("cohort_rows", "society_rows", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicInequalityError("economic_inequality_invalid_row")
        if type(self.coverage) is not EconomicInequalityCoverage:
            raise EconomicInequalityError("economic_inequality_invalid_row")
        for name in (
            "overlap_member_count",
            "comparable_cohort_count",
            "comparable_society_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicInequalityError("economic_inequality_invalid_row")


def trend_direction(
    current: int | None,
    previous: int | None,
    *,
    threshold_milli: int,
) -> EconomicInequalityTrend:
    """Closed direction over two quantized Gini values."""

    if current is None or previous is None:
        return EconomicInequalityTrend.UNAVAILABLE
    if current - previous >= threshold_milli:
        return EconomicInequalityTrend.RISING
    if previous - current >= threshold_milli:
        return EconomicInequalityTrend.FALLING
    return EconomicInequalityTrend.STABLE


def _latest_values(
    possession_rows: Sequence[EconomicPossessionRow],
) -> dict[int, dict[str, int]]:
    latest: dict[tuple[str, int], EconomicPossessionRow] = {}
    for row in possession_rows:
        key = (row.owner_token, row.window_index)
        previous = latest.get(key)
        if previous is None or row.tick > previous.tick:
            latest[key] = row
    values: dict[int, dict[str, int]] = {}
    for (owner_token, window_index), row in latest.items():
        values.setdefault(window_index, {})[owner_token] = (
            row.observed_item_count
        )
    return values


def _gini_or_none(values: Sequence[int], min_samples: int) -> int | None:
    if len(values) < min_samples:
        return None
    return quantized_gini(tuple(values))


def compare_economic_inequality_strata(
    *,
    possession_rows: Sequence[EconomicPossessionRow] = (),
    cohort_memberships: Sequence[EconomicCohortMembership] = (),
    society_memberships: Sequence[EconomicSocietyMembership] = (),
    policy: EconomicInequalityAnalysisPolicy | None = None,
) -> EconomicComparisonResult:
    """Compose cohort and society comparisons from per-owner possession."""

    active = (
        default_economic_inequality_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not EconomicInequalityAnalysisPolicy:
        raise EconomicInequalityError("economic_inequality_invalid_policy")
    for family in (possession_rows, cohort_memberships, society_memberships):
        if isinstance(family, (str, bytes)) or not isinstance(family, Sequence):
            raise EconomicInequalityError("economic_inequality_invalid_input")
    if (
        isinstance(possession_rows, (str, bytes))
        or not isinstance(possession_rows, Sequence)
    ):
        raise EconomicInequalityError("economic_inequality_invalid_input")

    values_by_window = _latest_values(possession_rows)
    if not values_by_window:
        return EconomicComparisonResult(
            coverage=EconomicInequalityCoverage.MISSING,
            notices=("economic_inequality_missing_comparison_evidence",),
        )

    coverage = EconomicInequalityCoverage.COMPLETE
    notices: list[str] = []

    generation_of = {
        membership.owner_token: membership.generation_index
        for membership in cohort_memberships
    }
    observed_owners = {
        owner for owners in values_by_window.values() for owner in owners
    }
    unresolved = observed_owners - set(generation_of)
    if unresolved:
        coverage = EconomicInequalityCoverage.PARTIAL
        notices.append("economic_inequality_missing_cohort_membership")

    cohort_rows: list[EconomicCohortRow] = []
    previous_gini: dict[str, int | None] = {}
    comparable_cohorts: set[str] = set()
    for window_index in sorted(values_by_window):
        owners = values_by_window[window_index]
        groups: dict[int, list[int]] = {}
        for owner, value in owners.items():
            generation = generation_of.get(owner)
            if generation is None:
                continue
            groups.setdefault(generation, []).append(value)
        for generation in sorted(groups):
            vector = tuple(sorted(groups[generation]))
            if len(vector) < active.min_distribution_samples:
                continue
            token = economic_inequality_cohort_token(generation)
            summary = inequality_distribution_summary(
                vector, min_samples=active.min_distribution_samples
            )
            gini = _gini_or_none(vector, active.min_distribution_samples)
            trend = trend_direction(
                gini,
                previous_gini.get(token),
                threshold_milli=active.trend_threshold_milli,
            )
            previous_gini[token] = gini
            comparable_cohorts.add(token)
            cohort_rows.append(
                EconomicCohortRow(
                    cohort_token=token,
                    generation_index=generation,
                    window_index=window_index,
                    owner_count=len(vector),
                    comparable=gini is not None,
                    gini_milli=gini,
                    median_milli=summary.median,
                    iqr_milli=summary.iqr,
                    trend=trend,
                    availability=(
                        EconomicInequalityAvailability.AVAILABLE
                        if gini is not None
                        else EconomicInequalityAvailability.INSUFFICIENT_SAMPLES
                    ),
                )
            )
    if not comparable_cohorts:
        notices.append("economic_inequality_insufficient_cohorts")
        _LOG.warning("economic_inequality_insufficient_cohorts")

    membership_counts: dict[str, int] = {}
    society_windows: dict[tuple[str, int], set[str]] = {}
    for membership in society_memberships:
        membership_counts[membership.owner_token] = (
            membership_counts.get(membership.owner_token, 0) + 1
        )
        for window_index in membership.window_indexes:
            society_windows.setdefault(
                (membership.society_token, window_index), set()
            ).add(membership.owner_token)
    overlap_member_count = sum(
        1 for count in membership_counts.values() if count > 1
    )

    society_rows: list[EconomicSocietyRow] = []
    previous_society_gini: dict[str, int | None] = {}
    comparable_societies: set[str] = set()
    for (society_token, window_index), members in sorted(
        society_windows.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        owners = values_by_window.get(window_index, {})
        vector = tuple(
            sorted(owners[owner] for owner in members if owner in owners)
        )
        if len(vector) < active.min_distribution_samples:
            continue
        summary = inequality_distribution_summary(
            vector, min_samples=active.min_distribution_samples
        )
        gini = _gini_or_none(vector, active.min_distribution_samples)
        trend = trend_direction(
            gini,
            previous_society_gini.get(society_token),
            threshold_milli=active.trend_threshold_milli,
        )
        previous_society_gini[society_token] = gini
        comparable_societies.add(society_token)
        society_rows.append(
            EconomicSocietyRow(
                society_token=society_token,
                window_index=window_index,
                owner_count=len(vector),
                comparable=gini is not None,
                gini_milli=gini,
                median_milli=summary.median,
                iqr_milli=summary.iqr,
                trend=trend,
                availability=(
                    EconomicInequalityAvailability.AVAILABLE
                    if gini is not None
                    else EconomicInequalityAvailability.INSUFFICIENT_SAMPLES
                ),
            )
        )
    if not society_memberships:
        notices.append("economic_inequality_insufficient_societies")
        _LOG.warning("economic_inequality_insufficient_societies")

    cohort_rows.sort(key=lambda row: (row.window_index, row.cohort_token))
    society_rows.sort(key=lambda row: (row.window_index, row.society_token))
    _LOG.debug(
        "economic_inequality_comparisons cohorts=%d societies=%d "
        "overlap_members=%d",
        len(cohort_rows),
        len(society_rows),
        overlap_member_count,
    )
    _LOG.info(
        "economic_inequality_comparisons_complete cohorts=%d societies=%d",
        len(cohort_rows),
        len(society_rows),
    )
    return EconomicComparisonResult(
        cohort_rows=tuple(cohort_rows),
        society_rows=tuple(society_rows),
        notices=tuple(dict.fromkeys(notices)),
        coverage=coverage,
        overlap_member_count=overlap_member_count,
        comparable_cohort_count=len(comparable_cohorts),
        comparable_society_count=len(comparable_societies),
    )
