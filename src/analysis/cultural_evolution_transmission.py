"""Mutation, fidelity, and transmission classifications on explicit edges."""

from __future__ import annotations

import logging
from typing import Final

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    TransmissionEdge,
)
from analysis.models import MetricAvailability

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.cultural_evolution_transmission"
)

CULTURAL_EVOLUTION_TRANSMISSION_FAMILY: Final[str] = "cultural_evolution_transmission"
CULTURAL_EVOLUTION_TRANSMISSION_ALGORITHM_VERSION: Final[str] = (
    "cultural-evolution-transmission@1"
)

_DIMENSION: Final[str] = "technology"
_REPRESENTATION: Final[str] = "transmission_edge"

_KNOWN_GENERATIONS: Final[frozenset[str]] = frozenset(
    {"horizontal", "intergenerational", "reverse_intergenerational"}
)

__all__ = [
    "CULTURAL_EVOLUTION_TRANSMISSION_ALGORITHM_VERSION",
    "CULTURAL_EVOLUTION_TRANSMISSION_FAMILY",
    "compute_cultural_evolution_transmission",
]


def _measurement(
    *,
    measurement_id: str,
    units: str,
    value: float | None,
    numerator: float | None,
    denominator: float | None,
    availability: MetricAvailability,
    reason_code: str | None,
    population_basis: str,
    denominator_code: str,
    coverage_observed: int,
    coverage_expected: int | None,
    evidence_ids: tuple[str, ...] = (),
) -> CulturalMeasurement:
    return CulturalMeasurement(
        family=CULTURAL_EVOLUTION_TRANSMISSION_FAMILY,
        algorithm_version=CULTURAL_EVOLUTION_TRANSMISSION_ALGORITHM_VERSION,
        policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        measurement_id=measurement_id,
        dimension=_DIMENSION,
        representation=_REPRESENTATION,
        scope="global",
        partition_id=None,
        group_ids=(),
        population_basis=population_basis,
        denominator_code=denominator_code,
        baseline_tick=0,
        end_tick=0,
        trait_id=None,
        lineage_id=None,
        subject_id=None,
        units=units,
        value=value,
        numerator=numerator,
        denominator=denominator,
        availability=availability,
        reason_code=reason_code,
        coverage_observed=coverage_observed,
        coverage_expected=coverage_expected,
        left_censored=False,
        right_censored=False,
        evidence_ids=evidence_ids,
    )


def _ratio(
    numerator: int,
    denominator: int,
    *,
    measurement_id: str,
    reason_when_empty: str = "zero_opportunities",
    evidence: tuple[str, ...] = (),
) -> CulturalMeasurement:
    if denominator <= 0:
        return _measurement(
            measurement_id=measurement_id,
            units="proportion",
            value=None,
            numerator=float(numerator),
            denominator=float(denominator),
            availability=MetricAvailability.UNKNOWN,
            reason_code=reason_when_empty,
            population_basis="comparable_single_source_edges",
            denominator_code="comparable_single_source_edges",
            coverage_observed=0,
            coverage_expected=0,
            evidence_ids=evidence,
        )
    return _measurement(
        measurement_id=measurement_id,
        units="proportion",
        value=numerator / denominator,
        numerator=float(numerator),
        denominator=float(denominator),
        availability=MetricAvailability.PRESENT,
        reason_code=None,
        population_basis="comparable_single_source_edges",
        denominator_code="comparable_single_source_edges",
        coverage_observed=denominator,
        coverage_expected=denominator,
        evidence_ids=evidence,
    )


def _count(
    value: int,
    *,
    measurement_id: str,
    denominator: int,
    evidence: tuple[str, ...] = (),
) -> CulturalMeasurement:
    return _measurement(
        measurement_id=measurement_id,
        units="count",
        value=float(value),
        numerator=float(value),
        denominator=float(denominator),
        availability=MetricAvailability.PRESENT,
        reason_code=None,
        population_basis="attributable_acquisitions",
        denominator_code="attributable_acquisitions",
        coverage_observed=value,
        coverage_expected=denominator,
        evidence_ids=evidence,
    )


def _edge_evidence(edges: tuple[TransmissionEdge, ...]) -> tuple[str, ...]:
    return tuple(sorted({item for edge in edges for item in edge.evidence_ids}))


def compute_cultural_evolution_transmission(
    inputs: CulturalEvolutionInputs,
) -> tuple[CulturalMeasurement, ...]:
    """Classify explicit attributable acquisition edges without new policy."""
    if type(inputs) is not CulturalEvolutionInputs:
        raise TypeError("inputs must be CulturalEvolutionInputs")
    edges = tuple(
        sorted(
            inputs.transmission_edges,
            key=lambda edge: (
                edge.edge_id,
                edge.receiver_owner_id,
                edge.acquisition_boundary,
            ),
        )
    )
    candidates = len(edges)
    resolved = tuple(edge for edge in edges if edge.attribution_status == "resolved")
    comparable = tuple(
        edge
        for edge in resolved
        if edge.source_digest is not None
        and edge.target_digest is not None
        and not edge.recombined
    )
    equal = sum(1 for edge in comparable if edge.source_digest == edge.target_digest)
    changed = len(comparable) - equal
    declared_mutated = sum(1 for edge in edges if edge.mutated)
    recombined = sum(1 for edge in edges if edge.recombined)
    ambiguous = sum(
        1 for edge in edges if edge.attribution_status == "ambiguous_source"
    )
    unknown = sum(1 for edge in edges if edge.attribution_status == "unknown_source")
    independent = sum(
        1
        for edge in edges
        if edge.attribution_status == "independent_rediscovery"
        or edge.modality == "independent_rediscovery"
    )
    artifact = sum(1 for edge in edges if edge.modality == "artifact")
    known_generation = tuple(
        edge for edge in edges if edge.generation_class in _KNOWN_GENERATIONS
    )
    horizontal = sum(
        1 for edge in known_generation if edge.generation_class == "horizontal"
    )
    forward = sum(
        1 for edge in known_generation if edge.generation_class == "intergenerational"
    )
    reverse = sum(
        1
        for edge in known_generation
        if edge.generation_class == "reverse_intergenerational"
    )
    unknown_generation = candidates - len(known_generation)
    kin_vertical = sum(1 for edge in known_generation if edge.kin_vertical)

    evidence = _edge_evidence(edges)
    comparable_evidence = _edge_evidence(comparable)
    rows: list[CulturalMeasurement] = [
        _count(
            candidates,
            measurement_id="acquisition_candidate_count",
            denominator=candidates,
            evidence=evidence,
        ),
        _count(
            len(resolved),
            measurement_id="attributable_edge_count",
            denominator=candidates,
            evidence=evidence,
        ),
        _count(
            len(comparable),
            measurement_id="comparable_edge_count",
            denominator=candidates,
            evidence=comparable_evidence,
        ),
        _count(
            ambiguous,
            measurement_id="ambiguous_source_count",
            denominator=candidates,
            evidence=evidence,
        ),
        _count(
            unknown,
            measurement_id="unknown_source_count",
            denominator=candidates,
            evidence=evidence,
        ),
        _count(
            independent,
            measurement_id="independent_rediscovery_count",
            denominator=candidates,
            evidence=evidence,
        ),
        _count(
            artifact,
            measurement_id="artifact_acquisition_count",
            denominator=candidates,
            evidence=evidence,
        ),
        _count(
            declared_mutated,
            measurement_id="declared_mutation_count",
            denominator=candidates,
            evidence=evidence,
        ),
        _count(
            recombined,
            measurement_id="recombination_count",
            denominator=candidates,
            evidence=evidence,
        ),
        _count(
            kin_vertical,
            measurement_id="vertical_kin_count",
            denominator=len(known_generation),
            evidence=evidence,
        ),
        _ratio(
            equal,
            len(comparable),
            measurement_id="exact_fidelity",
            reason_when_empty="no_comparable_edges",
            evidence=comparable_evidence,
        ),
        _ratio(
            changed,
            len(comparable),
            measurement_id="mutation_rate",
            reason_when_empty="no_comparable_edges",
            evidence=comparable_evidence,
        ),
        _ratio(
            declared_mutated,
            candidates,
            measurement_id="declared_mutation_share",
            evidence=evidence,
        ),
        _ratio(
            recombined,
            candidates,
            measurement_id="recombination_share",
            evidence=evidence,
        ),
        _ratio(
            horizontal,
            len(known_generation),
            measurement_id="horizontal_share",
            evidence=evidence,
        ),
        _ratio(
            forward,
            len(known_generation),
            measurement_id="forward_intergenerational_share",
            evidence=evidence,
        ),
        _ratio(
            reverse,
            len(known_generation),
            measurement_id="reverse_intergenerational_share",
            evidence=evidence,
        ),
        _ratio(
            unknown_generation,
            candidates,
            measurement_id="unknown_generation_share",
            evidence=evidence,
        ),
        _ratio(
            kin_vertical,
            len(known_generation),
            measurement_id="vertical_kin_share",
            evidence=evidence,
        ),
    ]
    rows.sort(key=lambda row: row.measurement_id)
    _LOG.debug(
        "cultural_evolution_transmission_computed candidate_count=%s "
        "comparable_count=%s row_count=%s",
        candidates,
        len(comparable),
        len(rows),
    )
    return tuple(rows)
