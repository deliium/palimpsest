"""Neighborhood means of private reputation ledgers.

Analysis-only. This module does not import agent cognition or write a mean
back onto any owner.
"""

from __future__ import annotations

import logging
from collections import defaultdict
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
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from world.identifiers import require_stable_id

__all__ = [
    "DISTRIBUTED_REPUTATION_METRIC_VERSION",
    "DistributedReputationMetricResult",
    "NeighborhoodReputationMeans",
    "compute_distributed_reputation",
]

DISTRIBUTED_REPUTATION_METRIC_VERSION: Final[str] = "distributed_reputation@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.reputation_metrics")
_DIMENSIONS: Final[tuple[str, ...]] = (
    "reliability",
    "harm",
    "generosity",
    "competence",
)
_READING_THRESHOLD: Final[float] = 0.4


@dataclass(frozen=True, slots=True)
class NeighborhoodReputationMeans:
    """One neighborhood's mean on each dimension for one target."""

    neighborhood_id: str
    reliability: float
    harm: float
    generosity: float
    competence: float
    readings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DistributedReputationMetricResult:
    """Per-neighborhood means and pairwise gaps. Not a cognition input."""

    document: MetricDocument
    neighborhoods: tuple[NeighborhoodReputationMeans, ...]
    gaps: Mapping[str, float]


def compute_distributed_reputation(
    ledgers: Sequence[object],
    owner_neighborhoods: Mapping[str, str],
    *,
    target_id: str,
    run_id: str,
    input_revision: str,
) -> DistributedReputationMetricResult:
    """Average owner heads inside caller-supplied neighborhoods."""
    if isinstance(ledgers, (set, frozenset, Mapping, str)) or not isinstance(
        ledgers, Sequence
    ):
        raise TypeError("ledgers: not_ordered")
    if not isinstance(owner_neighborhoods, Mapping):
        raise TypeError("owner_neighborhoods: invalid_type")
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    target = require_stable_id("target_id", target_id)
    grouped: dict[str, list[Mapping[str, float]]] = defaultdict(list)
    for ledger in ledgers:
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if not isinstance(owner, str):
            raise TypeError("ledgers: invalid_type")
        neighborhood = owner_neighborhoods.get(owner)
        if neighborhood is None:
            continue
        profiles = getattr(ledger, "profiles", None)
        if not isinstance(profiles, tuple):
            raise TypeError("ledgers: invalid_type")
        for profile in profiles:
            profile_target = getattr(getattr(profile, "target_id", None), "value", None)
            if profile_target != target:
                continue
            grouped[str(neighborhood)].append(_dimension_values(profile))
    neighborhoods = _means(grouped)
    gaps = _gaps(neighborhoods)
    _LOG.debug(
        "distributed_reputation_metric ledger_count=%s neighborhood_count=%s "
        "reliability_gap=%s harm_gap=%s generosity_gap=%s competence_gap=%s",
        len(ledgers),
        len(neighborhoods),
        gaps["reliability"],
        gaps["harm"],
        gaps["generosity"],
        gaps["competence"],
    )
    spec = metric_specification(MetricFamilyId.DISTRIBUTED_REPUTATION)
    if not ledgers or not neighborhoods:
        return DistributedReputationMetricResult(
            document=_document(
                spec,
                document_run,
                revision,
                MetricAvailability.ABSENT,
                {},
                notes_code="no_ledgers",
            ),
            neighborhoods=(),
            gaps={},
        )
    values = {
        f"{name}_gap": quantize_float(gaps[name]) for name in _DIMENSIONS
    }
    return DistributedReputationMetricResult(
        document=_document(
            spec,
            document_run,
            revision,
            MetricAvailability.PRESENT,
            values,
            notes_code="ok",
            observed=len(neighborhoods),
            expected=len(neighborhoods),
        ),
        neighborhoods=neighborhoods,
        gaps=gaps,
    )


def _dimension_values(profile: object) -> Mapping[str, float]:
    values: dict[str, float] = {}
    for name in _DIMENSIONS:
        state = getattr(profile, name, None)
        number = getattr(state, "value", None)
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise TypeError("ledgers: invalid_type")
        values[name] = float(number)
    return values


def _means(
    grouped: Mapping[str, Sequence[Mapping[str, float]]],
) -> tuple[NeighborhoodReputationMeans, ...]:
    rows: list[NeighborhoodReputationMeans] = []
    for neighborhood_id in sorted(grouped):
        samples = grouped[neighborhood_id]
        if not samples:
            continue
        averaged = {
            name: quantize_float(
                sum(sample[name] for sample in samples) / len(samples)
            )
            for name in _DIMENSIONS
        }
        rows.append(
            NeighborhoodReputationMeans(
                neighborhood_id=neighborhood_id,
                reliability=averaged["reliability"],
                harm=averaged["harm"],
                generosity=averaged["generosity"],
                competence=averaged["competence"],
                readings=_readings(averaged),
            )
        )
    return tuple(rows)


def _readings(values: Mapping[str, float]) -> tuple[str, ...]:
    labels: list[str] = []
    reliability = values["reliability"]
    if reliability >= _READING_THRESHOLD:
        labels.append("trustworthy")
    elif reliability <= -_READING_THRESHOLD:
        labels.append("unreliable")
    if values["harm"] >= _READING_THRESHOLD:
        labels.append("dangerous")
    if values["generosity"] >= _READING_THRESHOLD:
        labels.append("generous")
    if values["competence"] >= _READING_THRESHOLD:
        labels.append("competent")
    return tuple(labels)


def _gaps(
    neighborhoods: Sequence[NeighborhoodReputationMeans],
) -> dict[str, float]:
    gaps: dict[str, float] = {}
    for name in _DIMENSIONS:
        numbers = [getattr(row, name) for row in neighborhoods]
        if len(numbers) < 2:
            gaps[name] = 0.0
            continue
        gaps[name] = quantize_float(max(numbers) - min(numbers))
    return gaps


def _document(
    spec: MetricSpecification,
    run_id: str,
    revision: str,
    availability: MetricAvailability,
    values: Mapping[str, float],
    *,
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=expected)
    family = spec.family_id
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="distributed_reputation",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
