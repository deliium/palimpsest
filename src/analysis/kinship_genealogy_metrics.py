"""Analysis-only kinship genealogy metric (``kinship_genealogy@1``).

Never feeds cognition. Callers supply detached parent→child edge rows.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import networkx as nx

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "KINSHIP_GENEALOGY_METRIC_VERSION",
    "KinshipEdgeRow",
    "KinshipGenealogyError",
    "compute_kinship_genealogy",
]

KINSHIP_GENEALOGY_METRIC_VERSION: Final[str] = "kinship_genealogy@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.kinship_genealogy")
_LAYER: Final[str] = "research_analytics"


class KinshipGenealogyError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error("kinship_genealogy_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class KinshipEdgeRow:
    """One detached parent→child edge. Not a live engine graph."""

    parent_agent_id: str
    child_agent_id: str
    established_tick: int = 0


def compute_kinship_genealogy(
    edge_rows: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    known_agent_ids: Sequence[str] | None = None,
    max_depth: int = 8,
) -> MetricDocument:
    """Graph stats over detached kinship edges (analysis-only)."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    depth_cap = require_exact_nonneg_int("max_depth", max_depth)
    if depth_cap < 1:
        raise KinshipGenealogyError("invalid_max_depth")
    edges = _edge_rows(edge_rows)
    agents = _agent_universe(edges, known_agent_ids)
    _LOG.debug(
        "kinship_genealogy edge_count=%s agent_count=%s max_depth=%s",
        len(edges),
        len(agents),
        depth_cap,
    )
    spec = metric_specification(MetricFamilyId.KINSHIP_GENEALOGY)
    if spec.version_identifier != KINSHIP_GENEALOGY_METRIC_VERSION:
        raise KinshipGenealogyError("unsupported_metric_version")
    if not edges and not agents:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_kinship_rows",
        )
    graph = nx.DiGraph()
    graph.add_nodes_from(agents)
    for edge in edges:
        graph.add_edge(edge.parent_agent_id, edge.child_agent_id)
    undirected = graph.to_undirected(as_view=True)
    components = [
        frozenset(component)
        for component in nx.connected_components(undirected)
        if len(component) >= 1
    ]
    component_sizes = tuple(
        sorted((len(component) for component in components), reverse=True)
    )
    orphans = sum(1 for agent in agents if graph.degree(agent) == 0)
    depth_samples: list[float] = []
    for root in sorted(agents):
        depths = nx.single_source_shortest_path_length(graph, root, cutoff=depth_cap)
        if depths:
            depth_samples.append(float(max(depths.values())))
    mean_depth = (
        0.0
        if not depth_samples
        else require_finite(sum(depth_samples) / len(depth_samples))
    )
    values: dict[str, object] = {
        "layer": _LAYER,
        "edge_count": len(edges),
        "component_sizes": ",".join(str(size) for size in component_sizes),
        "mean_depth_reached": quantize_float(mean_depth),
        "orphan_count": orphans,
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(edges),
        expected=max(len(edges), 1),
    )


def _edge_rows(rows: Sequence[object]) -> tuple[KinshipEdgeRow, ...]:
    if isinstance(rows, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        rows, Sequence
    ):
        raise KinshipGenealogyError("invalid_edge_rows")
    parsed: list[KinshipEdgeRow] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        item = _parse_edge(index, row)
        key = (item.parent_agent_id, item.child_agent_id)
        if key in seen:
            raise KinshipGenealogyError("duplicate_edge")
        seen.add(key)
        parsed.append(item)
    parsed.sort(
        key=lambda item: (
            item.parent_agent_id,
            item.child_agent_id,
            item.established_tick,
        )
    )
    return tuple(parsed)


def _parse_edge(index: int, row: object) -> KinshipEdgeRow:
    if type(row) is KinshipEdgeRow:
        return row
    try:
        parent = require_stable_id(
            f"edge[{index}].parent_agent_id",
            getattr(row, "parent_agent_id", None)
            if not isinstance(row, Mapping)
            else row.get("parent_agent_id"),
        )
        child = require_stable_id(
            f"edge[{index}].child_agent_id",
            getattr(row, "child_agent_id", None)
            if not isinstance(row, Mapping)
            else row.get("child_agent_id"),
        )
        tick_raw = (
            getattr(row, "established_tick", 0)
            if not isinstance(row, Mapping)
            else row.get("established_tick", 0)
        )
        tick = require_exact_nonneg_int(f"edge[{index}].established_tick", tick_raw)
    except (TypeError, ValueError) as exc:
        raise KinshipGenealogyError("invalid_edge_row") from exc
    if parent == child:
        raise KinshipGenealogyError("self_parent_edge")
    return KinshipEdgeRow(
        parent_agent_id=parent,
        child_agent_id=child,
        established_tick=tick,
    )


def _agent_universe(
    edges: Sequence[KinshipEdgeRow],
    known_agent_ids: Sequence[str] | None,
) -> tuple[str, ...]:
    agents: set[str] = set()
    for edge in edges:
        agents.add(edge.parent_agent_id)
        agents.add(edge.child_agent_id)
    if known_agent_ids is not None:
        if isinstance(known_agent_ids, (str, bytes)) or not isinstance(
            known_agent_ids, Sequence
        ):
            raise KinshipGenealogyError("invalid_known_agent_ids")
        for index, agent_id in enumerate(known_agent_ids):
            agents.add(require_stable_id(f"known_agent_ids[{index}]", agent_id))
    return tuple(sorted(agents))


def _document(
    spec: MetricSpecification,
    run_id: str,
    revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    *,
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="kinship_genealogy",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
