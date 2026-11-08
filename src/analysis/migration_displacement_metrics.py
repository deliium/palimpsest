# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Four detached migration-displacement metric families.

Counts, durations, ratios, closed-label distributions, and coverage only. No
composite migration, displacement, integration, wellbeing, or assimilation
value exists, and nothing here feeds cognition, prompts, memory, world state,
observer semantics, or stop selectors.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from typing import Final

from analysis.migration_displacement_policy import (
    MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION,
)
from analysis.migration_displacement_rows import (
    MigrationDisplacementHarvestRows,
    MigrationWaveRow,
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
    MIGRATION_CAUSE_KINDS,
    MIGRATION_CAUSE_SOURCES,
    MIGRATION_CLUSTER_SIZE_BUCKETS,
    MIGRATION_OUTCOME_LABELS,
    MIGRATION_RESIDENCE_BUCKETS,
    MetricFamilyId,
    metric_specification,
)

__all__ = [
    "compute_migration_cause_evidence",
    "compute_migration_cluster_cohesion",
    "compute_migration_integration_outcome",
    "compute_migration_wave_structure",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.migration_displacement.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _mean(total: int, count: int) -> float | None:
    if count <= 0:
        return None
    return quantize_float(total / count)


def _require(rows: object) -> MigrationDisplacementHarvestRows:
    if type(rows) is not MigrationDisplacementHarvestRows:
        raise ValueError("migration_metrics: invalid_harvest")
    return rows


def _distribution(values: Sequence[int]) -> str:
    counts = Counter(values)
    return ";".join(f"{key}={counts[key]}" for key in sorted(counts))


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
            source_kind="migration_displacement_analysis",
            source_ids=(
                run_id,
                input_revision,
                MIGRATION_DISPLACEMENT_ANALYSIS_POLICY_VERSION,
            ),
            notes_code="detached_migration_displacement_analysis",
        ),
    )


def _state(rows: MigrationDisplacementHarvestRows, *, has_input: bool) -> str:
    if not has_input:
        return "unknown"
    return "present" if rows.coverage == "complete" else "partial"


def _coverage_counts(items: Sequence[object]) -> Counter[str]:
    return Counter(str(getattr(item, "coverage", "missing")) for item in items)


def _wave_origins(
    harvest: MigrationDisplacementHarvestRows, wave: MigrationWaveRow
) -> set[str]:
    members = set(wave.participant_tokens)
    return {
        row.origin_token
        for row in harvest.movements
        if row.participant_token in members
        and row.destination_token == wave.destination_token
        and wave.start_tick <= row.start_tick <= wave.end_tick
    }


def compute_migration_wave_structure(
    rows: MigrationDisplacementHarvestRows,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    harvest = _require(rows)
    waves = harvest.waves
    participants = {token for wave in waves for token in wave.participant_tokens}
    origins = {wave.origin_token for wave in waves}
    destinations: Counter[str] = Counter()
    for wave in waves:
        destinations[wave.destination_token] += len(wave.participant_tokens)
    wave_participants = sum(len(wave.participant_tokens) for wave in waves)
    modal = max(destinations.values()) if destinations else 0
    by_label = Counter(item.classification for item in harvest.outcomes)
    coverage = _coverage_counts(waves)
    clustered = sum(1 for wave in waves if wave.cluster_tokens)
    values: dict[str, object] = {
        "wave_count": len(waves),
        "participant_count": len(participants),
        "distinct_origin_count": len(origins),
        "distinct_destination_count": len(destinations),
        "wave_participant_mean": _mean(wave_participants, len(waves)),
        "wave_participant_max": max(
            (len(wave.participant_tokens) for wave in waves), default=0
        ),
        "route_length_counts": _distribution(
            [len(wave.route_tokens) for wave in waves]
        ),
        "wave_duration_ticks": max(
            (wave.end_tick - wave.start_tick for wave in waves), default=0
        ),
        "return_count": by_label["returned"],
        "onward_count": by_label["onward"],
        "same_origin_share": _ratio(
            sum(1 for wave in waves if len(_wave_origins(harvest, wave)) <= 1),
            len(waves),
        ),
        "same_destination_share": _ratio(modal, wave_participants),
        "cluster_overlap_count": clustered,
        "coverage_complete": coverage["complete"],
        "coverage_partial": coverage["partial"],
        "coverage_missing": coverage["missing"],
    }
    complete = coverage["complete"]
    return _document(
        MetricFamilyId.MIGRATION_WAVE_STRUCTURE,
        state=_state(harvest, has_input=bool(harvest.movements)),
        observed=complete,
        expected=len(waves),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_migration_cause_evidence(
    rows: MigrationDisplacementHarvestRows,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    harvest = _require(rows)
    causes = harvest.causes
    waves = harvest.waves
    kinds = Counter(item.cause_kind for item in causes)
    sources = Counter(item.source_kind for item in causes)
    owners_with_cause = {item.owner_token for item in causes}
    wave_owners = {token for wave in waves for token in wave.participant_tokens}
    labels = Counter(wave.displacement_classification for wave in waves)
    with_cause = sum(1 for wave in waves if wave.independent_cause_count > 0)
    values: dict[str, object] = {}
    for kind in MIGRATION_CAUSE_KINDS:
        values[f"cause_count:{kind}"] = kinds[kind]
    for source in MIGRATION_CAUSE_SOURCES:
        values[f"source_count:{source}"] = sources[source]
    values.update(
        {
            "owner_coverage_ratio": _ratio(
                len(owners_with_cause & wave_owners), len(wave_owners)
            ),
            "wave_with_cause_count": with_cause,
            "wave_without_cause_count": len(waves) - with_cause,
            "contradicted_cause_count": sum(
                1 for item in causes if item.status == "contradicted"
            ),
            "unresolved_anchor_count": sum(
                1 for item in causes if item.coverage == "unresolved"
            ),
            "same_root_suppressed_count": sum(
                wave.same_root_suppressed_count for wave in waves
            ),
            "displacement_like_count": labels["displacement_like"],
            "mixed_count": labels["mixed"],
            "not_displacement_like_count": labels["not_displacement_like"],
            "unknown_count": labels["unknown"],
            "independent_cause_mean": _mean(
                sum(wave.independent_cause_count for wave in waves), len(waves)
            ),
        }
    )
    return _document(
        MetricFamilyId.MIGRATION_CAUSE_EVIDENCE,
        state=_state(harvest, has_input=bool(harvest.owner_tokens)),
        observed=len(owners_with_cause & wave_owners),
        expected=len(wave_owners),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def _size_bucket(size: int) -> str:
    if size <= 4:
        return str(max(size, 2))
    return "5_to_8" if size <= 8 else "9_plus"


def compute_migration_cluster_cohesion(
    rows: MigrationDisplacementHarvestRows,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    harvest = _require(rows)
    clusters = harvest.clusters
    basis_totals: Counter[str] = Counter()
    for cluster in clusters:
        for basis, number in cluster.basis_counts:
            basis_totals[basis] += number
    referenced = {token for wave in harvest.waves for token in wave.cluster_tokens}
    sizes = Counter(_size_bucket(len(item.member_tokens)) for item in clusters)
    coverage = _coverage_counts(clusters)
    values: dict[str, object] = {"cluster_count": len(clusters)}
    for bucket in MIGRATION_CLUSTER_SIZE_BUCKETS:
        values[f"cluster_size:{bucket}"] = sizes[bucket]
    values.update(
        {
            "co_movement_pair_count": basis_totals["co_movement"],
            "kinship_supported_pair_count": basis_totals["kinship"],
            "organization_supported_pair_count": basis_totals["organization"],
            "communication_supported_pair_count": basis_totals["communication"],
            "relationship_supported_pair_count": basis_totals["relationship"],
            "independent_support_ratio": _ratio(
                sum(1 for item in clusters if len(item.basis_counts) >= 2),
                len(clusters),
            ),
            "cluster_wave_overlap_count": sum(
                1 for item in clusters if item.cluster_token in referenced
            ),
            "unknown_cluster_count": coverage["missing"],
            "coverage_complete": coverage["complete"],
            "coverage_partial": coverage["partial"],
        }
    )
    return _document(
        MetricFamilyId.MIGRATION_CLUSTER_COHESION,
        state=_state(harvest, has_input=bool(harvest.movements)),
        observed=coverage["complete"],
        expected=len(clusters),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def _residence_bucket(ticks: int) -> str:
    if ticks <= 0:
        return "0"
    if ticks <= 3:
        return "1_to_3"
    if ticks <= 15:
        return "4_to_15"
    if ticks <= 31:
        return "16_to_31"
    return "32_plus"


def compute_migration_integration_outcome(
    rows: MigrationDisplacementHarvestRows,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    harvest = _require(rows)
    outcomes = harvest.outcomes
    labels = Counter(item.classification for item in outcomes)
    buckets = Counter(_residence_bucket(item.residence_ticks) for item in outcomes)
    coverage = _coverage_counts(outcomes)
    values: dict[str, object] = {}
    for label in MIGRATION_OUTCOME_LABELS:
        values[f"outcome:{label}"] = labels[label]
    for bucket in MIGRATION_RESIDENCE_BUCKETS:
        values[f"residence_ticks:{bucket}"] = buckets[bucket]
    values.update(
        {
            "access_evidence_count": sum(i.access_evidence_count for i in outcomes),
            "participation_evidence_count": sum(
                i.participation_evidence_count for i in outcomes
            ),
            "relationship_evidence_count": sum(
                i.relationship_evidence_count for i in outcomes
            ),
            "conflict_evidence_count": sum(i.conflict_evidence_count for i in outcomes),
            "censored_count": sum(1 for i in outcomes if i.censored),
            "unknown_count": labels["unknown"],
            "complete_coverage_count": coverage["complete"],
            "partial_coverage_count": coverage["partial"],
            "missing_coverage_count": coverage["missing"],
        }
    )
    return _document(
        MetricFamilyId.MIGRATION_INTEGRATION_OUTCOME,
        state=_state(harvest, has_input=bool(harvest.movements)),
        observed=coverage["complete"],
        expected=len(outcomes),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )
