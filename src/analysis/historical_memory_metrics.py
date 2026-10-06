"""Analysis-only historical memory layer / transition / query metrics."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping
from typing import Final

from analysis.historical_memory import (
    HistoricalMemoryHarvest,
    HistoricalMemoryLayerId,
    HistoricalMemoryQueryId,
    HistoricalMemoryTransitionCause,
    materialize_historical_memory_from_harvest,
)
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
    "HISTORICAL_MEMORY_LAYERS_METRIC_VERSION",
    "HISTORICAL_MEMORY_QUERIES_METRIC_VERSION",
    "HISTORICAL_MEMORY_TRANSITIONS_METRIC_VERSION",
    "compute_historical_memory_layers",
    "compute_historical_memory_queries",
    "compute_historical_memory_transitions",
]

HISTORICAL_MEMORY_LAYERS_METRIC_VERSION: Final[str] = (
    "historical_memory_layers@1"
)
HISTORICAL_MEMORY_TRANSITIONS_METRIC_VERSION: Final[str] = (
    "historical_memory_transitions@1"
)
HISTORICAL_MEMORY_QUERIES_METRIC_VERSION: Final[str] = (
    "historical_memory_queries@1"
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.historical_memory")
_LAYER: Final[str] = "research_analytics"
_CENSOR: Final[str] = (
    "analysis-only historical memory; never cognition"
)


class HistoricalMemoryMetricError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error(
            "historical_memory_metric_invalid reason_code=%s", reason_code
        )
        super().__init__(reason_code)


def _document(
    spec: MetricSpecification,
    run_id: str,
    revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    *,
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
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
            source_kind="historical_memory",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _require_harvest(harvest: object) -> HistoricalMemoryHarvest:
    if type(harvest) is not HistoricalMemoryHarvest:
        raise HistoricalMemoryMetricError("invalid_harvest_type")
    return harvest


def compute_historical_memory_layers(
    harvest: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Layer histogram and witness/carrier shares over tracked sources."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    bundle = _require_harvest(harvest)
    _LOG.debug(
        "historical_memory_metric_assemble family_id=%s source_count=%s",
        MetricFamilyId.HISTORICAL_MEMORY_LAYERS.value,
        len(bundle.sources),
    )
    spec = metric_specification(MetricFamilyId.HISTORICAL_MEMORY_LAYERS)
    if spec.version_identifier != HISTORICAL_MEMORY_LAYERS_METRIC_VERSION:
        raise HistoricalMemoryMetricError("unsupported_metric_version")
    if not bundle.sources:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_historical_memory_sources",
        )
    _graph, assignments, _transitions, _report = (
        materialize_historical_memory_from_harvest(bundle)
    )
    layer_counts: Counter[str] = Counter()
    living_witness_total = 0
    communicative_carriers = 0
    cultural_carriers = 0
    for assignment in assignments:
        layer_counts[assignment.layer.value] += 1
        living_witness_total += len(assignment.living_witness_ids)
        communicative_carriers += len(assignment.communicative_carrier_ids)
        cultural_carriers += len(assignment.cultural_carrier_ids)
    unattested = len(bundle.sources) - len(assignments)
    if unattested > 0:
        layer_counts[HistoricalMemoryLayerId.UNATTESTED.value] += unattested
    source_count = len(bundle.sources)
    values: dict[str, object] = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "source_count": source_count,
        "assignment_count": len(assignments),
        "living_count": layer_counts.get(HistoricalMemoryLayerId.LIVING.value, 0),
        "communicative_count": layer_counts.get(
            HistoricalMemoryLayerId.COMMUNICATIVE.value, 0
        ),
        "cultural_count": layer_counts.get(
            HistoricalMemoryLayerId.CULTURAL.value, 0
        ),
        "unattested_count": layer_counts.get(
            HistoricalMemoryLayerId.UNATTESTED.value, 0
        ),
        "mean_living_witness_count": quantize_float(
            living_witness_total / source_count
        ),
        "communicative_carrier_share": quantize_float(
            communicative_carriers
            / max(1, communicative_carriers + cultural_carriers)
        ),
        "cultural_carrier_share": quantize_float(
            cultural_carriers
            / max(1, communicative_carriers + cultural_carriers)
        ),
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=source_count,
        expected=source_count,
    )


def compute_historical_memory_transitions(
    harvest: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Transition counts by cause and living->communicative / cultural rates."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    bundle = _require_harvest(harvest)
    _LOG.debug(
        "historical_memory_metric_assemble family_id=%s source_count=%s",
        MetricFamilyId.HISTORICAL_MEMORY_TRANSITIONS.value,
        len(bundle.sources),
    )
    spec = metric_specification(MetricFamilyId.HISTORICAL_MEMORY_TRANSITIONS)
    if spec.version_identifier != HISTORICAL_MEMORY_TRANSITIONS_METRIC_VERSION:
        raise HistoricalMemoryMetricError("unsupported_metric_version")
    if not bundle.sources:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_historical_memory_sources",
        )
    _graph, _assignments, transitions, _report = (
        materialize_historical_memory_from_harvest(bundle)
    )
    if not transitions:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_historical_memory_transitions",
        )
    causes: Counter[str] = Counter()
    living_to_comm = 0
    comm_to_cultural = 0
    death_linked = 0
    for row in transitions:
        causes[row.cause.value] += 1
        if (
            row.from_layer is HistoricalMemoryLayerId.LIVING
            and row.to_layer is HistoricalMemoryLayerId.COMMUNICATIVE
        ):
            living_to_comm += 1
        if (
            row.from_layer is HistoricalMemoryLayerId.COMMUNICATIVE
            and row.to_layer is HistoricalMemoryLayerId.CULTURAL
        ):
            comm_to_cultural += 1
        if row.cause in {
            HistoricalMemoryTransitionCause.LAST_DIRECT_WITNESS_DIED,
            HistoricalMemoryTransitionCause.WITNESS_CHAIN_EXPIRED,
        }:
            death_linked += 1
    total = len(transitions)
    values: dict[str, object] = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "transition_count": total,
        "living_to_communicative_count": living_to_comm,
        "communicative_to_cultural_count": comm_to_cultural,
        "living_to_communicative_rate": quantize_float(living_to_comm / total),
        "communicative_to_cultural_rate": quantize_float(comm_to_cultural / total),
        "death_linked_share": quantize_float(death_linked / total),
    }
    for cause in HistoricalMemoryTransitionCause:
        values[f"cause_{cause.value}_count"] = causes.get(cause.value, 0)
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=total,
        expected=total,
    )


def compute_historical_memory_queries(
    harvest: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Aggregated true-counts for the three locked researcher queries."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    bundle = _require_harvest(harvest)
    _LOG.debug(
        "historical_memory_metric_assemble family_id=%s source_count=%s",
        MetricFamilyId.HISTORICAL_MEMORY_QUERIES.value,
        len(bundle.sources),
    )
    spec = metric_specification(MetricFamilyId.HISTORICAL_MEMORY_QUERIES)
    if spec.version_identifier != HISTORICAL_MEMORY_QUERIES_METRIC_VERSION:
        raise HistoricalMemoryMetricError("unsupported_metric_version")
    if not bundle.sources:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_historical_memory_sources",
        )
    _graph, _assignments, _transitions, report = (
        materialize_historical_memory_from_harvest(bundle)
    )
    values: dict[str, object] = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "source_count": report.source_count,
        "answer_count": len(report.answers),
        "as_of_tick": report.as_of_tick,
    }
    for query_id in HistoricalMemoryQueryId:
        key = f"true_count_{query_id.value}"
        values[key] = int(report.true_counts_by_query_id.get(query_id.value, 0))
        values[f"true_share_{query_id.value}"] = quantize_float(
            int(report.true_counts_by_query_id.get(query_id.value, 0))
            / max(1, report.source_count)
        )
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=report.source_count,
        expected=report.source_count,
    )
