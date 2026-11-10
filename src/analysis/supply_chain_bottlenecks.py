"""Descriptive supply bottlenecks with locked thresholds.

Rows carry counts and integer milli ratios only. No severity, rank, priority,
score, recommendation, or suggested action exists.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from analysis.supply_chain_contract import (
    NONE_TOKEN,
    SUPPLY_BOTTLENECK_PREFIX,
    SupplyBottleneckKind,
    SupplyChainError,
    SupplyCoverage,
    SupplyEdgeKind,
    analysis_supply_token,
)
from analysis.supply_chain_events import (
    SupplyEvidenceHarvest,
    SupplyRecipeSpec,
    SupplyStageObservation,
)
from analysis.supply_chain_graph import SupplyDependencyGraph
from analysis.supply_chain_policy import (
    BOTTLENECK_DEMAND_MIN,
    BOTTLENECK_MIN_EVENTS,
    BOTTLENECK_SHARE_MILLI,
    BOTTLENECK_SHORTFALL_MILLI,
    LOW_SKILL_LEVEL,
    SupplyChainAnalysisPolicy,
)

__all__ = ["SupplyBottleneck", "detect_bottlenecks"]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.bottlenecks")


@dataclass(frozen=True, slots=True)
class SupplyBottleneck:
    bottleneck_token: str
    window_index: int
    kind: SupplyBottleneckKind
    stage_token: str
    edge_token: str
    observed_count: int
    demand_count: int
    supply_count: int
    ratio_milli: int
    location_token: str
    organization_token: str
    skill_domain: str
    coverage: SupplyCoverage

    def __post_init__(self) -> None:
        if self.kind not in SupplyBottleneckKind:
            raise SupplyChainError("supply_chain_invalid_policy")
        if self.stage_token == NONE_TOKEN and self.edge_token == NONE_TOKEN:
            raise SupplyChainError("supply_chain_invalid_policy")
        for name in (
            "window_index",
            "observed_count",
            "demand_count",
            "supply_count",
            "ratio_milli",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise SupplyChainError("supply_chain_invalid_policy")


def _milli(numerator: int, denominator: int) -> int:
    return numerator * 1000 // max(denominator, 1)


def _recipe_map(evidence: SupplyEvidenceHarvest) -> dict[str, SupplyRecipeSpec]:
    return {recipe.recipe_id: recipe for recipe in evidence.recipes}


def _producer_by_name(
    recipes: Mapping[str, SupplyRecipeSpec],
) -> dict[str, SupplyRecipeSpec]:
    return {recipe.output_name: recipe for recipe in recipes.values()}


def _rows_by_window_recipe(
    evidence: SupplyEvidenceHarvest,
) -> dict[tuple[int, str], tuple[SupplyStageObservation, ...]]:
    grouped: dict[tuple[int, str], list[SupplyStageObservation]] = {}
    for row in evidence.rows:
        grouped.setdefault((row.window_index, row.recipe_id), []).append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _token(
    kind: SupplyBottleneckKind,
    window: int,
    stage: str,
    edge: str,
    location: str,
    organization: str,
    skill: str,
) -> str:
    return analysis_supply_token(
        SUPPLY_BOTTLENECK_PREFIX,
        (
            f"{kind.value}\x1f{window}\x1f{stage}\x1f{edge}\x1f"
            f"{location}\x1f{organization}\x1f{skill}"
        ),
    )


def _append(
    rows: list[SupplyBottleneck],
    *,
    kind: SupplyBottleneckKind,
    window: int,
    stage: str,
    edge: str = NONE_TOKEN,
    observed: int,
    demand: int,
    supply: int,
    ratio: int,
    location: str = NONE_TOKEN,
    organization: str = NONE_TOKEN,
    skill: str = NONE_TOKEN,
    coverage: SupplyCoverage,
) -> None:
    rows.append(
        SupplyBottleneck(
            bottleneck_token=_token(
                kind, window, stage, edge, location, organization, skill
            ),
            window_index=window,
            kind=kind,
            stage_token=stage,
            edge_token=edge,
            observed_count=observed,
            demand_count=demand,
            supply_count=supply,
            ratio_milli=ratio,
            location_token=location,
            organization_token=organization,
            skill_domain=skill,
            coverage=coverage,
        )
    )


def detect_bottlenecks(
    graph: SupplyDependencyGraph,
    evidence: SupplyEvidenceHarvest,
    *,
    policy: SupplyChainAnalysisPolicy,
    notices: set[str] | None = None,
) -> tuple[SupplyBottleneck, ...]:
    """Return deterministic descriptive bottlenecks; never a ranking."""
    if type(graph) is not SupplyDependencyGraph or type(evidence) is not (
        SupplyEvidenceHarvest
    ):
        raise SupplyChainError("supply_chain_invalid_policy")
    recipes = _recipe_map(evidence)
    producers = _producer_by_name(recipes)
    grouped = _rows_by_window_recipe(evidence)
    rows: list[SupplyBottleneck] = []

    # Upstream shortfall over observed item edges.
    for edge in graph.edges:
        if edge.edge_kind not in {
            SupplyEdgeKind.ITEM_TO_ITEM,
            SupplyEdgeKind.ITEM_TO_STRUCTURE,
            SupplyEdgeKind.ITEM_TO_STORAGE,
        }:
            continue
        group = grouped.get((edge.window_index, edge.recipe_id), ())
        if not group:
            continue
        attempts = sum(1 for row in group if row.attempt)
        completions = sum(1 for row in group if row.completed)
        demand = max(attempts, completions)
        producer = producers.get(edge.from_token)
        if producer is None:
            continue
        upstream = grouped.get((edge.window_index, producer.recipe_id), ())
        supply = sum(1 for row in upstream if row.completed)
        if demand < BOTTLENECK_DEMAND_MIN:
            continue
        ratio = _milli(demand - supply, demand)
        if ratio < BOTTLENECK_SHORTFALL_MILLI:
            continue
        _append(
            rows,
            kind=SupplyBottleneckKind.UPSTREAM_SHORTFALL,
            window=edge.window_index,
            stage=edge.to_token,
            edge=edge.edge_token,
            observed=demand,
            demand=demand,
            supply=supply,
            ratio=ratio,
            coverage=edge.coverage,
        )

    for (window, recipe_id), group in sorted(grouped.items()):
        spec = recipes.get(recipe_id)
        if spec is None:
            continue
        completed = [row for row in group if row.completed]
        if len(completed) < BOTTLENECK_MIN_EVENTS:
            continue
        # Single-location concentration.
        location_counts: dict[str, int] = {}
        for row in completed:
            if row.location_token != NONE_TOKEN:
                location_counts[row.location_token] = (
                    location_counts.get(row.location_token, 0) + 1
                )
        if location_counts:
            top_location, top_count = max(
                sorted(location_counts.items()), key=lambda item: item[1]
            )
            ratio = _milli(top_count, len(completed))
            if ratio >= BOTTLENECK_SHARE_MILLI:
                _append(
                    rows,
                    kind=SupplyBottleneckKind.SINGLE_LOCATION_CONCENTRATION,
                    window=window,
                    stage=spec.output_name,
                    observed=len(completed),
                    demand=len(completed),
                    supply=top_count,
                    ratio=ratio,
                    location=top_location,
                    coverage=SupplyCoverage.PARTIAL,
                )
        # Transport dependency.
        elsewhere = sum(
            edge.created_elsewhere_count
            for edge in graph.edges
            if edge.window_index == window
            and edge.recipe_id == recipe_id
            and edge.edge_kind is SupplyEdgeKind.TRANSPORT
        )
        ratio = _milli(elsewhere, len(completed))
        if elsewhere and ratio >= BOTTLENECK_SHARE_MILLI:
            _append(
                rows,
                kind=SupplyBottleneckKind.TRANSPORT_DEPENDENCY,
                window=window,
                stage=spec.output_name,
                observed=len(completed),
                demand=len(completed),
                supply=elsewhere,
                ratio=ratio,
                coverage=SupplyCoverage.PARTIAL,
            )
        # Tool dependency: completed tool recipes with under-supplied consumers.
        if spec.tool_role is not None:
            downstream = [
                other
                for other in recipes.values()
                if spec.output_name in other.item_input_names
            ]
            for consumer in downstream:
                consumer_rows = grouped.get((window, consumer.recipe_id), ())
                if not consumer_rows:
                    continue
                demand = max(
                    sum(1 for row in consumer_rows if row.attempt),
                    sum(1 for row in consumer_rows if row.completed),
                )
                supply = len(completed)
                if demand < BOTTLENECK_DEMAND_MIN:
                    continue
                ratio = _milli(demand - supply, demand)
                if ratio < BOTTLENECK_SHORTFALL_MILLI:
                    continue
                _append(
                    rows,
                    kind=SupplyBottleneckKind.TOOL_DEPENDENCY,
                    window=window,
                    stage=consumer.output_name,
                    observed=demand,
                    demand=demand,
                    supply=supply,
                    ratio=ratio,
                    skill=spec.tool_role,
                    coverage=SupplyCoverage.PARTIAL,
                )
        # Infrastructure dependency.
        if evidence.infrastructure_coverage is not SupplyCoverage.MISSING:
            backed = 0
            for row in completed:
                if row.location_token == NONE_TOKEN:
                    continue
                if any(
                    fact.location_token == row.location_token
                    for fact in evidence.infrastructure
                ):
                    backed += 1
            if backed:
                ratio = _milli(backed, len(completed))
                if ratio >= BOTTLENECK_SHARE_MILLI:
                    _append(
                        rows,
                        kind=SupplyBottleneckKind.INFRASTRUCTURE_DEPENDENCY,
                        window=window,
                        stage=spec.output_name,
                        observed=len(completed),
                        demand=len(completed),
                        supply=backed,
                        ratio=ratio,
                        coverage=SupplyCoverage.PARTIAL,
                    )
        # Organization dependency.
        if evidence.organization_coverage is not SupplyCoverage.MISSING:
            organization_counts: dict[str, int] = {}
            for row in completed:
                for claim in evidence.organization_claims:
                    if row.actor_token in claim.actor_tokens:
                        organization_counts[claim.organization_token] = (
                            organization_counts.get(claim.organization_token, 0) + 1
                        )
            for organization, count in sorted(organization_counts.items()):
                ratio = _milli(count, len(completed))
                if ratio >= BOTTLENECK_SHARE_MILLI:
                    _append(
                        rows,
                        kind=SupplyBottleneckKind.ORGANIZATION_DEPENDENCY,
                        window=window,
                        stage=spec.output_name,
                        observed=len(completed),
                        demand=len(completed),
                        supply=count,
                        ratio=ratio,
                        organization=organization,
                        coverage=SupplyCoverage.PARTIAL,
                    )
        # Skill constraint.
        if (
            spec.skill_domain is not None
            and evidence.skill_coverage is not SupplyCoverage.MISSING
        ):
            levels = {
                level.agent_token: level.level
                for level in evidence.skill_levels
                if level.domain == spec.skill_domain
            }
            performers = {row.actor_token for row in completed}
            low = sum(
                1 for actor in performers if levels.get(actor, 1.0) <= LOW_SKILL_LEVEL
            )
            ratio = _milli(low, len(performers))
            if low and ratio >= BOTTLENECK_SHARE_MILLI:
                _append(
                    rows,
                    kind=SupplyBottleneckKind.SKILL_CONSTRAINT,
                    window=window,
                    stage=spec.output_name,
                    observed=len(performers),
                    demand=len(performers),
                    supply=low,
                    ratio=ratio,
                    skill=spec.skill_domain,
                    coverage=SupplyCoverage.PARTIAL,
                )

    rows.sort(
        key=lambda row: (
            row.window_index,
            row.kind.value,
            row.stage_token,
            row.location_token,
            row.organization_token,
            row.skill_domain,
        )
    )
    if len(rows) > policy.max_bottlenecks:
        dropped = len(rows) - policy.max_bottlenecks
        rows = rows[: policy.max_bottlenecks]
        if notices is not None:
            notices.add("bottleneck_truncated")
        _LOG.warning(
            "supply_chain_bottleneck_truncated kept=%s dropped=%s",
            len(rows),
            dropped,
        )
    _LOG.debug(
        "supply_chain_bottlenecks_detected count=%s kinds=%s",
        len(rows),
        len({row.kind for row in rows}),
    )
    return tuple(rows)
