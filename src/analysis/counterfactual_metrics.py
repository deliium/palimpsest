"""Compare counterfactual audits with committed event ids after the run.

This module reads audit fields and event ids. It does not import the
scenario generator and it is not an input to cognition.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.events import WorldEvent
from world.identifiers import require_stable_id

__all__ = [
    "COUNTERFACTUAL_REASONING_METRIC_VERSION",
    "compute_counterfactual_reasoning_metrics",
]

COUNTERFACTUAL_REASONING_METRIC_VERSION: Final[str] = "counterfactual_reasoning@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.counterfactual_metrics")


def compute_counterfactual_reasoning_metrics(
    audits: Sequence[object],
    events: Sequence[WorldEvent],
    *,
    scenario_ids: Sequence[str],
    run_id: str,
    input_revision: str,
    arm_id: str,
) -> MetricDocument:
    """Report the audit scenario count and how many ids match events."""
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise TypeError("audits: not_ordered")
    if isinstance(events, (set, frozenset, Mapping, str)) or not isinstance(
        events, Sequence
    ):
        raise TypeError("events: not_ordered")
    if isinstance(scenario_ids, (set, frozenset, Mapping, str)) or not isinstance(
        scenario_ids, Sequence
    ):
        raise TypeError("scenario_ids: not_ordered")
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    arm = require_stable_id("arm_id", arm_id)
    committed = tuple(events)
    event_ids: set[str] = set()
    for event in committed:
        if type(event) is not WorldEvent:
            raise TypeError("events: invalid_type")
        event_ids.add(event.event_id.value)
    scenario_count = 0
    for audit in audits:
        count = getattr(audit, "scenario_count", None)
        if type(count) is not int or isinstance(count, bool) or count < 0:
            raise TypeError("audits: invalid_type")
        scenario_count += count
    overlap = sum(1 for scenario_id in scenario_ids if scenario_id in event_ids)
    _LOG.debug(
        "counterfactual_metric arm_id=%s scenario_count=%s event_overlap_count=%s",
        arm,
        scenario_count,
        overlap,
    )
    spec = metric_specification(MetricFamilyId.COUNTERFACTUAL_REASONING)
    if not audits:
        return MetricDocument(
            schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
            metric_family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            library_versions=library_versions(),
            run_id=document_run,
            input_revision=revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            coverage=None,
            availability=MetricAvailability.ABSENT,
            values={},
            provenance=MetricProvenance(
                source_kind="counterfactual_reasoning",
                source_ids=(),
                notes_code="no_audits",
            ),
        )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=document_run,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(observed=scenario_count, expected=len(audits)),
        availability=MetricAvailability.PRESENT,
        values={
            "scenario_count": quantize_float(float(scenario_count)),
            "event_overlap_count": quantize_float(float(overlap)),
        },
        provenance=MetricProvenance(
            source_kind="counterfactual_reasoning",
            source_ids=(document_run,),
            notes_code="ok",
        ),
    )
