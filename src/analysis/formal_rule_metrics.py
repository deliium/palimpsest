"""Three detached metric documents over formal-rule analysis."""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Final

from analysis.formal_rule_layers import FormalRuleLayerView
from analysis.formal_rule_lineage import FormalRuleSummary
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
    "compute_formal_rule_authority_metric",
    "compute_formal_rule_development_metric",
    "compute_formal_rule_response_metric",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.formal_rule_metrics")


def _histogram(values: Counter[str]) -> str:
    return json.dumps(dict(sorted(values.items())), separators=(",", ":"))


def _availability(summary: FormalRuleSummary) -> MetricAvailability:
    if not summary.candidates:
        return MetricAvailability.ABSENT
    if summary.coverage.partial:
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _coverage(summary: FormalRuleSummary) -> MetricCoverage:
    fraction = summary.coverage.coverage_fraction
    return MetricCoverage(
        observed=summary.coverage.observed,
        expected=summary.coverage.expected,
        ratio=None if fraction is None else quantize_float(fraction),
    )


def _document(
    summary: FormalRuleSummary,
    view: FormalRuleLayerView,
    family: MetricFamilyId,
    *,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
    notes_code: str,
) -> MetricDocument:
    if type(summary) is not FormalRuleSummary:
        raise TypeError("summary must be FormalRuleSummary")
    if type(view) is not FormalRuleLayerView:
        raise TypeError("view must be FormalRuleLayerView")
    spec = metric_specification(family)
    availability = _availability(summary)
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
        coverage=_coverage(summary),
        availability=availability,
        values={} if availability is MetricAvailability.ABSENT else values,
        provenance=MetricProvenance(
            source_kind="formal_rule_analysis",
            source_ids=(run_id,),
            notes_code=notes_code,
        ),
    )


def compute_formal_rule_development_metric(
    summary: FormalRuleSummary,
    layers: FormalRuleLayerView,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Detached stage and version development counts."""

    stages = Counter(
        stage
        for item in summary.development
        for stage, count in item.stage_counts
        for _ in range(count)
    )
    constraints = Counter(
        constraint
        for row in layers.analytical
        for constraint in row.constraint_kinds
    )
    mean_versions = [
        item.mean_version_count for item in summary.development
    ]
    values = {
        "candidate_count": len(summary.candidates),
        "active_count": sum(
            1
            for item in layers.analytical
            if item.status.value
            in {"recognized", "partial", "contested", "fragmented", "temporary"}
        ),
        "documented_count": sum(
            item.documented_count for item in summary.development
        ),
        "recognized_enforcement_count": sum(
            item.recognized_enforcement_count for item in summary.development
        ),
        "stage_histogram": _histogram(stages),
        "constraint_histogram": _histogram(constraints),
        "written_representation_count": sum(
            item.written_count for item in summary.development
        ),
        "mean_version_count": (
            quantize_float(sum(mean_versions) / len(mean_versions))
            if mean_versions
            else None
        ),
        "coverage": summary.coverage.coverage_fraction,
    }
    _LOG.info("formal_rule_metrics documents=3")
    return _document(
        summary,
        layers,
        MetricFamilyId.FORMAL_RULE_DEVELOPMENT,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="formal_rule_development_detached",
    )


def compute_formal_rule_authority_metric(
    summary: FormalRuleSummary,
    layers: FormalRuleLayerView,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Detached recognized-authority and competing-system counts."""

    histogram = Counter(
        kind
        for item in summary.authority
        for kind, count in item.authority_histogram
        for _ in range(count)
    )
    values = {
        "system_count": sum(item.system_count for item in summary.authority),
        "proponent_count": sum(
            item.proponent_count for item in summary.authority
        ),
        "recognized_authority_count": sum(
            item.recognized_authority_count for item in summary.authority
        ),
        "authority_histogram": _histogram(histogram),
        "competing_system_count": sum(
            item.competing_count for item in summary.authority
        ),
        "contested_system_count": sum(
            item.contested_count for item in summary.authority
        ),
        "coverage": summary.coverage.coverage_fraction,
    }
    return _document(
        summary,
        layers,
        MetricFamilyId.FORMAL_RULE_AUTHORITY,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="formal_rule_authority_detached",
    )


def compute_formal_rule_response_metric(
    summary: FormalRuleSummary,
    layers: FormalRuleLayerView,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Detached declared-response and expected-sanction counts."""

    responses = Counter(
        {
            "follow": sum(item.follow_count for item in summary.response),
            "violate": sum(item.violate_count for item in summary.response),
            "challenge": sum(item.challenge_count for item in summary.response),
            "reinterpret": sum(
                item.reinterpret_count for item in summary.response
            ),
            "ignore": sum(item.ignore_count for item in summary.response),
        }
    )
    sanctions = Counter(
        kind
        for item in summary.response
        for kind, count in item.sanction_histogram
        for _ in range(count)
    )
    values = {
        "follow_count": responses["follow"],
        "violate_count": responses["violate"],
        "challenge_count": responses["challenge"],
        "reinterpret_count": responses["reinterpret"],
        "ignore_count": responses["ignore"],
        "response_histogram": _histogram(responses),
        "expected_sanction_histogram": _histogram(sanctions),
        "exception_count": sum(
            item.exception_count for item in summary.response
        ),
        "coverage": summary.coverage.coverage_fraction,
    }
    return _document(
        summary,
        layers,
        MetricFamilyId.FORMAL_RULE_RESPONSE,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="formal_rule_response_detached",
    )
