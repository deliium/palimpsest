"""Four descriptive diffusion metric families. Counts only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.science_diffusion_contract import DiffusionStage
from analysis.science_diffusion_lineage import (
    DiffusionAssessment,
    DiffusionChangeKind,
    DiffusionLossScope,
    DiffusionRediscoveryKind,
)
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_science_diffusion_channels",
    "compute_science_diffusion_fidelity",
    "compute_science_diffusion_genealogy",
    "compute_science_diffusion_persistence",
]

_ABSENT: Final[MetricCoverage] = MetricCoverage(observed=0, expected=0, ratio=None)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _require(analysis: object) -> DiffusionAssessment:
    if type(analysis) is not DiffusionAssessment:
        raise ValueError("science_diffusion_analysis_invalid_type")
    return analysis


def _coverage(
    analysis: DiffusionAssessment, lanes: tuple[str, ...]
) -> tuple[MetricAvailability, MetricCoverage]:
    if not analysis.windows:
        return MetricAvailability.UNKNOWN, _ABSENT
    expected = len(analysis.windows)
    complete = 0
    partial = 0
    for window in analysis.windows:
        states = dict(window.lane_states)
        values = [states.get(lane) for lane in lanes]
        if all(value == "complete" for value in values):
            complete += 1
        elif any(value in {"complete", "partial"} for value in values):
            partial += 1
    if complete == expected:
        return (
            MetricAvailability.PRESENT,
            MetricCoverage(
                observed=complete,
                expected=expected,
                ratio=_ratio(complete, expected),
            ),
        )
    if complete or partial:
        return (
            MetricAvailability.PARTIAL,
            MetricCoverage(
                observed=complete,
                expected=expected,
                ratio=_ratio(complete, expected),
            ),
        )
    return MetricAvailability.UNKNOWN, _ABSENT


def _document(
    family: MetricFamilyId,
    analysis: DiffusionAssessment,
    *,
    lanes: tuple[str, ...],
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    availability, coverage = _coverage(analysis, lanes)
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
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="science_diffusion_analysis",
            source_ids=(
                run_id,
                input_revision,
                "science-diffusion.v1",
                "science-diffusion",
                notes_code,
            ),
        ),
    )


def compute_science_diffusion_channels(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    counts = {
        stage: len(data.transmissions_for_stage(stage))
        for stage in (
            DiffusionStage.DELIVERED,
            DiffusionStage.INTERPRETED,
            DiffusionStage.ADOPTED,
            DiffusionStage.LOCALLY_DERIVED,
            DiffusionStage.REPORTED_REFERENCE,
            DiffusionStage.CARRIED,
        )
    }
    lanes = {
        lane: sum(1 for row in data.transmissions if row.lane == lane)
        for lane in (
            "speech",
            "teaching",
            "records",
            "organizations",
            "migration",
            "societies",
            "translation",
            "science",
        )
    }
    return _document(
        MetricFamilyId.SCIENCE_DIFFUSION_CHANNELS,
        data,
        lanes=("science", "speech", "records"),
        run_id=run_id,
        input_revision=input_revision,
        values={
            "delivered_count": counts[DiffusionStage.DELIVERED],
            "interpreted_count": counts[DiffusionStage.INTERPRETED],
            "adopted_count": counts[DiffusionStage.ADOPTED],
            "locally_derived_count": counts[DiffusionStage.LOCALLY_DERIVED],
            "reported_reference_count": counts[DiffusionStage.REPORTED_REFERENCE],
            "carried_count": counts[DiffusionStage.CARRIED],
            **{f"{lane}_count": value for lane, value in lanes.items()},
            "context_flagged_count": sum(
                1 for row in data.transmissions if row.context_flags
            ),
        },
        notes_code="channels",
    )


def compute_science_diffusion_fidelity(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    comparable = sum(
        1
        for row in data.changes
        if row.from_version is not None and row.to_version is not None
    )
    mutations = sum(
        1 for row in data.changes if row.kind is DiffusionChangeKind.MUTATION
    )
    divergent = sum(
        1
        for row in data.changes
        if row.kind is DiffusionChangeKind.MISUNDERSTANDING
    )
    translations = sum(
        1 for row in data.changes if row.kind is DiffusionChangeKind.TRANSLATION
    )
    return _document(
        MetricFamilyId.SCIENCE_DIFFUSION_FIDELITY,
        data,
        lanes=("science", "speech", "records", "translation"),
        run_id=run_id,
        input_revision=input_revision,
        values={
            "comparable_pair_count": comparable,
            "mutation_count": mutations,
            "divergent_reading_count": divergent,
            "bound_translation_count": translations,
        },
        notes_code="fidelity",
    )


def compute_science_diffusion_persistence(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    scoped = sum(
        1
        for row in data.losses
        if row.scope
        in {DiffusionLossScope.OWNER_VERSION, DiffusionLossScope.PHYSICAL_CARRIER}
    )
    observed = sum(
        1
        for row in data.losses
        if row.scope is DiffusionLossScope.OBSERVED_LINEAGE and row.confirmed
    )
    reuptake = sum(
        1
        for row in data.rediscoveries
        if row.kind is DiffusionRediscoveryKind.REACQUIRED
    )
    independent = sum(
        1
        for row in data.rediscoveries
        if row.kind is DiffusionRediscoveryKind.INDEPENDENT
    )
    return _document(
        MetricFamilyId.SCIENCE_DIFFUSION_PERSISTENCE,
        data,
        lanes=("science", "speech", "records"),
        run_id=run_id,
        input_revision=input_revision,
        values={
            "complete_window_count": sum(
                1 for row in data.windows if row.complete
            ),
            "scoped_loss_count": scoped,
            "confirmed_observed_loss_count": observed,
            "reuptake_count": reuptake,
            "independent_rediscovery_count": independent,
        },
        notes_code="persistence",
    )


def compute_science_diffusion_genealogy(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    eligible = sum(
        1
        for row in data.transmissions
        if row.lane in {"teaching", "records"}
        and row.source_version is not None
        and row.stage in {"delivered", "interpreted", "adopted"}
    )
    exact = sum(1 for row in data.v3_links if not row.ambiguous)
    ambiguous = sum(1 for row in data.v3_links if row.ambiguous)
    unresolved = sum(
        1
        for row in data.diagnostics
        if row in {"genealogy_anchor_missing", "ambiguous_source"}
    )
    teaching = sum(
        1 for row in data.v3_links if row.relation == "teaching_uptake"
    )
    written = sum(
        1 for row in data.v3_links if row.relation == "written_record_uptake"
    )
    return _document(
        MetricFamilyId.SCIENCE_DIFFUSION_GENEALOGY,
        data,
        lanes=("knowledge_genealogy", "teaching", "records"),
        run_id=run_id,
        input_revision=input_revision,
        values={
            "eligible_recipient_carrier_count": eligible,
            "exact_link_count": exact,
            "ambiguous_link_count": ambiguous,
            "unresolved_link_count": unresolved,
            "teaching_link_count": teaching,
            "written_record_link_count": written,
        },
        notes_code="genealogy",
    )
