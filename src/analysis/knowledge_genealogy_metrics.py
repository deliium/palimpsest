"""Analysis-only knowledge genealogy holders / lineage / mutation metrics.

Never feeds cognition. Duck-types detached practical-knowledge audit rows.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.historical_memory import is_agent_living_at
from analysis.knowledge_genealogy import (
    KnowledgeGenealogyEdgeKind,
    KnowledgeGenealogyNodeKind,
    build_knowledge_genealogy_graph,
    query_independent_emergence_count,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "KNOWLEDGE_GENEALOGY_HOLDERS_METRIC_VERSION",
    "KNOWLEDGE_GENEALOGY_LINEAGE_METRIC_VERSION",
    "KNOWLEDGE_GENEALOGY_MUTATION_METRIC_VERSION",
    "compute_knowledge_genealogy_holders",
    "compute_knowledge_genealogy_lineage",
    "compute_knowledge_genealogy_mutation",
]

KNOWLEDGE_GENEALOGY_HOLDERS_METRIC_VERSION: Final[str] = (
    "knowledge_genealogy_holders@1"
)
KNOWLEDGE_GENEALOGY_LINEAGE_METRIC_VERSION: Final[str] = (
    "knowledge_genealogy_lineage@1"
)
KNOWLEDGE_GENEALOGY_MUTATION_METRIC_VERSION: Final[str] = (
    "knowledge_genealogy_mutation@1"
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.knowledge_genealogy_metrics")
_LAYER: Final[str] = "research_analytics"
_CENSOR: Final[str] = "analysis-only knowledge genealogy; never cognition"


class KnowledgeGenealogyMetricError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error("knowledge_genealogy_metric_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


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
            source_kind="knowledge_genealogy",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _audit_rows(audits: Sequence[object]) -> tuple[object, ...]:
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise KnowledgeGenealogyMetricError("audits_not_ordered")
    rows: list[object] = []
    for audit in audits:
        name = type(audit).__name__
        if name not in {"PracticalKnowledgeAudit", "SimpleNamespace"} and not hasattr(
            audit, "content_key"
        ):
            raise KnowledgeGenealogyMetricError("invalid_audit_type")
        if getattr(audit, "content_key", None) is None:
            raise KnowledgeGenealogyMetricError("invalid_audit_type")
        rows.append(audit)
    return tuple(rows)


def _owner_token(row: object) -> str | None:
    owner = getattr(row, "owner_id", None)
    if type(owner) is str:
        return owner
    nested = getattr(owner, "value", None)
    return nested if type(nested) is str else None


def compute_knowledge_genealogy_holders(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    as_of_tick: int = 0,
    death_ticks: Mapping[str, int] | None = None,
    died_events: Sequence[object] | None = None,
) -> MetricDocument:
    """Active holders per technique; living vs dead; mean hop; teacher coverage."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    rows = _audit_rows(audits)
    _LOG.debug(
        "knowledge_genealogy_metric_compute family_id=%s audit_count=%s",
        MetricFamilyId.KNOWLEDGE_GENEALOGY_HOLDERS.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.KNOWLEDGE_GENEALOGY_HOLDERS)
    if spec.version_identifier != KNOWLEDGE_GENEALOGY_HOLDERS_METRIC_VERSION:
        raise KnowledgeGenealogyMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_practical_knowledge_audits",
        )
    graph = build_knowledge_genealogy_graph(
        rows,
        as_of_tick=tick,
        death_ticks=death_ticks,
        died_events=died_events,
    )
    active = [
        node
        for node in graph.nodes
        if node.kind is KnowledgeGenealogyNodeKind.KNOWLEDGE_ENTRY
        and node.active is True
    ]
    techniques = {node.content_key for node in active if node.content_key}
    living = 0
    dead = 0
    hop_sum = 0
    with_teacher = 0
    for node in active:
        agent = node.agent_id
        if agent is None:
            continue
        if is_agent_living_at(agent, tick, graph.death_ticks):
            living += 1
        else:
            dead += 1
        hop_sum += 0 if node.hop_index is None else node.hop_index
    for row in rows:
        if bool(getattr(row, "active", True)) and (
            getattr(row, "teacher_agent_id", None)
            or getattr(row, "source_agent_id", None)
        ):
            with_teacher += 1
    values: dict[str, object] = {
        "layer": _LAYER,
        "active_entry_count": len(active),
        "technique_count": len(techniques),
        "living_holder_count": living,
        "dead_holder_count": dead,
        "mean_hop_index": quantize_float(hop_sum / len(active) if active else 0.0),
        "teacher_coverage_share": quantize_float(
            with_teacher / len(rows) if rows else 0.0
        ),
        "censoring_policy": _CENSOR,
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


def compute_knowledge_genealogy_lineage(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    as_of_tick: int = 0,
    death_ticks: Mapping[str, int] | None = None,
    died_events: Sequence[object] | None = None,
) -> MetricDocument:
    """Root counts, multi-parent share, combination rate, DAG depth, dual emergence."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    rows = _audit_rows(audits)
    _LOG.debug(
        "knowledge_genealogy_metric_compute family_id=%s audit_count=%s",
        MetricFamilyId.KNOWLEDGE_GENEALOGY_LINEAGE.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.KNOWLEDGE_GENEALOGY_LINEAGE)
    if spec.version_identifier != KNOWLEDGE_GENEALOGY_LINEAGE_METRIC_VERSION:
        raise KnowledgeGenealogyMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_practical_knowledge_audits",
        )
    graph = build_knowledge_genealogy_graph(
        rows,
        as_of_tick=tick,
        death_ticks=death_ticks,
        died_events=died_events,
    )
    roots = [
        node
        for node in graph.nodes
        if node.kind is KnowledgeGenealogyNodeKind.INDEPENDENT_ROOT
    ]
    multi_parent = sum(
        1
        for row in rows
        if len(tuple(getattr(row, "parent_entry_ids", ()) or ())) >= 2
    )
    combination = sum(
        1 for row in rows if str(getattr(row, "origin", "")) == "combination"
    )
    owner_hops = [
        int(getattr(row, "hop_index", 0))
        for row in rows
        if isinstance(getattr(row, "hop_index", None), int)
    ]
    analysis_depths = [edge.depth for edge in graph.edges]
    dual_keys = 0
    technique_keys = {
        str(getattr(row, "content_key", ""))
        for row in rows
        if getattr(row, "content_key", None)
    }
    for key in technique_keys:
        if not key:
            continue
        emergence = query_independent_emergence_count(graph, content_key=key)
        if emergence.emerged_independently_twice:
            dual_keys += 1
    values: dict[str, object] = {
        "layer": _LAYER,
        "independent_root_count": len(roots),
        "multi_parent_share": quantize_float(multi_parent / len(rows)),
        "combination_rate": quantize_float(combination / len(rows)),
        "max_owner_local_hop": max(owner_hops) if owner_hops else 0,
        "max_analysis_dag_depth": max(analysis_depths) if analysis_depths else 0,
        "dual_independent_emergence_rate": quantize_float(
            dual_keys / len(technique_keys) if technique_keys else 0.0
        ),
        "unresolved_transmission_count": graph.unresolved_transmission_count,
        "censoring_policy": _CENSOR,
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


def compute_knowledge_genealogy_mutation(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Mutated hop share, mean fingerprint distance, origin histogram."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.debug(
        "knowledge_genealogy_metric_compute family_id=%s audit_count=%s",
        MetricFamilyId.KNOWLEDGE_GENEALOGY_MUTATION.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.KNOWLEDGE_GENEALOGY_MUTATION)
    if spec.version_identifier != KNOWLEDGE_GENEALOGY_MUTATION_METRIC_VERSION:
        raise KnowledgeGenealogyMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_practical_knowledge_audits",
        )
    mutated = sum(1 for row in rows if bool(getattr(row, "mutated", False)))
    distances: list[float] = []
    origins: Counter[str] = Counter()
    for row in rows:
        origin = str(getattr(row, "origin", "unknown"))
        origins[origin] += 1
        distance = getattr(row, "fingerprint_distance_q", 0.0)
        if isinstance(distance, (int, float)) and not isinstance(distance, bool):
            distances.append(float(distance))
    values: dict[str, object] = {
        "layer": _LAYER,
        "audit_count": len(rows),
        "mutated_count": mutated,
        "mutated_hop_share": quantize_float(mutated / len(rows)),
        "mean_fingerprint_distance_q": quantize_float(
            sum(distances) / len(distances) if distances else 0.0
        ),
        "censoring_policy": _CENSOR,
    }
    for origin, count in sorted(origins.items()):
        values[f"origin_{origin}_count"] = count
    # Ensure we never leak fingerprints into notes/values keys.
    assert not any(
        "fingerprint" in key and key != "mean_fingerprint_distance_q"
        for key in values
    )
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


# Silence unused import lint for edge kind (used by callers / future joins).
_ = KnowledgeGenealogyEdgeKind
