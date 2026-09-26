"""Compare subjective causal confidence with objective event frequencies.

This module is analysis-only. It reads harvested audit snapshots and committed
events. It does not update a world model and it is not an input to cognition.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from world.models import PhysicalRules

__all__ = [
    "CAUSAL_WORLD_MODEL_METRIC_VERSION",
    "CausalComparison",
    "CausalWorldModelMetricResult",
    "compute_causal_world_model_metrics",
]

CAUSAL_WORLD_MODEL_METRIC_VERSION: Final[str] = "causal_world_model@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.causal_world_model_metrics")
_JOINABLE: Final[frozenset[str]] = frozenset({"location", "day_phase", "action"})
_SEARCH: Final[frozenset[str]] = frozenset({"search_success", "search_failure"})


def _reason(field: str, code: str) -> ValueError:
    return ValueError(f"{field}: {code}")


@dataclass(frozen=True, slots=True)
class CausalComparison:
    """One hypothesis compared after the run."""

    hypothesis_id: str
    outcome: str
    predicted_confidence: float
    empirical_status: str
    empirical_rate: float | None = None
    absolute_error: float | None = None


@dataclass(frozen=True, slots=True)
class CausalWorldModelMetricResult:
    """Aggregate document plus per-hypothesis comparisons."""

    document: MetricDocument
    comparisons: tuple[CausalComparison, ...]


def compute_causal_world_model_metrics(
    audits: Sequence[object],
    events: Sequence[WorldEvent],
    *,
    physical_rules: PhysicalRules,
    run_id: str,
    input_revision: str,
) -> CausalWorldModelMetricResult:
    """Match joinable atoms to committed events. Unjoinable atoms stay unmatched."""
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise TypeError("audits: not_ordered")
    if isinstance(events, (set, frozenset, Mapping, str)) or not isinstance(
        events, Sequence
    ):
        raise TypeError("events: not_ordered")
    if type(physical_rules) is not PhysicalRules:
        raise TypeError("physical_rules: invalid_type")
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    committed = tuple(events)
    for event in committed:
        if type(event) is not WorldEvent:
            raise TypeError("events: invalid_type")
    comparisons: list[CausalComparison] = []
    for audit in audits:
        snapshots = getattr(audit, "snapshots", None)
        if not isinstance(snapshots, tuple):
            raise TypeError("audits: invalid_type")
        for snapshot in snapshots:
            comparisons.append(_compare(snapshot, committed, physical_rules))
    spec = metric_specification(MetricFamilyId.CAUSAL_WORLD_MODEL)
    matched = sum(1 for item in comparisons if item.empirical_status == "matched")
    unmatched = len(comparisons) - matched
    _LOG.debug(
        "causal_world_model_metric hypothesis_count=%s matched_count=%s "
        "unmatched_count=%s",
        len(comparisons),
        matched,
        unmatched,
    )
    if not comparisons:
        document = MetricDocument(
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
                source_kind="causal_world_model",
                source_ids=(),
                notes_code="no_hypotheses",
            ),
        )
        return CausalWorldModelMetricResult(document=document, comparisons=())
    errors = [
        item.absolute_error
        for item in comparisons
        if item.absolute_error is not None
    ]
    maximum = max(errors) if errors else 0.0
    values = {
        "hypothesis_count": quantize_float(float(len(comparisons))),
        "matched_count": quantize_float(float(matched)),
        "unmatched_count": quantize_float(float(unmatched)),
        "max_absolute_error": quantize_float(maximum),
    }
    document = MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=document_run,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(observed=matched, expected=len(comparisons)),
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="causal_world_model",
            source_ids=(document_run,),
            notes_code="ok",
        ),
    )
    return CausalWorldModelMetricResult(
        document=document, comparisons=tuple(comparisons)
    )


def _compare(
    snapshot: object,
    events: tuple[WorldEvent, ...],
    rules: PhysicalRules,
) -> CausalComparison:
    hypothesis_id = getattr(snapshot, "hypothesis_id", None)
    outcome = getattr(snapshot, "outcome", None)
    confidence = getattr(snapshot, "confidence", None)
    tokens = getattr(snapshot, "atom_tokens", None)
    if (
        not isinstance(hypothesis_id, str)
        or not isinstance(outcome, str)
        or not isinstance(confidence, float)
        or not isinstance(tokens, tuple)
    ):
        raise TypeError("snapshots: invalid_type")
    parsed = _parse_tokens(tokens)
    if any(slot not in _JOINABLE for slot, _value in parsed):
        return CausalComparison(
            hypothesis_id=hypothesis_id,
            outcome=outcome,
            predicted_confidence=quantize_float(confidence),
            empirical_status="unmatched",
        )
    trials = [event for event in events if _event_matches(event, parsed, rules)]
    if not trials or outcome not in _SEARCH:
        return CausalComparison(
            hypothesis_id=hypothesis_id,
            outcome=outcome,
            predicted_confidence=quantize_float(confidence),
            empirical_status="unmatched",
        )
    hits = sum(1 for event in trials if _search_hit(event, outcome))
    rate = quantize_float(hits / len(trials))
    predicted = quantize_float(confidence)
    return CausalComparison(
        hypothesis_id=hypothesis_id,
        outcome=outcome,
        predicted_confidence=predicted,
        empirical_status="matched",
        empirical_rate=rate,
        absolute_error=quantize_float(abs(predicted - rate)),
    )


def _parse_tokens(tokens: tuple[object, ...]) -> tuple[tuple[str, str], ...]:
    parsed: list[tuple[str, str]] = []
    for token in tokens:
        if not isinstance(token, str) or token.count("=") != 1:
            raise _reason("atom_tokens", "invalid_token")
        slot, value = token.split("=", 1)
        if not slot or not value:
            raise _reason("atom_tokens", "invalid_token")
        parsed.append((slot, value))
    return tuple(parsed)


def _event_matches(
    event: WorldEvent,
    atoms: tuple[tuple[str, str], ...],
    rules: PhysicalRules,
) -> bool:
    for slot, value in atoms:
        if slot == "location":
            occurrence = event.occurrence
            origin = None if occurrence is None else occurrence.origin_location_id
            if origin is None or origin.value != value:
                return False
        elif slot == "day_phase":
            phase = rules.day_phase_for_tick(event.tick)
            if phase.value != value:
                return False
        elif slot == "action":
            kind = getattr(event.details, "kind", None)
            if kind != value:
                return False
    return True


def _search_hit(event: WorldEvent, outcome: str) -> bool:
    success = getattr(event.details, "success", None)
    if outcome == "search_success":
        return success is True
    if outcome == "search_failure":
        return success is False
    return False
