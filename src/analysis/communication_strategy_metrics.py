"""Join hidden utterance audits to committed occurrences.

Analysis-only. It does not import the strategy chooser and it is not an
input to ``CognitiveLoop``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.events import WorldEvent
from world.identifiers import require_stable_id

__all__ = [
    "COMMUNICATION_STRATEGY_METRIC_VERSION",
    "CommunicationStrategyMetricResult",
    "compute_communication_strategy_metrics",
]

COMMUNICATION_STRATEGY_METRIC_VERSION: Final[str] = "communication_strategy@1"
_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.communication_strategy_metrics"
)
_DECEPTION = frozenset(
    {
        "deliberate_false_statement",
        "exaggeration",
        "selective_disclosure",
    }
)
_COMMUNICATION_KINDS = frozenset({"talk", "ask", "tell"})
_CATEGORIES = (
    "memory_error",
    "uncertain_inference",
    "deliberate_deception",
    "not_asserted",
    "veridical",
    "unmatched",
)


@dataclass(frozen=True, slots=True)
class CommunicationStrategyMetricResult:
    """Aggregate document. Counts are not fed back into planning."""

    document: MetricDocument
    categories: tuple[str, ...]
    cascade_count: int


def compute_communication_strategy_metrics(
    audits: Sequence[object],
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
) -> CommunicationStrategyMetricResult:
    """Classify audits. An empty audit sequence is absent and has no rate."""
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
    by_id = {event.event_id.value: event for event in committed}
    categories = tuple(_category(audit, by_id) for audit in audits)
    cascade = _cascade_count(audits, committed)
    counts = {name: categories.count(name) for name in _CATEGORIES}
    _LOG.debug(
        "communication_strategy_metric audit_count=%s memory_error=%s "
        "uncertain_inference=%s deliberate_deception=%s not_asserted=%s "
        "veridical=%s unmatched_count=%s cascade_count=%s",
        len(audits),
        counts["memory_error"],
        counts["uncertain_inference"],
        counts["deliberate_deception"],
        counts["not_asserted"],
        counts["veridical"],
        counts["unmatched"],
        cascade,
    )
    spec = metric_specification(MetricFamilyId.COMMUNICATION_STRATEGY)
    if not audits:
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
                source_kind="communication_strategy",
                source_ids=(),
                notes_code="no_audits",
            ),
        )
        return CommunicationStrategyMetricResult(
            document=document, categories=(), cascade_count=0
        )
    values = {
        name: quantize_float(float(counts[name]))
        for name in _CATEGORIES
    }
    values["cascade_count"] = quantize_float(float(cascade))
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
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="communication_strategy",
            source_ids=(document_run,),
            notes_code="ok",
        ),
    )
    return CommunicationStrategyMetricResult(
        document=document, categories=categories, cascade_count=cascade
    )


def _category(audit: object, events: Mapping[str, WorldEvent]) -> str:
    stance = _value(getattr(audit, "stance", None))
    strategy = _value(getattr(audit, "strategy", None))
    if stance in {"refuse", "withhold"}:
        return "not_asserted"
    if stance == "hedge":
        return "uncertain_inference"
    if strategy in _DECEPTION:
        return "deliberate_deception"
    if stance != "assert_match":
        return "unmatched"
    cited = getattr(audit, "cited_event_id", None)
    if type(cited) is not str:
        return "unmatched"
    event = events.get(cited)
    if event is None:
        return "unmatched"
    source = _tokens(getattr(audit, "source_atom_tokens", ()))
    if source <= _public_tokens(event):
        return "veridical"
    return "memory_error"


def _cascade_count(audits: Sequence[object], events: Sequence[WorldEvent]) -> int:
    renders: list[tuple[object, tuple[str, ...]]] = []
    for audit in audits:
        if _value(getattr(audit, "divergence", None)) != "atom_substituted":
            continue
        rendered = _render_tokens(audit, events)
        if rendered is None:
            continue
        renders.append((getattr(audit, "owner_id", None), rendered))
    count = 0
    for audit in audits:
        if _value(getattr(audit, "stance", None)) != "assert_match":
            continue
        if _hop(audit, events) > 1:
            continue
        owner = getattr(audit, "owner_id", None)
        tokens = _tokens(getattr(audit, "source_atom_tokens", ()))
        if not tokens:
            continue
        for origin_owner, rendered in renders:
            if owner == origin_owner:
                continue
            if tokens == set(rendered):
                count += 1
                break
    return count


def _render_tokens(
    audit: object, events: Sequence[WorldEvent]
) -> tuple[str, ...] | None:
    explicit = getattr(audit, "rendered_atom_tokens", None)
    if isinstance(explicit, tuple) and explicit:
        return explicit
    source = _tokens(getattr(audit, "source_atom_tokens", ()))
    tick = getattr(audit, "tick", None)
    for event in events:
        details = event.details
        kind = getattr(details, "kind", None)
        if kind not in _COMMUNICATION_KINDS:
            continue
        if tick is not None and event.tick != tick:
            continue
        concepts = _utterance_concepts(details)
        if concepts and set(concepts) != source:
            return concepts
    return None


def _hop(audit: object, events: Sequence[WorldEvent]) -> int:
    raw = getattr(audit, "hop_count", None)
    if type(raw) is int:
        return raw
    tick = getattr(audit, "tick", None)
    for event in events:
        details = event.details
        if getattr(details, "kind", None) not in _COMMUNICATION_KINDS:
            continue
        if tick is not None and event.tick != tick:
            continue
        utterance = getattr(details, "utterance", None)
        declared = getattr(utterance, "declared", None)
        hop = getattr(declared, "hop_count", None)
        if type(hop) is int:
            return hop
    return 0


def _public_tokens(event: WorldEvent) -> set[str]:
    details = event.details
    kind = getattr(details, "kind", None)
    if kind in _COMMUNICATION_KINDS:
        return set(_utterance_concepts(details))
    tokens: set[str] = set()
    if type(kind) is str:
        tokens.add(kind)
    if event.actor_id is not None:
        tokens.add(event.actor_id.value)
    if event.target_id is not None:
        tokens.add(event.target_id.value)
    occurrence = event.occurrence
    destination = getattr(occurrence, "destination_location_id", None)
    if destination is not None:
        tokens.add(destination.value)
    return tokens


def _utterance_concepts(details: object) -> tuple[str, ...]:
    utterance = getattr(details, "utterance", None)
    content = getattr(utterance, "content", None)
    concepts = getattr(content, "concepts", ())
    if isinstance(concepts, tuple):
        return concepts
    return ()


def _tokens(value: object) -> set[str]:
    if isinstance(value, tuple):
        return {item for item in value if type(item) is str}
    return set()


def _value(item: object) -> str:
    raw = getattr(item, "value", item)
    return raw if type(raw) is str else ""
