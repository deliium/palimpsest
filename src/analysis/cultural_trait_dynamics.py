"""Frequency, persistence, extinction, and diversity for cultural inventories."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Final

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CULTURAL_FEATURE_DIMENSIONS,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    EvidencePointer,
    InventoryBoundary,
)
from analysis.models import MetricAvailability

_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_trait_dynamics")

CULTURAL_TRAIT_DYNAMICS_FAMILY: Final[str] = "cultural_trait_dynamics"
CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION: Final[str] = "cultural-trait-dynamics@1"

_REPRESENTATION: Final[dict[str, str]] = {
    **{dimension: "ledger_carriage" for dimension in CULTURAL_FEATURE_DIMENSIONS},
    "vocabulary": "label_inventory",
    "narrative": "narrative_lineage",
    "technology": "practical_content_key",
}

_ALL_DIMENSIONS: Final[tuple[str, ...]] = (
    *CULTURAL_FEATURE_DIMENSIONS,
    "vocabulary",
    "narrative",
    "technology",
)

__all__ = [
    "CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION",
    "CULTURAL_TRAIT_DYNAMICS_FAMILY",
    "compute_cultural_trait_dynamics",
]


def _measurement(
    *,
    measurement_id: str,
    dimension: str,
    units: str,
    value: float | None,
    numerator: float | None,
    denominator: float | None,
    availability: MetricAvailability,
    reason_code: str | None,
    coverage_observed: int,
    coverage_expected: int | None,
    baseline_tick: int,
    end_tick: int,
    trait_id: str | None = None,
    evidence_ids: tuple[str, ...] = (),
    left_censored: bool = False,
    right_censored: bool = False,
) -> CulturalMeasurement:
    return CulturalMeasurement(
        family=CULTURAL_TRAIT_DYNAMICS_FAMILY,
        algorithm_version=CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION,
        policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        measurement_id=measurement_id,
        dimension=dimension,
        representation=_REPRESENTATION[dimension],
        scope="global",
        partition_id=None,
        group_ids=(),
        population_basis=(
            "fixed_baseline_traits"
            if measurement_id in {"endpoint_persistence", "continuous_persistence"}
            else "carrier_incidences"
            if measurement_id
            in {
                "richness",
                "shannon_entropy",
                "effective_diversity",
                "simpson_diversity",
            }
            else "eligible_living_owners"
        ),
        denominator_code=(
            "fixed_baseline_traits"
            if measurement_id in {"endpoint_persistence", "continuous_persistence"}
            else "carrier_incidences"
            if measurement_id
            in {
                "richness",
                "shannon_entropy",
                "effective_diversity",
                "simpson_diversity",
            }
            else "eligible_living_owners"
        ),
        baseline_tick=baseline_tick,
        end_tick=end_tick,
        trait_id=trait_id,
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
        left_censored=left_censored,
        right_censored=right_censored,
        evidence_ids=evidence_ids,
    )


def _coverage_index(
    boundary: InventoryBoundary,
) -> dict[tuple[str, str], str]:
    return {
        (owner, dimension): coverage
        for owner, dimension, coverage in boundary.owner_dimension_coverage
    }


def _dimension_population(
    boundary: InventoryBoundary, dimension: str
) -> tuple[tuple[str, ...], int, int, bool]:
    """Return eligible living owners, observed, expected, complete."""
    coverage = _coverage_index(boundary)
    eligible: list[str] = []
    observed = 0
    missing = 0
    for owner in boundary.living_owner_ids:
        code = coverage.get((owner, dimension))
        if code == "disabled":
            continue
        eligible.append(owner)
        if code == "complete":
            observed += 1
        else:
            missing += 1
    return tuple(eligible), observed, len(eligible), missing == 0


def _carriers(boundary: InventoryBoundary, dimension: str) -> dict[str, set[str]]:
    carriers: dict[str, set[str]] = defaultdict(set)
    living = set(boundary.living_owner_ids)
    for entry in boundary.entries:
        if entry.dimension != dimension:
            continue
        if entry.owner_id not in living:
            continue
        carriers[entry.content_digest].add(entry.owner_id)
    return dict(carriers)


def _entry_pointers(
    inputs: CulturalEvolutionInputs,
) -> dict[tuple[str, int, str], EvidencePointer]:
    return {
        (pointer.owner_id or "", pointer.boundary_tick, pointer.local_id or ""): pointer
        for pointer in inputs.evidence_pointers
        if pointer.source_kind.startswith("trait:")
    }


def _roster_pointer(
    inputs: CulturalEvolutionInputs, boundary_tick: int
) -> EvidencePointer | None:
    for pointer in inputs.evidence_pointers:
        if (
            pointer.source_kind == "roster"
            and pointer.boundary_tick == boundary_tick
            and pointer.local_id == f"roster:{boundary_tick}"
        ):
            return pointer
    return None


def _trait_evidence(
    inputs: CulturalEvolutionInputs,
    boundary: InventoryBoundary,
    dimension: str,
    trait_id: str | None,
) -> tuple[str, ...]:
    pointer_index = _entry_pointers(inputs)
    ids: set[str] = set()
    roster = _roster_pointer(inputs, boundary.boundary_tick)
    if roster is not None:
        ids.add(roster.pointer_id)
    if trait_id is not None:
        for entry in boundary.entries:
            if entry.dimension != dimension:
                continue
            if entry.content_digest != trait_id:
                continue
            pointer = pointer_index.get(
                (entry.owner_id, boundary.boundary_tick, entry.local_entry_id)
            )
            if pointer is not None:
                ids.add(pointer.pointer_id)
    return tuple(sorted(ids))


def _frequency_rows(
    inputs: CulturalEvolutionInputs,
    boundaries: tuple[InventoryBoundary, ...],
    trait_union: dict[str, set[str]],
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    for boundary in boundaries:
        for dimension in _ALL_DIMENSIONS:
            _, observed, expected, complete = _dimension_population(boundary, dimension)
            carriers = _carriers(boundary, dimension)
            for trait_id in sorted(trait_union[dimension]):
                carrier_count = len(carriers.get(trait_id, set()))
                evidence = _trait_evidence(inputs, boundary, dimension, trait_id)
                if expected == 0:
                    availability = MetricAvailability.UNKNOWN
                    value = None
                    reason = "population_unavailable"
                elif complete:
                    availability = MetricAvailability.PRESENT
                    value = carrier_count / expected
                    reason = None
                else:
                    availability = MetricAvailability.PARTIAL
                    value = None
                    reason = "partial_owner_coverage"
                rows.append(
                    _measurement(
                        measurement_id="trait_frequency",
                        dimension=dimension,
                        units="proportion",
                        value=value,
                        numerator=float(carrier_count),
                        denominator=float(expected),
                        availability=availability,
                        reason_code=reason,
                        coverage_observed=observed,
                        coverage_expected=expected,
                        baseline_tick=boundary.boundary_tick,
                        end_tick=boundary.boundary_tick,
                        trait_id=trait_id,
                        evidence_ids=evidence,
                    )
                )
    return rows


def _diversity_rows(
    boundaries: tuple[InventoryBoundary, ...],
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    for boundary in boundaries:
        for dimension in _ALL_DIMENSIONS:
            _, observed, expected, complete = _dimension_population(boundary, dimension)
            carriers = _carriers(boundary, dimension)
            incidences = sum(len(owners) for owners in carriers.values())
            evidence: tuple[str, ...] = ()
            if expected == 0:
                availability = MetricAvailability.UNKNOWN
                reason = "population_unavailable"
            elif not complete:
                availability = MetricAvailability.PARTIAL
                reason = "partial_owner_coverage"
            else:
                availability = MetricAvailability.PRESENT
                reason = None
            if availability is not MetricAvailability.PRESENT:
                for measurement_id, units in (
                    ("richness", "count"),
                    ("shannon_entropy", "nats"),
                    ("effective_diversity", "effective_traits"),
                    ("simpson_diversity", "proportion"),
                ):
                    rows.append(
                        _measurement(
                            measurement_id=measurement_id,
                            dimension=dimension,
                            units=units,
                            value=None,
                            numerator=None,
                            denominator=None,
                            availability=availability,
                            reason_code=reason,
                            coverage_observed=observed,
                            coverage_expected=expected,
                            baseline_tick=boundary.boundary_tick,
                            end_tick=boundary.boundary_tick,
                            evidence_ids=evidence,
                        )
                    )
                continue
            if incidences == 0:
                rich = 0.0
                entropy = 0.0
                effective = 0.0
                simpson = 0.0
            else:
                probabilities = [
                    len(owners) / incidences for owners in carriers.values()
                ]
                rich = float(len(probabilities))
                entropy = -sum(p * math.log(p) for p in probabilities if p > 0.0)
                effective = math.exp(entropy)
                simpson = 1.0 - sum(p * p for p in probabilities)
            for measurement_id, units, value in (
                ("richness", "count", rich),
                ("shannon_entropy", "nats", entropy),
                ("effective_diversity", "effective_traits", effective),
                ("simpson_diversity", "proportion", simpson),
            ):
                rows.append(
                    _measurement(
                        measurement_id=measurement_id,
                        dimension=dimension,
                        units=units,
                        value=value,
                        numerator=None,
                        denominator=None,
                        availability=MetricAvailability.PRESENT,
                        reason_code=None,
                        coverage_observed=observed,
                        coverage_expected=expected,
                        baseline_tick=boundary.boundary_tick,
                        end_tick=boundary.boundary_tick,
                        evidence_ids=evidence,
                    )
                )
    return rows


def _baseline_cohort(boundary: InventoryBoundary, dimension: str) -> set[str]:
    return set(_carriers(boundary, dimension))


def _persistence_rows(
    inputs: CulturalEvolutionInputs,
    boundary_by_tick: dict[int, InventoryBoundary],
    resolved_end: int | None,
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    baseline_tick = inputs.window.baseline_boundary
    baseline = boundary_by_tick.get(baseline_tick)
    for dimension in _ALL_DIMENSIONS:
        if baseline is None:
            rows.append(
                _measurement(
                    measurement_id="endpoint_persistence",
                    dimension=dimension,
                    units="proportion",
                    value=None,
                    numerator=None,
                    denominator=None,
                    availability=MetricAvailability.UNKNOWN,
                    reason_code="missing_baseline",
                    coverage_observed=0,
                    coverage_expected=None,
                    baseline_tick=baseline_tick,
                    end_tick=resolved_end
                    if resolved_end is not None
                    else baseline_tick,
                    left_censored=True,
                )
            )
            rows.append(
                _measurement(
                    measurement_id="continuous_persistence",
                    dimension=dimension,
                    units="proportion",
                    value=None,
                    numerator=None,
                    denominator=None,
                    availability=MetricAvailability.UNKNOWN,
                    reason_code="missing_baseline",
                    coverage_observed=0,
                    coverage_expected=None,
                    baseline_tick=baseline_tick,
                    end_tick=resolved_end
                    if resolved_end is not None
                    else baseline_tick,
                    left_censored=True,
                )
            )
            continue
        _, observed, expected, baseline_complete = _dimension_population(
            baseline, dimension
        )
        baseline_traits = _baseline_cohort(baseline, dimension)
        if expected == 0:
            reason = "population_unavailable"
            availability = MetricAvailability.UNKNOWN
            baseline_value: float | None = None
        elif not baseline_complete:
            reason = "partial_baseline"
            availability = MetricAvailability.PARTIAL
            baseline_value = None
        elif not baseline_traits:
            reason = "empty_baseline"
            availability = MetricAvailability.PRESENT
            baseline_value = None
        else:
            reason = None
            availability = MetricAvailability.PRESENT
            baseline_value = float(len(baseline_traits))
        if resolved_end is None:
            rows.append(
                _measurement(
                    measurement_id="endpoint_persistence",
                    dimension=dimension,
                    units="proportion",
                    value=None,
                    numerator=None,
                    denominator=baseline_value,
                    availability=MetricAvailability.UNKNOWN,
                    reason_code="missing_endpoint",
                    coverage_observed=observed,
                    coverage_expected=expected,
                    baseline_tick=baseline_tick,
                    end_tick=baseline_tick,
                    right_censored=True,
                )
            )
            rows.append(
                _measurement(
                    measurement_id="continuous_persistence",
                    dimension=dimension,
                    units="proportion",
                    value=None,
                    numerator=None,
                    denominator=baseline_value,
                    availability=MetricAvailability.UNKNOWN,
                    reason_code="missing_endpoint",
                    coverage_observed=observed,
                    coverage_expected=expected,
                    baseline_tick=baseline_tick,
                    end_tick=baseline_tick,
                    right_censored=True,
                )
            )
            continue
        endpoint = boundary_by_tick.get(resolved_end)
        if endpoint is None:
            for measurement_id in (
                "endpoint_persistence",
                "continuous_persistence",
            ):
                rows.append(
                    _measurement(
                        measurement_id=measurement_id,
                        dimension=dimension,
                        units="proportion",
                        value=None,
                        numerator=None,
                        denominator=baseline_value,
                        availability=MetricAvailability.UNKNOWN,
                        reason_code="missing_endpoint",
                        coverage_observed=observed,
                        coverage_expected=expected,
                        baseline_tick=baseline_tick,
                        end_tick=resolved_end,
                        right_censored=True,
                    )
                )
            continue
        _, endpoint_observed, endpoint_expected, endpoint_complete = (
            _dimension_population(endpoint, dimension)
        )
        if availability is MetricAvailability.PRESENT and not baseline_traits:
            for measurement_id in (
                "endpoint_persistence",
                "continuous_persistence",
            ):
                rows.append(
                    _measurement(
                        measurement_id=measurement_id,
                        dimension=dimension,
                        units="proportion",
                        value=None,
                        numerator=0.0,
                        denominator=0.0,
                        availability=MetricAvailability.PRESENT,
                        reason_code="empty_baseline",
                        coverage_observed=observed,
                        coverage_expected=expected,
                        baseline_tick=baseline_tick,
                        end_tick=resolved_end,
                    )
                )
            continue
        if availability is not MetricAvailability.PRESENT:
            for measurement_id in (
                "endpoint_persistence",
                "continuous_persistence",
            ):
                rows.append(
                    _measurement(
                        measurement_id=measurement_id,
                        dimension=dimension,
                        units="proportion",
                        value=None,
                        numerator=None,
                        denominator=baseline_value,
                        availability=availability,
                        reason_code=reason,
                        coverage_observed=observed,
                        coverage_expected=expected,
                        baseline_tick=baseline_tick,
                        end_tick=resolved_end,
                    )
                )
            continue
        endpoint_carriers = _baseline_cohort(endpoint, dimension)
        retained_endpoint = baseline_traits & endpoint_carriers
        endpoint_value = len(retained_endpoint) / len(baseline_traits)
        endpoint_evidence = _trait_evidence(inputs, endpoint, dimension, None)
        rows.append(
            _measurement(
                measurement_id="endpoint_persistence",
                dimension=dimension,
                units="proportion",
                value=endpoint_value,
                numerator=float(len(retained_endpoint)),
                denominator=float(len(baseline_traits)),
                availability=(
                    MetricAvailability.PRESENT
                    if endpoint_complete and endpoint_expected > 0
                    else MetricAvailability.PARTIAL
                ),
                reason_code=(
                    None
                    if endpoint_complete and endpoint_expected > 0
                    else "partial_endpoint"
                ),
                coverage_observed=endpoint_observed,
                coverage_expected=endpoint_expected,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                evidence_ids=endpoint_evidence,
            )
        )
        intermediate = [
            boundary
            for boundary in inputs.boundaries
            if baseline_tick <= boundary.boundary_tick <= resolved_end
        ]
        continuous_complete = True
        for boundary in intermediate:
            _, _, _, complete = _dimension_population(boundary, dimension)
            if not complete:
                continuous_complete = False
                break
            if boundary.boundary_tick < resolved_end:
                if not (baseline_traits & _baseline_cohort(boundary, dimension)):
                    pass
        censored = (
            not continuous_complete
            or bool(inputs.gaps)
            or (resolved_end - baseline_tick) + 1 != len(intermediate)
        )
        continuous_retained: set[str] = set()
        if not censored:
            continuous_retained = {
                trait
                for trait in baseline_traits
                if all(
                    trait in _baseline_cohort(boundary, dimension)
                    for boundary in intermediate
                )
            }
        rows.append(
            _measurement(
                measurement_id="continuous_persistence",
                dimension=dimension,
                units="proportion",
                value=(
                    None
                    if censored
                    else len(continuous_retained) / len(baseline_traits)
                ),
                numerator=(None if censored else float(len(continuous_retained))),
                denominator=float(len(baseline_traits)),
                availability=(
                    MetricAvailability.UNKNOWN
                    if censored
                    else MetricAvailability.PRESENT
                ),
                reason_code=("censored_intermediate" if censored else None),
                coverage_observed=observed,
                coverage_expected=expected,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                left_censored=bool(inputs.gaps),
                right_censored=not continuous_complete,
            )
        )
    return rows


def _extinction_rows(
    inputs: CulturalEvolutionInputs,
    boundary_by_tick: dict[int, InventoryBoundary],
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    ticks = sorted(boundary_by_tick)
    for dimension in _ALL_DIMENSIONS:
        carriers_by_tick = {
            tick: _carriers(boundary_by_tick[tick], dimension) for tick in ticks
        }
        for index, tick in enumerate(ticks[:-1]):
            next_tick = ticks[index + 1]
            if next_tick != tick + 1:
                continue
            boundary = boundary_by_tick[tick]
            next_boundary = boundary_by_tick[next_tick]
            _, _, expected, complete = _dimension_population(boundary, dimension)
            _, next_observed, next_expected, next_complete = _dimension_population(
                next_boundary, dimension
            )
            if not complete or not next_complete:
                continue
            if expected == 0 or next_expected == 0:
                continue
            previous = carriers_by_tick[tick]
            following = carriers_by_tick[next_tick]
            for trait_id in sorted(set(previous)):
                if previous.get(trait_id) and not following.get(trait_id):
                    evidence = _trait_evidence(
                        inputs, next_boundary, dimension, trait_id
                    )
                    rows.append(
                        _measurement(
                            measurement_id="extinction_transition",
                            dimension=dimension,
                            units="count",
                            value=1.0,
                            numerator=1.0,
                            denominator=1.0,
                            availability=MetricAvailability.PRESENT,
                            reason_code=None,
                            coverage_observed=next_observed,
                            coverage_expected=next_expected,
                            baseline_tick=tick,
                            end_tick=next_tick,
                            trait_id=trait_id,
                            evidence_ids=evidence,
                        )
                    )
    return rows


def _sort_key(measurement: CulturalMeasurement) -> tuple[object, ...]:
    return (
        measurement.measurement_id,
        measurement.dimension,
        measurement.trait_id or "",
        measurement.baseline_tick,
        measurement.end_tick,
    )


def compute_cultural_trait_dynamics(
    inputs: CulturalEvolutionInputs,
) -> tuple[CulturalMeasurement, ...]:
    """Compute separate frequency, persistence, extinction and diversity rows."""
    if type(inputs) is not CulturalEvolutionInputs:
        raise TypeError("inputs must be CulturalEvolutionInputs")
    boundaries = tuple(inputs.boundaries)
    if not boundaries:
        _LOG.debug("cultural_trait_dynamics_skipped reason_code=%s", "no_boundaries")
        return ()
    boundary_by_tick = {boundary.boundary_tick: boundary for boundary in boundaries}
    resolved_end = (
        inputs.window.end_boundary
        if inputs.window.end_boundary is not None
        else max(boundary_by_tick)
    )
    trait_union: dict[str, set[str]] = {
        dimension: set() for dimension in _ALL_DIMENSIONS
    }
    for boundary in boundaries:
        for dimension in _ALL_DIMENSIONS:
            trait_union[dimension].update(_carriers(boundary, dimension))
    rows: list[CulturalMeasurement] = []
    rows.extend(_frequency_rows(inputs, boundaries, trait_union))
    rows.extend(_diversity_rows(boundaries))
    rows.extend(_persistence_rows(inputs, boundary_by_tick, resolved_end))
    rows.extend(_extinction_rows(inputs, boundary_by_tick))
    rows.sort(key=_sort_key)
    _LOG.debug(
        "cultural_trait_dynamics_computed boundary_count=%s row_count=%s "
        "dimension_count=%s",
        len(boundaries),
        len(rows),
        len(_ALL_DIMENSIONS),
    )
    return tuple(rows)
