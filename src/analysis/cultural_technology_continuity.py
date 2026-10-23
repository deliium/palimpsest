"""Living practical-knowledge retention, archive preservation, and global loss."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Final

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    ArchiveKnowledgeState,
    CulturalEvolutionInputs,
    CulturalMeasurement,
    InventoryBoundary,
    TraitPresence,
)
from analysis.models import MetricAvailability

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.cultural_technology_continuity"
)

CULTURAL_TECHNOLOGY_CONTINUITY_FAMILY: Final[str] = "cultural_technology_continuity"
CULTURAL_TECHNOLOGY_CONTINUITY_ALGORITHM_VERSION: Final[str] = (
    "cultural-technology-continuity@1"
)
_DIMENSION: Final[str] = "technology"

__all__ = [
    "CULTURAL_TECHNOLOGY_CONTINUITY_ALGORITHM_VERSION",
    "CULTURAL_TECHNOLOGY_CONTINUITY_FAMILY",
    "compute_cultural_technology_continuity",
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
    population_basis: str = "fixed_baseline_traits",
    lineage_id: str | None = None,
) -> CulturalMeasurement:
    return CulturalMeasurement(
        family=CULTURAL_TECHNOLOGY_CONTINUITY_FAMILY,
        algorithm_version=CULTURAL_TECHNOLOGY_CONTINUITY_ALGORITHM_VERSION,
        policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        measurement_id=measurement_id,
        dimension=_DIMENSION,
        representation="practical_content_key",
        scope="global",
        partition_id=None,
        group_ids=(),
        population_basis=population_basis,
        denominator_code=population_basis,
        baseline_tick=baseline_tick,
        end_tick=end_tick,
        trait_id=None,
        lineage_id=lineage_id,
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


def _entries(boundary: InventoryBoundary) -> tuple[TraitPresence, ...]:
    living = set(boundary.living_owner_ids)
    return tuple(
        entry
        for entry in boundary.entries
        if entry.dimension == _DIMENSION and entry.owner_id in living
    )


def _key(entry: TraitPresence) -> str:
    return entry.lineage_key or entry.local_entry_id


def _baseline_keys(boundary: InventoryBoundary) -> dict[str, set[str]]:
    keys: dict[str, set[str]] = defaultdict(set)
    for entry in _entries(boundary):
        keys[_key(entry)].add(entry.content_digest)
    return dict(keys)


def _key_evidence(
    inputs: CulturalEvolutionInputs,
    boundary: InventoryBoundary,
    keys: set[str] | None = None,
) -> tuple[str, ...]:
    ids: set[str] = set()
    for pointer in inputs.evidence_pointers:
        if pointer.source_kind != "trait:technology":
            continue
        if pointer.boundary_tick != boundary.boundary_tick:
            continue
        if keys is not None:
            entries = {
                entry.local_entry_id: entry
                for entry in _entries(boundary)
                if _key(entry) in keys
            }
            if pointer.local_id not in entries:
                continue
        ids.add(pointer.pointer_id)
    return tuple(sorted(ids))


def _archive_states_at(
    inputs: CulturalEvolutionInputs, boundary_tick: int
) -> dict[str, tuple[ArchiveKnowledgeState, ...]]:
    states: dict[str, list[ArchiveKnowledgeState]] = defaultdict(list)
    for state in inputs.archive_states:
        if state.boundary_tick == boundary_tick:
            states[state.subject_id].append(state)
    return {key: tuple(value) for key, value in states.items()}


def _archive_status(
    states: tuple[ArchiveKnowledgeState, ...] | None,
    variant_digests: set[str],
) -> str:
    if states is None:
        return "unknown"
    for state in states:
        if state.record_present and state.content_digest in variant_digests:
            return "preserved"
    return "absent"


def compute_cultural_technology_continuity(
    inputs: CulturalEvolutionInputs,
) -> tuple[CulturalMeasurement, ...]:
    """Measure living retention separately from archival preservation."""
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
            ("baseline_content_key_count", "count"),
            ("living_retention", "proportion"),
            ("exact_variant_retention", "proportion"),
            ("living_loss_count", "count"),
            ("living_loss_share", "proportion"),
            ("technology_preserved_count", "count"),
            ("technology_absent_count", "count"),
            ("technology_unknown_count", "count"),
            ("global_loss_count", "count"),
            ("global_loss_share", "proportion"),
            ("not_performable_count", "count"),
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
                )
            )
        rows.sort(key=lambda row: row.measurement_id)
        return tuple(rows)
    baseline_keys = _baseline_keys(baseline)
    baseline_variants = {
        (key, digest) for key, digests in baseline_keys.items() for digest in digests
    }
    baseline_count = len(baseline_keys)
    baseline_evidence = _key_evidence(inputs, baseline)
    if baseline_count == 0:
        for measurement_id, units in (
            ("living_retention", "proportion"),
            ("exact_variant_retention", "proportion"),
            ("living_loss_share", "proportion"),
            ("global_loss_share", "proportion"),
        ):
            rows.append(
                _measurement(
                    measurement_id=measurement_id,
                    units=units,
                    value=None,
                    numerator=0.0,
                    denominator=0.0,
                    availability=MetricAvailability.PRESENT,
                    reason_code="empty_baseline",
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=len(baseline.living_owner_ids),
                    coverage_expected=len(baseline.living_owner_ids),
                    evidence_ids=baseline_evidence,
                )
            )
        for measurement_id, units in (
            ("baseline_content_key_count", "count"),
            ("living_loss_count", "count"),
            ("technology_preserved_count", "count"),
            ("technology_absent_count", "count"),
            ("technology_unknown_count", "count"),
            ("global_loss_count", "count"),
            ("not_performable_count", "count"),
        ):
            rows.append(
                _measurement(
                    measurement_id=measurement_id,
                    units=units,
                    value=0.0,
                    numerator=0.0,
                    denominator=0.0,
                    availability=MetricAvailability.PRESENT,
                    reason_code="empty_baseline",
                    baseline_tick=baseline_tick,
                    end_tick=end_tick,
                    coverage_observed=len(baseline.living_owner_ids),
                    coverage_expected=len(baseline.living_owner_ids),
                    evidence_ids=baseline_evidence,
                )
            )
        rows.sort(key=lambda row: row.measurement_id)
        return tuple(rows)
    endpoint = boundary_by_tick.get(resolved_end) if resolved_end is not None else None
    if endpoint is None:
        for measurement_id, units in (
            ("living_retention", "proportion"),
            ("exact_variant_retention", "proportion"),
            ("living_loss_count", "count"),
            ("living_loss_share", "proportion"),
            ("technology_preserved_count", "count"),
            ("technology_absent_count", "count"),
            ("technology_unknown_count", "count"),
            ("global_loss_count", "count"),
            ("global_loss_share", "proportion"),
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
                    evidence_ids=baseline_evidence,
                )
            )
        rows.append(
            _measurement(
                measurement_id="baseline_content_key_count",
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
                evidence_ids=baseline_evidence,
            )
        )
        rows.sort(key=lambda row: row.measurement_id)
        return tuple(rows)
    assert resolved_end is not None
    endpoint_keys = _baseline_keys(endpoint)
    endpoint_variants = {
        (key, digest) for key, digests in endpoint_keys.items() for digest in digests
    }
    retained_keys = set(baseline_keys) & set(endpoint_keys)
    retained_variants = baseline_variants & endpoint_variants
    endpoint_evidence = _key_evidence(inputs, endpoint, retained_keys)
    living_retention = len(retained_keys) / baseline_count
    variant_retention = (
        len(retained_variants) / len(baseline_variants) if baseline_variants else None
    )
    archive = _archive_states_at(inputs, resolved_end)
    preserved = 0
    absent = 0
    unknown = 0
    global_loss = 0
    for key, digests in baseline_keys.items():
        if key in endpoint_keys:
            preserved += 1
            continue
        status = _archive_status(archive.get(key), digests)
        if status == "preserved":
            preserved += 1
        elif status == "absent":
            absent += 1
            global_loss += 1
        else:
            unknown += 1
    global_loss_known = unknown == 0
    living_loss = baseline_count - len(retained_keys)
    rows.extend(
        (
            _measurement(
                measurement_id="baseline_content_key_count",
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
                evidence_ids=baseline_evidence,
            ),
            _measurement(
                measurement_id="living_retention",
                units="proportion",
                value=living_retention,
                numerator=float(len(retained_keys)),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=len(retained_keys),
                coverage_expected=baseline_count,
                evidence_ids=endpoint_evidence,
            ),
            _measurement(
                measurement_id="exact_variant_retention",
                units="proportion",
                value=variant_retention,
                numerator=float(len(retained_variants)),
                denominator=float(len(baseline_variants)),
                availability=(
                    MetricAvailability.PRESENT
                    if variant_retention is not None
                    else MetricAvailability.UNKNOWN
                ),
                reason_code=(
                    None if variant_retention is not None else "empty_baseline"
                ),
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=len(retained_variants),
                coverage_expected=len(baseline_variants),
                evidence_ids=endpoint_evidence,
            ),
            _measurement(
                measurement_id="living_loss_count",
                units="count",
                value=float(living_loss),
                numerator=float(living_loss),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=baseline_count,
                coverage_expected=baseline_count,
                evidence_ids=baseline_evidence,
            ),
            _measurement(
                measurement_id="living_loss_share",
                units="proportion",
                value=living_loss / baseline_count,
                numerator=float(living_loss),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=baseline_count,
                coverage_expected=baseline_count,
                evidence_ids=baseline_evidence,
            ),
            _measurement(
                measurement_id="technology_preserved_count",
                units="count",
                value=float(preserved),
                numerator=float(preserved),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=preserved,
                coverage_expected=baseline_count,
                evidence_ids=baseline_evidence,
            ),
            _measurement(
                measurement_id="technology_absent_count",
                units="count",
                value=float(absent),
                numerator=float(absent),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=absent,
                coverage_expected=baseline_count,
                evidence_ids=baseline_evidence,
            ),
            _measurement(
                measurement_id="technology_unknown_count",
                units="count",
                value=float(unknown),
                numerator=float(unknown),
                denominator=float(baseline_count),
                availability=MetricAvailability.PRESENT,
                reason_code=None,
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=unknown,
                coverage_expected=baseline_count,
                evidence_ids=baseline_evidence,
            ),
            _measurement(
                measurement_id="global_loss_count",
                units="count",
                value=float(global_loss) if global_loss_known else None,
                numerator=float(global_loss),
                denominator=float(baseline_count),
                availability=(
                    MetricAvailability.PRESENT
                    if global_loss_known
                    else MetricAvailability.UNKNOWN
                ),
                reason_code=None if global_loss_known else "unknown_archive_coverage",
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=baseline_count - unknown,
                coverage_expected=baseline_count,
                evidence_ids=baseline_evidence,
            ),
            _measurement(
                measurement_id="global_loss_share",
                units="proportion",
                value=(global_loss / baseline_count if global_loss_known else None),
                numerator=float(global_loss) if global_loss_known else None,
                denominator=float(baseline_count),
                availability=(
                    MetricAvailability.PRESENT
                    if global_loss_known
                    else MetricAvailability.UNKNOWN
                ),
                reason_code=None if global_loss_known else "unknown_archive_coverage",
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=baseline_count - unknown,
                coverage_expected=baseline_count,
                evidence_ids=baseline_evidence,
            ),
            _measurement(
                measurement_id="not_performable_count",
                units="count",
                value=None,
                numerator=None,
                denominator=float(baseline_count),
                availability=MetricAvailability.UNKNOWN,
                reason_code="no_performability_evidence",
                baseline_tick=baseline_tick,
                end_tick=resolved_end,
                coverage_observed=0,
                coverage_expected=baseline_count,
                evidence_ids=baseline_evidence,
            ),
        )
    )
    rows.sort(key=lambda row: row.measurement_id)
    _LOG.debug(
        "cultural_technology_continuity_computed baseline_keys=%s "
        "retained_keys=%s archive_unknown=%s",
        baseline_count,
        len(retained_keys),
        unknown,
    )
    return tuple(rows)
