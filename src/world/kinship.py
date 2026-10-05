"""Objective kinship genealogy (parent→child edges only).

Genealogy is authoritative objective fact, not subjective social valence.
Sibling / ancestor / descendant relations are derived queries.
"""

from __future__ import annotations

import hashlib
import logging
from collections import deque
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOGGER: Final[logging.Logger] = logging.getLogger("world.kinship")

__all__ = [
    "KinshipEdge",
    "KinshipGraph",
    "ancestors_of",
    "children_of",
    "descendants_of",
    "establish_edge",
    "parents_of",
    "related",
    "siblings_of",
    "stable_kinship_edge_id",
    "validate_bootstrap_edges",
]

_MAX_QUERY_DEPTH_CEILING: Final[int] = 32
_MAX_PARENTS_DEFAULT: Final[int] = 2


def stable_kinship_edge_id(
    *,
    parent_agent_id: AgentId,
    child_agent_id: AgentId,
    established_tick: int,
) -> str:
    payload = (
        f"{parent_agent_id.value}|{child_agent_id.value}|{established_tick}"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class KinshipEdge:
    """Directed parent→child objective edge."""

    parent_agent_id: AgentId
    child_agent_id: AgentId
    established_tick: int
    edge_id: str

    def __post_init__(self) -> None:
        if type(self.parent_agent_id) is not AgentId:
            raise TypeError("parent_agent_id must be AgentId")
        if type(self.child_agent_id) is not AgentId:
            raise TypeError("child_agent_id must be AgentId")
        if self.parent_agent_id == self.child_agent_id:
            _LOGGER.error(
                "kinship_self_parent code=kinship_self_parent parent=%s",
                self.parent_agent_id.value,
            )
            raise ValueError(
                "parent and child must differ (code=kinship_self_parent)"
            )
        object.__setattr__(
            self,
            "established_tick",
            require_exact_nonneg_int(
                "KinshipEdge.established_tick", self.established_tick
            ),
        )
        object.__setattr__(
            self,
            "edge_id",
            require_stable_id("KinshipEdge.edge_id", self.edge_id),
        )
        expected = stable_kinship_edge_id(
            parent_agent_id=self.parent_agent_id,
            child_agent_id=self.child_agent_id,
            established_tick=self.established_tick,
        )
        if self.edge_id != expected:
            _LOGGER.error(
                "kinship_edge_id_mismatch code=kinship_edge_id_mismatch "
                "expected=%s actual=%s",
                expected,
                self.edge_id,
            )
            raise ValueError(
                "edge_id must match stable kinship hash "
                "(code=kinship_edge_id_mismatch)"
            )


@dataclass(frozen=True, slots=True)
class KinshipGraph:
    """Immutable genealogy graph with bidirectional adjacency indexes."""

    edges: tuple[KinshipEdge, ...]
    max_parents_per_child: int = _MAX_PARENTS_DEFAULT
    children_by_parent: Mapping[AgentId, tuple[AgentId, ...]] = field(
        default_factory=dict
    )
    parents_by_child: Mapping[AgentId, tuple[AgentId, ...]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_parents_per_child",
            require_exact_nonneg_int(
                "KinshipGraph.max_parents_per_child",
                self.max_parents_per_child,
            )
            or _MAX_PARENTS_DEFAULT,
        )
        if self.max_parents_per_child < 1:
            raise ValueError("max_parents_per_child must be positive")
        if isinstance(self.edges, (str, bytes)) or not isinstance(
            self.edges, Sequence
        ):
            raise TypeError("edges must be a sequence")
        edge_list = tuple(self.edges)
        for edge in edge_list:
            if type(edge) is not KinshipEdge:
                raise TypeError("edges entries must be KinshipEdge")
        children: dict[AgentId, list[AgentId]] = {}
        parents: dict[AgentId, list[AgentId]] = {}
        seen_pairs: set[tuple[str, str]] = set()
        for edge in edge_list:
            pair = (edge.parent_agent_id.value, edge.child_agent_id.value)
            if pair in seen_pairs:
                _LOGGER.error(
                    "kinship_duplicate_edge code=kinship_duplicate_edge "
                    "parent=%s child=%s",
                    pair[0],
                    pair[1],
                )
                raise ValueError(
                    "duplicate parent→child edge (code=kinship_duplicate_edge)"
                )
            seen_pairs.add(pair)
            children.setdefault(edge.parent_agent_id, []).append(
                edge.child_agent_id
            )
            parents.setdefault(edge.child_agent_id, []).append(
                edge.parent_agent_id
            )
        for child_id, parent_list in parents.items():
            if len(parent_list) > self.max_parents_per_child:
                _LOGGER.error(
                    "kinship_too_many_parents code=kinship_too_many_parents "
                    "child=%s count=%s",
                    child_id.value,
                    len(parent_list),
                )
                raise ValueError(
                    "too many parents for child "
                    "(code=kinship_too_many_parents)"
                )
        object.__setattr__(self, "edges", edge_list)
        object.__setattr__(
            self,
            "children_by_parent",
            {
                agent_id: tuple(sorted(child_ids, key=lambda c: c.value))
                for agent_id, child_ids in children.items()
            },
        )
        object.__setattr__(
            self,
            "parents_by_child",
            {
                agent_id: tuple(sorted(parent_ids, key=lambda p: p.value))
                for agent_id, parent_ids in parents.items()
            },
        )
        if edge_list:
            _validate_acyclic(children)

    @classmethod
    def empty(cls, *, max_parents_per_child: int = _MAX_PARENTS_DEFAULT) -> KinshipGraph:
        return cls(
            edges=(),
            max_parents_per_child=max_parents_per_child,
        )

    def with_edge(
        self,
        edge: KinshipEdge,
        *,
        known_agent_ids: Collection[AgentId] | None = None,
    ) -> KinshipGraph:
        """Return a new graph containing ``edge`` (immutable update)."""
        if known_agent_ids is not None:
            known = {agent_id.value for agent_id in known_agent_ids}
            if edge.parent_agent_id.value not in known:
                _LOGGER.error(
                    "kinship_unknown_agent code=kinship_unknown_agent "
                    "role=parent agent=%s",
                    edge.parent_agent_id.value,
                )
                raise ValueError(
                    "unknown parent agent id (code=kinship_unknown_agent)"
                )
            if edge.child_agent_id.value not in known:
                _LOGGER.error(
                    "kinship_unknown_agent code=kinship_unknown_agent "
                    "role=child agent=%s",
                    edge.child_agent_id.value,
                )
                raise ValueError(
                    "unknown child agent id (code=kinship_unknown_agent)"
                )
        return KinshipGraph(
            edges=(*self.edges, edge),
            max_parents_per_child=self.max_parents_per_child,
        )


def _validate_acyclic(children: Mapping[AgentId, list[AgentId]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()
    nodes: set[AgentId] = set()
    for parent, child_list in children.items():
        nodes.add(parent)
        for child in child_list:
            nodes.add(child)

    def visit(node: AgentId) -> None:
        key = node.value
        if key in visited:
            return
        if key in visiting:
            _LOGGER.error(
                "kinship_cycle_rejected code=kinship_cycle_rejected agent=%s",
                key,
            )
            raise ValueError("kinship cycle detected (code=kinship_cycle_rejected)")
        visiting.add(key)
        for child in children.get(node, ()):
            visit(child)
        visiting.remove(key)
        visited.add(key)

    for node in sorted(nodes, key=lambda agent: agent.value):
        visit(node)


def _would_create_cycle(
    graph: KinshipGraph,
    edge: KinshipEdge,
) -> bool:
    """True if adding parent→child would make child an ancestor of parent."""
    return _reachable(
        graph,
        start=edge.child_agent_id,
        target=edge.parent_agent_id,
    )


def _reachable(graph: KinshipGraph, *, start: AgentId, target: AgentId) -> bool:
    if start == target:
        return True
    queue: deque[tuple[AgentId, int]] = deque([(start, 0)])
    visited: set[str] = set()
    while queue:
        node, _depth = queue.popleft()
        key = node.value
        if key in visited:
            continue
        visited.add(key)
        for parent in graph.parents_by_child.get(node, ()):
            if parent == target:
                return True
            queue.append((parent, _depth + 1))
        for child in graph.children_by_parent.get(node, ()):
            if child == target:
                return True
            queue.append((child, _depth + 1))
    return False


def establish_edge(
    graph: KinshipGraph,
    *,
    parent_agent_id: AgentId,
    child_agent_id: AgentId,
    established_tick: int,
    max_parents_per_child: int,
    known_agent_ids: Collection[AgentId],
) -> tuple[KinshipGraph, KinshipEdge]:
    """Validate and return graph with a new edge."""
    edge = KinshipEdge(
        parent_agent_id=parent_agent_id,
        child_agent_id=child_agent_id,
        established_tick=established_tick,
        edge_id=stable_kinship_edge_id(
            parent_agent_id=parent_agent_id,
            child_agent_id=child_agent_id,
            established_tick=established_tick,
        ),
    )
    pair = (parent_agent_id.value, child_agent_id.value)
    for existing in graph.edges:
        if (
            existing.parent_agent_id.value,
            existing.child_agent_id.value,
        ) == pair:
            _LOGGER.error(
                "kinship_duplicate_edge code=kinship_duplicate_edge "
                "parent=%s child=%s",
                pair[0],
                pair[1],
            )
            raise ValueError(
                "duplicate parent→child edge (code=kinship_duplicate_edge)"
            )
    if _would_create_cycle(graph, edge):
        _LOGGER.error(
            "kinship_cycle_rejected code=kinship_cycle_rejected "
            "parent=%s child=%s",
            parent_agent_id.value,
            child_agent_id.value,
        )
        raise ValueError("kinship cycle detected (code=kinship_cycle_rejected)")
    parent_count = len(graph.parents_by_child.get(child_agent_id, ()))
    if parent_count >= max_parents_per_child:
        _LOGGER.error(
            "kinship_too_many_parents code=kinship_too_many_parents "
            "child=%s count=%s max=%s",
            child_agent_id.value,
            parent_count + 1,
            max_parents_per_child,
        )
        raise ValueError("too many parents for child (code=kinship_too_many_parents)")
    if graph.max_parents_per_child != max_parents_per_child:
        graph = KinshipGraph(
            edges=graph.edges,
            max_parents_per_child=max_parents_per_child,
        )
    next_graph = graph.with_edge(edge, known_agent_ids=known_agent_ids)
    _LOGGER.debug(
        "kinship_edge_established parent=%s child=%s tick=%s edge_id=%s",
        parent_agent_id.value,
        child_agent_id.value,
        established_tick,
        edge.edge_id,
    )
    return next_graph, edge


def parents_of(graph: KinshipGraph, agent_id: AgentId) -> tuple[AgentId, ...]:
    result = graph.parents_by_child.get(agent_id, ())
    _LOGGER.debug(
        "kinship_query agent_id=%s relation=parents depth=0 result_count=%s",
        agent_id.value,
        len(result),
    )
    return result


def children_of(graph: KinshipGraph, agent_id: AgentId) -> tuple[AgentId, ...]:
    result = graph.children_by_parent.get(agent_id, ())
    _LOGGER.debug(
        "kinship_query agent_id=%s relation=children depth=0 result_count=%s",
        agent_id.value,
        len(result),
    )
    return result


def siblings_of(graph: KinshipGraph, agent_id: AgentId) -> tuple[AgentId, ...]:
    siblings: set[AgentId] = set()
    for parent in parents_of(graph, agent_id):
        for child in children_of(graph, parent):
            if child != agent_id:
                siblings.add(child)
    result = tuple(sorted(siblings, key=lambda agent: agent.value))
    _LOGGER.debug(
        "kinship_query agent_id=%s relation=siblings depth=1 result_count=%s",
        agent_id.value,
        len(result),
    )
    return result


def _normalize_depth(max_depth: int, *, config_cap: int) -> int:
    depth = require_exact_nonneg_int("max_depth", max_depth)
    cap = require_exact_nonneg_int("config_cap", config_cap)
    if cap < 1 or cap > _MAX_QUERY_DEPTH_CEILING:
        raise ValueError("config max_query_depth out of range")
    if depth < 1:
        raise ValueError("max_depth must be positive")
    return min(depth, cap)


def ancestors_of(
    graph: KinshipGraph,
    agent_id: AgentId,
    *,
    max_depth: int,
    config_max_depth: int,
) -> tuple[AgentId, ...]:
    limit = _normalize_depth(max_depth, config_cap=config_max_depth)
    seen: dict[str, int] = {}
    queue: deque[tuple[AgentId, int]] = deque([(agent_id, 0)])
    ordered: list[AgentId] = []
    while queue:
        node, depth = queue.popleft()
        if depth >= limit:
            continue
        for parent in graph.parents_by_child.get(node, ()):
            key = parent.value
            if key in seen:
                continue
            seen[key] = depth + 1
            ordered.append(parent)
            queue.append((parent, depth + 1))
    ordered.sort(key=lambda agent: (seen[agent.value], agent.value))
    result = tuple(ordered)
    _LOGGER.debug(
        "kinship_query agent_id=%s relation=ancestors depth=%s result_count=%s",
        agent_id.value,
        limit,
        len(result),
    )
    return result


def descendants_of(
    graph: KinshipGraph,
    agent_id: AgentId,
    *,
    max_depth: int,
    config_max_depth: int,
) -> tuple[AgentId, ...]:
    limit = _normalize_depth(max_depth, config_cap=config_max_depth)
    seen: dict[str, int] = {}
    queue: deque[tuple[AgentId, int]] = deque([(agent_id, 0)])
    ordered: list[AgentId] = []
    while queue:
        node, depth = queue.popleft()
        if depth >= limit:
            continue
        for child in graph.children_by_parent.get(node, ()):
            key = child.value
            if key in seen:
                continue
            seen[key] = depth + 1
            ordered.append(child)
            queue.append((child, depth + 1))
    ordered.sort(key=lambda agent: (seen[agent.value], agent.value))
    result = tuple(ordered)
    _LOGGER.debug(
        "kinship_query agent_id=%s relation=descendants depth=%s result_count=%s",
        agent_id.value,
        limit,
        len(result),
    )
    return result


def related(
    graph: KinshipGraph,
    agent_a: AgentId,
    agent_b: AgentId,
    *,
    max_depth: int,
    config_max_depth: int,
) -> bool:
    if agent_a == agent_b:
        return True
    limit = _normalize_depth(max_depth, config_cap=config_max_depth)
    ancestors_a = {agent_a.value, *(
        item.value for item in ancestors_of(
            graph, agent_a, max_depth=limit, config_max_depth=limit
        )
    )}
    if agent_b.value in ancestors_a:
        return True
    ancestors_b = {agent_b.value, *(
        item.value for item in ancestors_of(
            graph, agent_b, max_depth=limit, config_max_depth=limit
        )
    )}
    return bool(ancestors_a & ancestors_b)


def validate_bootstrap_edges(
    edges: Sequence[KinshipEdge],
    *,
    registered_agent_ids: Collection[AgentId],
    max_parents_per_child: int,
) -> KinshipGraph:
    """Build graph from bootstrap edges in order."""
    known = tuple(registered_agent_ids)
    graph = KinshipGraph.empty(max_parents_per_child=max_parents_per_child)
    for edge in edges:
        graph, _ = establish_edge(
            graph,
            parent_agent_id=edge.parent_agent_id,
            child_agent_id=edge.child_agent_id,
            established_tick=edge.established_tick,
            max_parents_per_child=max_parents_per_child,
            known_agent_ids=known,
        )
    _LOGGER.info(
        "kinship_bootstrap_validated edge_count=%s agent_count=%s",
        len(graph.edges),
        len(known),
    )
    return graph
