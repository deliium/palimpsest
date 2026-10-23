"""Baseline-cohort narrative survival with explicit owner-local ancestry."""

from __future__ import annotations

import logging
from typing import Final

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    InventoryBoundary,
    TraitPresence,
)
from analysis.models import MetricAvailability

_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_narrative_survival")

CULTURAL_NARRATIVE_SURVIVAL_FAMILY: Final[str] = "cultural_narrative_survival@1"
CULTURAL_NARRATIVE_SURVIVAL_ALGORITHM_VERSION: Final[str] = (
    "cultural-narrative-survival@1"
)
_DIMENSION: Final[str] = "narrative"

__all__ = [
    "CULTURAL_NARRATIVE_SURVIVAL_ALGORITHM_VERSION",
    "CULTURAL_NARRATIVE_SURVIVAL_FAMILY",
    "compute_cultural_narrative_survival",
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
    baseline_tick: int,
    end_tick: int,
    coverage_observed: int,
    coverage_expected: int | None,
    evidence_ids: tuple[str, ...] = (),
    left_censored: bool = False,
    right_censored: bool = False,
    population_basis: str = "fixed_baseline_traits",
) -> CulturalMeasurement:
    return CulturalMeasurement(
        family=CULTURAL_NARRATIVE_SURVIVAL_FAMILY,
        algorithm_version=CULTURAL_NARRATIVE_SURVIVAL_ALGORITHM_VERSION,
        policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        measurement_id=measurement_id,
        dimension=_DIMENSION,
        representation="narrative_lineage",
        scope="global",
        partition_id=None,
        group_ids=(),
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
        left_censored=left_censored,
        right_censored=right_censored,
        evidence_ids=evidence_ids,
    )


def _narrative_entries(
    boundary: InventoryBoundary,
) -> tuple[TraitPresence, ...]:
    living = set(boundary.living_owner_ids)
    return tuple(
        entry
        for entry in boundary.entries
        if entry.dimension == _DIMENSION and entry.owner_id in living
    )


def _variant_key(entry: TraitPresence) -> tuple[str, str]:
    return (entry.owner_id, entry.local_entry_id)


def _build_graph(
    boundaries: tuple[InventoryBoundary, ...],
) -> dict[tuple[str, str], tuple[tuple[str, str], ...]]:
    graph: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {}
    for boundary in boundaries:
        for entry in _narrative_entries(boundary):
            child = _variant_key(entry)
            parents = tuple(
                (entry.owner_id, parent_id) for parent_id in entry.parent_refs
            )
            previous = graph.get(child)
            if previous is not None and set(previous) != set(parents):
                raise ValueError("narrative_conflicting_parents")
            graph[child] = tuple(sorted(set(parents)))
    _assert_acyclic(graph)
    return graph


def _assert_acyclic(
    graph: dict[tuple[str, str], tuple[tuple[str, str], ...]],
) -> None:
    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def walk(node: tuple[str, str]) -> None:
        if node in visited:
            return
        if node in visiting:
            raise ValueError("narrative_ancestry_cycle")
        visiting.add(node)
        for parent in graph.get(node, ()):
            walk(parent)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        walk(node)


def _ancestors(
    key: tuple[str, str],
    graph: dict[tuple[str, str], tuple[tuple[str, str], ...]],
    memo: dict[tuple[str, str], frozenset[tuple[str, str]]],
) -> frozenset[tuple[str, str]]:
    cached = memo.get(key)
    if cached is not None:
        return cached
    found: set[tuple[str, str]] = set()
    stack = list(graph.get(key, ()))
    while stack:
        parent = stack.pop()
        if parent in found:
            continue
        found.add(parent)
        stack.extend(graph.get(parent, ()))
    frozen = frozenset(found)
    memo[key] = frozen
    return frozen


def _surviving_baseline(
    baseline_keys: set[tuple[str, str]],
    endpoint_keys: set[tuple[str, str]],
    graph: dict[tuple[str, str], tuple[tuple[str, str], ...]],
) -> set[tuple[str, str]]:
    memo: dict[tuple[str, str], frozenset[tuple[str, str]]] = {}
    surviving: set[tuple[str, str]] = set()
    for key in endpoint_keys:
        if key in baseline_keys:
            surviving.add(key)
        surviving.update(_ancestors(key, graph, memo) & baseline_keys)
    return surviving


def _persistence(
    baseline_keys: set[tuple[str, str]],
    boundary: InventoryBoundary,
    graph: dict[tuple[str, str], tuple[tuple[str, str], ...]],
) -> set[tuple[str, str]]:
    return _surviving_baseline(
        baseline_keys,
        {_variant_key(entry) for entry in _narrative_entries(boundary)},
        graph,
    )


def _entry_evidence(
    inputs: CulturalEvolutionInputs,
    entries: tuple[TraitPresence, ...],
) -> tuple[str, ...]:
    pointer_ids = {
        pointer.pointer_id
        for pointer in inputs.evidence_pointers
        if pointer.source_kind == "trait:narrative"
    }
    relevant: set[str] = set()
    for pointer in inputs.evidence_pointers:
        if pointer.source_kind == "trait:narrative":
            relevant.add(pointer.pointer_id)
    for entry in entries:
        for pointer in inputs.evidence_pointers:
            if (
                pointer.source_kind == "trait:narrative"
                and pointer.owner_id == entry.owner_id
                and pointer.local_id == entry.local_entry_id
            ):
                relevant.add(pointer.pointer_id)
    if relevant:
        return tuple(sorted(relevant))
    return tuple(sorted(pointer_ids))


def compute_cultural_narrative_survival(
    inputs: CulturalEvolutionInputs,
) -> tuple[CulturalMeasurement, ...]:
    """Measure baseline narrative continuity by explicit owner-local ancestry."""
    if type(inputs) is not CulturalEvolutionInputs:
        raise TypeError("inputs must be CulturalEvolutionInputs")
    boundary_by_tick = {
        boundary.boundary_tick: boundary for boundary in inputs.boundaries
    }
    baseline_tick = inputs.window.baseline_boundary
    resolved_end = (
        inputs.window.end_boundary
        if inputs.window.end_boundary is not None
        else (max(boundary_by_tick) if boundary_by_tick else None)
    )
    end_tick = resolved_end if resolved_end is not None else baseline_tick
    baseline = boundary_by_tick.get(baseline_tick)
    rows: list[CulturalMeasurement] = []
    if baseline is None:
        for measurement_id, units in (
            ("baseline_variant_count", "count"),
            ("surviving_baseline_count", "count"),
            ("unresolved_baseline_count", "count"),
            ("endpoint_persistence", "proportion"),
            ("continuous_persistence", "proportion"),
            ("witnessed_generation_span", "generations"),
            ("observed_duration", "ticks"),
        ):
            rows.append(
                _measurement(
                    measurement_id=measurement_id,
                    units=units,
                    value=None,
                    numerator=None,
                    denominator=None,
                    availability=MetricAvailability.UNKNOWN,
                    reason_code="missing_baseline",
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=0,
                    coverage_expected=None,
                    left_censored=True,
                )
            )
        rows.sort(key=lambda row: row.measurement_id)
        return tuple(rows)
    graph = _build_graph(tuple(inputs.boundaries))
    baseline_entries = _narrative_entries(baseline)
    baseline_keys = {_variant_key(entry) for entry in baseline_entries}
    evidence = _entry_evidence(inputs, baseline_entries)
    baseline_count = len(baseline_keys)
    if baseline_count == 0:
        rows.extend(
            (
                _measurement(
                    measurement_id="baseline_variant_count",
                    units="count",
                    value=0.0,
                    numerator=0.0,
                    denominator=0.0,
                    availability=MetricAvailability.PRESENT,
                    reason_code=None,
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=len(baseline.living_owner_ids),
                    coverage_expected=len(baseline.living_owner_ids),
                    evidence_ids=evidence,
                ),
                _measurement(
                    measurement_id="surviving_baseline_count",
                    units="count",
                    value=0.0,
                    numerator=0.0,
                    denominator=0.0,
                    availability=MetricAvailability.PRESENT,
                    reason_code="empty_baseline",
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=len(baseline.living_owner_ids),
                    coverage_expected=len(baseline.living_owner_ids),
                    evidence_ids=evidence,
                ),
                _measurement(
                    measurement_id="unresolved_baseline_count",
                    units="count",
                    value=0.0,
                    numerator=0.0,
                    denominator=0.0,
                    availability=MetricAvailability.PRESENT,
                    reason_code=None,
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=len(baseline.living_owner_ids),
                    coverage_expected=len(baseline.living_owner_ids),
                    evidence_ids=evidence,
                ),
                _measurement(
                    measurement_id="endpoint_persistence",
                    units="proportion",
                    value=None,
                    numerator=0.0,
                    denominator=0.0,
                    availability=MetricAvailability.PRESENT,
                    reason_code="empty_baseline",
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=len(baseline.living_owner_ids),
                    coverage_expected=len(baseline.living_owner_ids),
                    evidence_ids=evidence,
                ),
                _measurement(
                    measurement_id="continuous_persistence",
                    units="proportion",
                    value=None,
                    numerator=0.0,
                    denominator=0.0,
                    availability=MetricAvailability.PRESENT,
                    reason_code="empty_baseline",
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=len(baseline.living_owner_ids),
                    coverage_expected=len(baseline.living_owner_ids),
                    evidence_ids=evidence,
                ),
                _measurement(
                    measurement_id="witnessed_generation_span",
                    units="generations",
                    value=0.0,
                    numerator=0.0,
                    denominator=None,
                    availability=MetricAvailability.PRESENT,
                    reason_code="empty_baseline",
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=0,
                    coverage_expected=0,
                    evidence_ids=evidence,
                ),
                _measurement(
                    measurement_id="observed_duration",
                    units="ticks",
                    value=float(max(0, end_tick - baseline_tick)),
                    numerator=None,
                    denominator=None,
                    availability=MetricAvailability.PRESENT,
                    reason_code=None,
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=1,
                    coverage_expected=1,
                    evidence_ids=evidence,
                ),
            )
        )
        rows.sort(key=lambda row: row.measurement_id)
        return tuple(rows)
    endpoint = boundary_by_tick.get(resolved_end) if resolved_end is not None else None
    if endpoint is None:
        for measurement_id, units in (
            ("surviving_baseline_count", "count"),
            ("unresolved_baseline_count", "count"),
            ("endpoint_persistence", "proportion"),
            ("continuous_persistence", "proportion"),
        ):
            rows.append(
                _measurement(
                    measurement_id=measurement_id,
                    units=units,
                    value=None,
                    numerator=None,
                    denominator=float(baseline_count),
                    availability=MetricAvailability.UNKNOWN,
                    reason_code="missing_endpoint",
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=len(baseline.living_owner_ids),
                    coverage_expected=len(baseline.living_owner_ids),
                    evidence_ids=evidence,
                    right_censored=True,
                )
            )
        rows.append(
            _measurement(
                measurement_id="baseline_variant_count",
                units="count",
                value=float(baseline_count),
                numerator=float(baseline_count),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=end_tick,
                coverage_observed=len(baseline.living_owner_ids),
                coverage_expected=len(baseline.living_owner_ids),
                evidence_ids=evidence,
            )
        )
        rows.append(
            _measurement(
                measurement_id="observed_duration",
                units="ticks",
                value=float(max(0, end_tick - baseline_tick)),
                numerator=None,
                denominator=None,
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=end_tick,
                coverage_observed=1,
                coverage_expected=1,
                evidence_ids=evidence,
            )
        )
        rows.sort(key=lambda row: row.measurement_id)
        return tuple(rows)
    assert resolved_end is not None
    surviving = _persistence(baseline_keys, endpoint, graph)
    surviving_count = len(surviving)
    intermediate = [
        boundary
        for boundary in inputs.boundaries
        if baseline_tick <= boundary.boundary_tick <= resolved_end
    ]
    censored = bool(inputs.gaps) or (resolved_end - baseline_tick) + 1 != len(
        intermediate
    )
    continuous_surviving = set(baseline_keys)
    for boundary in intermediate:
        continuous_surviving &= _persistence(baseline_keys, boundary, graph)
        if not continuous_surviving:
            break
    unresolved_count = 0
    generation_values = {
        boundary.generation_by_owner.get(entry.owner_id)
        for entry in _narrative_entries(endpoint)
        for key in surviving
        if key[0] == entry.owner_id
    }
    generations = sorted(value for value in generation_values if value is not None)
    generation_span = float(generations[-1] - generations[0]) if generations else 0.0
    rows.extend(
        (
            _measurement(
                measurement_id="baseline_variant_count",
                units="count",
                value=float(baseline_count),
                numerator=float(baseline_count),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=len(baseline.living_owner_ids),
                coverage_expected=len(baseline.living_owner_ids),
                evidence_ids=evidence,
            ),
            _measurement(
                measurement_id="surviving_baseline_count",
                units="count",
                value=float(surviving_count),
                numerator=float(surviving_count),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=len(baseline.living_owner_ids),
                coverage_expected=len(baseline.living_owner_ids),
                evidence_ids=evidence,
            ),
            _measurement(
                measurement_id="unresolved_baseline_count",
                units="count",
                value=float(unresolved_count),
                numerator=float(unresolved_count),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=len(baseline.living_owner_ids),
                coverage_expected=len(baseline.living_owner_ids),
                evidence_ids=evidence,
            ),
            _measurement(
                measurement_id="endpoint_persistence",
                units="proportion",
                value=(None if unresolved_count else surviving_count / baseline_count),
                numerator=float(surviving_count),
                denominator=float(baseline_count),
                availability=(
                    MetricAvailability.PARTIAL
                    if unresolved_count
                    else MetricAvailability.PRESENT
                ),
                reason_code=("unresolved_ancestry" if unresolved_count else None),
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=len(baseline.living_owner_ids),
                coverage_expected=len(baseline.living_owner_ids),
                evidence_ids=evidence,
            ),
            _measurement(
                measurement_id="continuous_persistence",
                units="proportion",
                value=(
                    None
                    if censored or unresolved_count
                    else len(continuous_surviving) / baseline_count
                ),
                numerator=(
                    None
                    if censored or unresolved_count
                    else float(len(continuous_surviving))
                ),
                denominator=float(baseline_count),
                availability=(
                    MetricAvailability.UNKNOWN
                    if censored
                    else MetricAvailability.PARTIAL
                    if unresolved_count
                    else MetricAvailability.PRESENT
                ),
                reason_code=(
                    "censored_intermediate"
                    if censored
                    else "unresolved_ancestry"
                    if unresolved_count
                    else None
                ),
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=len(baseline.living_owner_ids),
                coverage_expected=len(baseline.living_owner_ids),
                evidence_ids=evidence,
                left_censored=bool(inputs.gaps),
                right_censored=censored,
            ),
            _measurement(
                measurement_id="witnessed_generation_span",
                units="generations",
                value=generation_span,
                numerator=None,
                denominator=None,
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=len(generations),
                coverage_expected=None,
                evidence_ids=evidence,
            ),
            _measurement(
                measurement_id="observed_duration",
                units="ticks",
                value=float(max(0, resolved_end - baseline_tick)),
                numerator=None,
                denominator=None,
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=1,
                coverage_expected=1,
                evidence_ids=evidence,
            ),
        )
    )
    rows.sort(key=lambda row: row.measurement_id)
    _LOG.debug(
        "cultural_narrative_survival_computed baseline_count=%s "
        "surviving_count=%s unresolved_count=%s censored=%s",
        baseline_count,
        surviving_count,
        unresolved_count,
        censored,
    )
    return tuple(rows)
