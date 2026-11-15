"""Eight detached social-mobility metric families (catalog 228 -> 236)."""

from __future__ import annotations

import logging
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
from analysis.social_mobility_analysis import SocialMobilityAnalysis
from analysis.social_mobility_contract import (
    SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION,
    SOCIAL_MOBILITY_FORBIDDEN_KEYS,
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityError,
)
from analysis.social_mobility_rows import SocialMobilityDomainRow
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_educational_access_mobility",
    "compute_organization_role_mobility",
    "compute_productive_asset_mobility",
    "compute_resource_mobility",
    "compute_skill_mobility",
    "compute_social_influence_mobility",
    "compute_social_mobility_coverage",
    "compute_social_mobility_generation_lag",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)
_POLICY_TOKEN: Final[str] = "social-mobility"

_DOMAIN_FAMILIES: Final[dict[SocialMobilityDomain, MetricFamilyId]] = {
    SocialMobilityDomain.RESOURCES: MetricFamilyId.RESOURCE_MOBILITY,
    SocialMobilityDomain.SKILLS: MetricFamilyId.SKILL_MOBILITY,
    SocialMobilityDomain.SOCIAL_INFLUENCE: (MetricFamilyId.SOCIAL_INFLUENCE_MOBILITY),
    SocialMobilityDomain.ORGANIZATION_ROLES: (
        MetricFamilyId.ORGANIZATION_ROLE_MOBILITY
    ),
    SocialMobilityDomain.EDUCATIONAL_ACCESS: (
        MetricFamilyId.EDUCATIONAL_ACCESS_MOBILITY
    ),
    SocialMobilityDomain.PRODUCTIVE_ASSETS: (MetricFamilyId.PRODUCTIVE_ASSET_MOBILITY),
}


def _require(analysis: object) -> SocialMobilityAnalysis:
    if type(analysis) is not SocialMobilityAnalysis:
        raise SocialMobilityError("social_mobility_invalid_input")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _reject_forbidden(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in SOCIAL_MOBILITY_FORBIDDEN_KEYS:
            raise SocialMobilityError("social_mobility_forbidden_key")


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
    notes_code: str,
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
            observed=observed,
            expected=expected,
            ratio=_ratio(observed, expected),
        )
        _reject_forbidden(values)
        payload = dict(values)
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
            source_kind="social_mobility_analysis",
            source_ids=(
                run_id,
                input_revision,
                SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION,
                _POLICY_TOKEN,
                notes_code,
            ),
        ),
    )


def _domain_state(
    analysis: SocialMobilityAnalysis, domain: SocialMobilityDomain
) -> tuple[SocialMobilityDomainRow | None, str]:
    rows = sorted(
        (row for row in analysis.domain_rows if row.domain is domain),
        key=lambda row: row.window_index,
    )
    latest = rows[-1] if rows else None
    if (
        latest is None
        or latest.availability is not SocialMobilityAvailability.AVAILABLE
    ):
        return latest, "unknown"
    if latest.coverage is SocialMobilityCoverage.PARTIAL:
        return latest, "partial"
    return latest, "present"


def _compute_domain(
    analysis: SocialMobilityAnalysis,
    domain: SocialMobilityDomain,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    family = _DOMAIN_FAMILIES[domain]
    latest, state = _domain_state(analysis, domain)
    if state == "unknown":
        return _document(
            family,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code=(
                "social_mobility_insufficient_samples"
                if latest is not None
                else "social_mobility_unavailable"
            ),
        )
    assert latest is not None
    values = {
        "social_mobility_window_tick": latest.window_tick,
        "window_count": analysis.window_count,
        "pair_count": latest.pair_count,
        "resolved_pair_count": latest.resolved_pair_count,
        "rank_correlation_milli": latest.rank_correlation_milli,
        "same_bin_share_milli": latest.same_bin_share_milli,
        "upward_share_milli": latest.upward_share_milli,
        "downward_share_milli": latest.downward_share_milli,
        "mean_absolute_rank_change_milli": (latest.mean_absolute_rank_change_milli),
        "persistence_direction": latest.persistence_direction.value,
        "coverage": latest.coverage.value,
        "availability": latest.availability.value,
    }
    return _document(
        family,
        state=state,
        observed=latest.resolved_pair_count,
        expected=latest.pair_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="social_mobility_domain_ok",
    )


def compute_resource_mobility(
    analysis: SocialMobilityAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _compute_domain(
        _require(analysis),
        SocialMobilityDomain.RESOURCES,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_skill_mobility(
    analysis: SocialMobilityAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _compute_domain(
        _require(analysis),
        SocialMobilityDomain.SKILLS,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_social_influence_mobility(
    analysis: SocialMobilityAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _compute_domain(
        _require(analysis),
        SocialMobilityDomain.SOCIAL_INFLUENCE,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_organization_role_mobility(
    analysis: SocialMobilityAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _compute_domain(
        _require(analysis),
        SocialMobilityDomain.ORGANIZATION_ROLES,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_educational_access_mobility(
    analysis: SocialMobilityAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _compute_domain(
        _require(analysis),
        SocialMobilityDomain.EDUCATIONAL_ACCESS,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_productive_asset_mobility(
    analysis: SocialMobilityAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _compute_domain(
        _require(analysis),
        SocialMobilityDomain.PRODUCTIVE_ASSETS,
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_social_mobility_generation_lag(
    analysis: SocialMobilityAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    checked = _require(analysis)
    if not checked.lag_rows:
        return _document(
            MetricFamilyId.SOCIAL_MOBILITY_GENERATION_LAG,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="social_mobility_unavailable",
        )
    latest_window = max(row.window_index for row in checked.lag_rows)
    rows = [row for row in checked.lag_rows if row.window_index == latest_window]
    values: dict[str, object] = {
        "social_mobility_window_tick": max(row.window_tick for row in rows),
        "max_generation_lag": 4,
    }
    comparable = 0
    for lag in range(1, 5):
        selected = [row for row in rows if row.generation_lag == lag]
        pairs = sum(row.pair_count for row in selected)
        if selected:
            same = max(row.same_bin_share_milli for row in selected)
            upward = max(row.upward_share_milli for row in selected)
            downward = max(row.downward_share_milli for row in selected)
        else:
            same = upward = downward = 0
        if any(row.comparable for row in selected):
            comparable += 1
        values[f"lag{lag}_pair_count"] = pairs
        values[f"lag{lag}_same_bin_share_milli"] = same
        values[f"lag{lag}_upward_share_milli"] = upward
        values[f"lag{lag}_downward_share_milli"] = downward
    values["coverage"] = checked.generation_coverage.value
    values["availability"] = "available" if comparable else "insufficient_samples"
    state = (
        "partial"
        if comparable == 0
        or checked.generation_coverage is SocialMobilityCoverage.PARTIAL
        else "present"
    )
    return _document(
        MetricFamilyId.SOCIAL_MOBILITY_GENERATION_LAG,
        state=state,
        observed=comparable,
        expected=len(rows),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="social_mobility_generation_ok",
    )


def compute_social_mobility_coverage(
    analysis: SocialMobilityAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    checked = _require(analysis)
    coverage_row = checked.coverage_row
    if coverage_row is None:
        return _document(
            MetricFamilyId.SOCIAL_MOBILITY_COVERAGE,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="social_mobility_unavailable",
        )
    values = {
        "social_mobility_window_tick": coverage_row.window_tick,
        "generation_count": coverage_row.generation_count,
        "owner_count": coverage_row.owner_count,
        "genealogy_edge_count": coverage_row.genealogy_edge_count,
        "pair_count": coverage_row.pair_count,
        "resolved_pair_count": coverage_row.resolved_pair_count,
        "unresolved_pair_count": coverage_row.unresolved_pair_count,
        "domain_available_count": coverage_row.domain_available_count,
        "truncated": coverage_row.truncated,
        "coverage": coverage_row.coverage.value,
        "availability": (
            "available" if coverage_row.resolved_pair_count else "unavailable"
        ),
    }
    state = (
        "partial"
        if coverage_row.coverage is SocialMobilityCoverage.PARTIAL
        else "present"
    )
    return _document(
        MetricFamilyId.SOCIAL_MOBILITY_COVERAGE,
        state=state,
        observed=coverage_row.resolved_pair_count,
        expected=coverage_row.pair_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="social_mobility_coverage_ok",
    )
