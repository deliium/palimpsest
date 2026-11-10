"""Bounded detached supply-chain analysis composition."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from analysis.supply_chain_bottlenecks import SupplyBottleneck, detect_bottlenecks
from analysis.supply_chain_contract import (
    SupplyChainError,
    SupplyCoverage,
)
from analysis.supply_chain_events import (
    SupplyRecipeSpec,
    SupplyStageObservation,
    supply_evidence_from_events,
)
from analysis.supply_chain_graph import (
    SupplyChainPath,
    SupplyDependencyEdge,
    SupplyLocationRow,
    SupplyOrganizationRow,
    build_dependency_graph,
)
from analysis.supply_chain_identity import (
    SupplyChainLineageRow,
    group_chains_by_window,
    link_supply_chain_lineage,
)
from analysis.supply_chain_layers import (
    SupplyChainLayerView,
    assert_supply_chain_layer_separation,
    project_supply_chain_layers,
)
from analysis.supply_chain_policy import (
    SupplyChainAnalysisPolicy,
    default_supply_chain_analysis_policy,
)

__all__ = [
    "SupplyChainAnalysis",
    "SupplyChainLayerView",
    "assert_supply_chain_layer_separation",
    "empty_supply_chain_analysis",
    "harvest_supply_chain_analysis",
    "project_supply_chain_layers",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.analysis")

_TRUNCATION_NOTICES: Final[frozenset[str]] = frozenset(
    {
        "evidence_truncated",
        "stage_truncated",
        "edge_truncated",
        "chain_truncated",
        "bottleneck_truncated",
        "lineage_truncated",
        "location_truncated",
        "organization_truncated",
    }
)


@dataclass(frozen=True, slots=True)
class SupplyChainAnalysis:
    window_tick: int
    stages: tuple[SupplyStageObservation, ...] = ()
    edges: tuple[SupplyDependencyEdge, ...] = ()
    chains: tuple[SupplyChainPath, ...] = ()
    lineage: tuple[SupplyChainLineageRow, ...] = ()
    bottlenecks: tuple[SupplyBottleneck, ...] = ()
    locations: tuple[SupplyLocationRow, ...] = ()
    organizations: tuple[SupplyOrganizationRow, ...] = ()
    layers: SupplyChainLayerView = field(default_factory=SupplyChainLayerView)
    evidence_coverage: SupplyCoverage = SupplyCoverage.MISSING
    skill_coverage: SupplyCoverage = SupplyCoverage.MISSING
    infrastructure_coverage: SupplyCoverage = SupplyCoverage.MISSING
    organization_coverage: SupplyCoverage = SupplyCoverage.MISSING
    lineage_coverage: SupplyCoverage = SupplyCoverage.MISSING
    coverage: SupplyCoverage = SupplyCoverage.MISSING
    notices: tuple[str, ...] = ()
    stage_count: int = 0
    edge_count: int = 0
    chain_count: int = 0
    bottleneck_count: int = 0
    location_count: int = 0
    organization_count: int = 0
    sustained_chain_count: int = 0
    max_depth: int = 0

    def __post_init__(self) -> None:
        for name, rows in (
            ("stage_count", self.stages),
            ("edge_count", self.edges),
            ("chain_count", self.chains),
            ("bottleneck_count", self.bottlenecks),
            ("location_count", self.locations),
            ("organization_count", self.organizations),
        ):
            if getattr(self, name) != len(rows):
                raise SupplyChainError("supply_chain_invalid_policy")
        if isinstance(self.window_tick, bool) or type(self.window_tick) is not int:
            raise SupplyChainError("supply_chain_invalid_policy")
        if self.window_tick < 0:
            raise SupplyChainError("supply_chain_invalid_policy")


def _aggregate_coverage(
    analysis: SupplyChainAnalysis,
    notices: tuple[str, ...],
) -> SupplyCoverage:
    if not analysis.stages:
        return SupplyCoverage.MISSING
    dimensions = (
        analysis.evidence_coverage,
        analysis.skill_coverage,
        analysis.infrastructure_coverage,
        analysis.organization_coverage,
        analysis.lineage_coverage,
    )
    if any(
        coverage in {SupplyCoverage.PARTIAL, SupplyCoverage.MISSING}
        for coverage in dimensions
    ):
        return SupplyCoverage.PARTIAL
    if any(notice in _TRUNCATION_NOTICES for notice in notices):
        return SupplyCoverage.PARTIAL
    return SupplyCoverage.COMPLETE


def _lineage_coverage(
    lineage: Sequence[SupplyChainLineageRow],
    chains: Sequence[SupplyChainPath],
) -> SupplyCoverage:
    grouped = group_chains_by_window(tuple(chains))
    if len(grouped) < 2:
        return SupplyCoverage.MISSING
    if not lineage:
        return SupplyCoverage.PARTIAL
    if any(row.coverage is SupplyCoverage.PARTIAL for row in lineage):
        return SupplyCoverage.PARTIAL
    return SupplyCoverage.COMPLETE


def _sustained_count(lineage: Sequence[SupplyChainLineageRow]) -> int:
    transitions: dict[str, int] = {}
    for row in lineage:
        if row.status in {"continued", "transformed"}:
            transitions[row.chain_token] = transitions.get(row.chain_token, 0) + 1
    return sum(1 for count in transitions.values() if count >= 2)


def harvest_supply_chain_analysis(
    events: Sequence[object],
    *,
    recipes: Sequence[SupplyRecipeSpec],
    policy: SupplyChainAnalysisPolicy | None = None,
    window_tick: int | None = None,
    skill_levels: object | None = None,
    infrastructure: object | None = None,
    organization_claims: object | None = None,
) -> SupplyChainAnalysis:
    """Run evidence, graph, bottlenecks, lineage, rows, and layer projection."""
    resolved_policy = (
        default_supply_chain_analysis_policy() if policy is None else policy
    )
    if type(resolved_policy) is not SupplyChainAnalysisPolicy:
        raise SupplyChainError("supply_chain_invalid_policy")
    for recipe in recipes:
        if type(recipe) is not SupplyRecipeSpec:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
    tick = resolved_policy.window_ticks if window_tick is None else window_tick
    evidence = supply_evidence_from_events(
        events,  # type: ignore[arg-type]
        policy=resolved_policy,
        recipes=recipes,
        skill_levels=skill_levels,
        infrastructure=infrastructure,
        organization_claims=organization_claims,
    )
    graph = build_dependency_graph(evidence, policy=resolved_policy)
    truncation_notices: set[str] = set()
    bottlenecks = detect_bottlenecks(
        graph, evidence, policy=resolved_policy, notices=truncation_notices
    )
    lineage = link_supply_chain_lineage(
        graph.chains, policy=resolved_policy, notices=truncation_notices
    )
    layers = project_supply_chain_layers(
        stages=evidence.rows,
        edges=graph.edges,
        chains=graph.chains,
        lineage=lineage,
        bottlenecks=bottlenecks,
        locations=graph.locations,
        organizations=graph.organization_rows,
    )
    notices = tuple(
        sorted(set(evidence.notices) | set(graph.notices) | truncation_notices)
    )
    analysis = SupplyChainAnalysis(
        window_tick=tick,
        stages=evidence.rows,
        edges=graph.edges,
        chains=graph.chains,
        lineage=lineage,
        bottlenecks=bottlenecks,
        locations=graph.locations,
        organizations=graph.organization_rows,
        layers=layers,
        evidence_coverage=evidence.coverage,
        skill_coverage=evidence.skill_coverage,
        infrastructure_coverage=evidence.infrastructure_coverage,
        organization_coverage=evidence.organization_coverage,
        lineage_coverage=_lineage_coverage(lineage, graph.chains),
        notices=notices,
        stage_count=len(evidence.rows),
        edge_count=len(graph.edges),
        chain_count=len(graph.chains),
        bottleneck_count=len(bottlenecks),
        location_count=len(graph.locations),
        organization_count=len(graph.organization_rows),
        sustained_chain_count=_sustained_count(lineage),
        max_depth=max((chain.depth for chain in graph.chains), default=0),
    )
    coverage = _aggregate_coverage(analysis, notices)
    analysis = SupplyChainAnalysis(
        **{
            **{name: getattr(analysis, name) for name in analysis.__dataclass_fields__},
            "coverage": coverage,
        }
    )
    if coverage is SupplyCoverage.PARTIAL:
        _LOG.warning(
            "supply_chain_analysis_partial dimensions=%s",
            ",".join(
                coverage.value
                for coverage in (
                    analysis.evidence_coverage,
                    analysis.skill_coverage,
                    analysis.infrastructure_coverage,
                    analysis.organization_coverage,
                )
            ),
        )
    _LOG.info(
        "supply_chain_analysis_built stages=%s edges=%s chains=%s "
        "bottlenecks=%s coverage=%s",
        analysis.stage_count,
        analysis.edge_count,
        analysis.chain_count,
        analysis.bottleneck_count,
        analysis.coverage.value,
    )
    return analysis


def empty_supply_chain_analysis(*, window_tick: int = 0) -> SupplyChainAnalysis:
    """Return the canonical empty analysis object."""
    layers = project_supply_chain_layers(
        stages=(),
        edges=(),
        chains=(),
        lineage=(),
        bottlenecks=(),
        locations=(),
        organizations=(),
    )
    return SupplyChainAnalysis(
        window_tick=window_tick,
        layers=layers,
        evidence_coverage=SupplyCoverage.MISSING,
        skill_coverage=SupplyCoverage.MISSING,
        infrastructure_coverage=SupplyCoverage.MISSING,
        organization_coverage=SupplyCoverage.MISSING,
        lineage_coverage=SupplyCoverage.MISSING,
        coverage=SupplyCoverage.MISSING,
    )
