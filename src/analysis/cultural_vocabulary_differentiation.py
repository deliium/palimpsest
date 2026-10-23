"""Vocabulary inventory divergence, separate from semantic meaning drift."""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations
from typing import Final

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    InventoryBoundary,
)
from analysis.models import MetricAvailability
from analysis.numerical import jensen_shannon_divergence

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.cultural_vocabulary_differentiation"
)

CULTURAL_VOCABULARY_DIFFERENTIATION_FAMILY: Final[str] = (
    "cultural_vocabulary_differentiation"
)
CULTURAL_VOCABULARY_DIFFERENTIATION_ALGORITHM_VERSION: Final[str] = (
    "cultural-vocabulary-differentiation@1"
)
_DIMENSION: Final[str] = "vocabulary"

__all__ = [
    "CULTURAL_VOCABULARY_DIFFERENTIATION_ALGORITHM_VERSION",
    "CULTURAL_VOCABULARY_DIFFERENTIATION_FAMILY",
    "compute_cultural_vocabulary_differentiation",
]


def _measurement(
    *,
    measurement_id: str,
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
    population_basis: str = "fixed_eligible_pairs",
) -> CulturalMeasurement:
    return CulturalMeasurement(
        family=CULTURAL_VOCABULARY_DIFFERENTIATION_FAMILY,
        algorithm_version=CULTURAL_VOCABULARY_DIFFERENTIATION_ALGORITHM_VERSION,
        policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        measurement_id=measurement_id,
        dimension=_DIMENSION,
        representation="label_inventory",
        scope=scope,
        partition_id=partition_id,
        group_ids=group_ids,
        population_basis=population_basis,
        denominator_code=population_basis,
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


def _complete_owners(boundary: InventoryBoundary) -> set[str]:
    coverage = _coverage_index(boundary)
    return {
        owner
        for owner in boundary.living_owner_ids
        if coverage.get((owner, _DIMENSION)) == "complete"
    }


def _inventory(boundary: InventoryBoundary) -> dict[str, set[str]]:
    living = set(boundary.living_owner_ids)
    inventory: dict[str, set[str]] = defaultdict(set)
    for entry in boundary.entries:
        if (
            entry.dimension == _DIMENSION
            and entry.owner_id in living
            and entry.status in (None, "active")
        ):
            inventory[entry.owner_id].add(entry.content_digest)
    return dict(inventory)


def _memberships(
    inputs: CulturalEvolutionInputs,
) -> dict[tuple[int, str], dict[str, str]]:
    result: dict[tuple[int, str], dict[str, str]] = defaultdict(dict)
    for membership in inputs.group_memberships:
        key = (membership.boundary_tick, membership.basis_id)
        existing = result[key].get(membership.owner_id)
        if existing is not None and existing != membership.group_id:
            raise ValueError("ambiguous_group_membership")
        result[key][membership.owner_id] = membership.group_id
    return dict(result)


def _group_labels(inventory: dict[str, set[str]], owners: set[str]) -> set[str]:
    labels: set[str] = set()
    for owner in owners:
        labels.update(inventory.get(owner, set()))
    return labels


def _jaccard_distance(left: set[str], right: set[str]) -> float | None:
    if not left and not right:
        return None
    if not left or not right:
        return 1.0
    return 1.0 - len(left & right) / len(left | right)


def _group_evidence(
    inputs: CulturalEvolutionInputs, basis: str, group: str
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                evidence_id
                for membership in inputs.group_memberships
                if membership.basis_id == basis and membership.group_id == group
                for evidence_id in membership.evidence_ids
            }
        )
    )


def _point_rows(
    inputs: CulturalEvolutionInputs,
    boundary: InventoryBoundary,
    memberships: dict[tuple[int, str], dict[str, str]],
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    inventory = _inventory(boundary)
    complete = _complete_owners(boundary)
    bases = sorted(
        basis for (tick, basis) in memberships if tick == boundary.boundary_tick
    )
    for basis in bases:
        assignment = memberships[(boundary.boundary_tick, basis)]
        groups: dict[str, set[str]] = defaultdict(set)
        for owner, group in assignment.items():
            if owner in boundary.living_owner_ids:
                groups[group].add(owner)
        labels_by_group = {
            group: _group_labels(inventory, owners & complete)
            for group, owners in groups.items()
        }
        for group in sorted(groups):
            labels = labels_by_group[group]
            evidence = _group_evidence(inputs, basis, group)
            complete_owners = groups[group] & complete
            for measurement_id, status in (
                ("vocabulary_candidate_label_count", "candidate"),
                ("vocabulary_retired_label_count", "retired"),
            ):
                count = len(
                    {
                        entry.local_entry_id
                        for entry in boundary.entries
                        if entry.dimension == _DIMENSION
                        and entry.owner_id in complete_owners
                        and entry.status == status
                    }
                )
                rows.append(
                    _measurement(
                        measurement_id=measurement_id,
                        scope="group",
                        group_ids=(group,),
                        partition_id=basis,
                        value=float(count),
                        numerator=float(count),
                        denominator=float(len(complete_owners)),
                        availability=MetricAvailability.PRESENT,
                        reason_code=None,
                        baseline_tick=boundary.boundary_tick,
                        end_tick=boundary.boundary_tick,
                        coverage_observed=len(complete_owners),
                        coverage_expected=len(groups[group]),
                        units="count",
                        evidence_ids=evidence,
                        population_basis="eligible_living_owners",
                    )
                )
            rows.append(
                _measurement(
                    measurement_id="group_vocabulary_richness",
                    scope="group",
                    group_ids=(group,),
                    partition_id=basis,
                    value=float(len(labels)),
                    numerator=None,
                    denominator=None,
                    availability=MetricAvailability.PRESENT,
                    reason_code=None,
                    baseline_tick=boundary.boundary_tick,
                    end_tick=boundary.boundary_tick,
                    coverage_observed=len(groups[group] & complete),
                    coverage_expected=len(groups[group]),
                    units="count",
                    evidence_ids=evidence,
                )
            )
        for left, right in combinations(sorted(groups), 2):
            left_labels = labels_by_group[left]
            right_labels = labels_by_group[right]
            trait_union = sorted(left_labels | right_labels)
            left_counts = [
                float(
                    sum(
                        1
                        for owner in groups[left] & complete
                        if label in inventory.get(owner, set())
                    )
                )
                for label in trait_union
            ]
            right_counts = [
                float(
                    sum(
                        1
                        for owner in groups[right] & complete
                        if label in inventory.get(owner, set())
                    )
                )
                for label in trait_union
            ]
            divergence = jensen_shannon_divergence(left_counts, right_counts)
            distance = _jaccard_distance(left_labels, right_labels)
            evidence = tuple(
                sorted(
                    set(
                        _group_evidence(inputs, basis, left)
                        + _group_evidence(inputs, basis, right)
                    )
                )
            )
            rows.append(
                _measurement(
                    measurement_id="between_group_vocabulary_js",
                    scope="group_pair",
                    group_ids=(left, right),
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
                    coverage_observed=len((groups[left] | groups[right]) & complete),
                    coverage_expected=len(groups[left] | groups[right]),
                    units="nats",
                    evidence_ids=evidence,
                )
            )
            rows.append(
                _measurement(
                    measurement_id="between_group_vocabulary_jaccard",
                    scope="group_pair",
                    group_ids=(left, right),
                    partition_id=basis,
                    value=distance,
                    numerator=float(len(left_labels & right_labels)),
                    denominator=float(len(left_labels | right_labels)),
                    availability=(
                        MetricAvailability.PRESENT
                        if distance is not None
                        else MetricAvailability.UNKNOWN
                    ),
                    reason_code=None if distance is not None else "empty_union",
                    baseline_tick=boundary.boundary_tick,
                    end_tick=boundary.boundary_tick,
                    coverage_observed=len((groups[left] | groups[right]) & complete),
                    coverage_expected=len(groups[left] | groups[right]),
                    units="jaccard_distance",
                    evidence_ids=evidence,
                )
            )
            rows.append(
                _measurement(
                    measurement_id="between_group_shared_label_count",
                    scope="group_pair",
                    group_ids=(left, right),
                    partition_id=basis,
                    value=float(len(left_labels & right_labels)),
                    numerator=float(len(left_labels & right_labels)),
                    denominator=float(len(left_labels | right_labels)),
                    availability=MetricAvailability.PRESENT,
                    reason_code=None,
                    baseline_tick=boundary.boundary_tick,
                    end_tick=boundary.boundary_tick,
                    coverage_observed=len((groups[left] | groups[right]) & complete),
                    coverage_expected=len(groups[left] | groups[right]),
                    units="count",
                    evidence_ids=evidence,
                )
            )
            rows.append(
                _measurement(
                    measurement_id="between_group_label_union_size",
                    scope="group_pair",
                    group_ids=(left, right),
                    partition_id=basis,
                    value=float(len(left_labels | right_labels)),
                    numerator=None,
                    denominator=None,
                    availability=MetricAvailability.PRESENT,
                    reason_code=None,
                    baseline_tick=boundary.boundary_tick,
                    end_tick=boundary.boundary_tick,
                    coverage_observed=len((groups[left] | groups[right]) & complete),
                    coverage_expected=len(groups[left] | groups[right]),
                    units="count",
                    evidence_ids=evidence,
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
            evidence = _group_evidence(inputs, basis, group)
            if baseline is None or endpoint is None:
                rows.append(
                    _measurement(
                        measurement_id="within_group_vocabulary_convergence",
                        scope="group",
                        group_ids=(group,),
                        partition_id=basis,
                        value=None,
                        numerator=None,
                        denominator=None,
                        availability=MetricAvailability.UNKNOWN,
                        reason_code=(
                            "missing_baseline"
                            if baseline is None
                            else "missing_endpoint"
                        ),
                        baseline_tick=baseline_tick,
                        end_tick=resolved_end,
                        coverage_observed=0,
                        coverage_expected=None,
                        units="jaccard_distance",
                        evidence_ids=evidence,
                    )
                )
                continue
            baseline_inventory = _inventory(baseline)
            endpoint_inventory = _inventory(endpoint)
            baseline_complete = _complete_owners(baseline)
            endpoint_complete = _complete_owners(endpoint)
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
            baseline_distances: list[float] = []
            endpoint_distances: list[float] = []
            for left, right in combinations(sorted(cohort), 2):
                baseline_union = baseline_inventory.get(
                    left, set()
                ) | baseline_inventory.get(right, set())
                endpoint_union = endpoint_inventory.get(
                    left, set()
                ) | endpoint_inventory.get(right, set())
                if not baseline_union or not endpoint_union:
                    continue
                baseline_distance = _jaccard_distance(
                    baseline_inventory.get(left, set()),
                    baseline_inventory.get(right, set()),
                )
                endpoint_distance = _jaccard_distance(
                    endpoint_inventory.get(left, set()),
                    endpoint_inventory.get(right, set()),
                )
                if baseline_distance is None or endpoint_distance is None:
                    continue
                baseline_distances.append(baseline_distance)
                endpoint_distances.append(endpoint_distance)
            if not baseline_distances:
                rows.append(
                    _measurement(
                        measurement_id="within_group_vocabulary_convergence",
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
            baseline_mean = sum(baseline_distances) / len(baseline_distances)
            endpoint_mean = sum(endpoint_distances) / len(endpoint_distances)
            rows.append(
                _measurement(
                    measurement_id="within_group_vocabulary_convergence",
                    scope="group",
                    group_ids=(group,),
                    partition_id=basis,
                    value=baseline_mean - endpoint_mean,
                    numerator=float(len(baseline_distances)),
                    denominator=float(len(baseline_distances)),
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


def compute_cultural_vocabulary_differentiation(
    inputs: CulturalEvolutionInputs,
) -> tuple[CulturalMeasurement, ...]:
    """Compute label-inventory divergence without semantic referent truth."""
    if type(inputs) is not CulturalEvolutionInputs:
        raise TypeError("inputs must be CulturalEvolutionInputs")
    if not inputs.group_memberships:
        return ()
    memberships = _memberships(inputs)
    boundary_by_tick = {
        boundary.boundary_tick: boundary for boundary in inputs.boundaries
    }
    rows: list[CulturalMeasurement] = []
    for boundary in inputs.boundaries:
        rows.extend(_point_rows(inputs, boundary, memberships))
    rows.extend(_convergence_rows(inputs, boundary_by_tick, memberships))
    rows.sort(
        key=lambda row: (
            row.measurement_id,
            row.baseline_tick,
            row.end_tick,
            row.group_ids,
        )
    )
    _LOG.debug(
        "cultural_vocabulary_differentiation_computed boundary_count=%s row_count=%s",
        len(boundary_by_tick),
        len(rows),
    )
    return tuple(rows)
