"""Build the detached production dependency structure and observed stage rows.

Recipe structure arrives only as ``SupplyRecipeSpec`` values. This module never
imports the world production catalog, ``WorldState``, a runtime, or a store.
Labor participation is an explicit actor-to-recipe join and never becomes an
edge row.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from analysis.economic_cascades_contract import (
    CascadeCoverage,
    CascadeDependencyKind,
    EconomicCascadesError,
)
from analysis.economic_cascades_policy import (
    EconomicCascadesPolicy,
    default_policy,
    window_tick,
)
from analysis.economic_cascades_rows import (
    CascadeDependencyEdgeRow,
    CascadeStageRow,
)
from analysis.supply_chain_events import (
    SupplyRecipeSpec,
    SupplyStageObservation,
)

__all__ = [
    "INFRASTRUCTURE_STAGE_ACTIONS",
    "CascadeDependencyResult",
    "build_economic_cascade_dependencies",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_cascades.dependencies"
)

INFRASTRUCTURE_STAGE_ACTIONS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "irrigation": frozenset({"harvest"}),
        "storage": frozenset({"store"}),
        "trade_post": frozenset({"store", "craft"}),
        "road": frozenset({"harvest", "craft", "build"}),
        "bridge": frozenset({"harvest", "craft"}),
    }
)


@dataclass(frozen=True, slots=True)
class CascadeDependencyResult:
    """Observed stage rows, dependency edges, and private labor joins."""

    stage_rows: tuple[CascadeStageRow, ...] = ()
    edges: tuple[CascadeDependencyEdgeRow, ...] = ()
    labor_joins: tuple[tuple[str, tuple[str, ...]], ...] = ()
    notices: tuple[str, ...] = ()
    coverage: CascadeCoverage = CascadeCoverage.MISSING
    stage_count: int = 0
    edge_count: int = 0
    max_depth: int = 0

    def __post_init__(self) -> None:
        for name in ("stage_rows", "edges", "labor_joins", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicCascadesError("economic_cascades_invalid_chain")
        if type(self.coverage) is not CascadeCoverage:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        for name in ("stage_count", "edge_count", "max_depth"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicCascadesError("economic_cascades_invalid_chain")


def _require_recipe(value: object) -> SupplyRecipeSpec:
    if type(value) is not SupplyRecipeSpec:
        raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
    return value


def _recipe_map(recipes: Sequence[SupplyRecipeSpec]) -> dict[str, SupplyRecipeSpec]:
    if isinstance(recipes, (str, bytes)) or not isinstance(recipes, Sequence):
        raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
    by_id: dict[str, SupplyRecipeSpec] = {}
    for recipe in recipes:
        spec = _require_recipe(recipe)
        if spec.recipe_id in by_id:
            raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
        by_id[spec.recipe_id] = spec
    return by_id


def _producer_by_output(
    recipes: Mapping[str, SupplyRecipeSpec],
) -> dict[str, str]:
    producers: dict[str, str] = {}
    for recipe_id in sorted(recipes):
        producers.setdefault(recipes[recipe_id].output_name, recipe_id)
    return producers


def _depths(
    recipes: Mapping[str, SupplyRecipeSpec],
    producer_by_output: Mapping[str, str],
) -> tuple[dict[str, int], bool]:
    """Return recipe depths and whether the input graph contains a cycle."""

    depths: dict[str, int] = {}
    visiting: set[str] = set()
    cycle = False

    def visit(recipe_id: str) -> int:
        nonlocal cycle
        cached = depths.get(recipe_id)
        if cached is not None:
            return cached
        if recipe_id in visiting:
            cycle = True
            return 1
        visiting.add(recipe_id)
        spec = recipes[recipe_id]
        parents = [
            producer_by_output[name]
            for name in (*spec.resource_input_names, *spec.item_input_names)
            if name in producer_by_output
            and producer_by_output[name] != recipe_id
        ]
        depth = 1 + max((visit(parent) for parent in parents), default=0)
        visiting.discard(recipe_id)
        depths[recipe_id] = depth
        return depth

    for recipe_id in sorted(recipes):
        visit(recipe_id)
    return depths, cycle


def _stage_groups(
    stages: Sequence[SupplyStageObservation],
) -> dict[tuple[int, str, str], list[SupplyStageObservation]]:
    groups: dict[tuple[int, str, str], list[SupplyStageObservation]] = {}
    for stage in stages:
        groups.setdefault(
            (stage.window_index, stage.recipe_id, stage.location_token), []
        ).append(stage)
    return groups


def _downstream_consumers(
    recipes: Mapping[str, SupplyRecipeSpec],
) -> dict[str, tuple[str, ...]]:
    consumers: dict[str, list[str]] = {}
    for recipe_id in sorted(recipes):
        spec = recipes[recipe_id]
        for name in (*spec.resource_input_names, *spec.item_input_names):
            consumers.setdefault(name, []).append(recipe_id)
    return {name: tuple(values) for name, values in consumers.items()}


def build_economic_cascade_dependencies(
    *,
    stages: Sequence[SupplyStageObservation],
    recipes: Sequence[SupplyRecipeSpec],
    infrastructure: Sequence[tuple[str, str, bool]] = (),
    routes: Sequence[tuple[str, str, str]] = (),
    policy: EconomicCascadesPolicy | None = None,
    require_complete_graph: bool = False,
) -> CascadeDependencyResult:
    """Build observed stage rows and real dependency edges."""

    active = default_policy() if policy is None else policy
    if type(active) is not EconomicCascadesPolicy:
        raise EconomicCascadesError("economic_cascades_invalid_policy")
    if isinstance(stages, (str, bytes)) or not isinstance(stages, Sequence):
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    for stage in stages:
        if type(stage) is not SupplyStageObservation:
            raise EconomicCascadesError("economic_cascades_invalid_event_order")
    by_id = _recipe_map(recipes)
    producer_by_output = _producer_by_output(by_id)
    depths, cycle = _depths(by_id, producer_by_output)
    notices: set[str] = set()
    if cycle:
        notices.add("recipe_cycle")
        _LOG.warning("economic_cascades_recipe_cycle")
        raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")

    if require_complete_graph:
        for recipe_id in sorted(by_id):
            spec = by_id[recipe_id]
            for name in spec.item_input_names:
                if name not in producer_by_output:
                    _LOG.warning("economic_cascades_incomplete_recipe_graph")
                    raise EconomicCascadesError(
                        "economic_cascades_invalid_recipe_spec"
                    )

    infrastructure_by_location: dict[str, list[tuple[str, bool]]] = {}
    for location_token, kind, operational in infrastructure:
        if type(location_token) is not str or not location_token:
            raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
        if type(kind) is not str or not kind:
            raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
        if type(operational) is not bool:
            raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
        infrastructure_by_location.setdefault(location_token, []).append(
            (kind, operational)
        )

    groups = _stage_groups(stages)
    consumers = _downstream_consumers(by_id)
    attempts_by_recipe_window: dict[tuple[int, str], int] = {}
    for stage in stages:
        if stage.attempt:
            attempt_key = (stage.window_index, stage.recipe_id)
            attempts_by_recipe_window[attempt_key] = (
                attempts_by_recipe_window.get(attempt_key, 0) + 1
            )

    stage_rows: list[CascadeStageRow] = []
    for group_key in sorted(groups):
        window_index, recipe_id, location_token = group_key
        consumer_spec = by_id.get(recipe_id)
        if consumer_spec is None:
            notices.add("unknown_recipe")
            continue
        observations = groups[group_key]
        attempt_count = sum(1 for item in observations if item.attempt)
        completion_count = sum(1 for item in observations if item.completed)
        downstream_demand = sum(
            attempts_by_recipe_window.get((window_index, consumer), 0)
            for consumer in consumers.get(consumer_spec.output_name, ())
            if consumer != recipe_id
        )
        demand_count = attempt_count + downstream_demand
        operational_kinds = {
            kind
            for kind, operational in infrastructure_by_location.get(
                location_token, ()
            )
            if operational
        }
        has_infrastructure = any(
            consumer_spec.action
            in INFRASTRUCTURE_STAGE_ACTIONS.get(kind, frozenset())
            for kind in operational_kinds
        )
        stage_rows.append(
            CascadeStageRow(
                window_index=window_index,
                window_tick=window_tick(window_index, active),
                recipe_id=recipe_id,
                action=consumer_spec.action,
                output_name=consumer_spec.output_name,
                output_kind=consumer_spec.output_kind,
                location_token=location_token,
                demand_count=demand_count,
                attempt_count=attempt_count,
                completion_count=completion_count,
                tool_dependent=consumer_spec.tool_role is not None,
                has_infrastructure=has_infrastructure,
                coverage=CascadeCoverage.COMPLETE,
            )
        )

    stage_rows.sort(
        key=lambda row: (
            row.window_index,
            row.recipe_id,
            row.location_token,
        )
    )
    if len(stage_rows) > active.max_stages:
        stage_rows = stage_rows[: active.max_stages]
        notices.add("stages_truncated")
        _LOG.warning(
            "economic_cascades_stages_truncated retained=%s cap=%s",
            len(stage_rows),
            active.max_stages,
        )

    edge_specs: list[tuple[str, str, CascadeDependencyKind, int, int]] = []
    for consumer_id in sorted(by_id):
        consumer = by_id[consumer_id]
        for name in consumer.resource_input_names:
            producer = producer_by_output.get(name)
            if producer is None or producer == consumer_id:
                continue
            edge_specs.append(
                (
                    producer,
                    consumer_id,
                    CascadeDependencyKind.RESOURCE_INPUT,
                    depths.get(consumer_id, 1),
                    1,
                )
            )
        for name in consumer.item_input_names:
            producer = producer_by_output.get(name)
            if producer is None or producer == consumer_id:
                continue
            edge_specs.append(
                (
                    producer,
                    consumer_id,
                    CascadeDependencyKind.ITEM_INPUT,
                    depths.get(consumer_id, 1),
                    1,
                )
            )

    tool_producers = [
        recipe_id
        for recipe_id in sorted(by_id)
        if by_id[recipe_id].output_kind == "tool"
    ]
    for producer in tool_producers:
        for consumer_id in sorted(by_id):
            consumer = by_id[consumer_id]
            if consumer.tool_role is None or consumer_id == producer:
                continue
            edge_specs.append(
                (
                    producer,
                    consumer_id,
                    CascadeDependencyKind.TOOL_DEPENDENCY,
                    depths.get(consumer_id, 1),
                    1,
                )
            )

    for location_token in sorted(infrastructure_by_location):
        for kind, operational in infrastructure_by_location[location_token]:
            if not operational:
                continue
            actions = INFRASTRUCTURE_STAGE_ACTIONS.get(kind, frozenset())
            for consumer_id in sorted(by_id):
                if by_id[consumer_id].action not in actions:
                    continue
                evidence = sum(
                    1
                    for item in stages
                    if item.recipe_id == consumer_id
                    and item.location_token == location_token
                )
                edge_specs.append(
                    (
                        f"asset:{kind}@{location_token}",
                        consumer_id,
                        CascadeDependencyKind.INFRASTRUCTURE_DEPENDENCY,
                        depths.get(consumer_id, 1),
                        max(1, evidence),
                    )
                )

    for origin, destination, status in routes:
        if type(origin) is not str or not origin:
            raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
        if type(destination) is not str or not destination:
            raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
        if status == "open":
            continue
        for location in sorted({origin, destination}):
            for consumer_id in sorted(by_id):
                evidence = sum(
                    1
                    for item in stages
                    if item.recipe_id == consumer_id
                    and item.location_token == location
                )
                if evidence == 0:
                    continue
                edge_specs.append(
                    (
                        f"route:{origin}->{destination}",
                        consumer_id,
                        CascadeDependencyKind.TRANSPORT_DEPENDENCY,
                        depths.get(consumer_id, 1),
                        evidence,
                    )
                )

    deduped: dict[tuple[int, str, str, str], tuple[int, int]] = {}
    windows_by_recipe: dict[str, set[int]] = {}
    for window_index, recipe_id, _location in groups:
        windows_by_recipe.setdefault(recipe_id, set()).add(window_index)
    ordered_windows = {
        recipe_id: tuple(sorted(values))
        for recipe_id, values in windows_by_recipe.items()
    }
    for upstream, downstream, kind, depth, evidence in edge_specs:
        if depth > active.max_chain_depth:
            notices.add("dependency_depth_truncated")
            continue
        for window_index in ordered_windows.get(downstream, (0,)):
            edge_key = (window_index, upstream, downstream, kind.value)
            previous = deduped.get(edge_key)
            if previous is None or evidence > previous[1]:
                deduped[edge_key] = (depth, max(1, evidence))
    if "dependency_depth_truncated" in notices:
        _LOG.warning("economic_cascades_dependency_depth_truncated")

    edges: list[CascadeDependencyEdgeRow] = []
    for (window_index, upstream, downstream, kind_value), (depth, evidence) in sorted(
        deduped.items()
    ):
        edges.append(
            CascadeDependencyEdgeRow(
                window_index=window_index,
                window_tick=window_tick(window_index, active),
                upstream_token=upstream,
                downstream_recipe_id=downstream,
                kind=CascadeDependencyKind(kind_value),
                depth=depth,
                evidence_count=evidence,
            )
        )
    edges.sort(
        key=lambda row: (
            row.kind.value,
            row.upstream_token,
            row.downstream_recipe_id,
        )
    )
    if len(edges) > active.max_dependency_edges:
        edges = edges[: active.max_dependency_edges]
        notices.add("edges_truncated")
        _LOG.warning(
            "economic_cascades_edges_truncated retained=%s cap=%s",
            len(edges),
            active.max_dependency_edges,
        )

    joins: dict[str, set[str]] = {}
    for stage in stages:
        if stage.completed:
            joins.setdefault(stage.actor_token, set()).add(stage.recipe_id)
    labor_joins = tuple(
        (actor, tuple(sorted(recipe_ids)))
        for actor, recipe_ids in sorted(joins.items())
    )

    max_depth = max((row.depth for row in edges), default=0)
    if not stage_rows and not edges:
        coverage = CascadeCoverage.MISSING
    elif notices:
        coverage = CascadeCoverage.PARTIAL
    else:
        coverage = CascadeCoverage.COMPLETE

    _LOG.debug(
        "economic_cascades_graph_built stages=%s edges=%s depth=%s",
        len(stage_rows),
        len(edges),
        max_depth,
    )
    _LOG.info(
        "economic_cascades_graph_complete stages=%s edges=%s",
        len(stage_rows),
        len(edges),
    )
    if coverage is CascadeCoverage.PARTIAL:
        _LOG.warning(
            "economic_cascades_partial_coverage notices=%s",
            ",".join(sorted(notices)),
        )
    return CascadeDependencyResult(
        stage_rows=tuple(stage_rows),
        edges=tuple(edges),
        labor_joins=labor_joins,
        notices=tuple(sorted(notices)),
        coverage=coverage,
        stage_count=len(stage_rows),
        edge_count=len(edges),
        max_depth=max_depth,
    )
