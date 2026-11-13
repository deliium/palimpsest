"""Deterministic per-window distributions for the six inequality dimensions."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.economic_inequality_contract import (
    EconomicInequalityAvailability,
    EconomicInequalityCoverage,
    EconomicInequalityDimension,
    EconomicInequalityError,
    EconomicInequalityMeasure,
)
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
    default_economic_inequality_analysis_policy,
)
from analysis.economic_inequality_rows import (
    EconomicAccessRow,
    EconomicControlClaimRow,
    EconomicCreditClaimRow,
    EconomicDimensionWindowRow,
    EconomicPossessionRow,
)
from analysis.inequality_indices import (
    inequality_distribution_summary,
    quantized_atkinson_eps_1,
    quantized_gini,
    quantized_theil_t,
    quantized_top_share,
)

__all__ = [
    "EconomicDetectionResult",
    "detect_economic_inequality_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.detection"
)

_DIMENSION_MEASURES: Final[
    tuple[tuple[EconomicInequalityDimension, EconomicInequalityMeasure, str], ...]
] = (
    (
        EconomicInequalityDimension.RESOURCE_POSSESSION,
        EconomicInequalityMeasure.OBSERVED_ITEM_COUNT,
        "observed_item_count",
    ),
    (
        EconomicInequalityDimension.PRODUCTIVE_TOOL_ACCESS,
        EconomicInequalityMeasure.OBSERVED_TOOL_COUNT,
        "observed_tool_count",
    ),
    (
        EconomicInequalityDimension.INFRASTRUCTURE_ACCESS,
        EconomicInequalityMeasure.ACCESSIBLE_INFRASTRUCTURE_COUNT,
        "accessible_infrastructure_count",
    ),
    (
        EconomicInequalityDimension.STORAGE_ACCESS,
        EconomicInequalityMeasure.ACCESSIBLE_STORAGE_COUNT,
        "accessible_storage_count",
    ),
    (
        EconomicInequalityDimension.CREDIT_RELATIONSHIP,
        EconomicInequalityMeasure.CLAIMED_PRINCIPAL_QUANTITY,
        "claimed_principal_quantity",
    ),
    (
        EconomicInequalityDimension.CREDIT_RELATIONSHIP,
        EconomicInequalityMeasure.OBSERVED_REPAYMENT_QUANTITY,
        "observed_repayment_quantity",
    ),
    (
        EconomicInequalityDimension.CREDIT_RELATIONSHIP,
        EconomicInequalityMeasure.CLAIMED_RELATIONSHIP_COUNT,
        "claimed_relationship_count",
    ),
    (
        EconomicInequalityDimension.ORGANIZATIONAL_RESOURCE_CONTROL,
        EconomicInequalityMeasure.CLAIMED_RESOURCE_CONTROL_COUNT,
        "claimed_resource_control_count",
    ),
    (
        EconomicInequalityDimension.ORGANIZATIONAL_RESOURCE_CONTROL,
        EconomicInequalityMeasure.CLAIMED_STORAGE_CONTROL_COUNT,
        "claimed_storage_control_count",
    ),
)


@dataclass(frozen=True, slots=True)
class EconomicDetectionResult:
    """Bounded dimension rows plus coverage and structural notices."""

    rows: tuple[EconomicDimensionWindowRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: EconomicInequalityCoverage = EconomicInequalityCoverage.MISSING
    window_count: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.rows, (str, bytes)) or not isinstance(self.rows, tuple):
            raise EconomicInequalityError("economic_inequality_invalid_row")
        if isinstance(self.notices, (str, bytes)) or not isinstance(
            self.notices, tuple
        ):
            raise EconomicInequalityError("economic_inequality_invalid_row")
        if type(self.coverage) is not EconomicInequalityCoverage:
            raise EconomicInequalityError("economic_inequality_invalid_row")
        if (
            isinstance(self.window_count, bool)
            or type(self.window_count) is not int
            or self.window_count < 0
        ):
            raise EconomicInequalityError("economic_inequality_invalid_row")


def _latest_by_owner(
    rows: Sequence[object],
) -> dict[tuple[str, int], object]:
    latest: dict[tuple[str, int], object] = {}
    for row in rows:
        key = (row.owner_token, row.window_index)  # type: ignore[attr-defined]
        previous = latest.get(key)
        if previous is None or row.tick > previous.tick:  # type: ignore[attr-defined]
            latest[key] = row
    return latest


def _source_rows(
    dimension: EconomicInequalityDimension,
    *,
    possession_rows: Sequence[EconomicPossessionRow],
    access_rows: Sequence[EconomicAccessRow],
    credit_rows: Sequence[EconomicCreditClaimRow],
    control_rows: Sequence[EconomicControlClaimRow],
) -> Sequence[object]:
    if dimension in {
        EconomicInequalityDimension.RESOURCE_POSSESSION,
        EconomicInequalityDimension.PRODUCTIVE_TOOL_ACCESS,
    }:
        return possession_rows
    if dimension in {
        EconomicInequalityDimension.INFRASTRUCTURE_ACCESS,
        EconomicInequalityDimension.STORAGE_ACCESS,
    }:
        return access_rows
    if dimension is EconomicInequalityDimension.CREDIT_RELATIONSHIP:
        return credit_rows
    return control_rows


def detect_economic_inequality_rows(
    *,
    possession_rows: Sequence[EconomicPossessionRow] = (),
    access_rows: Sequence[EconomicAccessRow] = (),
    credit_rows: Sequence[EconomicCreditClaimRow] = (),
    control_rows: Sequence[EconomicControlClaimRow] = (),
    policy: EconomicInequalityAnalysisPolicy | None = None,
) -> EconomicDetectionResult:
    """Build per-window, per-measure distribution rows deterministically."""

    active = (
        default_economic_inequality_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not EconomicInequalityAnalysisPolicy:
        raise EconomicInequalityError("economic_inequality_invalid_policy")

    for family in (possession_rows, access_rows, credit_rows, control_rows):
        if isinstance(family, (str, bytes)) or not isinstance(family, Sequence):
            raise EconomicInequalityError("economic_inequality_invalid_input")

    rows: list[EconomicDimensionWindowRow] = []
    coverage = EconomicInequalityCoverage.COMPLETE
    windows: set[int] = set()
    insufficient = 0
    excluded = 0
    vector_count = 0

    grouped: dict[
        tuple[EconomicInequalityDimension, EconomicInequalityMeasure],
        dict[int, dict[str, int]],
    ] = {}
    totals: dict[
        tuple[EconomicInequalityDimension, EconomicInequalityMeasure],
        dict[int, int],
    ] = {}
    partial_windows: set[tuple[EconomicInequalityDimension, int]] = set()

    for dimension, measure, attribute in _DIMENSION_MEASURES:
        source = _source_rows(
            dimension,
            possession_rows=possession_rows,
            access_rows=access_rows,
            credit_rows=credit_rows,
            control_rows=control_rows,
        )
        latest = _latest_by_owner(source)
        for (owner_token, window_index), row in latest.items():
            windows.add(window_index)
            totals.setdefault((dimension, measure), {}).setdefault(
                window_index, 0
            )
            totals[(dimension, measure)][window_index] += 1
            if dimension in {
                EconomicInequalityDimension.INFRASTRUCTURE_ACCESS,
                EconomicInequalityDimension.STORAGE_ACCESS,
            } and not row.location_known:  # type: ignore[attr-defined]
                excluded += 1
                partial_windows.add((dimension, window_index))
                coverage = EconomicInequalityCoverage.PARTIAL
                continue
            value = getattr(row, attribute)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicInequalityError(
                    "economic_inequality_out_of_range"
                )
            grouped.setdefault((dimension, measure), {}).setdefault(
                window_index, {}
            )[owner_token] = value

    for dimension, measure, _attribute in _DIMENSION_MEASURES:
        by_window = grouped.get((dimension, measure), {})
        expected_windows = totals.get((dimension, measure), {})
        for window_index in sorted(expected_windows):
            vector = tuple(sorted(by_window.get(window_index, {}).values()))
            vector_count += len(vector)
            summary = inequality_distribution_summary(
                vector, min_samples=active.min_distribution_samples
            )
            availability = summary.status
            if availability is EconomicInequalityAvailability.INSUFFICIENT_SAMPLES:
                insufficient += 1
            row_coverage = (
                EconomicInequalityCoverage.PARTIAL
                if (dimension, window_index) in partial_windows
                else EconomicInequalityCoverage.COMPLETE
            )
            if row_coverage is EconomicInequalityCoverage.PARTIAL:
                coverage = EconomicInequalityCoverage.PARTIAL
            rows.append(
                EconomicDimensionWindowRow(
                    dimension=dimension,
                    measure=measure,
                    window_index=window_index,
                    window_tick=(window_index + 1) * active.window_ticks - 1,
                    owner_count=expected_windows[window_index],
                    observed_owner_count=len(vector),
                    minimum=summary.minimum,
                    p25=summary.p25,
                    median=summary.median,
                    p75=summary.p75,
                    maximum=summary.maximum,
                    iqr=summary.iqr,
                    dispersion=summary.dispersion,
                    bin_shares_milli=summary.bin_shares_milli,
                    gini_milli=(
                        quantized_gini(vector)
                        if availability
                        is EconomicInequalityAvailability.AVAILABLE
                        else None
                    ),
                    theil_t_milli=(
                        quantized_theil_t(vector)
                        if availability
                        is EconomicInequalityAvailability.AVAILABLE
                        else None
                    ),
                    atkinson_eps_1_milli=(
                        quantized_atkinson_eps_1(vector)
                        if availability
                        is EconomicInequalityAvailability.AVAILABLE
                        else None
                    ),
                    top_share_milli=(
                        quantized_top_share(vector)
                        if availability
                        is EconomicInequalityAvailability.AVAILABLE
                        else None
                    ),
                    availability=availability,
                    coverage=row_coverage,
                )
            )

    rows.sort(
        key=lambda row: (
            row.window_index,
            row.dimension.value,
            row.measure.value,
        )
    )
    if insufficient:
        _LOG.warning(
            "economic_inequality_insufficient_samples count=%d", insufficient
        )
    if excluded:
        _LOG.warning(
            "economic_inequality_access_location_missing count=%d", excluded
        )
    _LOG.debug(
        "economic_inequality_detection_done windows=%d rows=%d values=%d",
        len(windows),
        len(rows),
        vector_count,
    )
    _LOG.info(
        "economic_inequality_detection_complete windows=%d rows=%d",
        len(windows),
        len(rows),
    )
    return EconomicDetectionResult(
        rows=tuple(rows),
        coverage=coverage,
        window_count=len(windows),
    )
