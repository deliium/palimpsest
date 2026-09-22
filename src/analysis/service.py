"""Experiment-only memory-drift analysis service.

Independently reads immutable objective events and subjective memory evidence,
joins them after reconstruction, and emits metadata-only operational logs.
Never injects WorldEvent into agents, cognition, memory, or reconstruction.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.contracts import MemoryEvidenceSource, ObjectiveEventSource
from analysis.evidence import EvidenceStage
from analysis.memory_drift import (
    AGENT_VISIBLE_PROJECTOR_VERSION,
    DRIFT_METRIC_VERSION,
    EVENT_FACT_PROJECTOR_VERSION,
    build_reconstruction_chains,
    compare_fact_sets,
    compute_memory_drift,
    cumulative_drift,
    evidence_stage_for_trace,
    project_agent_visible_observation,
    project_world_event,
)
from analysis.models import (
    ChainNodeKind,
    DriftDelta,
    DriftStep,
    MemoryDriftReport,
    MetricDocument,
    ObjectiveLinkStatus,
    StructuredFactSet,
)
from world.identifiers import require_stable_id
from world.observations import Observation

__all__ = ["MemoryDriftAnalysisService"]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.service")


class MemoryDriftAnalysisService:
    """Read-only experiment analysis over objective and subjective evidence."""

    __slots__ = ("_events", "_memory")

    def __init__(
        self,
        *,
        memory: MemoryEvidenceSource,
        events: ObjectiveEventSource,
    ) -> None:
        self._memory = memory
        self._events = events

    def analyze_memory_drift(
        self,
        *,
        experiment_id: str,
        run_id: str,
        owner_id: str,
        agent_visible: Sequence[Observation] | None = None,
        include_authoritative_world_gap: bool = True,
    ) -> MemoryDriftReport:
        """Join opaque source correlation with objective events and measure drift.

        Primary comparison uses agent-visible projection when provided. Optional
        authoritative-world gaps are separately labeled and never mixed into the
        primary chain baseline.
        """
        experiment_id = require_stable_id("experiment_id", experiment_id)
        run_id = require_stable_id("run_id", run_id)
        owner_id = require_stable_id("owner_id", owner_id)

        _LOG.debug(
            "memory_drift_analysis_start",
            extra={
                "operation": "analyze_memory_drift",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "projector_version": EVENT_FACT_PROJECTOR_VERSION,
                "agent_visible_projector_version": AGENT_VISIBLE_PROJECTOR_VERSION,
                "metric_version": DRIFT_METRIC_VERSION,
                "agent_visible_count": 0 if agent_visible is None else len(agent_visible),
            },
        )

        try:
            traces = self._memory.traces(run_id=run_id, owner_id=owner_id)
            reconstructions = self._memory.reconstructions(
                run_id=run_id, owner_id=owner_id
            )
            edges = self._memory.derivation_edges(run_id=run_id, owner_id=owner_id)
            objective_events = self._events.events_for_run(run_id)
        except Exception:
            _LOG.error(
                "memory_drift_analysis_read_failed",
                extra={
                    "operation": "analyze_memory_drift",
                    "experiment_id": experiment_id,
                    "run_id": run_id,
                    "owner_id": owner_id,
                    "reason_code": "read_failed",
                },
            )
            raise

        events_by_id = {event.event_id.value: event for event in objective_events}
        reconstruction_sources = {
            item.reconstruction_id: frozenset(item.source_memory_ids)
            for item in reconstructions
        }
        derived_reconstructions = {
            edge.derived_memory_id: edge.reconstruction_id
            for edge in edges
            if edge.reconstruction_id is not None
        }
        traces_by_id = {trace.memory_id.value: trace for trace in traces}

        visible_by_source: dict[str, StructuredFactSet] = {}
        if agent_visible:
            for observation in agent_visible:
                facts = project_agent_visible_observation(observation)
                for occurrence in observation.occurrences:
                    event_id = (
                        None
                        if occurrence.provenance.source_event_id is None
                        else occurrence.provenance.source_event_id.value
                    )
                    if event_id is not None:
                        visible_by_source[event_id] = facts
                for message in observation.communications:
                    event_id = (
                        None
                        if message.provenance.source_event_id is None
                        else message.provenance.source_event_id.value
                    )
                    if event_id is not None:
                        visible_by_source[event_id] = facts

        chains = build_reconstruction_chains(
            traces=traces,
            reconstructions=reconstructions,
            edges=edges,
            events_by_id=events_by_id,
            agent_visible_by_source_id=visible_by_source or None,
            include_authoritative_world=not bool(visible_by_source),
        )

        steps: list[DriftStep] = []
        authoritative_gaps: list[DriftStep] = []
        cumulative: list[DriftDelta] = []
        linked = 0
        unlinked = 0
        absent = 0
        broken_provenance = 0
        stage_counts: dict[str, int] = {}

        for chain in chains:
            if chain.objective_link is ObjectiveLinkStatus.LINKED:
                linked += 1
            elif chain.objective_link is ObjectiveLinkStatus.UNLINKED:
                unlinked += 1
                _LOG.warning(
                    "memory_drift_unlinked_source",
                    extra={
                        "operation": "analyze_memory_drift",
                        "experiment_id": experiment_id,
                        "run_id": run_id,
                        "owner_id": owner_id,
                        "reason_code": "unlinked_observed_source",
                    },
                )
            elif chain.objective_link is ObjectiveLinkStatus.ABSENT:
                absent += 1

            provenance_ok = True
            for index in range(len(chain.nodes) - 1):
                before = chain.nodes[index]
                after = chain.nodes[index + 1]
                continuous = _edge_continuous(
                    before_kind=before.kind,
                    before_id=before.node_id,
                    after_kind=after.kind,
                    after_id=after.node_id,
                    reconstruction_sources=reconstruction_sources,
                    derived_reconstructions=derived_reconstructions,
                )
                if not continuous:
                    provenance_ok = False
                    broken_provenance += 1
                    _LOG.warning(
                        "memory_drift_provenance_break",
                        extra={
                            "operation": "analyze_memory_drift",
                            "experiment_id": experiment_id,
                            "run_id": run_id,
                            "owner_id": owner_id,
                            "reason_code": "provenance_break",
                        },
                    )
                stage = _stage_for_node(
                    after.kind, after.node_id, traces_by_id=traces_by_id
                )
                if stage is not None:
                    stage_counts[stage.value] = stage_counts.get(stage.value, 0) + 1
                delta = compare_fact_sets(
                    before.facts,
                    after.facts,
                    provenance_continuous=continuous,
                )
                steps.append(
                    DriftStep(
                        chain_root_memory_id=chain.root_memory_id,
                        from_kind=before.kind,
                        to_kind=after.kind,
                        from_id=before.node_id,
                        to_id=after.node_id,
                        delta=delta,
                        evidence_stage=stage,
                        comparison_label="primary",
                    )
                )

            if (
                include_authoritative_world_gap
                and chain.observed_source_id is not None
                and chain.objective_link is ObjectiveLinkStatus.LINKED
            ):
                event = events_by_id.get(chain.observed_source_id)
                root_node = next(
                    (
                        node
                        for node in chain.nodes
                        if node.kind is ChainNodeKind.ROOT_TRACE
                    ),
                    None,
                )
                if event is not None and root_node is not None:
                    world_facts = project_world_event(event)
                    gap = compare_fact_sets(
                        world_facts,
                        root_node.facts,
                        provenance_continuous=True,
                    )
                    authoritative_gaps.append(
                        DriftStep(
                            chain_root_memory_id=chain.root_memory_id,
                            from_kind=ChainNodeKind.AUTHORITATIVE_WORLD_GAP,
                            to_kind=ChainNodeKind.ROOT_TRACE,
                            from_id=chain.observed_source_id,
                            to_id=root_node.node_id,
                            delta=gap,
                            evidence_stage=EvidenceStage.OBJECTIVE_EVENT_STATE,
                            comparison_label="authoritative_world_gap",
                        )
                    )

            first_facts = chain.nodes[0].facts
            last_facts = chain.nodes[-1].facts
            cumulative.append(
                cumulative_drift(
                    first_facts,
                    last_facts,
                    provenance_continuous=provenance_ok,
                )
            )

        report = MemoryDriftReport(
            experiment_id=experiment_id,
            run_id=run_id,
            owner_id=owner_id,
            projector_version=(
                AGENT_VISIBLE_PROJECTOR_VERSION
                if visible_by_source
                else EVENT_FACT_PROJECTOR_VERSION
            ),
            metric_version=DRIFT_METRIC_VERSION,
            chains=chains,
            steps=tuple(steps),
            cumulative=tuple(cumulative),
            linked_count=linked,
            unlinked_count=unlinked,
            absent_source_count=absent,
            authoritative_gap_steps=tuple(authoritative_gaps),
            evidence_stage_counts=stage_counts or None,
        )
        _LOG.debug(
            "memory_drift_analysis_metrics",
            extra={
                "operation": "analyze_memory_drift",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "chain_length_total": sum(len(chain.nodes) for chain in chains),
                "chain_count": len(chains),
                "linked_count": linked,
                "unlinked_count": unlinked,
                "absent_source_count": absent,
                "broken_provenance_count": broken_provenance,
                "authoritative_gap_count": len(authoritative_gaps),
                "metric_names": (
                    "retained_concepts",
                    "lost_concepts",
                    "added_concepts",
                    "confidence_delta",
                    "salience_delta",
                    "canonical_equal",
                ),
            },
        )
        _LOG.info(
            "memory_drift_analysis_complete",
            extra={
                "operation": "analyze_memory_drift",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "comparison_count": len(steps),
                "chain_count": len(chains),
            },
        )
        return report

    def analyze_memory_drift_document(
        self,
        *,
        experiment_id: str,
        run_id: str,
        owner_id: str,
        input_revision: str,
        agent_visible: Sequence[Observation] | None = None,
        include_authoritative_world_gap: bool = True,
    ) -> MetricDocument:
        """Analyze drift and emit a catalog MetricDocument."""
        report = self.analyze_memory_drift(
            experiment_id=experiment_id,
            run_id=run_id,
            owner_id=owner_id,
            agent_visible=agent_visible,
            include_authoritative_world_gap=include_authoritative_world_gap,
        )
        return compute_memory_drift(report, input_revision=input_revision)


def _stage_for_node(
    kind: ChainNodeKind,
    node_id: str,
    *,
    traces_by_id: Mapping[str, object],
) -> EvidenceStage | None:
    if kind is ChainNodeKind.AGENT_VISIBLE_PROJECTION:
        return EvidenceStage.AGENT_VISIBLE_PROJECTION
    if kind is ChainNodeKind.OBJECTIVE_EVENT:
        return EvidenceStage.OBJECTIVE_EVENT_STATE
    if kind is ChainNodeKind.RECONSTRUCTION:
        return EvidenceStage.RECONSTRUCTION
    if kind in (ChainNodeKind.ROOT_TRACE, ChainNodeKind.DERIVED_TRACE):
        trace = traces_by_id.get(node_id)
        if trace is not None:
            return evidence_stage_for_trace(trace)  # type: ignore[arg-type]
        return EvidenceStage.DIRECT_TRACE
    return None


def _edge_continuous(
    *,
    before_kind: ChainNodeKind,
    before_id: str,
    after_kind: ChainNodeKind,
    after_id: str,
    reconstruction_sources: dict[str, frozenset[str]],
    derived_reconstructions: dict[str, str],
) -> bool:
    if before_kind is ChainNodeKind.AGENT_VISIBLE_PROJECTION:
        return after_kind is ChainNodeKind.ROOT_TRACE
    if before_kind is ChainNodeKind.OBJECTIVE_EVENT:
        return after_kind is ChainNodeKind.ROOT_TRACE
    if (
        before_kind is ChainNodeKind.ROOT_TRACE
        or before_kind is ChainNodeKind.DERIVED_TRACE
    ) and after_kind is ChainNodeKind.RECONSTRUCTION:
        sources = reconstruction_sources.get(after_id)
        return sources is not None and before_id in sources
    if (
        before_kind is ChainNodeKind.RECONSTRUCTION
        and after_kind is ChainNodeKind.DERIVED_TRACE
    ):
        return derived_reconstructions.get(after_id) == before_id
    if (
        before_kind is ChainNodeKind.DERIVED_TRACE
        and after_kind is ChainNodeKind.RECONSTRUCTION
    ):
        sources = reconstruction_sources.get(after_id)
        return sources is not None and before_id in sources
    if (
        before_kind is ChainNodeKind.ROOT_TRACE
        and after_kind is ChainNodeKind.DERIVED_TRACE
    ):
        return derived_reconstructions.get(after_id) is not None
    return True
