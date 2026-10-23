"""Six additive cultural-evolution metric documents over normalized evidence."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Final

from analysis.cultural_evolution_evidence import (
    CulturalEvolutionInputs,
    CulturalMeasurement,
)
from analysis.cultural_evolution_transmission import (
    compute_cultural_evolution_transmission,
)
from analysis.cultural_narrative_survival import (
    compute_cultural_narrative_survival,
)
from analysis.cultural_population_structure import (
    compute_cultural_population_structure,
)
from analysis.cultural_technology_continuity import (
    compute_cultural_technology_continuity,
)
from analysis.cultural_trait_dynamics import compute_cultural_trait_dynamics
from analysis.cultural_vocabulary_differentiation import (
    compute_cultural_vocabulary_differentiation,
)
from analysis.evidence import EvidenceStage
from analysis.models import (
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.serialization import encode_metric_document
from analysis.specifications import MetricFamilyId
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_evolution_metrics")

_MEASUREMENT_REGISTRY: Final[
    dict[MetricFamilyId, dict[str, frozenset[tuple[str, str]]]]
] = {
    MetricFamilyId.CULTURAL_TRAIT_DYNAMICS: {
        "trait_frequency": frozenset({("proportion", "eligible_living_owners")}),
        "endpoint_persistence": frozenset({("proportion", "fixed_baseline_traits")}),
        "continuous_persistence": frozenset({("proportion", "fixed_baseline_traits")}),
        "extinction_transition": frozenset({("count", "eligible_living_owners")}),
        "richness": frozenset({("count", "carrier_incidences")}),
        "shannon_entropy": frozenset({("nats", "carrier_incidences")}),
        "effective_diversity": frozenset({("effective_traits", "carrier_incidences")}),
        "simpson_diversity": frozenset({("proportion", "carrier_incidences")}),
    },
    MetricFamilyId.CULTURAL_EVOLUTION_TRANSMISSION: {
        "exact_fidelity": frozenset({("proportion", "comparable_single_source_edges")}),
        "mutation_rate": frozenset({("proportion", "comparable_single_source_edges")}),
        "declared_mutation_share": frozenset(
            {("proportion", "comparable_single_source_edges")}
        ),
        "recombination_share": frozenset(
            {("proportion", "comparable_single_source_edges")}
        ),
        "horizontal_share": frozenset(
            {("proportion", "comparable_single_source_edges")}
        ),
        "forward_intergenerational_share": frozenset(
            {("proportion", "comparable_single_source_edges")}
        ),
        "reverse_intergenerational_share": frozenset(
            {("proportion", "comparable_single_source_edges")}
        ),
        "unknown_generation_share": frozenset(
            {("proportion", "comparable_single_source_edges")}
        ),
        "vertical_kin_share": frozenset(
            {("proportion", "comparable_single_source_edges")}
        ),
        "acquisition_candidate_count": frozenset(
            {("count", "attributable_acquisitions")}
        ),
        "attributable_edge_count": frozenset({("count", "attributable_acquisitions")}),
        "comparable_edge_count": frozenset({("count", "attributable_acquisitions")}),
        "ambiguous_source_count": frozenset({("count", "attributable_acquisitions")}),
        "unknown_source_count": frozenset({("count", "attributable_acquisitions")}),
        "independent_rediscovery_count": frozenset(
            {("count", "attributable_acquisitions")}
        ),
        "artifact_acquisition_count": frozenset(
            {("count", "attributable_acquisitions")}
        ),
        "declared_mutation_count": frozenset({("count", "attributable_acquisitions")}),
        "recombination_count": frozenset({("count", "attributable_acquisitions")}),
        "vertical_kin_count": frozenset({("count", "attributable_acquisitions")}),
    },
    MetricFamilyId.CULTURAL_POPULATION_STRUCTURE: {
        "between_group_js_divergence": frozenset({("nats", "fixed_eligible_pairs")}),
        "within_group_pairwise_distance": frozenset(
            {("jaccard_distance", "fixed_eligible_pairs")}
        ),
        "within_group_convergence": frozenset(
            {("jaccard_distance", "fixed_eligible_pairs")}
        ),
    },
    MetricFamilyId.CULTURAL_NARRATIVE_SURVIVAL: {
        "baseline_variant_count": frozenset({("count", "fixed_baseline_traits")}),
        "surviving_baseline_count": frozenset({("count", "fixed_baseline_traits")}),
        "unresolved_baseline_count": frozenset({("count", "fixed_baseline_traits")}),
        "endpoint_persistence": frozenset({("proportion", "fixed_baseline_traits")}),
        "continuous_persistence": frozenset({("proportion", "fixed_baseline_traits")}),
        "witnessed_generation_span": frozenset(
            {("generations", "fixed_baseline_traits")}
        ),
        "observed_duration": frozenset({("ticks", "fixed_baseline_traits")}),
    },
    MetricFamilyId.CULTURAL_VOCABULARY_DIFFERENTIATION: {
        "group_vocabulary_richness": frozenset({("count", "fixed_eligible_pairs")}),
        "between_group_vocabulary_js": frozenset({("nats", "fixed_eligible_pairs")}),
        "between_group_vocabulary_jaccard": frozenset(
            {("jaccard_distance", "fixed_eligible_pairs")}
        ),
        "between_group_shared_label_count": frozenset(
            {("count", "fixed_eligible_pairs")}
        ),
        "between_group_label_union_size": frozenset(
            {("count", "fixed_eligible_pairs")}
        ),
        "within_group_vocabulary_convergence": frozenset(
            {("jaccard_distance", "fixed_eligible_pairs")}
        ),
    },
    MetricFamilyId.CULTURAL_TECHNOLOGY_CONTINUITY: {
        "baseline_content_key_count": frozenset({("count", "fixed_baseline_traits")}),
        "living_retention": frozenset({("proportion", "fixed_baseline_traits")}),
        "exact_variant_retention": frozenset({("proportion", "fixed_baseline_traits")}),
        "living_loss_count": frozenset({("count", "fixed_baseline_traits")}),
        "living_loss_share": frozenset({("proportion", "fixed_baseline_traits")}),
        "technology_preserved_count": frozenset({("count", "fixed_baseline_traits")}),
        "technology_absent_count": frozenset({("count", "fixed_baseline_traits")}),
        "technology_unknown_count": frozenset({("count", "fixed_baseline_traits")}),
        "global_loss_count": frozenset({("count", "fixed_baseline_traits")}),
        "global_loss_share": frozenset({("proportion", "fixed_baseline_traits")}),
        "not_performable_count": frozenset({("count", "fixed_baseline_traits")}),
    },
}

_FAMILY_POPULATIONS: Final[dict[MetricFamilyId, tuple[str, str]]] = {
    family: (
        "cultural_evolution_normalized_evidence",
        "fixed_scientific_selector_denominator",
    )
    for family in _MEASUREMENT_REGISTRY
}

_COMPUTE: Final[
    dict[
        MetricFamilyId,
        Callable[[CulturalEvolutionInputs], tuple[CulturalMeasurement, ...]],
    ]
] = {
    MetricFamilyId.CULTURAL_TRAIT_DYNAMICS: compute_cultural_trait_dynamics,
    MetricFamilyId.CULTURAL_EVOLUTION_TRANSMISSION: (
        compute_cultural_evolution_transmission
    ),
    MetricFamilyId.CULTURAL_POPULATION_STRUCTURE: (
        compute_cultural_population_structure
    ),
    MetricFamilyId.CULTURAL_NARRATIVE_SURVIVAL: (compute_cultural_narrative_survival),
    MetricFamilyId.CULTURAL_VOCABULARY_DIFFERENTIATION: (
        compute_cultural_vocabulary_differentiation
    ),
    MetricFamilyId.CULTURAL_TECHNOLOGY_CONTINUITY: (
        compute_cultural_technology_continuity
    ),
}

__all__ = [
    "CULTURAL_EVOLUTION_FAMILIES",
    "assemble_cultural_evolution_documents",
]

CULTURAL_EVOLUTION_FAMILIES: Final[tuple[MetricFamilyId, ...]] = tuple(
    _MEASUREMENT_REGISTRY
)


def _selector(row: CulturalMeasurement) -> tuple[object, ...]:
    return (
        row.measurement_id,
        row.dimension,
        row.representation,
        row.scope,
        row.partition_id or "",
        row.group_ids,
        row.population_basis,
        row.denominator_code,
        row.baseline_tick,
        row.end_tick,
        row.trait_id or "",
        row.lineage_id or "",
        row.subject_id or "",
        row.units,
    )


def _validated_rows(
    family: MetricFamilyId,
    rows: tuple[CulturalMeasurement, ...],
) -> list[dict[str, object]]:
    registry = _MEASUREMENT_REGISTRY[family]
    payloads: list[dict[str, object]] = []
    for row in rows:
        if row.family != family.value:
            raise ValueError("cultural_measurement_family_mismatch")
        allowed = registry.get(row.measurement_id)
        if allowed is None:
            raise ValueError("cultural_measurement_unknown_formula")
        if (row.units, row.denominator_code) not in allowed:
            raise ValueError("cultural_measurement_invalid_combination")
        payload = row.to_payload()
        if row.value is not None:
            payload["value"] = quantize_float(row.value)
        if row.numerator is not None:
            payload["numerator"] = quantize_float(row.numerator)
        if row.denominator is not None:
            payload["denominator"] = quantize_float(row.denominator)
        payloads.append(payload)
    payloads.sort(
        key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
    )
    return payloads


def _availability(rows: tuple[CulturalMeasurement, ...]) -> MetricAvailability:
    if not rows:
        return MetricAvailability.UNKNOWN
    statuses = {row.availability for row in rows}
    if statuses == {MetricAvailability.PRESENT}:
        return MetricAvailability.PRESENT
    if MetricAvailability.PRESENT in statuses or MetricAvailability.PARTIAL in statuses:
        return MetricAvailability.PARTIAL
    if MetricAvailability.ABSENT in statuses:
        return MetricAvailability.ABSENT
    return MetricAvailability.UNKNOWN


def _coverage(rows: tuple[CulturalMeasurement, ...]) -> MetricCoverage | None:
    observed = sum(row.coverage_observed for row in rows)
    expected_values = [
        row.coverage_expected for row in rows if row.coverage_expected is not None
    ]
    if not expected_values:
        return None
    expected = sum(expected_values)
    return MetricCoverage(
        observed=observed,
        expected=expected,
        ratio=(observed / expected) if expected > 0 else None,
    )


def assemble_cultural_evolution_documents(
    inputs: CulturalEvolutionInputs,
    *,
    evidence_manifest_digest: str,
) -> tuple[MetricDocument, ...]:
    """Assemble six separate documents bound to a normalized evidence digest."""
    if type(inputs) is not CulturalEvolutionInputs:
        raise TypeError("inputs must be CulturalEvolutionInputs")
    digest = require_stable_id("evidence_manifest_digest", evidence_manifest_digest)
    resolved_end = (
        inputs.window.end_boundary
        if inputs.window.end_boundary is not None
        else max((boundary.boundary_tick for boundary in inputs.boundaries), default=0)
    )
    documents: list[MetricDocument] = []
    for family in CULTURAL_EVOLUTION_FAMILIES:
        rows = _COMPUTE[family](inputs) if inputs.boundaries else ()
        payloads = _validated_rows(family, rows)
        rows_json = json.dumps(
            payloads,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        population, denominator = _FAMILY_POPULATIONS[family]
        document = MetricDocument(
            schema_version="1",
            metric_family=family.value,
            algorithm_version="1",
            library_versions=library_versions(),
            run_id=inputs.run_id,
            input_revision=inputs.source_revision,
            evidence_stages=frozenset(
                {
                    EvidenceStage.BELIEF_REVISION_TESTIMONY,
                    EvidenceStage.OBJECTIVE_EVENT_STATE,
                }
            ),
            population=population,
            denominator=denominator,
            coverage=_coverage(rows),
            availability=_availability(rows),
            values={
                "policy_version": inputs.policy_version,
                "window_start": inputs.window.baseline_boundary,
                "window_end": resolved_end,
                "measurement_count": len(rows),
                "rows_json": rows_json,
                "evidence_manifest_digest": digest,
            },
            provenance=MetricProvenance(
                source_kind="cultural_evolution_evidence",
                source_ids=(digest,),
                notes_code="normalized_evidence",
            ),
        )
        encode_metric_document(document)
        documents.append(document)
    _LOG.debug(
        "cultural_evolution_documents_assembled run_id=%s document_count=%s",
        inputs.run_id,
        len(documents),
    )
    return tuple(documents)
