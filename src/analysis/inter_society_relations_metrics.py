"""Four detached inter-society relation metric families (catalog 180 -> 184).

Additive beside existing ``inter_society_relation_lanes@1``. Counts, coverage,
availability, and window/comparison vectors only — never a civilization
relationship score.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Final

from analysis.inter_society_relations_contract import (
    INTER_SOCIETY_DOMAIN_KEYS,
    INTER_SOCIETY_RELATIONS_ANALYSIS_POLICY_VERSION,
    InterSocietyAvailability,
)
from analysis.inter_society_relations_detection import InterSocietyRelationsAnalysis
from analysis.inter_society_relations_layers import InterSocietyPairCandidate
from analysis.inter_society_relations_timeseries import (
    build_pair_window_series,
    compare_inter_society_pairs,
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
    "compute_inter_society_domain_evidence",
    "compute_inter_society_pair_comparison",
    "compute_inter_society_relation_structure",
    "compute_inter_society_relation_timeseries",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.inter_society_relations.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
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
        payload = values
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
            source_kind="inter_society_relations_analysis",
            source_ids=(
                run_id,
                input_revision,
                INTER_SOCIETY_RELATIONS_ANALYSIS_POLICY_VERSION,
            ),
            notes_code="detached_inter_society_relations_analysis",
        ),
    )


def _require(analysis: object) -> InterSocietyRelationsAnalysis:
    if type(analysis) is not InterSocietyRelationsAnalysis:
        raise ValueError("inter_society_relations_metrics: invalid_analysis")
    return analysis


def _state(analysis: InterSocietyRelationsAnalysis) -> str:
    if analysis.pair_count == 0:
        return "unknown"
    if any(pair.status == "partial" for pair in analysis.pairs):
        return "partial"
    return "present"


def compute_inter_society_relation_structure(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Pair inventory structure counts without a composite relationship score."""
    rows = _require(analysis)
    state = _state(rows)
    if state == "unknown":
        _LOG.debug("inter_society_relations_metric_empty family=structure")
        return _document(
            MetricFamilyId.INTER_SOCIETY_RELATION_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    status_counts = Counter(pair.status for pair in rows.pairs)
    overlap_pairs = sum(1 for pair in rows.pairs if pair.overlap_member_count > 0)
    values: dict[str, object] = {
        "pair_count": rows.pair_count,
        "status_observed": status_counts.get("observed", 0),
        "status_partial": status_counts.get("partial", 0),
        "status_empty": status_counts.get("empty", 0),
        "overlap_pair_count": overlap_pairs,
        "window_tick": rows.window_tick,
    }
    return _document(
        MetricFamilyId.INTER_SOCIETY_RELATION_STRUCTURE,
        state=state,
        observed=rows.pair_count,
        expected=rows.pair_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_inter_society_domain_evidence(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Per-domain availability histograms and event counts across pairs."""
    rows = _require(analysis)
    state = _state(rows)
    if state == "unknown":
        _LOG.debug("inter_society_relations_metric_empty family=domain_evidence")
        return _document(
            MetricFamilyId.INTER_SOCIETY_DOMAIN_EVIDENCE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    values: dict[str, object] = {"pair_count": rows.pair_count}
    for domain in sorted(INTER_SOCIETY_DOMAIN_KEYS):
        present = 0
        partial = 0
        absent = 0
        event_total = 0
        for pair in rows.pairs:
            panel = next(item for item in pair.panels if item.domain.value == domain)
            if panel.availability is InterSocietyAvailability.PRESENT:
                present += 1
            elif panel.availability is InterSocietyAvailability.PARTIAL:
                partial += 1
            else:
                absent += 1
            event_total += panel.event_count
        values[f"{domain}_present"] = present
        values[f"{domain}_partial"] = partial
        values[f"{domain}_absent"] = absent
        values[f"{domain}_event_count"] = event_total
    return _document(
        MetricFamilyId.INTER_SOCIETY_DOMAIN_EVIDENCE,
        state=state,
        observed=rows.pair_count,
        expected=rows.pair_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_inter_society_relation_timeseries(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Windowed series length and coverage — never a relationship trajectory score."""
    rows = _require(analysis)
    state = _state(rows)
    if state == "unknown":
        _LOG.debug("inter_society_relations_metric_empty family=timeseries")
        return _document(
            MetricFamilyId.INTER_SOCIETY_RELATION_TIMESERIES,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    series = build_pair_window_series(rows.pairs)
    window_points = sum(len(item.points) for item in series)
    values: dict[str, object] = {
        "pair_series_count": len(series),
        "window_point_count": window_points,
        "max_windows_per_pair": max((len(item.points) for item in series), default=0),
    }
    return _document(
        MetricFamilyId.INTER_SOCIETY_RELATION_TIMESERIES,
        state=state,
        observed=window_points,
        expected=max(window_points, 1),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_inter_society_pair_comparison(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
    left_pair: InterSocietyPairCandidate | None = None,
    right_pair: InterSocietyPairCandidate | None = None,
) -> MetricDocument:
    """Vectorial pair comparison counts; empty when fewer than two pairs."""
    rows = _require(analysis)
    if rows.pair_count < 2 and (left_pair is None or right_pair is None):
        _LOG.debug("inter_society_relations_metric_empty family=pair_comparison")
        return _document(
            MetricFamilyId.INTER_SOCIETY_PAIR_COMPARISON,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    left = left_pair or rows.pairs[0]
    right = right_pair or rows.pairs[1]
    view = compare_inter_society_pairs(left, right)
    values: dict[str, object] = {
        "domain_count": len(view.domain_deltas),
        "left_window_tick": view.left_window_tick,
        "right_window_tick": view.right_window_tick,
    }
    for domain, delta, left_av, right_av in view.domain_deltas:
        values[f"{domain}_count_delta"] = delta
        values[f"{domain}_left_availability"] = left_av
        values[f"{domain}_right_availability"] = right_av
    return _document(
        MetricFamilyId.INTER_SOCIETY_PAIR_COMPARISON,
        state="present",
        observed=len(view.domain_deltas),
        expected=len(INTER_SOCIETY_DOMAIN_KEYS),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )
