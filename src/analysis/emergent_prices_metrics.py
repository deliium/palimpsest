"""Four detached emergent-price metric families (catalog 208 -> 212)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.emergent_prices_analysis import EmergentPricesAnalysis
from analysis.emergent_prices_contract import (
    EMERGENT_PRICES_ANALYSIS_POLICY_VERSION,
    PRICE_FORBIDDEN_KEYS,
    EmergentPriceAnalysisError,
    PriceAlignment,
    PriceCoverage,
    PriceDistributionStatus,
    PriceRelation,
    PriceUnitSource,
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
from world.identifiers import require_stable_id

__all__ = [
    "assemble_emergent_price_metrics",
    "compute_market_price_convergence",
    "compute_price_distribution_dispersion",
    "compute_price_expectation_structure",
    "compute_price_reference_unit_alignment",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.emergent_prices.metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)
_POLICY_TOKEN: Final[str] = "emergent-prices"


def _require(analysis: object) -> EmergentPricesAnalysis:
    if type(analysis) is not EmergentPricesAnalysis:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)



def _state(coverage: PriceCoverage) -> str:
    if coverage is PriceCoverage.MISSING:
        return "unknown"
    if coverage is PriceCoverage.PARTIAL:
        return "partial"
    return "present"


def _reject_forbidden_fields(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in PRICE_FORBIDDEN_KEYS:
            raise EmergentPriceAnalysisError("price_analysis_forbidden_key")


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
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
            observed=observed, expected=expected, ratio=_ratio(observed, expected)
        )
        _reject_forbidden_fields(values)
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
            source_kind="emergent_prices_analysis",
            source_ids=(
                run_id,
                input_revision,
                EMERGENT_PRICES_ANALYSIS_POLICY_VERSION,
                _POLICY_TOKEN,
            ),
            notes_code="detached_price_analysis",
        ),
    )


def _ids(run_id: str, input_revision: str) -> tuple[str, str]:
    return (
        require_stable_id("run_id", run_id),
        require_stable_id("input_revision", input_revision),
    )


def _coverage_of(rows: Sequence[object]) -> PriceCoverage:
    if not rows:
        return PriceCoverage.MISSING
    partial = any(
        getattr(row, "coverage", PriceCoverage.COMPLETE) is PriceCoverage.PARTIAL
        for row in rows
    )
    return PriceCoverage.PARTIAL if partial else PriceCoverage.COMPLETE


def compute_price_expectation_structure(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe owner expectation counts and integer confidence."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.expectation_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.PRICE_EXPECTATION_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    confidences = [row.confidence_milli for row in rows.expectations]
    complete = sum(
        1
        for row in rows.expectations
        if row.coverage is PriceCoverage.COMPLETE
    )
    values = {
        "window_tick": rows.window_tick,
        "expectation_row_count": len(rows.expectations),
        "strong_count": sum(
            1 for row in rows.expectations if row.level == "strong"
        ),
        "expected_count": sum(
            1 for row in rows.expectations if row.level == "expected"
        ),
        "weak_count": sum(
            1 for row in rows.expectations if row.level == "weak"
        ),
        "valuation_row_count": sum(
            1 for row in rows.expectations if row.valuation_reservation > 0
        ),
        "mean_confidence_milli": (
            0 if not confidences else sum(confidences) // len(confidences)
        ),
        "expectation_coverage": rows.expectation_coverage.value,
    }
    return _document(
        MetricFamilyId.PRICE_EXPECTATION_STRUCTURE,
        state=state,
        observed=complete,
        expected=len(rows.expectations),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_price_distribution_dispersion(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe distribution counts, IQR, and dispersion in integer milli."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.distribution_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.PRICE_DISTRIBUTION_DISPERSION,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    available = [
        row
        for row in rows.distributions
        if row.status is PriceDistributionStatus.AVAILABLE
    ]
    iqrs = [row.iqr_milli for row in available]
    dispersions = [row.dispersion_milli for row in available]
    values = {
        "window_tick": rows.window_tick,
        "distribution_count": len(rows.distributions),
        "completed_distribution_count": sum(
            1
            for row in rows.distributions
            if row.sample_source.value == "completed"
        ),
        "quoted_distribution_count": sum(
            1
            for row in rows.distributions
            if row.sample_source.value == "quoted"
        ),
        "available_count": len(available),
        "insufficient_count": sum(
            1
            for row in rows.distributions
            if row.status is PriceDistributionStatus.INSUFFICIENT_SAMPLES
        ),
        "mean_iqr_milli": 0 if not iqrs else sum(iqrs) // len(iqrs),
        "mean_dispersion_milli": (
            0 if not dispersions else sum(dispersions) // len(dispersions)
        ),
        "item_kind_count": len({row.item_kind for row in rows.distributions}),
        "unit_count": len({row.unit_kind for row in rows.distributions}),
        "distribution_coverage": rows.distribution_coverage.value,
    }
    return _document(
        MetricFamilyId.PRICE_DISTRIBUTION_DISPERSION,
        state=state,
        observed=sum(row.sample_count for row in available),
        expected=sum(row.sample_count for row in rows.distributions),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_price_reference_unit_alignment(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe unit sources and researcher-only alignment counts."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    coverage = _coverage_of(rows.units)
    state = _state(coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.PRICE_REFERENCE_UNIT_ALIGNMENT,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    complete = sum(
        1 for row in rows.units if row.coverage is PriceCoverage.COMPLETE
    )
    values = {
        "window_tick": rows.window_tick,
        "unit_row_count": len(rows.units),
        "owner_reference_count": sum(
            1
            for row in rows.units
            if row.unit_source is PriceUnitSource.OWNER_REFERENCE
        ),
        "observed_medium_count": sum(
            1
            for row in rows.units
            if row.unit_source is PriceUnitSource.OBSERVED_MEDIUM
        ),
        "exchange_counterpart_count": sum(
            1
            for row in rows.units
            if row.unit_source is PriceUnitSource.EXCHANGE_COUNTERPART
        ),
        "quoted_count": sum(
            1 for row in rows.units if row.unit_source is PriceUnitSource.QUOTED
        ),
        "consistent_count": sum(
            1
            for row in rows.units
            if row.unit_alignment is PriceAlignment.CONSISTENT
        ),
        "unresolved_count": sum(
            1
            for row in rows.units
            if row.unit_alignment is PriceAlignment.UNRESOLVED
        ),
        "inconsistent_count": sum(
            1
            for row in rows.units
            if row.unit_alignment is PriceAlignment.INCONSISTENT
        ),
        "unit_coverage": coverage.value,
    }
    return _document(
        MetricFamilyId.PRICE_REFERENCE_UNIT_ALIGNMENT,
        state=state,
        observed=complete,
        expected=len(rows.units),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_market_price_convergence(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe pairwise convergence counts and mean overlap only."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.relation_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.MARKET_PRICE_CONVERGENCE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    overlaps = [row.overlap_milli for row in rows.relations]
    values = {
        "window_tick": rows.window_tick,
        "relation_count": len(rows.relations),
        "converged_count": sum(
            1
            for row in rows.relations
            if row.relation is PriceRelation.CONVERGED
        ),
        "partially_converged_count": sum(
            1
            for row in rows.relations
            if row.relation is PriceRelation.PARTIALLY_CONVERGED
        ),
        "divergent_count": sum(
            1
            for row in rows.relations
            if row.relation is PriceRelation.DIVERGENT
        ),
        "insufficient_count": sum(
            1
            for row in rows.relations
            if row.relation is PriceRelation.INSUFFICIENT_EVIDENCE
        ),
        "mean_overlap_milli": (
            0 if not overlaps else sum(overlaps) // len(overlaps)
        ),
        "market_pair_count": len(
            {(row.group_a_token, row.group_b_token) for row in rows.relations}
        ),
        "relation_coverage": rows.relation_coverage.value,
    }
    return _document(
        MetricFamilyId.MARKET_PRICE_CONVERGENCE,
        state=state,
        observed=sum(
            1
            for row in rows.relations
            if row.coverage is PriceCoverage.COMPLETE
        ),
        expected=len(rows.relations),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def assemble_emergent_price_metrics(
    analysis: EmergentPricesAnalysis, *, run_id: str, input_revision: str
) -> tuple[MetricDocument, ...]:
    """Return the four price families in catalog order."""

    return (
        compute_price_expectation_structure(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_price_distribution_dispersion(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_price_reference_unit_alignment(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_market_price_convergence(
            analysis, run_id=run_id, input_revision=input_revision
        ),
    )
