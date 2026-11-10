"""Observed supply dependency graph and bounded chain paths."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.supply_chain_contract import (
    NONE_TOKEN,
    SUPPLY_CHAIN_PREFIX,
    SUPPLY_EDGE_PREFIX,
    SUPPLY_STAGE_PREFIX,
    SupplyChainError,
    SupplyCoverage,
    SupplyEdgeKind,
    SupplyNodeKind,
    analysis_supply_token,
)
from analysis.supply_chain_events import (
    SupplyEvidenceHarvest,
    SupplyInfrastructureFact,
    SupplyOrganizationClaim,
    SupplyRecipeSpec,
    SupplyStageObservation,
)
from analysis.supply_chain_policy import (
    MAX_CHAIN_DEPTH,
    SupplyChainAnalysisPolicy,
)

__all__ = [
    "SupplyChainPath",
    "SupplyDependencyEdge",
    "SupplyDependencyGraph",
    "SupplyDependencyNode",
    "SupplyLocationRow",
    "SupplyOrganizationRow",
    "build_dependency_graph",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.graph")


@dataclass(frozen=True, slots=True)
class SupplyDependencyNode:
    node_token: str
    node_kind: SupplyNodeKind
    label_token: str
    window_index: int
    observation_count: int
    completed_count: int
    coverage: SupplyCoverage


@dataclass(frozen=True, slots=True)
class SupplyDependencyEdge:
    edge_token: str
    window_index: int
    from_kind: SupplyNodeKind
    from_token: str
    to_kind: SupplyNodeKind
    to_token: str
    edge_kind: SupplyEdgeKind
    recipe_id: str
    observed_count: int
    completed_count: int
    share_milli: int
    created_elsewhere_count: int
    coverage: SupplyCoverage


@dataclass(frozen=True, slots=True)
class SupplyChainPath:
    chain_token: str
    window_index: int
    stage_tokens: tuple[str, ...]
    edge_tokens: tuple[str, ...]
    depth: int
    location_tokens: tuple[str, ...]
    organization_tokens: tuple[str, ...]
    completed_count: int
    coverage: SupplyCoverage


@dataclass(frozen=True, slots=True)
class SupplyLocationRow:
    location_token: str
    window_index: int
    observed_count: int
    completed_count: int
    coverage: SupplyCoverage


@dataclass(frozen=True, slots=True)
class SupplyOrganizationRow:
    organization_token: str
    window_index: int
    actor_count: int
    claim_count: int
    completed_count: int
    coverage: SupplyCoverage


@dataclass(frozen=True, slots=True)
class SupplyDependencyGraph:
    nodes: tuple[SupplyDependencyNode, ...] = ()
    edges: tuple[SupplyDependencyEdge, ...] = ()
    chains: tuple[SupplyChainPath, ...] = ()
    locations: tuple[SupplyLocationRow, ...] = ()
    organization_rows: tuple[SupplyOrganizationRow, ...] = ()
    coverage: SupplyCoverage = SupplyCoverage.MISSING
    notices: tuple[str, ...] = ()


class _NodeAccumulator:
    __slots__ = ("completed_count", "observation_count")

    def __init__(self) -> None:
        self.observation_count = 0
        self.completed_count = 0


def _row_coverage(
    row: SupplyStageObservation, evidence: SupplyCoverage
) -> SupplyCoverage:
    if row.location_token == NONE_TOKEN or NONE_TOKEN in row.item_names:
        return SupplyCoverage.PARTIAL
    return evidence


def _node(
    window: int,
    kind: SupplyNodeKind,
    token: str,
) -> tuple[str, str]:
    node_token = analysis_supply_token(
        SUPPLY_STAGE_PREFIX, f"{window}\x1f{kind.value}\x1f{token}"
    )
    return node_token, token


def _add_edge(
    edges: dict[tuple[int, str, str, str, str], dict[str, object]],
    *,
    window: int,
    edge_kind: SupplyEdgeKind,
    from_kind: SupplyNodeKind,
    from_token: str,
    to_kind: SupplyNodeKind,
    to_token: str,
    recipe_id: str,
    observed_count: int,
    completed_count: int,
    coverage: SupplyCoverage,
    created_elsewhere_count: int = 0,
    group_key: tuple[int, str] = (0, ""),
) -> str:
    edge_token = analysis_supply_token(
        SUPPLY_EDGE_PREFIX,
        (
            f"{window}\x1f{edge_kind.value}\x1f{from_kind.value}\x1f"
            f"{from_token}\x1f{to_kind.value}\x1f{to_token}\x1f{recipe_id}"
        ),
    )
    key = (window, edge_kind.value, from_token, to_token, recipe_id)
    entry = edges.get(key)
    if entry is None:
        entry = {
            "token": edge_token,
            "window": window,
            "from_kind": from_kind,
            "to_kind": to_kind,
            "recipe_id": recipe_id,
            "observed_count": observed_count,
            "completed_count": completed_count,
            "created_elsewhere_count": 0,
            "coverage": coverage,
            "group_key": group_key,
        }
        edges[key] = entry
    entry["created_elsewhere_count"] = (
        cast(int, entry["created_elsewhere_count"]) + created_elsewhere_count
    )
    if entry["group_key"] != group_key:
        entry["observed_count"] = (
            cast(int, entry["observed_count"]) + observed_count
        )
        entry["completed_count"] = (
            cast(int, entry["completed_count"]) + completed_count
        )
        entry["group_key"] = group_key
        if coverage is SupplyCoverage.PARTIAL:
            entry["coverage"] = coverage
    return edge_token


def _recipe_map(evidence: SupplyEvidenceHarvest) -> dict[str, SupplyRecipeSpec]:
    return {recipe.recipe_id: recipe for recipe in evidence.recipes}


def _infrastructure_at(
    evidence: SupplyEvidenceHarvest, location: str
) -> tuple[SupplyInfrastructureFact, ...]:
    return tuple(
        fact for fact in evidence.infrastructure if fact.location_token == location
    )


def _claims_for_actor(
    evidence: SupplyEvidenceHarvest, actor: str
) -> tuple[SupplyOrganizationClaim, ...]:
    return tuple(
        claim for claim in evidence.organization_claims if actor in claim.actor_tokens
    )


def _build_chain_paths(
    edges: Sequence[SupplyDependencyEdge],
    *,
    policy: SupplyChainAnalysisPolicy,
) -> tuple[tuple[SupplyChainPath, ...], bool]:
    adjacency: dict[int, dict[str, list[SupplyDependencyEdge]]] = {}
    incoming: dict[int, set[str]] = {}
    for edge in edges:
        if edge.edge_kind not in {
            SupplyEdgeKind.RESOURCE_TO_ITEM,
            SupplyEdgeKind.ITEM_TO_ITEM,
        }:
            continue
        if edge.from_token == edge.to_token:
            continue
        window_edges = adjacency.setdefault(edge.window_index, {})
        window_edges.setdefault(edge.from_token, []).append(edge)
        incoming.setdefault(edge.window_index, set()).add(edge.to_token)
        incoming[edge.window_index].add(edge.from_token)
    paths: list[SupplyChainPath] = []
    truncated = False
    for window in sorted(adjacency):
        if len(paths) >= policy.max_chains:
            truncated = True
            break
        starts = sorted(
            token for token in adjacency[window] if token not in incoming[window]
        )
        if not starts:
            starts = sorted(adjacency[window])
        for start in starts:
            if len(paths) >= policy.max_chains:
                truncated = True
                break
            stack: list[tuple[str, list[SupplyDependencyEdge], tuple[str, ...]]] = [
                (start, [], (start,))
            ]
            while stack:
                node, path_edges, stages = stack.pop()
                next_edges = sorted(
                    adjacency[window].get(node, ()),
                    key=lambda edge: (edge.to_token, edge.edge_token),
                )
                if not next_edges:
                    if len(path_edges) >= 1:
                        depth = len(path_edges) + 1
                        if depth >= 2:
                            edge_tokens = tuple(edge.edge_token for edge in path_edges)
                            chain_token = analysis_supply_token(
                                SUPPLY_CHAIN_PREFIX, "|".join(edge_tokens)
                            )
                            locations = ()
                            paths.append(
                                SupplyChainPath(
                                    chain_token=chain_token,
                                    window_index=window,
                                    stage_tokens=tuple(stages),
                                    edge_tokens=edge_tokens,
                                    depth=depth,
                                    location_tokens=locations,
                                    organization_tokens=(),
                                    completed_count=min(
                                        edge.completed_count for edge in path_edges
                                    ),
                                    coverage=(
                                        SupplyCoverage.PARTIAL
                                        if any(
                                            edge.coverage is SupplyCoverage.PARTIAL
                                            for edge in path_edges
                                        )
                                        else SupplyCoverage.COMPLETE
                                    ),
                                )
                            )
                            if len(paths) >= policy.max_chains:
                                truncated = True
                                stack.clear()
                                break
                    continue
                if len(path_edges) + 2 > MAX_CHAIN_DEPTH:
                    continue
                for edge in next_edges:
                    stack.append(
                        (
                            edge.to_token,
                            [*path_edges, edge],
                            (*stages, edge.to_token),
                        )
                    )
    unique: dict[str, SupplyChainPath] = {}
    for path in paths:
        unique[path.chain_token] = path
    ordered = tuple(
        unique[token]
        for token in sorted(
            unique,
            key=lambda token: (
                unique[token].window_index,
                unique[token].stage_tokens[0],
                unique[token].edge_tokens,
            ),
        )
    )
    return ordered, truncated


def build_dependency_graph(
    evidence: SupplyEvidenceHarvest,
    *,
    policy: SupplyChainAnalysisPolicy,
) -> SupplyDependencyGraph:
    """Derive the observed dependency graph and chain paths."""
    if type(evidence) is not SupplyEvidenceHarvest:
        raise SupplyChainError("supply_chain_invalid_policy")
    recipes = _recipe_map(evidence)
    notices: set[str] = set(evidence.notices)
    groups: dict[tuple[int, str], list[SupplyStageObservation]] = {}
    for row in evidence.rows:
        groups.setdefault((row.window_index, row.recipe_id), []).append(row)
    nodes: dict[tuple[int, SupplyNodeKind, str], _NodeAccumulator] = {}
    edges: dict[tuple[int, str, str, str, str], dict[str, object]] = {}
    locations: dict[tuple[int, str], list[SupplyStageObservation]] = {}

    def touch(
        window: int,
        kind: SupplyNodeKind,
        token: str,
        *,
        completed: bool,
    ) -> None:
        if token == NONE_TOKEN:
            return
        accumulator = nodes.setdefault((window, kind, token), _NodeAccumulator())
        accumulator.observation_count += 1
        if completed:
            accumulator.completed_count += 1

    for (window, recipe_id), rows in sorted(groups.items()):
        spec = recipes.get(recipe_id)
        if spec is None:
            notices.add("unknown_recipe")
            continue
        observed = len(rows)
        completed_rows = [row for row in rows if row.completed]
        completed = len(completed_rows)
        output_kind = _output_node_kind(spec)
        for row in rows:
            if row.location_token != NONE_TOKEN:
                locations.setdefault((window, row.location_token), []).append(row)
        for row in completed_rows:
            output_token = spec.output_name
            row_coverage = _row_coverage(row, evidence.coverage)
            touch(window, output_kind, output_token, completed=True)
            if row.location_token != NONE_TOKEN:
                touch(
                    window, SupplyNodeKind.LOCATION, row.location_token, completed=True
                )
                _add_edge(
                    edges,
                    window=window,
                    edge_kind=SupplyEdgeKind.LOCATION_TO_STAGE,
                    from_kind=SupplyNodeKind.LOCATION,
                    from_token=row.location_token,
                    to_kind=output_kind,
                    to_token=output_token,
                    recipe_id=recipe_id,
                    observed_count=observed,
                    completed_count=completed,
                    group_key=(window, recipe_id),
                    coverage=row_coverage,
                )
                for fact in _infrastructure_at(evidence, row.location_token):
                    for kind in fact.kinds:
                        touch(
                            window,
                            SupplyNodeKind.INFRASTRUCTURE,
                            kind,
                            completed=True,
                        )
                        _add_edge(
                            edges,
                            window=window,
                            edge_kind=SupplyEdgeKind.INFRASTRUCTURE_TO_STAGE,
                            from_kind=SupplyNodeKind.INFRASTRUCTURE,
                            from_token=kind,
                            to_kind=output_kind,
                            to_token=output_token,
                            recipe_id=recipe_id,
                            observed_count=observed,
                            completed_count=completed,
                            group_key=(window, recipe_id),
                            coverage=row_coverage,
                        )
            for claim in _claims_for_actor(evidence, row.actor_token):
                touch(
                    window,
                    SupplyNodeKind.ORGANIZATION,
                    claim.organization_token,
                    completed=True,
                )
                _add_edge(
                    edges,
                    window=window,
                    edge_kind=SupplyEdgeKind.ORGANIZATION_TO_STAGE,
                    from_kind=SupplyNodeKind.ORGANIZATION,
                    from_token=claim.organization_token,
                    to_kind=output_kind,
                    to_token=output_token,
                    recipe_id=recipe_id,
                    observed_count=observed,
                    completed_count=completed,
                    group_key=(window, recipe_id),
                    coverage=row_coverage,
                )
            if spec.tool_role is not None:
                touch(window, SupplyNodeKind.TOOL, spec.tool_role, completed=True)
                _add_edge(
                    edges,
                    window=window,
                    edge_kind=SupplyEdgeKind.TOOL_TO_STAGE,
                    from_kind=SupplyNodeKind.TOOL,
                    from_token=spec.tool_role,
                    to_kind=output_kind,
                    to_token=output_token,
                    recipe_id=recipe_id,
                    observed_count=observed,
                    completed_count=completed,
                    group_key=(window, recipe_id),
                    coverage=row_coverage,
                )
            if (
                spec.skill_domain is not None
                and evidence.skill_coverage is not SupplyCoverage.MISSING
            ):
                touch(window, SupplyNodeKind.SKILL, spec.skill_domain, completed=True)
                _add_edge(
                    edges,
                    window=window,
                    edge_kind=SupplyEdgeKind.SKILL_TO_STAGE,
                    from_kind=SupplyNodeKind.SKILL,
                    from_token=spec.skill_domain,
                    to_kind=output_kind,
                    to_token=output_token,
                    recipe_id=recipe_id,
                    observed_count=observed,
                    completed_count=completed,
                    group_key=(window, recipe_id),
                    coverage=row_coverage,
                )
            if spec.action == "harvest":
                if spec.resource_input_names:
                    resource = spec.resource_input_names[0]
                    touch(window, SupplyNodeKind.RESOURCE, resource, completed=True)
                    _add_edge(
                        edges,
                        window=window,
                        edge_kind=SupplyEdgeKind.RESOURCE_TO_ITEM,
                        from_kind=SupplyNodeKind.RESOURCE,
                        from_token=resource,
                        to_kind=output_kind,
                        to_token=output_token,
                        recipe_id=recipe_id,
                        observed_count=observed,
                        completed_count=completed,
                        group_key=(window, recipe_id),
                        coverage=row_coverage,
                    )
            if spec.action in {"craft", "build", "repair", "store"}:
                edge_kind = _terminal_edge_kind(spec)
                creation_by_token = {
                    creation.item_token: creation
                    for creation in evidence.item_creations
                }
                created_elsewhere = 0
                for name in row.item_names:
                    if name == NONE_TOKEN:
                        continue
                    touch(window, SupplyNodeKind.ITEM, name, completed=True)
                    _add_edge(
                        edges,
                        window=window,
                        edge_kind=edge_kind,
                        from_kind=SupplyNodeKind.ITEM,
                        from_token=name,
                        to_kind=output_kind,
                        to_token=output_token,
                        recipe_id=recipe_id,
                        observed_count=observed,
                        completed_count=completed,
                        group_key=(window, recipe_id),
                        coverage=row_coverage,
                    )
                for item_token in row.item_tokens:
                    creation = creation_by_token.get(item_token)
                    if creation is None:
                        continue
                    if (
                        row.location_token != NONE_TOKEN
                        and creation.location_token != NONE_TOKEN
                        and creation.location_token != row.location_token
                    ):
                        created_elsewhere += 1
                        creation_spec = recipes.get(creation.recipe_id)
                        name = (
                            creation.recipe_id
                            if creation_spec is None
                            else creation_spec.output_name
                        )
                        touch(window, SupplyNodeKind.ITEM, name, completed=True)
                        _add_edge(
                            edges,
                            window=window,
                            edge_kind=SupplyEdgeKind.TRANSPORT,
                            from_kind=SupplyNodeKind.ITEM,
                            from_token=name,
                            to_kind=output_kind,
                            to_token=output_token,
                            recipe_id=recipe_id,
                            observed_count=observed,
                            completed_count=completed,
                            group_key=(window, recipe_id),
                            coverage=row_coverage,
                            created_elsewhere_count=1,
                        )
                del created_elsewhere

    node_rows = tuple(
        SupplyDependencyNode(
            node_token=_node(window, kind, token)[0],
            node_kind=kind,
            label_token=token,
            window_index=window,
            observation_count=accumulator.observation_count,
            completed_count=accumulator.completed_count,
            coverage=(
                SupplyCoverage.COMPLETE
                if accumulator.completed_count == accumulator.observation_count
                else SupplyCoverage.PARTIAL
            ),
        )
        for (window, kind, token), accumulator in sorted(
            nodes.items(), key=lambda item: (item[0][0], item[0][1].value, item[0][2])
        )
    )
    if len(node_rows) > policy.max_stages:
        node_rows = node_rows[: policy.max_stages]
        notices.add("stage_truncated")
    edge_rows = tuple(
        SupplyDependencyEdge(
            edge_token=str(entry["token"]),
            window_index=cast(int, entry["window"]),
            from_kind=cast(SupplyNodeKind, entry["from_kind"]),
            from_token=key[2],
            to_kind=cast(SupplyNodeKind, entry["to_kind"]),
            to_token=key[3],
            edge_kind=SupplyEdgeKind(key[1]),
            recipe_id=str(entry["recipe_id"]),
            observed_count=cast(int, entry["observed_count"]),
            completed_count=cast(int, entry["completed_count"]),
            share_milli=(
                cast(int, entry["completed_count"])
                * 1000
                // max(cast(int, entry["observed_count"]), 1)
            ),
            created_elsewhere_count=cast(int, entry["created_elsewhere_count"]),
            coverage=cast(SupplyCoverage, entry["coverage"]),
        )
        for key, entry in sorted(
            edges.items(),
            key=lambda item: (item[0][0], item[0][1], item[0][2], item[0][3]),
        )
    )
    if len(edge_rows) > policy.max_edges:
        edge_rows = edge_rows[: policy.max_edges]
        notices.add("edge_truncated")
    chain_rows, chains_truncated = _build_chain_paths(edge_rows, policy=policy)
    if chains_truncated:
        notices.add("chain_truncated")
    location_rows = tuple(
        SupplyLocationRow(
            location_token=location,
            window_index=window,
            observed_count=len(rows),
            completed_count=sum(1 for row in rows if row.completed),
            coverage=(
                SupplyCoverage.COMPLETE
                if all(row.completed for row in rows)
                else SupplyCoverage.PARTIAL
            ),
        )
        for (window, location), rows in sorted(locations.items())
    )
    if len(location_rows) > policy.max_locations:
        location_rows = location_rows[: policy.max_locations]
        notices.add("location_truncated")
    organization_accumulator: dict[tuple[int, str], list[int]] = {}
    for (window, _recipe_id), rows in groups.items():
        for row in rows:
            if not row.completed:
                continue
            for claim in _claims_for_actor(evidence, row.actor_token):
                entry = organization_accumulator.setdefault(
                    (window, claim.organization_token), [0, 0, 0]
                )
                entry[0] += 1
                entry[1] = max(entry[1], len(claim.actor_tokens))
                entry[2] = max(entry[2], claim.claim_count)
    organization_rows = tuple(
        SupplyOrganizationRow(
            organization_token=organization,
            window_index=window,
            actor_count=values[1],
            claim_count=values[2],
            completed_count=values[0],
            coverage=(
                SupplyCoverage.COMPLETE
                if evidence.organization_coverage is SupplyCoverage.COMPLETE
                else SupplyCoverage.PARTIAL
            ),
        )
        for (window, organization), values in sorted(organization_accumulator.items())
    )
    if len(organization_rows) > policy.max_organizations:
        organization_rows = organization_rows[: policy.max_organizations]
        notices.add("organization_truncated")
    if not node_rows:
        coverage = SupplyCoverage.MISSING
    elif notices or any(node.coverage is SupplyCoverage.PARTIAL for node in node_rows):
        coverage = SupplyCoverage.PARTIAL
    else:
        coverage = SupplyCoverage.COMPLETE
    if notices:
        _LOG.warning("supply_chain_graph_partial notices=%s", ",".join(sorted(notices)))
    _LOG.debug(
        "supply_chain_graph_built nodes=%s edges=%s chains=%s",
        len(node_rows),
        len(edge_rows),
        len(chain_rows),
    )
    return SupplyDependencyGraph(
        nodes=node_rows,
        edges=edge_rows,
        chains=chain_rows,
        locations=location_rows,
        organization_rows=organization_rows,
        coverage=coverage,
        notices=tuple(sorted(notices)),
    )


def _output_node_kind(spec: SupplyRecipeSpec) -> SupplyNodeKind:
    if spec.output_kind == "structure":
        return SupplyNodeKind.STRUCTURE
    if spec.output_kind == "storage":
        return SupplyNodeKind.STORAGE
    if spec.output_kind == "tool":
        return SupplyNodeKind.TOOL
    return SupplyNodeKind.ITEM


def _terminal_edge_kind(spec: SupplyRecipeSpec) -> SupplyEdgeKind:
    if spec.action == "craft":
        return SupplyEdgeKind.ITEM_TO_ITEM
    if spec.output_kind == "storage":
        return SupplyEdgeKind.ITEM_TO_STORAGE
    return SupplyEdgeKind.ITEM_TO_STRUCTURE
