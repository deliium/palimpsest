"""Analysis-only knowledge / skill genealogy DAG and researcher queries.

Never imported by cognition. Builds detached graphs over duck-typed practical-
knowledge audit rows. Cross-owner ``transmitted_from`` edges are analysis joins
only — live ledgers never store peer ``entry_id`` parents.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.historical_memory import _death_ticks_from_events, is_agent_living_at
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    lineage_edge_key,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
)
from simulation.lineage_ports import LineageSourceProjection
from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.knowledge_genealogy")

KNOWLEDGE_GENEALOGY_QUERY_DEPTH_CEILING: Final[int] = 64
_CENSORING_POLICY: Final[str] = "analysis_only_never_cognition"

__all__ = [
    "KNOWLEDGE_GENEALOGY_QUERY_DEPTH_CEILING",
    "KnowledgeGenealogyEdge",
    "KnowledgeGenealogyEdgeKind",
    "KnowledgeGenealogyGraph",
    "KnowledgeGenealogyNode",
    "KnowledgeGenealogyNodeKind",
    "KnowledgeGenealogyQueryId",
    "KnowledgeGenealogyQueryResult",
    "build_knowledge_genealogy_graph",
    "build_qualified_knowledge_lineage",
    "death_ticks_for_knowledge_genealogy",
    "query_independent_emergence_count",
    "query_oldest_surviving_lineage_origin",
    "query_who_currently_knows",
    "query_who_taught",
    "run_knowledge_genealogy_query",
]


class KnowledgeGenealogyNodeKind(StrEnum):
    HOLDER = "holder"
    KNOWLEDGE_ENTRY = "knowledge_entry"
    INDEPENDENT_ROOT = "independent_root"


class KnowledgeGenealogyEdgeKind(StrEnum):
    HOLDS = "holds"
    TRANSMITTED_FROM = "transmitted_from"
    COMBINED_FROM = "combined_from"
    MUTATED_FROM = "mutated_from"
    UNRESOLVED_TRANSMISSION = "unresolved_transmission"


class KnowledgeGenealogyQueryId(StrEnum):
    WHO_CURRENTLY_KNOWS = "who_currently_knows"
    WHO_TAUGHT = "who_taught"
    OLDEST_SURVIVING_LINEAGE_ORIGIN = "oldest_surviving_lineage_origin"
    INDEPENDENT_EMERGENCE_COUNT = "independent_emergence_count"


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogyNode:
    """One analysis node (holder, knowledge entry, or independent root)."""

    node_id: str
    kind: KnowledgeGenealogyNodeKind
    ref_token: str
    content_key: str | None = None
    agent_id: str | None = None
    acquired_tick: int | None = None
    hop_index: int | None = None
    active: bool | None = None
    origin: str | None = None
    kind_token: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_stable_id("node_id", self.node_id))
        if type(self.kind) is not KnowledgeGenealogyNodeKind:
            raise TypeError("kind must be KnowledgeGenealogyNodeKind")
        object.__setattr__(
            self, "ref_token", require_stable_id("ref_token", self.ref_token)
        )


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogyEdge:
    """One analysis edge between genealogy nodes."""

    edge_id: str
    kind: KnowledgeGenealogyEdgeKind
    source_node_id: str
    target_node_id: str
    depth: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_stable_id("edge_id", self.edge_id))
        if type(self.kind) is not KnowledgeGenealogyEdgeKind:
            raise TypeError("kind must be KnowledgeGenealogyEdgeKind")
        object.__setattr__(
            self,
            "source_node_id",
            require_stable_id("source_node_id", self.source_node_id),
        )
        object.__setattr__(
            self,
            "target_node_id",
            require_stable_id("target_node_id", self.target_node_id),
        )
        object.__setattr__(self, "depth", require_exact_nonneg_int("depth", self.depth))


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogyGraph:
    """Frozen analysis DAG over detached practical-knowledge audit rows."""

    nodes: tuple[KnowledgeGenealogyNode, ...]
    edges: tuple[KnowledgeGenealogyEdge, ...]
    as_of_tick: int
    unresolved_transmission_count: int
    death_ticks: Mapping[str, int]
    generation_index_by_agent: Mapping[str, int]
    censoring_policy: str = _CENSORING_POLICY

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(
            self, "as_of_tick", require_exact_nonneg_int("as_of_tick", self.as_of_tick)
        )
        object.__setattr__(
            self,
            "unresolved_transmission_count",
            require_exact_nonneg_int(
                "unresolved_transmission_count", self.unresolved_transmission_count
            ),
        )
        object.__setattr__(self, "death_ticks", dict(self.death_ticks))
        object.__setattr__(
            self, "generation_index_by_agent", dict(self.generation_index_by_agent)
        )
        object.__setattr__(
            self,
            "censoring_policy",
            require_stable_id("censoring_policy", self.censoring_policy),
        )


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogyQueryResult:
    """Deterministic researcher query result (ids / counts only)."""

    query_id: KnowledgeGenealogyQueryId
    as_of_tick: int
    content_key: str
    items: tuple[tuple[int, str], ...]
    count: int
    emerged_independently_twice: bool | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.query_id) is not KnowledgeGenealogyQueryId:
            raise TypeError("query_id must be KnowledgeGenealogyQueryId")
        object.__setattr__(
            self, "as_of_tick", require_exact_nonneg_int("as_of_tick", self.as_of_tick)
        )
        object.__setattr__(
            self, "content_key", require_stable_id("content_key", self.content_key)
        )
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "count", require_exact_nonneg_int("count", self.count))
        object.__setattr__(self, "notes", tuple(self.notes))


@dataclass(frozen=True, slots=True)
class _AuditRow:
    owner_id: str
    entry_id: str
    kind: str
    content_key: str
    origin: str
    parent_entry_ids: tuple[str, ...]
    lineage_root_id: str
    hop_index: int
    mutated: bool
    acquired_tick: int
    tick: int
    active: bool
    source_agent_id: str | None
    teacher_agent_id: str | None
    capability_anchor: str | None


def death_ticks_for_knowledge_genealogy(
    *,
    death_ticks: Mapping[str, int] | None = None,
    died_events: Sequence[object] | None = None,
) -> dict[str, int]:
    """Derive death ticks from explicit map and/or Died events (genealogy-only)."""
    return _death_ticks_from_events(died_events, death_ticks)


def _token(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if type(value) is str:
        return value
    nested = getattr(value, "value", None)
    if type(nested) is str:
        return nested
    _LOG.debug(
        "knowledge_genealogy_row_skipped field=%s reason_code=malformed_token",
        field,
    )
    return None


def _bool(value: object, *, default: bool = False) -> bool:
    if type(value) is bool:
        return value
    return default


def _int(value: object, *, field: str, default: int = 0) -> int | None:
    if isinstance(value, bool) or type(value) is not int:
        _LOG.debug(
            "knowledge_genealogy_row_skipped field=%s reason_code=malformed_int",
            field,
        )
        return None
    if value < 0:
        return None
    return value


def _normalize_audits(rows: Sequence[object]) -> tuple[_AuditRow, ...]:
    """Last audit row per ``entry_id`` wins for current state."""
    by_entry: dict[str, _AuditRow] = {}
    order: list[str] = []
    for raw in rows:
        owner = _token(getattr(raw, "owner_id", None), field="owner_id")
        entry_id = _token(getattr(raw, "entry_id", None), field="entry_id")
        kind = _token(getattr(raw, "kind", None), field="kind")
        content_key = _token(getattr(raw, "content_key", None), field="content_key")
        origin = _token(getattr(raw, "origin", None), field="origin")
        root = _token(getattr(raw, "lineage_root_id", None), field="lineage_root_id")
        if None in (owner, entry_id, kind, content_key, origin, root):
            continue
        assert owner and entry_id and kind and content_key and origin and root
        hop = _int(getattr(raw, "hop_index", 0), field="hop_index")
        acquired = _int(getattr(raw, "acquired_tick", 0), field="acquired_tick")
        tick = _int(getattr(raw, "tick", acquired or 0), field="tick")
        if hop is None or acquired is None or tick is None:
            continue
        parents_raw = getattr(raw, "parent_entry_ids", ()) or ()
        if isinstance(parents_raw, (str, bytes)):
            continue
        parents: list[str] = []
        ok = True
        for item in parents_raw:
            token = _token(item, field="parent_entry_ids")
            if token is None:
                ok = False
                break
            parents.append(token)
        if not ok:
            continue
        row = _AuditRow(
            owner_id=owner,
            entry_id=entry_id,
            kind=kind,
            content_key=content_key,
            origin=origin,
            parent_entry_ids=tuple(parents),
            lineage_root_id=root,
            hop_index=hop,
            mutated=_bool(getattr(raw, "mutated", False)),
            acquired_tick=acquired,
            tick=tick,
            active=_bool(getattr(raw, "active", True), default=True),
            source_agent_id=_token(
                getattr(raw, "source_agent_id", None), field="source_agent_id"
            ),
            teacher_agent_id=_token(
                getattr(raw, "teacher_agent_id", None), field="teacher_agent_id"
            ),
            capability_anchor=_token(
                getattr(raw, "capability_anchor", None), field="capability_anchor"
            ),
        )
        if entry_id not in by_entry:
            order.append(entry_id)
        by_entry[entry_id] = row
    return tuple(by_entry[entry_id] for entry_id in order)


def _clamp_depth(max_query_depth: int) -> int:
    depth = require_exact_nonneg_int("max_query_depth", max_query_depth)
    if depth < 1:
        depth = 1
    return min(depth, KNOWLEDGE_GENEALOGY_QUERY_DEPTH_CEILING)


def _holder_node_id(agent_id: str) -> str:
    return f"holder:{agent_id}"


def _entry_node_id(entry_id: str) -> str:
    return f"entry:{entry_id}"


def _root_node_id(root_id: str) -> str:
    return f"root:{root_id}"


def _find_peer_source_entry(
    *,
    source_agent_id: str,
    content_key: str,
    child_tick: int,
    by_owner: Mapping[str, tuple[_AuditRow, ...]],
) -> _AuditRow | None:
    candidates = [
        row
        for row in by_owner.get(source_agent_id, ())
        if row.content_key == content_key
        and row.active
        and row.acquired_tick <= child_tick
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda row: (-row.acquired_tick, row.entry_id))
    return candidates[0]


def build_knowledge_genealogy_graph(
    audit_rows: Sequence[object],
    *,
    as_of_tick: int,
    death_ticks: Mapping[str, int] | None = None,
    died_events: Sequence[object] | None = None,
    generation_index_by_agent: Mapping[str, int] | None = None,
    max_query_depth: int = 32,
) -> KnowledgeGenealogyGraph:
    """Build a frozen analysis DAG from detached practical-knowledge audits."""
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    depth_cap = _clamp_depth(max_query_depth)
    deaths = death_ticks_for_knowledge_genealogy(
        death_ticks=death_ticks, died_events=died_events
    )
    gens = {
        require_stable_id("generation_index_by_agent", key): require_exact_nonneg_int(
            "generation_index", value
        )
        for key, value in dict(generation_index_by_agent or {}).items()
    }
    audits = _normalize_audits(audit_rows)
    by_owner: dict[str, list[_AuditRow]] = {}
    for row in audits:
        by_owner.setdefault(row.owner_id, []).append(row)
    owner_tuple = {key: tuple(value) for key, value in by_owner.items()}

    nodes: dict[str, KnowledgeGenealogyNode] = {}
    edges: list[KnowledgeGenealogyEdge] = []
    unresolved = 0

    def add_node(node: KnowledgeGenealogyNode) -> None:
        nodes.setdefault(node.node_id, node)

    for row in audits:
        holder_id = _holder_node_id(row.owner_id)
        entry_id = _entry_node_id(row.entry_id)
        add_node(
            KnowledgeGenealogyNode(
                node_id=holder_id,
                kind=KnowledgeGenealogyNodeKind.HOLDER,
                ref_token=row.owner_id,
                agent_id=row.owner_id,
            )
        )
        add_node(
            KnowledgeGenealogyNode(
                node_id=entry_id,
                kind=KnowledgeGenealogyNodeKind.KNOWLEDGE_ENTRY,
                ref_token=row.entry_id,
                content_key=row.content_key,
                agent_id=row.owner_id,
                acquired_tick=row.acquired_tick,
                hop_index=row.hop_index,
                active=row.active,
                origin=row.origin,
                kind_token=row.kind,
            )
        )
        if row.origin == "independent_discovery":
            root_id = _root_node_id(row.lineage_root_id)
            add_node(
                KnowledgeGenealogyNode(
                    node_id=root_id,
                    kind=KnowledgeGenealogyNodeKind.INDEPENDENT_ROOT,
                    ref_token=row.lineage_root_id,
                    content_key=row.content_key,
                    agent_id=row.owner_id,
                    acquired_tick=row.acquired_tick,
                    hop_index=0,
                    active=row.active,
                    origin=row.origin,
                    kind_token=row.kind,
                )
            )
            edges.append(
                KnowledgeGenealogyEdge(
                    edge_id=f"root-entry:{row.lineage_root_id}:{row.entry_id}",
                    kind=KnowledgeGenealogyEdgeKind.TRANSMITTED_FROM,
                    source_node_id=root_id,
                    target_node_id=entry_id,
                    depth=0,
                )
            )
        if row.active:
            edges.append(
                KnowledgeGenealogyEdge(
                    edge_id=f"holds:{row.owner_id}:{row.entry_id}",
                    kind=KnowledgeGenealogyEdgeKind.HOLDS,
                    source_node_id=holder_id,
                    target_node_id=entry_id,
                    depth=0,
                )
            )
        # Owner-local parent edges.
        known_entry_ids = {r.entry_id for r in audits}
        for parent_id in row.parent_entry_ids:
            parent_node = _entry_node_id(parent_id)
            if parent_node not in nodes and parent_id not in known_entry_ids:
                # Missing parent still gets a stub node for DAG continuity.
                add_node(
                    KnowledgeGenealogyNode(
                        node_id=parent_node,
                        kind=KnowledgeGenealogyNodeKind.KNOWLEDGE_ENTRY,
                        ref_token=parent_id,
                        agent_id=row.owner_id,
                        active=False,
                    )
                )
            edge_kind = (
                KnowledgeGenealogyEdgeKind.COMBINED_FROM
                if row.origin == "combination" or len(row.parent_entry_ids) >= 2
                else KnowledgeGenealogyEdgeKind.MUTATED_FROM
                if row.mutated or len(row.parent_entry_ids) == 1
                else KnowledgeGenealogyEdgeKind.TRANSMITTED_FROM
            )
            depth = min(row.hop_index, depth_cap)
            edges.append(
                KnowledgeGenealogyEdge(
                    edge_id=f"{edge_kind.value}:{parent_id}:{row.entry_id}",
                    kind=edge_kind,
                    source_node_id=parent_node,
                    target_node_id=entry_id,
                    depth=depth,
                )
            )
        # Cross-owner analysis join (never peer entry_id in live ledgers).
        peer_source = row.source_agent_id or row.teacher_agent_id
        if (
            peer_source
            and not row.parent_entry_ids
            and row.origin != "independent_discovery"
        ):
            peer = _find_peer_source_entry(
                source_agent_id=peer_source,
                content_key=row.content_key,
                child_tick=row.acquired_tick,
                by_owner=owner_tuple,
            )
            if peer is None:
                unresolved += 1
                edges.append(
                    KnowledgeGenealogyEdge(
                        edge_id=f"unresolved:{peer_source}:{row.entry_id}",
                        kind=KnowledgeGenealogyEdgeKind.UNRESOLVED_TRANSMISSION,
                        source_node_id=_holder_node_id(peer_source),
                        target_node_id=entry_id,
                        depth=min(1, depth_cap),
                    )
                )
                add_node(
                    KnowledgeGenealogyNode(
                        node_id=_holder_node_id(peer_source),
                        kind=KnowledgeGenealogyNodeKind.HOLDER,
                        ref_token=peer_source,
                        agent_id=peer_source,
                    )
                )
            else:
                edges.append(
                    KnowledgeGenealogyEdge(
                        edge_id=f"tx:{peer.entry_id}:{row.entry_id}",
                        kind=KnowledgeGenealogyEdgeKind.TRANSMITTED_FROM,
                        source_node_id=_entry_node_id(peer.entry_id),
                        target_node_id=entry_id,
                        depth=min(max(row.hop_index, 1), depth_cap),
                    )
                )

    sorted_nodes = tuple(
        sorted(nodes.values(), key=lambda node: (node.kind.value, node.node_id))
    )
    sorted_edges = tuple(
        sorted(edges, key=lambda edge: (edge.kind.value, edge.edge_id))
    )
    graph = KnowledgeGenealogyGraph(
        nodes=sorted_nodes,
        edges=sorted_edges,
        as_of_tick=tick,
        unresolved_transmission_count=unresolved,
        death_ticks=deaths,
        generation_index_by_agent=gens,
    )
    _LOG.debug(
        "knowledge_genealogy_graph_built node_count=%s edge_count=%s "
        "unresolved=%s as_of_tick=%s censoring_policy=%s",
        len(sorted_nodes),
        len(sorted_edges),
        unresolved,
        tick,
        _CENSORING_POLICY,
    )
    return graph


def _active_entries_for_key(
    graph: KnowledgeGenealogyGraph,
    *,
    content_key: str,
    kind: str | None,
) -> tuple[KnowledgeGenealogyNode, ...]:
    rows = []
    for node in graph.nodes:
        if node.kind is not KnowledgeGenealogyNodeKind.KNOWLEDGE_ENTRY:
            continue
        if node.content_key != content_key:
            continue
        if kind is not None and node.kind_token != kind:
            continue
        if node.active is not True:
            continue
        rows.append(node)
    return tuple(rows)


def query_who_currently_knows(
    graph: KnowledgeGenealogyGraph,
    *,
    content_key: str,
    kind: str | None = None,
    max_query_depth: int = 32,
) -> KnowledgeGenealogyQueryResult:
    """Living holders with an active entry for technique ``content_key``."""
    key = require_stable_id("content_key", content_key)
    _ = _clamp_depth(max_query_depth)
    items: list[tuple[int, str]] = []
    for node in _active_entries_for_key(graph, content_key=key, kind=kind):
        agent = node.agent_id
        if agent is None:
            continue
        if not is_agent_living_at(agent, graph.as_of_tick, graph.death_ticks):
            continue
        depth = (
            0
            if node.hop_index is None
            else min(node.hop_index, _clamp_depth(max_query_depth))
        )
        items.append((depth, agent))
    items = sorted(set(items), key=lambda row: (row[0], row[1]))
    result = KnowledgeGenealogyQueryResult(
        query_id=KnowledgeGenealogyQueryId.WHO_CURRENTLY_KNOWS,
        as_of_tick=graph.as_of_tick,
        content_key=key,
        items=tuple(items),
        count=len(items),
    )
    _LOG.debug(
        "knowledge_genealogy_query query_id=%s result_count=%s censoring_policy=%s",
        result.query_id.value,
        result.count,
        graph.censoring_policy,
    )
    return result


def query_who_taught(
    graph: KnowledgeGenealogyGraph,
    *,
    content_key: str,
    holder_agent_id: str | None = None,
    include_dead_holders: bool = True,
    kind: str | None = None,
    max_query_depth: int = 32,
) -> KnowledgeGenealogyQueryResult:
    """Distinct teacher/source agent ids for holder+technique edges."""
    key = require_stable_id("content_key", content_key)
    _ = _clamp_depth(max_query_depth)
    entry_by_id = {
        node.ref_token: node
        for node in graph.nodes
        if node.kind is KnowledgeGenealogyNodeKind.KNOWLEDGE_ENTRY
    }
    teachers: set[tuple[int, str]] = set()
    for edge in graph.edges:
        if edge.kind not in {
            KnowledgeGenealogyEdgeKind.TRANSMITTED_FROM,
            KnowledgeGenealogyEdgeKind.UNRESOLVED_TRANSMISSION,
        }:
            continue
        target = next(
            (n for n in graph.nodes if n.node_id == edge.target_node_id),
            None,
        )
        if target is None or target.content_key != key:
            continue
        if kind is not None and target.kind_token != kind:
            continue
        if holder_agent_id is not None and target.agent_id != holder_agent_id:
            continue
        if target.agent_id is not None and not include_dead_holders:
            if not is_agent_living_at(
                target.agent_id, graph.as_of_tick, graph.death_ticks
            ):
                continue
        source = next(
            (n for n in graph.nodes if n.node_id == edge.source_node_id),
            None,
        )
        if source is None:
            continue
        teacher = source.agent_id or (
            source.ref_token
            if source.kind is KnowledgeGenealogyNodeKind.HOLDER
            else None
        )
        if (
            teacher is None
            and source.kind is KnowledgeGenealogyNodeKind.KNOWLEDGE_ENTRY
        ):
            teacher = source.agent_id
        if teacher is None:
            # unresolved source is holder node ref
            if source.kind is KnowledgeGenealogyNodeKind.HOLDER:
                teacher = source.ref_token
        if teacher is None:
            continue
        if source.kind is KnowledgeGenealogyNodeKind.INDEPENDENT_ROOT:
            continue
        teachers.add((edge.depth, teacher))
    # Also scan entry origins for teacher/source without graph edge resolution.
    for node in entry_by_id.values():
        if node.content_key != key or node.active is not True:
            continue
        if kind is not None and node.kind_token != kind:
            continue
        if holder_agent_id is not None and node.agent_id != holder_agent_id:
            continue
        if node.agent_id is not None and not include_dead_holders:
            if not is_agent_living_at(
                node.agent_id, graph.as_of_tick, graph.death_ticks
            ):
                continue
    items = sorted(teachers, key=lambda row: (row[0], row[1]))
    result = KnowledgeGenealogyQueryResult(
        query_id=KnowledgeGenealogyQueryId.WHO_TAUGHT,
        as_of_tick=graph.as_of_tick,
        content_key=key,
        items=tuple(items),
        count=len(items),
    )
    _LOG.debug(
        "knowledge_genealogy_query query_id=%s result_count=%s censoring_policy=%s",
        result.query_id.value,
        result.count,
        graph.censoring_policy,
    )
    return result


def query_oldest_surviving_lineage_origin(
    graph: KnowledgeGenealogyGraph,
    *,
    content_key: str,
    kind: str | None = None,
    max_query_depth: int = 32,
) -> KnowledgeGenealogyQueryResult:
    """Oldest independent root still reachable from living active holders."""
    key = require_stable_id("content_key", content_key)
    _ = _clamp_depth(max_query_depth)
    living_holder_entries = {
        node.node_id
        for node in _active_entries_for_key(graph, content_key=key, kind=kind)
        if node.agent_id is not None
        and is_agent_living_at(node.agent_id, graph.as_of_tick, graph.death_ticks)
    }
    # Reachability: walk inbound edges from living entries up to roots.
    inbound: dict[str, list[str]] = {}
    for edge in graph.edges:
        inbound.setdefault(edge.target_node_id, []).append(edge.source_node_id)
    reachable_roots: list[tuple[int, str]] = []
    for start in living_holder_entries:
        stack = [start]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            node = next((n for n in graph.nodes if n.node_id == current), None)
            if node is None:
                continue
            if node.kind is KnowledgeGenealogyNodeKind.INDEPENDENT_ROOT:
                acquired = 0 if node.acquired_tick is None else node.acquired_tick
                reachable_roots.append((acquired, node.ref_token))
            for parent in inbound.get(current, ()):
                stack.append(parent)
    if not reachable_roots:
        result = KnowledgeGenealogyQueryResult(
            query_id=KnowledgeGenealogyQueryId.OLDEST_SURVIVING_LINEAGE_ORIGIN,
            as_of_tick=graph.as_of_tick,
            content_key=key,
            items=(),
            count=0,
            notes=("no_surviving_root",),
        )
    else:
        oldest = min(reachable_roots, key=lambda row: (row[0], row[1]))
        result = KnowledgeGenealogyQueryResult(
            query_id=KnowledgeGenealogyQueryId.OLDEST_SURVIVING_LINEAGE_ORIGIN,
            as_of_tick=graph.as_of_tick,
            content_key=key,
            items=(oldest,),
            count=1,
        )
    _LOG.debug(
        "knowledge_genealogy_query query_id=%s result_count=%s censoring_policy=%s",
        result.query_id.value,
        result.count,
        graph.censoring_policy,
    )
    return result


def query_independent_emergence_count(
    graph: KnowledgeGenealogyGraph,
    *,
    content_key: str,
    kind: str | None = None,
    independent_root_match: str = "content_key",
    max_query_depth: int = 32,
) -> KnowledgeGenealogyQueryResult:
    """Count distinct independent_discovery roots for a technique key."""
    key = require_stable_id("content_key", content_key)
    _ = _clamp_depth(max_query_depth)
    match = require_stable_id("independent_root_match", independent_root_match)
    roots: set[str] = set()
    for node in graph.nodes:
        if node.kind is not KnowledgeGenealogyNodeKind.INDEPENDENT_ROOT:
            continue
        if node.content_key != key:
            continue
        if match == "content_key_and_kind" and kind is not None:
            if node.kind_token != kind:
                continue
        elif match == "content_key_and_kind" and kind is None:
            # When kind filter absent, still distinct by root id only.
            pass
        roots.add(node.ref_token)
    # Fallback: independent_discovery entry lineage roots if root nodes absent.
    if not roots:
        for node in graph.nodes:
            if node.kind is not KnowledgeGenealogyNodeKind.KNOWLEDGE_ENTRY:
                continue
            if node.origin != "independent_discovery":
                continue
            if node.content_key != key:
                continue
            if match == "content_key_and_kind" and kind is not None:
                if node.kind_token != kind:
                    continue
            # Use lineage via edge to root if present; else entry ref.
            roots.add(node.ref_token)
    items = tuple(sorted((0, root_id) for root_id in roots))
    count = len(items)
    result = KnowledgeGenealogyQueryResult(
        query_id=KnowledgeGenealogyQueryId.INDEPENDENT_EMERGENCE_COUNT,
        as_of_tick=graph.as_of_tick,
        content_key=key,
        items=items,
        count=count,
        emerged_independently_twice=count >= 2,
    )
    _LOG.debug(
        "knowledge_genealogy_query query_id=%s result_count=%s censoring_policy=%s",
        result.query_id.value,
        result.count,
        graph.censoring_policy,
    )
    return result


def run_knowledge_genealogy_query(
    graph: KnowledgeGenealogyGraph,
    query_id: KnowledgeGenealogyQueryId | str,
    *,
    content_key: str,
    kind: str | None = None,
    holder_agent_id: str | None = None,
    include_dead_holders: bool = True,
    independent_root_match: str = "content_key",
    max_query_depth: int = 32,
) -> KnowledgeGenealogyQueryResult:
    """Dispatch one locked researcher query."""
    qid = (
        query_id
        if type(query_id) is KnowledgeGenealogyQueryId
        else KnowledgeGenealogyQueryId(str(query_id))
    )
    if qid is KnowledgeGenealogyQueryId.WHO_CURRENTLY_KNOWS:
        return query_who_currently_knows(
            graph,
            content_key=content_key,
            kind=kind,
            max_query_depth=max_query_depth,
        )
    if qid is KnowledgeGenealogyQueryId.WHO_TAUGHT:
        return query_who_taught(
            graph,
            content_key=content_key,
            holder_agent_id=holder_agent_id,
            include_dead_holders=include_dead_holders,
            kind=kind,
            max_query_depth=max_query_depth,
        )
    if qid is KnowledgeGenealogyQueryId.OLDEST_SURVIVING_LINEAGE_ORIGIN:
        return query_oldest_surviving_lineage_origin(
            graph,
            content_key=content_key,
            kind=kind,
            max_query_depth=max_query_depth,
        )
    if qid is KnowledgeGenealogyQueryId.INDEPENDENT_EMERGENCE_COUNT:
        return query_independent_emergence_count(
            graph,
            content_key=content_key,
            kind=kind,
            independent_root_match=independent_root_match,
            max_query_depth=max_query_depth,
        )
    raise ValueError(f"unknown knowledge genealogy query: {qid!r}")


def _qualified_entry_ref(
    run_id: RunId,
    owner_id: str,
    entry_id: str,
    *,
    family: LineageFamily = LineageFamily.KNOWLEDGE,
) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=family,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
        native_id=entry_id,
        identity_owner=owner_id,
    )


def _qualified_agent_ref(
    run_id: RunId, agent_id: str, *, family: LineageFamily = LineageFamily.KNOWLEDGE
) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=family,
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=LineageNativeKind.AGENT,
        native_id=agent_id,
    )


def _qualified_audits(rows: Sequence[object]) -> tuple[_AuditRow, ...]:
    grouped: dict[str, list[object]] = {}
    for row in rows:
        owner = _token(getattr(row, "owner_id", None), field="owner_id")
        if owner is None:
            continue
        grouped.setdefault(owner, []).append(row)
    normalized: list[_AuditRow] = []
    for owner in sorted(grouped):
        normalized.extend(_normalize_audits(grouped[owner]))
    return tuple(normalized)


def _add_qualified_edge(
    edges: dict[str, LineageEdge],
    *,
    run_id: RunId,
    relation: str,
    source_ref: LineageNodeRef,
    target_ref: LineageNodeRef,
    native_kind: LineageNativeKind,
    native_id: str,
    observed_tick: int,
    status_code: str,
    claim_owner_id: str | None = None,
) -> None:
    evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.ANALYTICAL,
        native_kind=native_kind,
        native_id=native_id,
        owner_id=(None if native_kind is LineageNativeKind.AGENT else claim_owner_id),
        observed_tick=observed_tick,
    )
    key = lineage_edge_key(
        relation=relation,
        source_key=source_ref.key,
        target_key=target_ref.key,
        native_kind=native_kind,
        native_id=native_id,
        claim_owner_id=claim_owner_id,
        evidence_keys=(evidence.key,),
    )
    edges.setdefault(
        key,
        LineageEdge(
            edge_key=key,
            source_key=source_ref.key,
            target_key=target_ref.key,
            relation=relation,
            native_kind=native_kind,
            native_id=native_id,
            claim_owner_id=claim_owner_id,
            evidence_refs=(evidence,),
            observed_tick=observed_tick,
            status_code=status_code,
        ),
    )


def build_qualified_knowledge_lineage(
    audit_rows: Sequence[object],
    *,
    run_id: RunId,
    as_of_tick: int,
    family: LineageFamily = LineageFamily.KNOWLEDGE,
    coverage: LineageCoverage | None = None,
    policy_version: str = "knowledge-analytical-lineage.v1",
) -> LineageSourceProjection:
    """Owner-qualified explorer DAG reusing legacy eligibility/tie-breaking."""
    if type(run_id) is not RunId:
        raise ValueError("run_id must be RunId")
    if family not in {LineageFamily.KNOWLEDGE, LineageFamily.TECHNOLOGY}:
        raise LineageError("invalid_lineage_scope")
    boundary = require_exact_nonneg_int("as_of_tick", as_of_tick)
    audits = tuple(
        row for row in _qualified_audits(audit_rows) if row.acquired_tick <= boundary
    )
    by_owner: dict[str, tuple[_AuditRow, ...]] = {}
    for row in audits:
        by_owner.setdefault(row.owner_id, ())
        by_owner[row.owner_id] += (row,)
    coverage_value = coverage or LineageCoverage(
        state=LineageCoverageState.COMPLETE,
        capture_start_tick=0,
        capture_end_tick=boundary,
        policy_version=policy_version,
    )
    if coverage_value.state is LineageCoverageState.DISABLED:
        return LineageSourceProjection(nodes=(), edges=(), coverage=coverage_value)

    nodes: dict[str, LineageNode] = {}
    edges: dict[str, LineageEdge] = {}
    anchors: dict[str, str | None] = {}
    for row in audits:
        holder_ref = _qualified_agent_ref(run_id, row.owner_id, family=family)
        nodes.setdefault(
            holder_ref.key,
            LineageNode(
                ref=holder_ref,
                state=LineageNodeState.OBSERVED,
                observed_tick=row.acquired_tick,
                status_code="analytical_agent_reference",
            ),
        )
        entry_ref = _qualified_entry_ref(
            run_id, row.owner_id, row.entry_id, family=family
        )
        entry_key = entry_ref.key
        anchors[entry_key] = row.capability_anchor
        nodes[entry_key] = LineageNode(
            ref=entry_ref,
            state=(
                LineageNodeState.OBSERVED if row.active else LineageNodeState.ARCHIVED
            ),
            observed_tick=row.tick,
            status_code=row.kind if row.active else f"inactive:{row.kind}",
            confidence_code=row.origin,
            counts=(("hop", row.hop_index),),
            source_observed_boundary=row.tick,
        )
        if row.active:
            _add_qualified_edge(
                edges,
                run_id=run_id,
                relation=KnowledgeGenealogyEdgeKind.HOLDS.value,
                source_ref=holder_ref,
                target_ref=entry_ref,
                native_kind=LineageNativeKind.AGENT,
                native_id=row.entry_id,
                observed_tick=row.tick,
                status_code="holder",
                claim_owner_id=row.owner_id,
            )
        if row.origin == "independent_discovery":
            root_ref = _qualified_entry_ref(
                run_id, row.owner_id, f"root:{row.lineage_root_id}", family=family
            )
            nodes.setdefault(
                root_ref.key,
                LineageNode(
                    ref=root_ref,
                    state=LineageNodeState.OBSERVED,
                    observed_tick=row.acquired_tick,
                    status_code="independent_root",
                    counts=(("hop", 0),),
                ),
            )
            _add_qualified_edge(
                edges,
                run_id=run_id,
                relation=KnowledgeGenealogyEdgeKind.TRANSMITTED_FROM.value,
                source_ref=root_ref,
                target_ref=entry_ref,
                native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
                native_id=row.entry_id,
                observed_tick=row.acquired_tick,
                status_code="independent_root",
                claim_owner_id=row.owner_id,
            )
        for parent_id in row.parent_entry_ids:
            parent_ref = _qualified_entry_ref(
                run_id, row.owner_id, parent_id, family=family
            )
            if parent_ref.key not in nodes:
                nodes[parent_ref.key] = LineageNode(
                    ref=parent_ref,
                    state=LineageNodeState.UNRESOLVED,
                    unresolved_reason="owner_local_parent_not_observed",
                )
                anchors[parent_ref.key] = None
            relation = (
                KnowledgeGenealogyEdgeKind.COMBINED_FROM.value
                if row.origin == "combination" or len(row.parent_entry_ids) >= 2
                else KnowledgeGenealogyEdgeKind.MUTATED_FROM.value
                if row.mutated or len(row.parent_entry_ids) == 1
                else KnowledgeGenealogyEdgeKind.TRANSMITTED_FROM.value
            )
            _add_qualified_edge(
                edges,
                run_id=run_id,
                relation=relation,
                source_ref=parent_ref,
                target_ref=entry_ref,
                native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
                native_id=row.entry_id,
                observed_tick=row.acquired_tick,
                status_code=row.origin,
                claim_owner_id=row.owner_id,
            )
        peer_source = row.source_agent_id or row.teacher_agent_id
        if (
            peer_source
            and not row.parent_entry_ids
            and row.origin != "independent_discovery"
        ):
            peer = _find_peer_source_entry(
                source_agent_id=peer_source,
                content_key=row.content_key,
                child_tick=row.acquired_tick,
                by_owner=by_owner,
            )
            peer_ref = (
                _qualified_entry_ref(run_id, peer_source, peer.entry_id, family=family)
                if peer is not None
                else _qualified_agent_ref(run_id, peer_source, family=family)
            )
            if peer is None:
                nodes.setdefault(
                    peer_ref.key,
                    LineageNode(
                        ref=peer_ref,
                        state=LineageNodeState.OBSERVED,
                        observed_tick=row.acquired_tick,
                        status_code="analytical_agent_reference",
                    ),
                )
                _add_qualified_edge(
                    edges,
                    run_id=run_id,
                    relation=(KnowledgeGenealogyEdgeKind.UNRESOLVED_TRANSMISSION.value),
                    source_ref=peer_ref,
                    target_ref=entry_ref,
                    native_kind=LineageNativeKind.AGENT,
                    native_id=row.entry_id,
                    observed_tick=row.acquired_tick,
                    status_code="unresolved_teacher",
                    claim_owner_id=row.owner_id,
                )
            else:
                _add_qualified_edge(
                    edges,
                    run_id=run_id,
                    relation=KnowledgeGenealogyEdgeKind.TRANSMITTED_FROM.value,
                    source_ref=peer_ref,
                    target_ref=entry_ref,
                    native_kind=LineageNativeKind.KNOWLEDGE_ENTRY,
                    native_id=row.entry_id,
                    observed_tick=row.acquired_tick,
                    status_code="analytical_transmission",
                    claim_owner_id=row.owner_id,
                )

    selected_keys = set(nodes)
    if family is LineageFamily.TECHNOLOGY:
        selected_keys = {key for key, anchor in anchors.items() if anchor is not None}
        frontier = list(selected_keys)
        sources_by_target: dict[str, list[str]] = {}
        for edge in edges.values():
            sources_by_target.setdefault(edge.target_key, []).append(edge.source_key)
        while frontier:
            target = frontier.pop()
            for source in sources_by_target.get(target, ()):
                if source not in selected_keys:
                    selected_keys.add(source)
                    frontier.append(source)
        selected_keys.update(
            key
            for key, node in nodes.items()
            if node.ref.native_kind is LineageNativeKind.AGENT
            and any(
                edge.source_key == key or edge.target_key == key
                for edge in edges.values()
                if edge.source_key in selected_keys or edge.target_key in selected_keys
            )
        )

    filtered_nodes = tuple(nodes[key] for key in sorted(selected_keys) if key in nodes)
    filtered_edges = tuple(
        edges[key]
        for key in sorted(edges)
        if edges[key].source_key in selected_keys
        and edges[key].target_key in selected_keys
    )
    _LOG.debug(
        "knowledge_qualified_lineage_projected run_id=%s as_of=%s family=%s "
        "row_count=%s node_count=%s edge_count=%s",
        run_id.value,
        boundary,
        family.value,
        len(audits),
        len(filtered_nodes),
        len(filtered_edges),
    )
    return LineageSourceProjection(
        nodes=filtered_nodes,
        edges=filtered_edges,
        coverage=coverage_value,
    )
