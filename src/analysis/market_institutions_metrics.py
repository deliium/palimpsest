"""Four detached market-like institution metric families (catalog 204 -> 208)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

from analysis.market_institutions_analysis import MarketInstitutionsAnalysis
from analysis.market_institutions_contract import (
    MARKET_FORBIDDEN_KEYS,
    MARKET_INSTITUTIONS_ANALYSIS_POLICY_VERSION,
    MarketAlignment,
    MarketCoverage,
    MarketInstitutionsError,
    MarketLineageStatus,
    MarketVenueStatus,
)
from analysis.market_institutions_rows import MarketVenueRow
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
    "assemble_market_institution_metrics",
    "compute_market_expectation_structure",
    "compute_market_role_structure",
    "compute_market_venue_persistence",
    "compute_market_venue_recurrence",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)
_POLICY_TOKEN: Final[str] = "market-institutions"


def _require(analysis: object) -> MarketInstitutionsAnalysis:
    if type(analysis) is not MarketInstitutionsAnalysis:
        raise MarketInstitutionsError("market_institutions_metrics_invalid_analysis")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _milli(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return numerator * 1_000 // denominator


def _state(coverage: MarketCoverage) -> str:
    if coverage is MarketCoverage.MISSING:
        return "unknown"
    if coverage is MarketCoverage.PARTIAL:
        return "partial"
    return "present"


def _reject_forbidden_fields(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in MARKET_FORBIDDEN_KEYS:
            raise MarketInstitutionsError(
                "market_institutions_metrics_forbidden_key"
            )


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
            source_kind="market_institutions_analysis",
            source_ids=(
                run_id,
                input_revision,
                MARKET_INSTITUTIONS_ANALYSIS_POLICY_VERSION,
                _POLICY_TOKEN,
            ),
            notes_code="detached_market_analysis",
        ),
    )


def _ids(run_id: str, input_revision: str) -> tuple[str, str]:
    return (
        require_stable_id("run_id", run_id),
        require_stable_id("input_revision", input_revision),
    )


def _latest_venue_rows(
    analysis: MarketInstitutionsAnalysis,
) -> tuple[MarketVenueRow, ...]:
    latest: dict[str, MarketVenueRow] = {}
    for row in analysis.venues:
        current = latest.get(row.venue_id)
        if current is None or row.window_index >= current.window_index:
            latest[row.venue_id] = row
    return tuple(latest.values())


def compute_market_venue_recurrence(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Describe venue recurrence counts and integer milli ratios."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.evidence_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.MARKET_VENUE_RECURRENCE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    latest = _latest_venue_rows(rows)
    recurrence = [row.recurrence_milli for row in latest]
    complete_venues = sum(
        1
        for row in latest
        if row.coverage is MarketCoverage.COMPLETE
        and row.status is not MarketVenueStatus.DORMANT
    )
    active_venues = [
        row for row in latest if row.status is not MarketVenueStatus.DORMANT
    ]
    values = {
        "window_tick": rows.window_tick,
        "venue_count": len({row.venue_id for row in rows.venues}),
        "gathering_count": len(rows.gatherings),
        "recurring_venue_count": sum(
            1
            for row in active_venues
            if row.active_window_count >= 2
        ),
        "persistent_venue_count": sum(
            1
            for row in active_venues
            if row.status is MarketVenueStatus.MARKET_LIKE_PERSISTENT
        ),
        "mean_recurrence_milli": (
            0 if not recurrence else sum(recurrence) // len(recurrence)
        ),
        "max_recurrence_milli": max(recurrence, default=0),
        "multi_party_gathering_count": sum(
            1 for row in rows.gatherings if row.distinct_party_count >= 2
        ),
        "coverage": rows.evidence_coverage.value,
    }
    return _document(
        MetricFamilyId.MARKET_VENUE_RECURRENCE,
        state=state,
        observed=complete_venues,
        expected=len(active_venues),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_market_venue_persistence(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Describe forward-only market lineage status counts."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.lineage_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.MARKET_VENUE_PERSISTENCE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    counts = {
        status: sum(1 for row in rows.lineage if row.status is status)
        for status in MarketLineageStatus
    }
    complete = sum(
        1
        for row in rows.lineage
        if row.coverage is MarketCoverage.COMPLETE
    )
    values = {
        "window_tick": rows.window_tick,
        "venue_count": len({row.venue_id for row in rows.venues}),
        "active_venue_count": len(
            {
                row.venue_id
                for row in rows.venues
                if row.status is not MarketVenueStatus.DORMANT
            }
        ),
        "emerged_count": counts[MarketLineageStatus.EMERGED],
        "continued_count": counts[MarketLineageStatus.CONTINUED],
        "transformed_count": counts[MarketLineageStatus.TRANSFORMED],
        "split_count": counts[MarketLineageStatus.SPLIT],
        "merge_count": counts[MarketLineageStatus.MERGE],
        "dissolved_count": counts[MarketLineageStatus.DISSOLVED],
        "rerouted_count": sum(1 for row in rows.lineage if row.rerouted),
        "sustained_market_count": sum(1 for row in rows.lineage if row.sustained),
        "coverage": rows.lineage_coverage.value,
    }
    return _document(
        MetricFamilyId.MARKET_VENUE_PERSISTENCE,
        state=state,
        observed=complete,
        expected=len(rows.lineage),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_market_expectation_structure(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Describe detached owner expectation rows without scoring persistence."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.expectation_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.MARKET_EXPECTATION_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    alignment = {
        value: sum(1 for row in rows.expectations if row.alignment is value)
        for value in MarketAlignment
    }
    complete = sum(
        1
        for row in rows.expectations
        if row.coverage is MarketCoverage.COMPLETE
    )
    values = {
        "window_tick": rows.window_tick,
        "expectation_row_count": len(rows.expectations),
        "expected_venue_count": len(
            {
                row.venue_id
                for row in rows.expectations
                if row.expectation in {"expected", "strong"}
            }
        ),
        "scheduled_venue_count": len(
            {
                row.venue_id
                for row in rows.expectations
                if row.cadence in {"recurring_interval", "periodic_window"}
            }
        ),
        "record_anchor_count": len({row.anchor_token for row in rows.records}),
        "consistent_count": alignment[MarketAlignment.CONSISTENT],
        "unresolved_count": alignment[MarketAlignment.UNRESOLVED],
        "inconsistent_count": alignment[MarketAlignment.INCONSISTENT],
        "not_applicable_count": alignment[MarketAlignment.NOT_APPLICABLE],
        "expectation_coverage": rows.expectation_coverage.value,
        "record_coverage": rows.record_coverage.value,
    }
    return _document(
        MetricFamilyId.MARKET_EXPECTATION_STRUCTURE,
        state=state,
        observed=complete,
        expected=len(rows.expectations),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_market_role_structure(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Describe detached owner role rows; brokers are never actors."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.role_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.MARKET_ROLE_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    complete = sum(
        1 for row in rows.roles if row.coverage is MarketCoverage.COMPLETE
    )
    values = {
        "window_tick": rows.window_tick,
        "role_row_count": len(rows.roles),
        "broker_like_count": sum(
            1 for row in rows.roles if row.role_kind == "broker"
        ),
        "recognized_role_count": sum(1 for row in rows.roles if row.recognized),
        "claimed_role_count": sum(
            1 for row in rows.roles if row.role_basis == "claimed"
        ),
        "venue_with_role_count": len({row.venue_id for row in rows.roles}),
        "mean_counterparty_count_milli": (
            0
            if not rows.roles
            else sum(row.counterparty_count for row in rows.roles)
            * 1_000
            // len(rows.roles)
        ),
        "role_coverage": rows.role_coverage.value,
    }
    return _document(
        MetricFamilyId.MARKET_ROLE_STRUCTURE,
        state=state,
        observed=complete,
        expected=len(rows.roles),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def assemble_market_institution_metrics(
    analysis: MarketInstitutionsAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> tuple[MetricDocument, ...]:
    """Return the four market families in catalog order."""

    return (
        compute_market_venue_recurrence(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_market_venue_persistence(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_market_expectation_structure(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_market_role_structure(
            analysis, run_id=run_id, input_revision=input_revision
        ),
    )
