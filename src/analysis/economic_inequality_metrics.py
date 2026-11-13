"""Eight detached economic-inequality metric families (catalog 220 -> 228)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final, cast

from analysis.economic_inequality_analysis import EconomicInequalityAnalysis
from analysis.economic_inequality_contract import (
    ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION,
    ECONOMIC_INEQUALITY_FORBIDDEN_KEYS,
    EconomicInequalityAvailability,
    EconomicInequalityCoverage,
    EconomicInequalityDimension,
    EconomicInequalityError,
    EconomicInequalityMeasure,
    EconomicInequalityTrend,
)
from analysis.economic_inequality_policy import (
    default_economic_inequality_analysis_policy,
)
from analysis.economic_inequality_rows import (
    EconomicCohortRow,
    EconomicDimensionWindowRow,
    EconomicSocietyRow,
)
from analysis.inequality_indices import (
    inequality_distribution_summary,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_credit_relationship_inequality",
    "compute_economic_inequality_cohorts",
    "compute_economic_inequality_society_comparison",
    "compute_infrastructure_access_inequality",
    "compute_organizational_resource_control_inequality",
    "compute_productive_tool_access_inequality",
    "compute_resource_possession_inequality",
    "compute_storage_access_inequality",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)
_POLICY_TOKEN: Final[str] = "economic-inequality"


def _require(analysis: object) -> EconomicInequalityAnalysis:
    if type(analysis) is not EconomicInequalityAnalysis:
        raise EconomicInequalityError("economic_inequality_invalid_input")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _reject_forbidden(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in ECONOMIC_INEQUALITY_FORBIDDEN_KEYS:
            raise EconomicInequalityError("economic_inequality_forbidden_key")


def _coverage_token(coverage: EconomicInequalityCoverage) -> str:
    return coverage.value


def _availability_token(
    availability: EconomicInequalityAvailability,
) -> str:
    return availability.value


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    if state == "unknown":
        availability = MetricAvailability.UNKNOWN
        coverage = _ABSENT_COVERAGE
        payload: dict[str, object] = {}
    else:
        availability = (
            MetricAvailability.PRESENT
            if state == "present"
            else MetricAvailability.PARTIAL
        )
        coverage = MetricCoverage(
            observed=observed,
            expected=expected,
            ratio=_ratio(observed, expected),
        )
        _reject_forbidden(values)
        payload = dict(values)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=payload,
        provenance=MetricProvenance(
            source_kind="economic_inequality_analysis",
            source_ids=(
                run_id,
                input_revision,
                ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION,
                _POLICY_TOKEN,
                notes_code,
            ),
        ),
    )


def _primary_measure(
    dimension: EconomicInequalityDimension,
) -> EconomicInequalityMeasure:
    if dimension is EconomicInequalityDimension.RESOURCE_POSSESSION:
        return EconomicInequalityMeasure.OBSERVED_ITEM_COUNT
    if dimension is EconomicInequalityDimension.PRODUCTIVE_TOOL_ACCESS:
        return EconomicInequalityMeasure.OBSERVED_TOOL_COUNT
    if dimension is EconomicInequalityDimension.INFRASTRUCTURE_ACCESS:
        return EconomicInequalityMeasure.ACCESSIBLE_INFRASTRUCTURE_COUNT
    if dimension is EconomicInequalityDimension.STORAGE_ACCESS:
        return EconomicInequalityMeasure.ACCESSIBLE_STORAGE_COUNT
    if dimension is EconomicInequalityDimension.CREDIT_RELATIONSHIP:
        return EconomicInequalityMeasure.CLAIMED_PRINCIPAL_QUANTITY
    return EconomicInequalityMeasure.CLAIMED_RESOURCE_CONTROL_COUNT


def _trend(
    rows: Sequence[EconomicDimensionWindowRow],
    *,
    threshold_milli: int,
) -> EconomicInequalityTrend:
    ginis = [
        row.gini_milli for row in rows if row.gini_milli is not None
    ]
    if len(ginis) < 2:
        return EconomicInequalityTrend.UNAVAILABLE
    current, previous = ginis[-1], ginis[-2]
    if current - previous >= threshold_milli:
        return EconomicInequalityTrend.RISING
    if previous - current >= threshold_milli:
        return EconomicInequalityTrend.FALLING
    return EconomicInequalityTrend.STABLE


def _dimension_state(
    latest: EconomicDimensionWindowRow | None,
) -> str:
    if latest is None:
        return "unknown"
    if latest.availability is not EconomicInequalityAvailability.AVAILABLE:
        return "unknown"
    if latest.coverage is EconomicInequalityCoverage.PARTIAL:
        return "partial"
    return "present"


def _compute_dimension(
    analysis: EconomicInequalityAnalysis,
    dimension: EconomicInequalityDimension,
    family: MetricFamilyId,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    measure = _primary_measure(dimension)
    rows = sorted(
        (
            row
            for row in analysis.dimension_rows
            if row.dimension is dimension and row.measure is measure
        ),
        key=lambda row: row.window_index,
    )
    latest = rows[-1] if rows else None
    state = _dimension_state(latest)
    if state == "unknown":
        return _document(
            family,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code=(
                "economic_inequality_insufficient_samples"
                if latest is not None
                else "economic_inequality_unavailable"
            ),
        )
    assert latest is not None
    threshold = default_economic_inequality_analysis_policy().trend_threshold_milli
    values = {
        "economic_inequality_window_tick": latest.window_tick,
        "window_count": analysis.window_count,
        "owner_count": latest.owner_count,
        "observed_owner_count": latest.observed_owner_count,
        "gini_latest": latest.gini_milli,
        "theil_t_latest": latest.theil_t_milli,
        "atkinson_eps_1_latest": latest.atkinson_eps_1_milli,
        "top_share_milli_latest": latest.top_share_milli,
        "median_latest": latest.median,
        "iqr_latest": latest.iqr,
        "trend_direction": _trend(rows, threshold_milli=threshold).value,
        "coverage": _coverage_token(latest.coverage),
        "availability": _availability_token(latest.availability),
    }
    return _document(
        family,
        state=state,
        observed=latest.observed_owner_count,
        expected=latest.owner_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="economic_inequality_dimension_ok",
    )


def compute_resource_possession_inequality(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    return _compute_dimension(
        _require(analysis),
        EconomicInequalityDimension.RESOURCE_POSSESSION,
        MetricFamilyId.RESOURCE_POSSESSION_INEQUALITY,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_productive_tool_access_inequality(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    return _compute_dimension(
        _require(analysis),
        EconomicInequalityDimension.PRODUCTIVE_TOOL_ACCESS,
        MetricFamilyId.PRODUCTIVE_TOOL_ACCESS_INEQUALITY,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_infrastructure_access_inequality(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    return _compute_dimension(
        _require(analysis),
        EconomicInequalityDimension.INFRASTRUCTURE_ACCESS,
        MetricFamilyId.INFRASTRUCTURE_ACCESS_INEQUALITY,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_storage_access_inequality(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    return _compute_dimension(
        _require(analysis),
        EconomicInequalityDimension.STORAGE_ACCESS,
        MetricFamilyId.STORAGE_ACCESS_INEQUALITY,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_credit_relationship_inequality(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    return _compute_dimension(
        _require(analysis),
        EconomicInequalityDimension.CREDIT_RELATIONSHIP,
        MetricFamilyId.CREDIT_RELATIONSHIP_INEQUALITY,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_organizational_resource_control_inequality(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    return _compute_dimension(
        _require(analysis),
        EconomicInequalityDimension.ORGANIZATIONAL_RESOURCE_CONTROL,
        MetricFamilyId.ORGANIZATIONAL_RESOURCE_CONTROL_INEQUALITY,
        run_id=run_id,
        input_revision=input_revision,
    )


def _latest_window_value(rows: Sequence[EconomicCohortRow | EconomicSocietyRow]) -> int:
    return max((row.window_index for row in rows), default=-1)


def _latest_rows(
    rows: Sequence[EconomicCohortRow | EconomicSocietyRow],
) -> tuple[EconomicCohortRow | EconomicSocietyRow, ...]:
    latest = _latest_window_value(rows)
    return tuple(row for row in rows if row.window_index == latest)


def _gini_summary(values: Sequence[int]) -> tuple[int | None, int | None, int | None]:
    summary = inequality_distribution_summary(
        tuple(values), min_samples=4
    )
    if summary.status is not EconomicInequalityAvailability.AVAILABLE:
        return None, None, None
    assert summary.median is not None
    assert summary.iqr is not None
    assert summary.maximum is not None
    assert summary.minimum is not None
    return summary.median, summary.iqr, summary.maximum - summary.minimum


def compute_economic_inequality_cohorts(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    analysis = _require(analysis)
    rows = analysis.cohort_rows
    latest = cast(
        tuple[EconomicCohortRow, ...], _latest_rows(rows)
    )
    cohort_tokens = {row.cohort_token for row in rows}
    comparable = {
        row.cohort_token
        for row in latest
        if row.comparable and row.gini_milli is not None
    }
    if not rows:
        return _document(
            MetricFamilyId.ECONOMIC_INEQUALITY_COHORTS,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="economic_inequality_missing_cohort_membership",
        )
    ginis = [
        row.gini_milli for row in latest if row.gini_milli is not None
    ]
    median, iqr, spread = _gini_summary(ginis)
    if median is None:
        return _document(
            MetricFamilyId.ECONOMIC_INEQUALITY_COHORTS,
            state="unknown",
            observed=len(comparable),
            expected=len(cohort_tokens),
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="economic_inequality_insufficient_cohorts",
        )
    trends = [row.trend for row in latest]
    values = {
        "economic_inequality_window_tick": (
            max((row.window_index for row in latest), default=0) + 1
        )
        * default_economic_inequality_analysis_policy().window_ticks
        - 1,
        "cohort_count": len(cohort_tokens),
        "comparable_cohort_count": len(comparable),
        "gini_median_milli": median,
        "gini_iqr_milli": iqr,
        "gini_range_milli": spread,
        "widening_count": trends.count(EconomicInequalityTrend.RISING),
        "narrowing_count": trends.count(EconomicInequalityTrend.FALLING),
        "stable_count": trends.count(EconomicInequalityTrend.STABLE),
        "insufficient_count": sum(
            1
            for row in latest
            if row.availability
            is EconomicInequalityAvailability.INSUFFICIENT_SAMPLES
        ),
        "coverage": analysis.comparison_coverage.value,
        "availability": (
            EconomicInequalityAvailability.AVAILABLE.value
            if len(comparable) >= 4
            else EconomicInequalityAvailability.INSUFFICIENT_SAMPLES.value
        ),
    }
    state = (
        "present"
        if analysis.comparison_coverage is EconomicInequalityCoverage.COMPLETE
        else "partial"
    )
    return _document(
        MetricFamilyId.ECONOMIC_INEQUALITY_COHORTS,
        state=state,
        observed=len(comparable),
        expected=len(cohort_tokens),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="economic_inequality_cohorts_ok",
    )


def compute_economic_inequality_society_comparison(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    analysis = _require(analysis)
    rows = analysis.society_rows
    latest = cast(
        tuple[EconomicSocietyRow, ...], _latest_rows(rows)
    )
    tokens = {row.society_token for row in rows}
    comparable = {
        row.society_token
        for row in latest
        if row.comparable and row.gini_milli is not None
    }
    if not rows:
        return _document(
            MetricFamilyId.ECONOMIC_INEQUALITY_SOCIETY_COMPARISON,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="economic_inequality_missing_society_membership",
        )
    ginis = [
        row.gini_milli for row in latest if row.gini_milli is not None
    ]
    median, iqr, spread = _gini_summary(ginis)
    if median is None:
        return _document(
            MetricFamilyId.ECONOMIC_INEQUALITY_SOCIETY_COMPARISON,
            state="unknown",
            observed=len(comparable),
            expected=len(tokens),
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="economic_inequality_insufficient_societies",
        )
    pooled = inequality_distribution_summary(
        tuple(ginis), min_samples=4
    ).median
    values = {
        "economic_inequality_window_tick": (
            max((row.window_index for row in latest), default=0) + 1
        )
        * default_economic_inequality_analysis_policy().window_ticks
        - 1,
        "society_count": len(tokens),
        "comparable_society_count": len(comparable),
        "gini_median_milli": median,
        "gini_iqr_milli": iqr,
        "gini_range_milli": spread,
        "above_pooled_median_count": sum(
            1 for gini in ginis if pooled is not None and gini > pooled
        ),
        "below_pooled_median_count": sum(
            1 for gini in ginis if pooled is not None and gini < pooled
        ),
        "equal_pooled_median_count": sum(
            1 for gini in ginis if pooled is not None and gini == pooled
        ),
        "overlap_member_count": analysis.overlap_member_count,
        "coverage": analysis.comparison_coverage.value,
        "availability": (
            EconomicInequalityAvailability.AVAILABLE.value
            if len(comparable) >= 4
            else EconomicInequalityAvailability.INSUFFICIENT_SAMPLES.value
        ),
    }
    state = (
        "present"
        if analysis.comparison_coverage is EconomicInequalityCoverage.COMPLETE
        else "partial"
    )
    return _document(
        MetricFamilyId.ECONOMIC_INEQUALITY_SOCIETY_COMPARISON,
        state=state,
        observed=len(comparable),
        expected=len(tokens),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="economic_inequality_societies_ok",
    )
