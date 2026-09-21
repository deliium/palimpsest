"""Experiment-only memory-drift analysis service.

Independently reads immutable objective events and subjective memory evidence,
joins them after reconstruction, and emits metadata-only operational logs.
Never injects WorldEvent into agents, cognition, memory, or reconstruction.
"""

from __future__ import annotations

import logging
from typing import Final

from analysis.contracts import MemoryEvidenceSource, ObjectiveEventSource
from analysis.memory_drift import (
    DRIFT_METRIC_VERSION,
    EVENT_FACT_PROJECTOR_VERSION,
    build_reconstruction_chains,
    compare_fact_sets,
    cumulative_drift,
)
from analysis.models import (
    ChainNodeKind,
    DriftDelta,
    DriftStep,
    MemoryDriftReport,
    ObjectiveLinkStatus,
)
from world.identifiers import require_stable_id

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
    ) -> MemoryDriftReport:
        """Join opaque source correlation with objective events and measure drift."""
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
                "metric_version": DRIFT_METRIC_VERSION,
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

        chains = build_reconstruction_chains(
            traces=traces,
            reconstructions=reconstructions,
            edges=edges,
            events_by_id=events_by_id,
        )

        steps: list[DriftStep] = []
        cumulative: list[DriftDelta] = []
        linked = 0
        unlinked = 0
        absent = 0
        broken_provenance = 0

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
            projector_version=EVENT_FACT_PROJECTOR_VERSION,
            metric_version=DRIFT_METRIC_VERSION,
            chains=chains,
            steps=tuple(steps),
            cumulative=tuple(cumulative),
            linked_count=linked,
            unlinked_count=unlinked,
            absent_source_count=absent,
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


def _edge_continuous(
    *,
    before_kind: ChainNodeKind,
    before_id: str,
    after_kind: ChainNodeKind,
    after_id: str,
    reconstruction_sources: dict[str, frozenset[str]],
    derived_reconstructions: dict[str, str],
) -> bool:
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
