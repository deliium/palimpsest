"""Group divergence and fixed-pair within-group convergence."""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations
from typing import Final

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CULTURAL_FEATURE_DIMENSIONS,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    InventoryBoundary,
)
from analysis.models import MetricAvailability
from analysis.numerical import jensen_shannon_divergence

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.cultural_population_structure"
)

CULTURAL_POPULATION_STRUCTURE_FAMILY: Final[str] = "cultural_population_structure@1"
CULTURAL_POPULATION_STRUCTURE_ALGORITHM_VERSION: Final[str] = (
    "cultural-population-structure@1"
)

_DIMENSIONS: Final[tuple[str, ...]] = (
    *CULTURAL_FEATURE_DIMENSIONS,
    "vocabulary",
    "narrative",
    "technology",
)

_REPRESENTATION: Final[dict[str, str]] = {
    **{dimension: "ledger_carriage" for dimension in CULTURAL_FEATURE_DIMENSIONS},
    "vocabulary": "label_inventory",
    "narrative": "narrative_lineage",
    "technology": "practical_content_key",
}

_KNOWN_GENERATIONS: Final[frozenset[str]] = frozenset(
    {"horizontal", "intergenerational", "reverse_intergenerational"}
)

__all__ = [
    "CULTURAL_POPULATION_STRUCTURE_ALGORITHM_VERSION",
    "CULTURAL_POPULATION_STRUCTURE_FAMILY",
    "compute_cultural_population_structure",
]


def _measurement(
    *,
    measurement_id: str,
    dimension: str,
    scope: str,
    group_ids: tuple[str, ...],
    partition_id: str | None,
    value: float | None,
    numerator: float | None,
    denominator: float | None,
    availability: MetricAvailability,
    reason_code: str | None,
    baseline_tick: int,
    end_tick: int,
    coverage_observed: int,
    coverage_expected: int | None,
    units: str,
    evidence_ids: tuple[str, ...] = (),
) -> CulturalMeasurement:
    return CulturalMeasurement(
        family=CULTURAL_POPULATION_STRUCTURE_FAMILY,
        algorithm_version=CULTURAL_POPULATION_STRUCTURE_ALGORITHM_VERSION,
        policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        measurement_id=measurement_id,
        dimension=dimension,
        representation=_REPRESENTATION[dimension],
        scope=scope,
        partition_id=partition_id,
        group_ids=group_ids,
        population_basis="fixed_eligible_pairs",
        denominator_code="fixed_eligible_pairs",
        baseline_tick=baseline_tick,
        end_tick=end_tick,
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


def _coverage_index(boundary: InventoryBoundary) -> dict[tuple[str, str], str]:
    return {
        (owner, dimension): coverage
        for owner, dimension, coverage in boundary.owner_dimension_coverage
    }


def _complete_owners(boundary: InventoryBoundary, dimension: str) -> set[str]:
    coverage = _coverage_index(boundary)
    return {
        owner
        for owner in boundary.living_owner_ids
        if coverage.get((owner, dimension)) == "complete"
    }


def _inventory(boundary: InventoryBoundary, dimension: str) -> dict[str, set[str]]:
    inventories: dict[str, set[str]] = defaultdict(set)
    living = set(boundary.living_owner_ids)
    for entry in boundary.entries:
        if entry.dimension == dimension and entry.owner_id in living:
            inventories[entry.owner_id].add(entry.content_digest)
    return dict(inventories)


def _memberships(
    inputs: CulturalEvolutionInputs,
) -> dict[tuple[int, str], dict[str, str]]:
    """Map (boundary, basis_id) -> owner -> group, rejecting overlap."""
    result: dict[tuple[int, str], dict[str, str]] = defaultdict(dict)
    for membership in inputs.group_memberships:
        key = (membership.boundary_tick, membership.basis_id)
        existing = result[key].get(membership.owner_id)
        if existing is not None and existing != membership.group_id:
            raise ValueError("ambiguous_group_membership")
        result[key][membership.owner_id] = membership.group_id
    return dict(result)


def _pair_distance(left: set[str], right: set[str]) -> float | None:
    if not left and not right:
        return None
    if not left or not right:
        return 1.0
    return 1.0 - (len(left & right) / len(left | right))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _point_structure_rows(
    inputs: CulturalEvolutionInputs,
    boundary: InventoryBoundary,
    memberships: dict[tuple[int, str], dict[str, str]],
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    inventories = {
        dimension: _inventory(boundary, dimension) for dimension in _DIMENSIONS
    }
    complete = {
        dimension: _complete_owners(boundary, dimension) for dimension in _DIMENSIONS
    }
    bases = sorted(
        basis
        for (tick, basis), _ in memberships.items()
        if tick == boundary.boundary_tick
    )
    for basis in bases:
        assignment = memberships[(boundary.boundary_tick, basis)]
        groups: dict[str, set[str]] = defaultdict(set)
        for owner, group in assignment.items():
            if owner in boundary.living_owner_ids:
                groups[group].add(owner)
        for dimension in _DIMENSIONS:
            distributions: dict[str, list[float]] = {}
            trait_union = sorted(
                {
                    trait
                    for owner in assignment
                    for trait in inventories[dimension].get(owner, set())
                }
            )
            for group in sorted(groups):
                owners = sorted(groups[group] & complete[dimension])
                distribution = [
                    float(
                        sum(
                            1
                            for owner in owners
                            if trait in inventories[dimension].get(owner, set())
                        )
                    )
                    for trait in trait_union
                ]
                distributions[group] = distribution
                pair_distances = [
                    distance
                    for left, right in combinations(owners, 2)
                    if (
                        distance := _pair_distance(
                            inventories[dimension].get(left, set()),
                            inventories[dimension].get(right, set()),
                        )
                    )
                    is not None
                ]
                evidence = tuple(
                    sorted(
                        {
                            evidence_id
                            for membership in inputs.group_memberships
                            if membership.boundary_tick == boundary.boundary_tick
                            and membership.basis_id == basis
                            and membership.group_id == group
                            for evidence_id in membership.evidence_ids
                        }
                    )
                )
                if not pair_distances:
                    rows.append(
                        _measurement(
                            measurement_id="within_group_pairwise_distance",
                            dimension=dimension,
                            scope="group",
                            group_ids=(group,),
                            partition_id=basis,
                            value=None,
                            numerator=None,
                            denominator=float(len(pair_distances)),
                            availability=MetricAvailability.UNKNOWN,
                            reason_code="no_eligible_pairs",
                            baseline_tick=boundary.boundary_tick,
                            end_tick=boundary.boundary_tick,
                            coverage_observed=len(owners),
                            coverage_expected=len(groups[group]),
                            units="jaccard_distance",
                            evidence_ids=evidence,
                        )
                    )
                else:
                    rows.append(
                        _measurement(
                            measurement_id="within_group_pairwise_distance",
                            dimension=dimension,
                            scope="group",
                            group_ids=(group,),
                            partition_id=basis,
                            value=_mean(pair_distances),
                            numerator=float(len(pair_distances)),
                            denominator=float(len(pair_distances)),
                            availability=MetricAvailability.PRESENT,
                            reason_code=None,
                            baseline_tick=boundary.boundary_tick,
                            end_tick=boundary.boundary_tick,
                            coverage_observed=len(owners),
                            coverage_expected=len(groups[group]),
                            units="jaccard_distance",
                            evidence_ids=evidence,
                        )
                    )
            for left_group, right_group in combinations(sorted(groups), 2):
                divergence = jensen_shannon_divergence(
                    distributions[left_group], distributions[right_group]
                )
                rows.append(
                    _measurement(
                        measurement_id="between_group_js_divergence",
                        dimension=dimension,
                        scope="group_pair",
                        group_ids=(left_group, right_group),
                        partition_id=basis,
                        value=divergence,
                        numerator=None,
                        denominator=None,
                        availability=(
                            MetricAvailability.PRESENT
                            if divergence is not None
                            else MetricAvailability.UNKNOWN
                        ),
                        reason_code=(
                            None if divergence is not None else "empty_group_mass"
                        ),
                        baseline_tick=boundary.boundary_tick,
                        end_tick=boundary.boundary_tick,
                        coverage_observed=len(groups[left_group] | groups[right_group]),
                        coverage_expected=len(groups[left_group] | groups[right_group]),
                        units="nats",
                    )
                )
    return rows


def _convergence_rows(
    inputs: CulturalEvolutionInputs,
    boundary_by_tick: dict[int, InventoryBoundary],
    memberships: dict[tuple[int, str], dict[str, str]],
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    baseline_tick = inputs.window.baseline_boundary
    resolved_end = (
        inputs.window.end_boundary
        if inputs.window.end_boundary is not None
        else (max(boundary_by_tick) if boundary_by_tick else None)
    )
    if resolved_end is None:
        return rows
    baseline = boundary_by_tick.get(baseline_tick)
    endpoint = boundary_by_tick.get(resolved_end)
    bases = sorted(
        {
            basis
            for (tick, basis) in memberships
            if tick in {baseline_tick, resolved_end}
        }
    )
    for basis in bases:
        baseline_assignment = memberships.get((baseline_tick, basis), {})
        endpoint_assignment = memberships.get((resolved_end, basis), {})
        if baseline is None or endpoint is None:
            groups = sorted(
                set(baseline_assignment.values()) | set(endpoint_assignment.values())
            )
        else:
            groups = sorted(
                set(baseline_assignment.values()) & set(endpoint_assignment.values())
            )
        for group in groups:
            evidence = tuple(
                sorted(
                    {
                        evidence_id
                        for membership in inputs.group_memberships
                        if membership.basis_id == basis
                        and membership.group_id == group
                        and membership.boundary_tick in {baseline_tick, resolved_end}
                        for evidence_id in membership.evidence_ids
                    }
                )
            )
            for dimension in _DIMENSIONS:
                if baseline is None or endpoint is None:
                    reason = (
                        "missing_baseline" if baseline is None else "missing_endpoint"
                    )
                    rows.append(
                        _measurement(
                            measurement_id="within_group_convergence",
                            dimension=dimension,
                            scope="group",
                            group_ids=(group,),
                            partition_id=basis,
                            value=None,
                            numerator=None,
                            denominator=None,
                            availability=MetricAvailability.UNKNOWN,
                            reason_code=reason,
                            baseline_tick=baseline_tick,
                            end_tick=resolved_end,
                            coverage_observed=0,
                            coverage_expected=None,
                            units="jaccard_distance",
                            evidence_ids=evidence,
                        )
                    )
                    continue
                baseline_inventory = _inventory(baseline, dimension)
                endpoint_inventory = _inventory(endpoint, dimension)
                baseline_complete = _complete_owners(baseline, dimension)
                endpoint_complete = _complete_owners(endpoint, dimension)
                cohort = (
                    {
                        owner
                        for owner in baseline.living_owner_ids
                        if baseline_assignment.get(owner) == group
                    }
                    & {
                        owner
                        for owner in endpoint.living_owner_ids
                        if endpoint_assignment.get(owner) == group
                    }
                    & baseline_complete
                    & endpoint_complete
                )
                pairs = list(combinations(sorted(cohort), 2))
                kept: list[tuple[str, str]] = []
                baseline_distances: list[float] = []
                endpoint_distances: list[float] = []
                for left, right in pairs:
                    baseline_union = baseline_inventory.get(
                        left, set()
                    ) | baseline_inventory.get(right, set())
                    endpoint_union = endpoint_inventory.get(
                        left, set()
                    ) | endpoint_inventory.get(right, set())
                    if not baseline_union or not endpoint_union:
                        continue
                    baseline_distance = _pair_distance(
                        baseline_inventory.get(left, set()),
                        baseline_inventory.get(right, set()),
                    )
                    endpoint_distance = _pair_distance(
                        endpoint_inventory.get(left, set()),
                        endpoint_inventory.get(right, set()),
                    )
                    if baseline_distance is None or endpoint_distance is None:
                        continue
                    kept.append((left, right))
                    baseline_distances.append(baseline_distance)
                    endpoint_distances.append(endpoint_distance)
                if not kept:
                    rows.append(
                        _measurement(
                            measurement_id="within_group_convergence",
                            dimension=dimension,
                            scope="group",
                            group_ids=(group,),
                            partition_id=basis,
                            value=None,
                            numerator=None,
                            denominator=0.0,
                            availability=MetricAvailability.UNKNOWN,
                            reason_code="no_eligible_pairs",
                            baseline_tick=baseline_tick,
                            end_tick=resolved_end,
                            coverage_observed=len(cohort),
                            coverage_expected=None,
                            units="jaccard_distance",
                            evidence_ids=evidence,
                        )
                    )
                    continue
                baseline_mean = _mean(baseline_distances)
                endpoint_mean = _mean(endpoint_distances)
                rows.append(
                    _measurement(
                        measurement_id="within_group_convergence",
                        dimension=dimension,
                        scope="group",
                        group_ids=(group,),
                        partition_id=basis,
                        value=baseline_mean - endpoint_mean,
                        numerator=float(len(kept)),
                        denominator=float(len(kept)),
                        availability=MetricAvailability.PRESENT,
                        reason_code=None,
                        baseline_tick=baseline_tick,
                        end_tick=resolved_end,
                        coverage_observed=len(cohort),
                        coverage_expected=len(cohort),
                        units="jaccard_distance",
                        evidence_ids=evidence,
                    )
                )
    return rows


def compute_cultural_population_structure(
    inputs: CulturalEvolutionInputs,
) -> tuple[CulturalMeasurement, ...]:
    """Compute dimensional group divergence and fixed-pair convergence."""
    if type(inputs) is not CulturalEvolutionInputs:
        raise TypeError("inputs must be CulturalEvolutionInputs")
    if not inputs.group_memberships:
        _LOG.debug(
            "cultural_population_structure_skipped reason_code=%s",
            "no_group_memberships",
        )
        return ()
    memberships = _memberships(inputs)
    boundary_by_tick = {
        boundary.boundary_tick: boundary for boundary in inputs.boundaries
    }
    rows: list[CulturalMeasurement] = []
    for boundary in inputs.boundaries:
        rows.extend(_point_structure_rows(inputs, boundary, memberships))
    rows.extend(_convergence_rows(inputs, boundary_by_tick, memberships))
    rows.sort(
        key=lambda row: (
            row.measurement_id,
            row.dimension,
            row.baseline_tick,
            row.end_tick,
            row.group_ids,
        )
    )
    _LOG.debug(
        "cultural_population_structure_computed boundary_count=%s "
        "group_count=%s row_count=%s",
        len(boundary_by_tick),
        len({membership.group_id for membership in inputs.group_memberships}),
        len(rows),
    )
    return tuple(rows)
