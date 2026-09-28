"""Compare future-action hypotheses with later committed occurrences.

Analysis-only. It does not import the mind updater and it is not an input
to ``CognitiveLoop``.
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

__all__ = [
    "THEORY_OF_MIND_METRIC_VERSION",
    "TheoryOfMindComparison",
    "TheoryOfMindMetricResult",
    "compute_theory_of_mind_metrics",
]

THEORY_OF_MIND_METRIC_VERSION: Final[str] = "theory_of_mind@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.theory_of_mind_metrics")


@dataclass(frozen=True, slots=True)
class TheoryOfMindComparison:
    """One future-action snapshot compared after the run."""

    hypothesis_id: str
    predicted_action: str
    empirical_status: str
    empirical_action: str | None = None
    empirical_rate: float | None = None
    absolute_error: float | None = None
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class TheoryOfMindMetricResult:
    """Aggregate document plus per-hypothesis comparisons."""

    document: MetricDocument
    comparisons: tuple[TheoryOfMindComparison, ...]


def compute_theory_of_mind_metrics(
    audits: Sequence[object],
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
) -> TheoryOfMindMetricResult:
    """Join future actions to a later occurrence by the hypothesized subject."""
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise TypeError("audits: not_ordered")
    if isinstance(events, (set, frozenset, Mapping, str)) or not isinstance(
        events, Sequence
    ):
        raise TypeError("events: not_ordered")
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    committed = tuple(events)
    for event in committed:
        if type(event) is not WorldEvent:
            raise TypeError("events: invalid_type")
    comparisons: list[TheoryOfMindComparison] = []
    for audit in audits:
        snapshots = getattr(audit, "snapshots", None)
        if not isinstance(snapshots, tuple):
            raise TypeError("audits: invalid_type")
        tick = getattr(audit, "tick", None)
        if type(tick) is not int:
            raise TypeError("audits: invalid_type")
        for snapshot in snapshots:
            if getattr(snapshot, "aspect", None) != "future_action":
                continue
            comparisons.append(_compare(snapshot, committed, tick))
    spec = metric_specification(MetricFamilyId.THEORY_OF_MIND)
    matched = sum(1 for item in comparisons if item.empirical_status == "matched")
    unmatched = len(comparisons) - matched
    _LOG.debug(
        "theory_of_mind_metric hypothesis_count=%s matched_count=%s unmatched_count=%s",
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
                source_kind="theory_of_mind",
                source_ids=(),
                notes_code="no_hypotheses",
            ),
        )
        return TheoryOfMindMetricResult(document=document, comparisons=())
    errors = [
        item.absolute_error for item in comparisons if item.absolute_error is not None
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
            source_kind="theory_of_mind",
            source_ids=(document_run,),
            notes_code="ok",
        ),
    )
    return TheoryOfMindMetricResult(document=document, comparisons=tuple(comparisons))


def _predicted_action(snapshot: object) -> str:
    tokens = getattr(snapshot, "atom_tokens", ())
    for token in tokens:
        if isinstance(token, str) and token.startswith("action="):
            return token.removeprefix("action=")
    return ""


def _compare(
    snapshot: object, events: tuple[WorldEvent, ...], tick: int
) -> TheoryOfMindComparison:
    hypothesis_id = str(getattr(snapshot, "hypothesis_id", ""))
    subject = str(getattr(snapshot, "subject_id", ""))
    confidence = float(getattr(snapshot, "confidence", 0.0))
    predicted = _predicted_action(snapshot)
    later = [
        event
        for event in events
        if event.tick > tick
        and event.actor_id is not None
        and event.actor_id.value == subject
    ]
    if not later:
        return TheoryOfMindComparison(
            hypothesis_id=hypothesis_id,
            predicted_action=predicted,
            empirical_status="unmatched",
            confidence=confidence,
        )
    later.sort(key=lambda event: (event.tick, event.sequence))
    empirical = later[0].details.kind
    rate = 1.0 if empirical == predicted else 0.0
    return TheoryOfMindComparison(
        hypothesis_id=hypothesis_id,
        predicted_action=predicted,
        empirical_status="matched",
        empirical_action=empirical,
        empirical_rate=rate,
        absolute_error=abs(confidence - rate),
        confidence=confidence,
    )
