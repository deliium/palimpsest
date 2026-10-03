"""Signed trust network and community structure metrics (Task 14).

Uses NetworkX with lexicographic node ordering. Community detection runs only
on an explicit nonnegative projection ``w = max(trust, 0)``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from typing import Final

import networkx as nx
from networkx.algorithms.community import (
    greedy_modularity_communities,
    modularity,
)

from analysis.evidence import EvidenceStage
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
    RelationshipEdgeRow,
)
from analysis.numerical import (
    SUPPORTED_COMMUNITY_ALGORITHM,
    library_versions,
    quantize_float,
    require_finite,
    sorted_graph_nodes,
)
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "build_signed_trust_digraph",
    "canonicalize_community_labels",
    "compute_group_community_structure",
    "compute_trust_network_structure",
    "nonnegative_undirected_projection",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.network_metrics")
_DEFAULT_TRUST_THRESHOLD: Final[float] = 0.0


def _document(
    *,
    family: str,
    algorithm_version: str,
    run_id: str,
    input_revision: str,
    evidence_stages: frozenset[EvidenceStage],
    population: str,
    denominator: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    coverage: MetricCoverage | None,
    notes_code: str,
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=evidence_stages,
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="network_metrics",
            source_ids=(),
            notes_code=notes_code,
        ),
    )


def build_signed_trust_digraph(
    rows: Sequence[RelationshipEdgeRow],
    *,
    agent_ids: Sequence[str] | None = None,
    trust_threshold: float = _DEFAULT_TRUST_THRESHOLD,
    drop_dead: bool = False,
    death_ticks: Mapping[str, int] | None = None,
) -> nx.DiGraph:
    """Build a sorted signed trust DiGraph from latest active revisions."""
    deaths = dict(death_ticks or {})
    latest: dict[tuple[str, str], RelationshipEdgeRow] = {}
    nodes: set[str] = set(agent_ids or ())
    for row in sorted(
        rows,
        key=lambda item: (
            item.source_id,
            item.target_id,
            item.logical_tick,
            item.ordinal,
        ),
    ):
        nodes.add(row.source_id)
        nodes.add(row.target_id)
        if row.activation_state != "active":
            continue
        if row.trust is None:
            continue
        if abs(row.trust) < trust_threshold:
            continue
        if row.trust_confidence is not None and row.trust_confidence < trust_threshold:
            continue
        latest[(row.source_id, row.target_id)] = row

    if drop_dead:
        nodes = {node for node in nodes if node not in deaths}

    graph = nx.DiGraph()
    for node in sorted_graph_nodes(nodes):
        graph.add_node(node)
    for (source, target), row in sorted(latest.items()):
        if source not in graph or target not in graph:
            continue
        assert row.trust is not None
        graph.add_edge(source, target, weight=float(row.trust), signed=True)
    return graph


def nonnegative_undirected_projection(digraph: nx.DiGraph) -> nx.Graph:
    """Project signed digraph to undirected nonnegative weights via max(trust,0)."""
    undirected = nx.Graph()
    for node in sorted_graph_nodes(digraph.nodes):
        undirected.add_node(node)
    for u, v, data in sorted(digraph.edges(data=True), key=lambda item: (item[0], item[1])):
        weight = float(data.get("weight", 0.0))
        projected = max(weight, 0.0)
        if projected <= 0.0:
            continue
        if undirected.has_edge(u, v):
            existing = float(undirected[u][v].get("weight", 0.0))
            undirected[u][v]["weight"] = max(existing, projected)
        else:
            undirected.add_edge(u, v, weight=projected)
    return undirected


def canonicalize_community_labels(
    communities: Sequence[frozenset[str]],
) -> tuple[tuple[str, ...], ...]:
    """Canonicalize community membership lists by min-node label order."""
    labeled = []
    for community in communities:
        members = tuple(sorted(community))
        if not members:
            continue
        labeled.append((members[0], members))
    labeled.sort(key=lambda item: item[0])
    return tuple(members for _, members in labeled)


def compute_trust_network_structure(
    rows: Sequence[RelationshipEdgeRow],
    *,
    run_id: str,
    input_revision: str,
    agent_ids: Sequence[str] | None = None,
    trust_threshold: float = _DEFAULT_TRUST_THRESHOLD,
    death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Density, reciprocity, degrees, components, and centralization."""
    started = time.perf_counter()
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.TRUST_NETWORK_STRUCTURE)
    graph = build_signed_trust_digraph(
        rows,
        agent_ids=agent_ids,
        trust_threshold=trust_threshold,
        death_ticks=death_ticks,
    )
    n = graph.number_of_nodes()
    m = graph.number_of_edges()
    if n == 0:
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="empty_graph",
        )

    density: float | None
    if n < 2:
        density = None
    else:
        density = quantize_float(require_finite(float(m) / float(n * (n - 1))))

    reciprocity = quantize_float(
        require_finite(float(nx.reciprocity(graph) if m > 0 else 0.0))
    )
    in_weights = [
        float(sum(data.get("weight", 0.0) for _, _, data in graph.in_edges(node, data=True)))
        for node in sorted_graph_nodes(graph.nodes)
    ]
    out_weights = [
        float(sum(data.get("weight", 0.0) for _, _, data in graph.out_edges(node, data=True)))
        for node in sorted_graph_nodes(graph.nodes)
    ]
    mean_in = quantize_float(require_finite(float(sum(in_weights) / n)))
    mean_out = quantize_float(require_finite(float(sum(out_weights) / n)))
    weak_components = nx.number_weakly_connected_components(graph)

    # Freeman out-degree centralization on nonnegative abs(trust) ranking projection.
    abs_out = [abs(value) for value in out_weights]
    centralization_out: float | None
    if n < 2:
        centralization_out = None
    else:
        max_out = max(abs_out) if abs_out else 0.0
        numerator = sum(max_out - value for value in abs_out)
        denominator = float((n - 1) * (n - 1))
        centralization_out = (
            None
            if denominator == 0.0
            else quantize_float(require_finite(numerator / denominator))
        )

    mean_degree_centrality: float | None
    mean_betweenness_centrality: float | None
    mean_closeness_centrality: float | None
    if n < 2:
        mean_degree_centrality = None
        mean_betweenness_centrality = None
        mean_closeness_centrality = None
    else:
        (
            mean_degree_centrality,
            mean_betweenness_centrality,
            mean_closeness_centrality,
        ) = _mean_centrality_summaries(graph)

    availability = MetricAvailability.PRESENT
    if n == 1:
        availability = MetricAvailability.PARTIAL

    centrality_present = {
        "centralization_out": centralization_out is not None,
        "mean_degree_centrality": mean_degree_centrality is not None,
        "mean_betweenness_centrality": mean_betweenness_centrality is not None,
        "mean_closeness_centrality": mean_closeness_centrality is not None,
    }
    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "trust_network_complete",
        extra={
            "operation": "compute_trust_network_structure",
            "family_id": spec.family_id.value,
            "run_id": run_id,
            "node_count": n,
            "edge_count": m,
            "weak_components": weak_components,
            "centrality_keys_present": centrality_present,
            "duration_ms": duration_ms,
        },
    )
    return _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values={
            "density": density,
            "reciprocity": reciprocity,
            "mean_in_degree_weight": mean_in,
            "mean_out_degree_weight": mean_out,
            "weak_components": int(weak_components),
            "node_count": n,
            "edge_count": m,
            "centralization_out": centralization_out,
            "mean_degree_centrality": mean_degree_centrality,
            "mean_betweenness_centrality": mean_betweenness_centrality,
            "mean_closeness_centrality": mean_closeness_centrality,
        },
        coverage=MetricCoverage(observed=m, expected=n * max(n - 1, 0), ratio=density),
        notes_code="ok",
    )


def _mean_centrality_summaries(
    digraph: nx.DiGraph,
) -> tuple[float, float, float]:
    """Exact mean centrality on nonnegative undirected projection.

    Nodes are added in lexicographic order. Self-loops are dropped. Callers
    must pass ``n >= 2``; empty/single-node graphs keep centrality keys absent.
    """
    projected = nonnegative_undirected_projection(digraph)
    ordered = nx.Graph()
    for node in sorted_graph_nodes(projected.nodes):
        ordered.add_node(node)
    for u, v, data in sorted(
        projected.edges(data=True), key=lambda item: (item[0], item[1])
    ):
        if u == v:
            continue
        ordered.add_edge(u, v, **data)

    degree_map = nx.degree_centrality(ordered)
    betweenness_map = nx.betweenness_centrality(ordered, normalized=True)
    closeness_map = nx.closeness_centrality(ordered)
    nodes = sorted_graph_nodes(ordered.nodes)
    count = len(nodes)
    mean_degree = quantize_float(
        require_finite(float(sum(degree_map[node] for node in nodes) / count))
    )
    mean_betweenness = quantize_float(
        require_finite(float(sum(betweenness_map[node] for node in nodes) / count))
    )
    mean_closeness = quantize_float(
        require_finite(float(sum(closeness_map[node] for node in nodes) / count))
    )
    return mean_degree, mean_betweenness, mean_closeness


def compute_group_community_structure(
    rows: Sequence[RelationshipEdgeRow],
    *,
    run_id: str,
    input_revision: str,
    agent_ids: Sequence[str] | None = None,
    trust_threshold: float = _DEFAULT_TRUST_THRESHOLD,
    death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Deterministic greedy modularity communities on nonnegative projection."""
    started = time.perf_counter()
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.GROUP_COMMUNITY_STRUCTURE)
    digraph = build_signed_trust_digraph(
        rows,
        agent_ids=agent_ids,
        trust_threshold=trust_threshold,
        death_ticks=death_ticks,
    )
    graph = nonnegative_undirected_projection(digraph)
    n = graph.number_of_nodes()
    if n == 0:
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="empty_graph",
        )

    # Deterministic tie-break: iterate nodes in sorted order via Graph copy.
    ordered = nx.Graph()
    for node in sorted_graph_nodes(graph.nodes):
        ordered.add_node(node)
    for u, v, data in sorted(graph.edges(data=True), key=lambda item: (item[0], item[1])):
        ordered.add_edge(u, v, **data)

    if ordered.number_of_edges() == 0:
        communities = [frozenset({node}) for node in sorted_graph_nodes(ordered.nodes)]
        modularity_value = 0.0
    else:
        raw = list(
            greedy_modularity_communities(ordered, weight="weight", cutoff=1, best_n=None)
        )
        communities = [frozenset(community) for community in raw]
        modularity_value = float(modularity(ordered, communities, weight="weight"))

    labels = canonicalize_community_labels(communities)
    community_count = len(labels)
    largest_share = quantize_float(
        require_finite(float(max(len(c) for c in labels)) / float(n))
    )
    mod_q = quantize_float(require_finite(modularity_value))

    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "group_community_complete",
        extra={
            "operation": "compute_group_community_structure",
            "run_id": run_id,
            "node_count": n,
            "community_count": community_count,
            "algorithm": SUPPORTED_COMMUNITY_ALGORITHM,
            "duration_ms": duration_ms,
        },
    )
    return _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        availability=MetricAvailability.PRESENT,
        values={
            "community_count": community_count,
            "modularity": mod_q,
            "largest_community_share": largest_share,
            "node_count": n,
        },
        coverage=MetricCoverage(
            observed=ordered.number_of_edges(),
            expected=max(n * (n - 1) // 2, 0),
            ratio=None,
        ),
        notes_code="ok",
    )
