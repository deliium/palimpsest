"""Raw regional crossings and dwell-qualified analytical migration flows."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.regional_population import (
    RegionalPopulationError,
    RegionalPopulationInput,
    fold_regional_history,
)
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "REGIONAL_MIGRATION_METRIC_VERSION",
    "compute_regional_migration_metrics",
]

REGIONAL_MIGRATION_METRIC_VERSION: Final[str] = "regional_migration@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.regional_migration_metrics")


def compute_regional_migration_metrics(
    inputs: RegionalPopulationInput,
) -> MetricDocument:
    """Report raw arrivals separately from residence-qualified migrations."""
    if type(inputs) is not RegionalPopulationInput:
        raise TypeError("inputs must be RegionalPopulationInput")
    history = fold_regional_history(inputs)
    spec = metric_specification(MetricFamilyId.REGIONAL_MIGRATION)
    if spec.version_identifier != REGIONAL_MIGRATION_METRIC_VERSION:
        raise RegionalPopulationError("unsupported_migration_metric_version")
    return_flows: Counter[tuple[str, str]] = Counter()
    prior_residences: dict[str, set[str]] = {}
    for row in history.qualified_migrations:
        seen = prior_residences.setdefault(row.body_id, {row.origin_region_id})
        if row.destination_region_id in seen:
            return_flows[(row.origin_region_id, row.destination_region_id)] += 1
        seen.add(row.origin_region_id)
        seen.add(row.destination_region_id)

    expected_boundaries = inputs.window_end + 1
    observed_boundaries = history.observed_boundaries
    complete = observed_boundaries == expected_boundaries
    values: dict[str, object] = {
        "assigned_unassigned_in": history.assigned_unassigned_in,
        "assigned_unassigned_out": history.assigned_unassigned_out,
        "interregional_raw_arrivals": sum(history.raw_interregional_flows.values()),
        "interregional_raw_departures": sum(history.raw_interregional_flows.values()),
        "qualified_migration_count": len(history.qualified_migrations),
        "qualified_migrations": len(history.qualified_migrations),
        "raw_flow_counts": len(history.raw_interregional_flows),
        "relocation_kind_counts": sum(history.relocation_kind_counts.values()),
        "return_flows": sum(return_flows.values()),
        "qualified_migration_from_region": 0,
        "qualified_migration_to_region": 0,
        "return_flow_count": sum(return_flows.values()),
        "residence_min_ticks": inputs.residence_min_ticks,
        "same_region_relocations_excluded": True,
    }
    migration_from: Counter[str] = Counter()
    migration_to: Counter[str] = Counter()
    for index, row in enumerate(history.qualified_migrations):
        migration_from[row.origin_region_id] += 1
        migration_to[row.destination_region_id] += 1
        prefix = f"qualified_migration:{index}"
        values[f"{prefix}:body_id"] = row.body_id
        values[f"{prefix}:candidate_arrival_boundary"] = row.candidate_arrival_boundary
        values[f"{prefix}:destination_region_id"] = row.destination_region_id
        values[f"{prefix}:origin_region_id"] = row.origin_region_id
        values[f"{prefix}:qualified_boundary"] = row.qualified_boundary
    for region, count in migration_from.items():
        values[f"qualified_migration_from_region:{region}"] = count
    for region, count in migration_to.items():
        values[f"qualified_migration_to_region:{region}"] = count
    values["qualified_migration_from_region"] = len(migration_from)
    values["qualified_migration_to_region"] = len(migration_to)
    for (origin, destination), count in history.raw_interregional_flows.items():
        values[f"raw_flow:{origin}->{destination}"] = count
    for kind, count in history.relocation_kind_counts.items():
        values[f"relocation_kind:{kind}"] = count
    for (origin, destination), count in return_flows.items():
        values[f"return_flow:{origin}->{destination}"] = count
    availability = (
        MetricAvailability.PRESENT if complete else MetricAvailability.PARTIAL
    )
    _LOG.info(
        "regional_migration_complete run_id=%s raw_flow_count=%s "
        "qualified_count=%s return_count=%s availability=%s",
        inputs.run_id,
        sum(history.raw_interregional_flows.values()),
        len(history.qualified_migrations),
        sum(return_flows.values()),
        availability.value,
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=inputs.run_id,
        input_revision=inputs.input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(
            observed=observed_boundaries, expected=expected_boundaries
        ),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="regional_migration",
            source_ids=(inputs.run_id,),
            notes_code="ok" if complete else "incomplete_prefix",
        ),
    )
