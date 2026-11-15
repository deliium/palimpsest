"""Bounded immutable social-mobility analysis value and canonical digest."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from typing import Final

from analysis.social_mobility_contract import (
    SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION,
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityError,
    SocialMobilityLayer,
)
from analysis.social_mobility_detection import detect_social_mobility_rows
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_generations import (
    compare_social_mobility_generations,
)
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_policy import (
    SocialMobilityAnalysisPolicy,
    default_social_mobility_analysis_policy,
    with_window_end,
)
from analysis.social_mobility_rows import (
    SocialMobilityCoverageRow,
    SocialMobilityDomainRow,
    SocialMobilityGenerationRow,
    SocialMobilityLagRow,
    SocialMobilityLayerBundle,
    SocialMobilityOutcomeRow,
    SocialMobilityPairRow,
)

__all__ = [
    "SocialMobilityAnalysis",
    "empty_social_mobility_analysis",
    "harvest_social_mobility_analysis",
    "social_mobility_analysis_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.analysis")


@dataclass(frozen=True, slots=True)
class SocialMobilityAnalysis:
    """Bounded detached mobility analysis; never a class or mobility score."""

    policy_version: str
    window_tick: int
    window_count: int
    coverage: SocialMobilityCoverage
    evidence_coverage: SocialMobilityCoverage
    domain_coverage: SocialMobilityCoverage
    generation_coverage: SocialMobilityCoverage
    domain_rows: tuple[SocialMobilityDomainRow, ...]
    generation_rows: tuple[SocialMobilityGenerationRow, ...]
    lag_rows: tuple[SocialMobilityLagRow, ...]
    pair_rows: tuple[SocialMobilityPairRow, ...]
    objective_rows: tuple[SocialMobilityOutcomeRow, ...]
    owner_rows: tuple[SocialMobilityOutcomeRow, ...]
    coverage_row: SocialMobilityCoverageRow | None
    notices: tuple[str, ...]
    owner_count: int
    generation_count: int
    genealogy_edge_count: int
    pair_count: int
    resolved_pair_count: int
    unresolved_pair_count: int
    domain_available_count: int

    def __post_init__(self) -> None:
        if self.policy_version != SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION:
            raise SocialMobilityError("social_mobility_analysis_invalid")
        for name in (
            "domain_rows",
            "generation_rows",
            "lag_rows",
            "pair_rows",
            "objective_rows",
            "owner_rows",
            "notices",
        ):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise SocialMobilityError("social_mobility_analysis_invalid")
        for name in (
            "window_tick",
            "window_count",
            "owner_count",
            "generation_count",
            "genealogy_edge_count",
            "pair_count",
            "resolved_pair_count",
            "unresolved_pair_count",
            "domain_available_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise SocialMobilityError("social_mobility_analysis_invalid")
        for name in (
            "coverage",
            "evidence_coverage",
            "domain_coverage",
            "generation_coverage",
        ):
            if type(getattr(self, name)) is not SocialMobilityCoverage:
                raise SocialMobilityError("social_mobility_analysis_invalid")
        if self.coverage is SocialMobilityCoverage.MISSING and self.row_count:
            raise SocialMobilityError("social_mobility_analysis_invalid")

    @property
    def row_count(self) -> int:
        return (
            len(self.domain_rows)
            + len(self.generation_rows)
            + len(self.lag_rows)
            + len(self.pair_rows)
            + (1 if self.coverage_row is not None else 0)
        )

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)


def empty_social_mobility_analysis() -> SocialMobilityAnalysis:
    """Return the explicit missing analysis with no invented rows."""

    return SocialMobilityAnalysis(
        policy_version=SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION,
        window_tick=0,
        window_count=0,
        coverage=SocialMobilityCoverage.MISSING,
        evidence_coverage=SocialMobilityCoverage.MISSING,
        domain_coverage=SocialMobilityCoverage.MISSING,
        generation_coverage=SocialMobilityCoverage.MISSING,
        domain_rows=(),
        generation_rows=(),
        lag_rows=(),
        pair_rows=(),
        objective_rows=(),
        owner_rows=(),
        coverage_row=None,
        notices=(),
        owner_count=0,
        generation_count=0,
        genealogy_edge_count=0,
        pair_count=0,
        resolved_pair_count=0,
        unresolved_pair_count=0,
        domain_available_count=0,
    )


def social_mobility_analysis_digest(analysis: SocialMobilityAnalysis) -> str:
    """Return a stable digest over bounded metadata and row counts only."""

    if type(analysis) is not SocialMobilityAnalysis:
        raise SocialMobilityError("social_mobility_invalid_input")
    parts = [
        analysis.policy_version,
        str(analysis.window_tick),
        str(analysis.window_count),
        analysis.coverage.value,
        analysis.evidence_coverage.value,
        analysis.domain_coverage.value,
        analysis.generation_coverage.value,
        str(len(analysis.domain_rows)),
        str(len(analysis.generation_rows)),
        str(len(analysis.lag_rows)),
        str(len(analysis.pair_rows)),
        str(len(analysis.objective_rows)),
        str(len(analysis.owner_rows)),
        str(analysis.owner_count),
        str(analysis.generation_count),
        str(analysis.genealogy_edge_count),
        str(analysis.pair_count),
        str(analysis.resolved_pair_count),
        str(analysis.unresolved_pair_count),
        str(analysis.domain_available_count),
        *analysis.notices,
    ]
    material = "\x1f".join(f"{len(part)}:{part}" for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _worst(*coverages: SocialMobilityCoverage) -> SocialMobilityCoverage:
    if SocialMobilityCoverage.MISSING in coverages:
        return SocialMobilityCoverage.MISSING
    if SocialMobilityCoverage.PARTIAL in coverages:
        return SocialMobilityCoverage.PARTIAL
    return SocialMobilityCoverage.COMPLETE


def _merge_notices(*groups: tuple[str, ...], limit: int) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for notice in group:
            if notice not in merged:
                merged.append(notice)
    return tuple(merged[:limit])


def _filter_genealogy_to_window(
    genealogy: SocialMobilityGenealogyHarvest,
    *,
    max_windows: int,
    max_depth: int,
) -> SocialMobilityGenealogyHarvest:
    """Drop genealogy evidence established outside the requested window prefix."""

    edges = tuple(edge for edge in genealogy.edges if edge.window_index < max_windows)
    if len(edges) == len(genealogy.edges):
        return genealogy
    parents_of: dict[str, set[str]] = {}
    for edge in edges:
        parents_of.setdefault(edge.child_token, set()).add(edge.parent_token)
    lineages = tuple(
        lineage
        for lineage in genealogy.lineages
        if _lineage_reachable(
            lineage.ancestor_token,
            lineage.descendant_token,
            parents_of=parents_of,
            max_depth=max_depth,
        )
    )
    return replace(genealogy, edges=edges, lineages=lineages)


def _lineage_reachable(
    ancestor_token: str,
    descendant_token: str,
    *,
    parents_of: dict[str, set[str]],
    max_depth: int,
) -> bool:
    pending: list[tuple[str, int]] = [(descendant_token, 0)]
    seen: set[str] = set()
    while pending:
        current, depth = pending.pop()
        if current in seen or depth > max_depth:
            continue
        seen.add(current)
        for parent in parents_of.get(current, ()):
            if parent == ancestor_token:
                return True
            pending.append((parent, depth + 1))
    return False


def harvest_social_mobility_analysis(
    *,
    genealogy: SocialMobilityGenealogyHarvest,
    outcomes: SocialMobilityOutcomeHarvest,
    policy: SocialMobilityAnalysisPolicy | None = None,
    window_end: int | None = None,
) -> SocialMobilityAnalysis:
    """Compose the bounded analysis from genealogy and outcome harvests."""

    active = default_social_mobility_analysis_policy() if policy is None else policy
    if window_end is not None:
        active = with_window_end(window_end, active)
        genealogy = _filter_genealogy_to_window(
            genealogy,
            max_windows=active.max_windows,
            max_depth=active.max_lineage_depth,
        )
    if not genealogy.edges and not genealogy.lineages:
        _LOG.debug("social_mobility_analysis_empty reason=no_genealogy")
        return empty_social_mobility_analysis()
    if not outcomes.rows:
        _LOG.debug("social_mobility_analysis_empty reason=no_outcomes")
        return empty_social_mobility_analysis()

    notices: list[str] = []
    partial = False

    rows = tuple(row for row in outcomes.rows if row.window_index < active.max_windows)
    owners = sorted({row.owner_token for row in rows})
    if len(owners) > active.max_owners:
        owners = owners[: active.max_owners]
        notices.append("social_mobility_owners_truncated")
        partial = True
    allowed = set(owners)
    rows = tuple(row for row in rows if row.owner_token in allowed)
    if not rows:
        return empty_social_mobility_analysis()

    capped_outcomes = replace(outcomes, rows=rows, owner_count=len(owners))
    detection = detect_social_mobility_rows(
        genealogy=genealogy, outcomes=capped_outcomes, policy=active
    )
    generations = compare_social_mobility_generations(
        genealogy=genealogy,
        outcomes=capped_outcomes,
        pair_rows=detection.pair_rows,
        policy=active,
    )

    pair_rows = tuple(
        sorted(
            detection.pair_rows,
            key=lambda row: (
                row.window_index,
                row.domain.value,
                row.ancestor_token,
                row.descendant_token,
            ),
        )
    )
    if len(pair_rows) > active.max_pairs:
        pair_rows = pair_rows[: active.max_pairs]
        notices.append("social_mobility_pairs_truncated")
        partial = True
    domain_rows = detection.domain_rows
    if len(domain_rows) > active.max_domain_rows:
        domain_rows = domain_rows[: active.max_domain_rows]
        notices.append("social_mobility_domains_truncated")
        partial = True
    generation_rows = generations.generation_rows
    if len(generation_rows) > active.max_generation_rows:
        generation_rows = generation_rows[: active.max_generation_rows]
        notices.append("social_mobility_generations_truncated")
        partial = True
    lag_rows = generations.lag_rows
    if len(lag_rows) > active.max_lag_rows:
        lag_rows = lag_rows[: active.max_lag_rows]
        notices.append("social_mobility_lags_truncated")
        partial = True

    windows = (
        {row.window_index for row in domain_rows}
        | {row.window_index for row in generation_rows}
        | {row.window_index for row in lag_rows}
        | {row.window_index for row in pair_rows}
    )
    window_index = max(windows, default=0)
    window_tick = window_index * active.window_ticks + active.window_ticks - 1
    generation_count = len(genealogy.generations)
    resolved = sum(1 for row in pair_rows if row.resolved)
    unresolved = len(pair_rows) - resolved
    domain_available = sum(
        1
        for row in domain_rows
        if row.window_index == window_index
        and row.availability is SocialMobilityAvailability.AVAILABLE
    )
    overall = _worst(
        genealogy.coverage,
        capped_outcomes.coverage,
        detection.coverage,
        generations.coverage,
    )
    if overall is SocialMobilityCoverage.MISSING and (pair_rows or domain_rows):
        overall = SocialMobilityCoverage.PARTIAL
    if partial or notices:
        overall = SocialMobilityCoverage.PARTIAL
    if not pair_rows and not domain_rows:
        overall = SocialMobilityCoverage.MISSING
    truncated = partial or overall is SocialMobilityCoverage.PARTIAL
    coverage_row = SocialMobilityCoverageRow(
        window_index=window_index,
        window_tick=window_tick,
        generation_count=generation_count,
        owner_count=len(owners),
        genealogy_edge_count=len(genealogy.edges),
        pair_count=len(pair_rows),
        resolved_pair_count=resolved,
        unresolved_pair_count=unresolved,
        domain_available_count=domain_available,
        truncated=truncated,
        coverage=overall,
    )

    objective_rows = tuple(
        row for row in rows if row.layer is SocialMobilityLayer.OBJECTIVE_OUTCOME
    )
    owner_rows = tuple(
        row for row in rows if row.layer is SocialMobilityLayer.OWNER_OUTCOME
    )
    SocialMobilityLayerBundle(
        objective_rows=objective_rows,
        owner_rows=owner_rows,
        pair_rows=pair_rows,
        domain_rows=domain_rows,
        generation_rows=generation_rows,
        coverage_row=coverage_row,
    )

    merged_notices = _merge_notices(
        genealogy.notices,
        capped_outcomes.notices,
        detection.notices,
        generations.notices,
        tuple(notices),
        limit=active.max_notices,
    )
    if overall is SocialMobilityCoverage.PARTIAL:
        _LOG.warning("social_mobility_partial_coverage")
    _LOG.info(
        "social_mobility_analysis_complete windows=%d rows=%d",
        len(windows),
        len(domain_rows) + len(generation_rows) + len(lag_rows) + len(pair_rows),
    )
    return SocialMobilityAnalysis(
        policy_version=SOCIAL_MOBILITY_ANALYSIS_POLICY_VERSION,
        window_tick=window_tick,
        window_count=len(windows),
        coverage=overall,
        evidence_coverage=_worst(genealogy.coverage, capped_outcomes.coverage),
        domain_coverage=detection.coverage,
        generation_coverage=generations.coverage,
        domain_rows=domain_rows,
        generation_rows=generation_rows,
        lag_rows=lag_rows,
        pair_rows=pair_rows,
        objective_rows=objective_rows,
        owner_rows=owner_rows,
        coverage_row=coverage_row,
        notices=merged_notices,
        owner_count=len(owners),
        generation_count=generation_count,
        genealogy_edge_count=len(genealogy.edges),
        pair_count=len(pair_rows),
        resolved_pair_count=resolved,
        unresolved_pair_count=unresolved,
        domain_available_count=domain_available,
    )
