"""Frequency, persistence, extinction, and diversity for cultural inventories."""

from __future__ import annotations

import heapq
import logging
import math
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Final

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CULTURAL_FEATURE_DIMENSIONS,
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
    CulturalMeasurement,
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
    "ALL_CULTURAL_DIMENSIONS",
    "CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION",
    "CULTURAL_TRAIT_DYNAMICS_FAMILY",
    "BoundaryTraitState",
    "TraitEvidenceIndex",
    "compute_cultural_trait_dynamics",
    "compute_cultural_trait_dynamics_from_states",
    "iter_cultural_trait_dynamics_from_states",
    "trait_sort_key",
]

ALL_CULTURAL_DIMENSIONS: Final[tuple[str, ...]] = _ALL_DIMENSIONS


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


@dataclass(frozen=True, slots=True)
class TraitEvidenceIndex:
    """Qualified trait/roster evidence pointers for one normalized capture."""

    entry_ids: Mapping[tuple[str, int, str], str]
    roster_ids: Mapping[int, str]

    @classmethod
    def from_inputs(cls, inputs: CulturalEvolutionInputs) -> TraitEvidenceIndex:
        entry_ids = {
            (pointer.owner_id or "", pointer.boundary_tick, pointer.local_id or ""): (
                pointer.pointer_id
            )
            for pointer in inputs.evidence_pointers
            if pointer.source_kind.startswith("trait:")
        }
        roster_ids = {
            pointer.boundary_tick: pointer.pointer_id
            for pointer in inputs.evidence_pointers
            if pointer.source_kind == "roster"
            and pointer.local_id == f"roster:{pointer.boundary_tick}"
        }
        return cls(entry_ids=entry_ids, roster_ids=roster_ids)


@dataclass(frozen=True, slots=True)
class BoundaryTraitState:
    """Sparse per-boundary primitives required by every trait formula.

    Carriers, coverage and qualified evidence are derived once per boundary, so
    repeated analysis and checkpoints do not rescan entries or pointers.
    """

    boundary_tick: int
    living_owner_ids: tuple[str, ...]
    owner_dimension_coverage: tuple[tuple[str, str, str], ...]
    carriers: Mapping[str, Mapping[str, tuple[str, ...]]]
    evidence: Mapping[tuple[str, str], tuple[str, ...]]

    @classmethod
    def from_boundary(
        cls,
        boundary: InventoryBoundary,
        index: TraitEvidenceIndex,
    ) -> BoundaryTraitState:
        if type(boundary) is not InventoryBoundary:
            raise TypeError("boundary must be InventoryBoundary")
        tick = boundary.boundary_tick
        living = boundary.living_owner_ids
        living_set = set(living)
        roster = index.roster_ids.get(tick)
        carriers: dict[str, Mapping[str, tuple[str, ...]]] = {}
        evidence: dict[tuple[str, str], tuple[str, ...]] = {}
        for dimension in _ALL_DIMENSIONS:
            owners_by_trait: dict[str, set[str]] = defaultdict(set)
            pointer_ids: dict[str, set[str]] = defaultdict(set)
            for entry in boundary.entries:
                if entry.dimension != dimension:
                    continue
                pointer = index.entry_ids.get(
                    (entry.owner_id, tick, entry.local_entry_id)
                )
                if pointer is not None:
                    pointer_ids[entry.content_digest].add(pointer)
                if entry.owner_id not in living_set:
                    continue
                if entry.status not in (None, "active"):
                    continue
                owners_by_trait[entry.content_digest].add(entry.owner_id)
            carriers[dimension] = {
                trait: tuple(sorted(owners))
                for trait, owners in owners_by_trait.items()
            }
            roster_ids = () if roster is None else (roster,)
            evidence[(dimension, "")] = roster_ids
            for trait, pointers in pointer_ids.items():
                evidence[(dimension, trait)] = tuple(sorted(pointers | set(roster_ids)))
        return cls(
            boundary_tick=tick,
            living_owner_ids=living,
            owner_dimension_coverage=boundary.owner_dimension_coverage,
            carriers=carriers,
            evidence=evidence,
        )

    @property
    def coverage(self) -> dict[tuple[str, str], str]:
        return {
            (owner, dimension): code
            for owner, dimension, code in self.owner_dimension_coverage
        }

    def carrier_map(self, dimension: str) -> dict[str, set[str]]:
        return {
            trait: set(owners)
            for trait, owners in self.carriers.get(dimension, {}).items()
        }

    def dimension_population(self, dimension: str) -> tuple[int, int, bool]:
        """Return observed, expected, and completeness for one dimension."""
        coverage = self.coverage
        observed = 0
        missing = 0
        expected = 0
        for owner in self.living_owner_ids:
            code = coverage.get((owner, dimension))
            if code == "disabled":
                continue
            expected += 1
            if code == "complete":
                observed += 1
            else:
                missing += 1
        return observed, expected, missing == 0


def _unavailable_reason(state: BoundaryTraitState, expected: int) -> str:
    if not state.living_owner_ids:
        return "population_empty"
    if expected == 0:
        return "channel_disabled"
    return "population_unavailable"


def _trait_evidence(
    state: BoundaryTraitState,
    dimension: str,
    trait_id: str | None,
) -> tuple[str, ...]:
    return state.evidence.get((dimension, trait_id or ""), ())


def _frequency_measurement(
    state: BoundaryTraitState,
    dimension: str,
    trait_id: str,
    carriers: Mapping[str, set[str]],
) -> CulturalMeasurement:
    observed, expected, complete = state.dimension_population(dimension)
    carrier_count = len(carriers.get(trait_id, set()))
    evidence = _trait_evidence(state, dimension, trait_id)
    if expected == 0:
        availability = MetricAvailability.UNKNOWN
        value = None
        reason = _unavailable_reason(state, expected)
    elif complete:
        availability = MetricAvailability.PRESENT
        value = carrier_count / expected
        reason = None
    else:
        availability = MetricAvailability.PARTIAL
        value = None
        reason = "partial_owner_coverage"
    return _measurement(
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
        baseline_tick=state.boundary_tick,
        end_tick=state.boundary_tick,
        trait_id=trait_id,
        evidence_ids=evidence,
    )


def _iter_frequency_rows(
    states: tuple[BoundaryTraitState, ...],
    trait_union: Mapping[str, set[str]],
) -> Iterator[CulturalMeasurement]:
    """Yield frequency rows already in canonical per-dimension/trait order."""
    for dimension in sorted(_ALL_DIMENSIONS):
        carriers_by_state = [(state, state.carrier_map(dimension)) for state in states]
        for trait_id in sorted(trait_union[dimension]):
            for state, carriers in carriers_by_state:
                yield _frequency_measurement(
                    state,
                    dimension,
                    trait_id,
                    carriers,
                )


def _diversity_rows(
    states: tuple[BoundaryTraitState, ...],
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    for state in states:
        for dimension in _ALL_DIMENSIONS:
            observed, expected, complete = state.dimension_population(dimension)
            carriers = state.carrier_map(dimension)
            incidences = sum(len(owners) for owners in carriers.values())
            evidence: tuple[str, ...] = ()
            if expected == 0:
                availability = MetricAvailability.UNKNOWN
                reason = _unavailable_reason(state, expected)
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
                            baseline_tick=state.boundary_tick,
                            end_tick=state.boundary_tick,
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
                        baseline_tick=state.boundary_tick,
                        end_tick=state.boundary_tick,
                        evidence_ids=evidence,
                    )
                )
    return rows


def _persistence_rows(
    states: tuple[BoundaryTraitState, ...],
    state_by_tick: dict[int, BoundaryTraitState],
    window: CulturalAnalysisWindow,
    gaps: tuple[str, ...],
    resolved_end: int | None,
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    baseline_tick = window.baseline_boundary
    baseline = state_by_tick.get(baseline_tick)
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
        observed, expected, baseline_complete = baseline.dimension_population(dimension)
        baseline_traits = set(baseline.carrier_map(dimension))
        if expected == 0:
            reason = _unavailable_reason(baseline, expected)
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
        endpoint = state_by_tick.get(resolved_end)
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
        endpoint_observed, endpoint_expected, endpoint_complete = (
            endpoint.dimension_population(dimension)
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
        endpoint_carriers = set(endpoint.carrier_map(dimension))
        retained_endpoint = baseline_traits & endpoint_carriers
        endpoint_value = len(retained_endpoint) / len(baseline_traits)
        endpoint_evidence = _trait_evidence(endpoint, dimension, None)
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
            state
            for state in states
            if baseline_tick <= state.boundary_tick <= resolved_end
        ]
        continuous_complete = True
        for state in intermediate:
            _, _, complete = state.dimension_population(dimension)
            if not complete:
                continuous_complete = False
                break
        censored = (
            not continuous_complete
            or bool(gaps)
            or (resolved_end - baseline_tick) + 1 != len(intermediate)
        )
        continuous_retained: set[str] = set()
        if not censored:
            continuous_retained = {
                trait
                for trait in baseline_traits
                if all(trait in state.carrier_map(dimension) for state in intermediate)
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
                left_censored=bool(gaps),
                right_censored=not continuous_complete,
            )
        )
    return rows


def _extinction_rows(
    states: tuple[BoundaryTraitState, ...],
    state_by_tick: dict[int, BoundaryTraitState],
) -> list[CulturalMeasurement]:
    rows: list[CulturalMeasurement] = []
    ticks = sorted(state_by_tick)
    carriers_by_tick = {
        tick: {
            dimension: state_by_tick[tick].carrier_map(dimension)
            for dimension in _ALL_DIMENSIONS
        }
        for tick in ticks
    }
    for dimension in _ALL_DIMENSIONS:
        for index, tick in enumerate(ticks[:-1]):
            next_tick = ticks[index + 1]
            if next_tick != tick + 1:
                continue
            state = state_by_tick[tick]
            next_state = state_by_tick[next_tick]
            _, expected, complete = state.dimension_population(dimension)
            next_observed, next_expected, next_complete = (
                next_state.dimension_population(dimension)
            )
            if not complete or not next_complete:
                continue
            if expected == 0 or next_expected == 0:
                continue
            previous = carriers_by_tick[tick][dimension]
            following = carriers_by_tick[next_tick][dimension]
            for trait_id in sorted(set(previous)):
                if previous.get(trait_id) and not following.get(trait_id):
                    evidence = _trait_evidence(next_state, dimension, trait_id)
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


def trait_sort_key(measurement: CulturalMeasurement) -> tuple[object, ...]:
    return (
        measurement.measurement_id,
        measurement.dimension,
        measurement.trait_id or "",
        measurement.baseline_tick,
        measurement.end_tick,
    )


def _resolved_end(
    states: tuple[BoundaryTraitState, ...], window: CulturalAnalysisWindow
) -> int | None:
    if window.end_boundary is not None:
        return window.end_boundary
    return max((state.boundary_tick for state in states), default=None)


def iter_cultural_trait_dynamics_from_states(
    states: tuple[BoundaryTraitState, ...],
    *,
    window: CulturalAnalysisWindow,
    gaps: tuple[str, ...] = (),
) -> Iterator[CulturalMeasurement]:
    """Yield exact rows in canonical order, streaming the large frequency group."""
    if not states:
        _LOG.debug("cultural_trait_dynamics_skipped reason_code=%s", "no_boundaries")
        return
    ordered = tuple(sorted(states, key=lambda state: state.boundary_tick))
    if len({state.boundary_tick for state in ordered}) != len(ordered):
        raise ValueError("duplicate_boundary_tick")
    state_by_tick = {state.boundary_tick: state for state in ordered}
    resolved_end = _resolved_end(ordered, window)
    trait_union: dict[str, set[str]] = {
        dimension: set() for dimension in _ALL_DIMENSIONS
    }
    for state in ordered:
        for dimension in _ALL_DIMENSIONS:
            trait_union[dimension].update(state.carrier_map(dimension))
    persistence = sorted(
        _persistence_rows(
            ordered,
            state_by_tick,
            window,
            tuple(gaps),
            resolved_end,
        ),
        key=trait_sort_key,
    )
    diversity = sorted(_diversity_rows(ordered), key=trait_sort_key)
    extinction = sorted(_extinction_rows(ordered, state_by_tick), key=trait_sort_key)
    yield from heapq.merge(
        persistence,
        diversity,
        extinction,
        _iter_frequency_rows(ordered, trait_union),
        key=trait_sort_key,
    )


def compute_cultural_trait_dynamics_from_states(
    states: tuple[BoundaryTraitState, ...],
    *,
    window: CulturalAnalysisWindow,
    gaps: tuple[str, ...] = (),
) -> tuple[CulturalMeasurement, ...]:
    """Compute exact trait dynamics from sparse boundary primitives.

    This is the second pass of the sealed-window reducer: the trait union is
    complete before any final row is emitted, so traits first appearing at the
    final boundary still produce earlier zero-frequency rows.
    """
    rows = tuple(
        iter_cultural_trait_dynamics_from_states(
            states,
            window=window,
            gaps=gaps,
        )
    )
    _LOG.debug(
        "cultural_trait_dynamics_computed boundary_count=%s row_count=%s "
        "dimension_count=%s",
        len(states),
        len(rows),
        len(_ALL_DIMENSIONS),
    )
    return rows


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
    index = TraitEvidenceIndex.from_inputs(inputs)
    states = tuple(
        BoundaryTraitState.from_boundary(boundary, index) for boundary in boundaries
    )
    return compute_cultural_trait_dynamics_from_states(
        states,
        window=inputs.window,
        gaps=inputs.gaps,
    )
