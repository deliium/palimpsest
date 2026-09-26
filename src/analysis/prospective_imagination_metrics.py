"""Compare a prospective audit with committed events after the run.

This module reads audit fields and events. It does not import the rollout and
it is not an input to cognition.
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
    "PROSPECTIVE_IMAGINATION_METRIC_VERSION",
    "compute_prospective_imagination_metrics",
]

PROSPECTIVE_IMAGINATION_METRIC_VERSION: Final[str] = "prospective_imagination@1"
_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.prospective_imagination_metrics"
)
_BAND_CONFIDENCE: Final[Mapping[str, float]] = {
    "low": 0.16,
    "medium": 0.495,
    "high": 0.83,
}
_DIRECTION: Final[Mapping[str, str]] = {
    "Moved": "move",
    "Searched": "search",
    "Waited": "wait",
    "Fled": "flee",
    "Drunk": "drink",
    "Eaten": "eat",
    "Slept": "sleep",
    "Talked": "talk",
    "Asked": "ask",
    "Told": "tell",
    "Helped": "help",
}
_HARM: Final[frozenset[str]] = frozenset({"Attacked", "Died"})


def compute_prospective_imagination_metrics(
    audits: Sequence[object],
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
    arm_id: str,
    place_id: str,
) -> MetricDocument:
    """Match the first committed command and count harm at one place id."""
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
    place = require_stable_id("place_id", place_id)
    arm = require_stable_id("arm_id", arm_id)
    committed = tuple(events)
    for event in committed:
        if type(event) is not WorldEvent:
            raise TypeError("events: invalid_type")
    spec = metric_specification(MetricFamilyId.PROSPECTIVE_IMAGINATION)
    command = _first_command(committed)
    harm_count = _harm_at(committed, place)
    matched = 0
    unmatched = 0
    errors: list[float] = []
    for audit in audits:
        direction = getattr(audit, "direction_code", None)
        band = getattr(audit, "confidence_band", None)
        if type(direction) is not str or type(band) is not str:
            raise TypeError("audits: invalid_type")
        if command is not None and command == direction:
            matched += 1
        else:
            unmatched += 1
        confidence = _BAND_CONFIDENCE.get(band)
        if confidence is None:
            raise TypeError("audits: invalid_type")
        rate = 0.0 if harm_count == 0 else 1.0
        errors.append(abs(confidence - rate))
    _LOG.debug(
        "prospective_imagination_metric arm_id=%s matched_count=%s "
        "unmatched_count=%s",
        arm,
        matched,
        unmatched,
    )
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
                source_kind="prospective_imagination",
                source_ids=(),
                notes_code="no_audits",
            ),
        )
    maximum = max(errors) if errors else 0.0
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
        coverage=MetricCoverage(observed=matched, expected=len(audits)),
        availability=MetricAvailability.PRESENT,
        values={
            "matched_count": quantize_float(float(matched)),
            "unmatched_count": quantize_float(float(unmatched)),
            "harm_count": quantize_float(float(harm_count)),
            "absolute_error": quantize_float(maximum),
        },
        provenance=MetricProvenance(
            source_kind="prospective_imagination",
            source_ids=(document_run,),
            notes_code="ok",
        ),
    )


def _first_command(events: tuple[WorldEvent, ...]) -> str | None:
    for event in events:
        direction = _DIRECTION.get(type(event.details).__name__)
        if direction is not None:
            return direction
    return None


def _harm_at(events: tuple[WorldEvent, ...], place_id: str) -> int:
    count = 0
    for event in events:
        if type(event.details).__name__ not in _HARM:
            continue
        details = event.details
        if type(details).__name__ == "Attacked" and not getattr(details, "damage", 0):
            continue
        if _place_of(event) == place_id:
            count += 1
    return count


def _place_of(event: WorldEvent) -> str | None:
    occurrence = event.occurrence
    if occurrence is None:
        return None
    for location in (occurrence.origin_location_id, occurrence.destination_location_id):
        if location is not None:
            return location.value
    return None
