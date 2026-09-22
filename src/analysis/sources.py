"""In-memory read-only evidence sources for experiment analysis tests and fakes.

Run/owner scope is stored on each evidence item (edges, reconstructions, scoped
traces). Readers filter by those fields — never by post-hoc unscoped scans.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.evidence import ScopedMemoryTrace
from analysis.memory_drift import evidence_from_reconstructed_memory
from analysis.models import ReconstructionEvidence, SubjectiveDerivationEdge
from memory.models import (
    AgentId,
    MemoryId,
    MemoryTrace,
    ReconstructedMemory,
    ReconstructionId,
)
from world.events import WorldEvent
from world.identifiers import EventId, require_stable_id

__all__ = [
    "InMemoryMemoryEvidenceSource",
    "InMemoryObjectiveEventSource",
    "reconstruction_evidence_from_durable",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.sources")


class InMemoryObjectiveEventSource:
    """Detached objective event snapshot keyed by run."""

    __slots__ = ("_by_run",)

    def __init__(
        self, events: Sequence[WorldEvent] | Mapping[str, Sequence[WorldEvent]]
    ) -> None:
        by_run: dict[str, tuple[WorldEvent, ...]]
        if isinstance(events, Mapping):
            by_run = {
                require_stable_id("run_id", run_id): tuple(run_events)
                for run_id, run_events in events.items()
            }
        else:
            built: dict[str, list[WorldEvent]] = {}
            for event in events:
                if type(event) is not WorldEvent:
                    raise TypeError("InMemoryObjectiveEventSource: invalid_event")
                built.setdefault(event.run_id, []).append(event)
            by_run = {key: tuple(value) for key, value in built.items()}
        self._by_run = by_run

    def events_for_run(self, run_id: str) -> tuple[WorldEvent, ...]:
        return self._by_run.get(require_stable_id("run_id", run_id), ())

    def event_by_id(self, run_id: str, event_id: EventId) -> WorldEvent | None:
        if type(event_id) is not EventId:
            raise TypeError(
                "InMemoryObjectiveEventSource.event_by_id: invalid_event_id"
            )
        for event in self.events_for_run(run_id):
            if event.event_id == event_id:
                return event
        return None


class InMemoryMemoryEvidenceSource:
    """Detached subjective evidence snapshot keyed by run/owner scope."""

    __slots__ = ("_edges", "_reconstructions", "_scoped_traces", "_traces")

    def __init__(
        self,
        *,
        traces: Sequence[MemoryTrace] = (),
        scoped_traces: Sequence[ScopedMemoryTrace] = (),
        reconstructions: Sequence[ReconstructionEvidence] = (),
        derivation_edges: Sequence[SubjectiveDerivationEdge] = (),
    ) -> None:
        for edge in derivation_edges:
            if type(edge) is not SubjectiveDerivationEdge:
                raise TypeError("InMemoryMemoryEvidenceSource: invalid_edge")
        for reconstruction in reconstructions:
            if type(reconstruction) is not ReconstructionEvidence:
                raise TypeError("InMemoryMemoryEvidenceSource: invalid_reconstruction")
        for scoped in scoped_traces:
            if type(scoped) is not ScopedMemoryTrace:
                raise TypeError("InMemoryMemoryEvidenceSource: invalid_scoped_trace")
        self._traces = tuple(traces)
        self._scoped_traces = tuple(scoped_traces)
        self._reconstructions = tuple(reconstructions)
        self._edges = tuple(derivation_edges)
        _LOG.debug(
            "memory_evidence_source_built",
            extra={
                "operation": "InMemoryMemoryEvidenceSource.__init__",
                "trace_count": len(self._traces),
                "scoped_trace_count": len(self._scoped_traces),
                "reconstruction_count": len(self._reconstructions),
                "edge_count": len(self._edges),
            },
        )

    def traces(self, *, run_id: str, owner_id: str) -> tuple[MemoryTrace, ...]:
        run_id = require_stable_id("run_id", run_id)
        owner_id = require_stable_id("owner_id", owner_id)
        scoped = tuple(
            item.trace
            for item in self._scoped_traces
            if item.run_id == run_id and item.owner_id == owner_id
        )
        if scoped:
            return scoped
        # Legacy path: unscoped MemoryTrace values match owner only (no run_id).
        return tuple(
            trace for trace in self._traces if trace.owner_id.value == owner_id
        )

    def reconstructions(
        self, *, run_id: str, owner_id: str
    ) -> tuple[ReconstructionEvidence, ...]:
        run_id = require_stable_id("run_id", run_id)
        owner_id = require_stable_id("owner_id", owner_id)
        return tuple(
            item
            for item in self._reconstructions
            if item.run_id == run_id and item.owner_id == owner_id
        )

    def derivation_edges(
        self, *, run_id: str, owner_id: str
    ) -> tuple[SubjectiveDerivationEdge, ...]:
        run_id = require_stable_id("run_id", run_id)
        owner_id = require_stable_id("owner_id", owner_id)
        return tuple(
            edge
            for edge in self._edges
            if edge.run_id == run_id and edge.owner_id == owner_id
        )


def reconstruction_evidence_from_durable(
    *,
    reconstruction_id: str,
    run_id: str,
    owner_id: str,
    source_memory_ids: Sequence[str],
    generation: int,
    created_tick: int,
    policy_id: str,
    policy_version: str,
    payload_sha256: str,
    derived_trace: MemoryTrace | None,
) -> ReconstructionEvidence:
    """Build analysis evidence from durable metadata plus optional derived trace."""
    sources = tuple(source_memory_ids)
    if derived_trace is None:
        return ReconstructionEvidence(
            reconstruction_id=reconstruction_id,
            run_id=run_id,
            owner_id=owner_id,
            source_memory_ids=sources,
            concepts=(),
            entity_ids=(),
            entity_labels=(),
            relations=(),
            context_tags=(),
            location_id=None,
            confidence=0.0,
            emotional_salience=0.0,
            generation=generation,
            created_tick=created_tick,
            policy_id=policy_id,
            policy_version=policy_version,
            narrative_fingerprint=payload_sha256,
            content_available=False,
        )
    source_ids = derived_trace.lineage.source_memory_ids or tuple(
        MemoryId(item) for item in sources
    )
    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId(reconstruction_id),
        owner_id=AgentId(owner_id),
        narrative="durable",
        concepts=derived_trace.concepts,
        entities=derived_trace.entities,
        relations=derived_trace.relations,
        context=derived_trace.context,
        confidence=derived_trace.confidence,
        emotional_salience=derived_trace.emotional_salience,
        source_memory_ids=source_ids,
        generation=generation,
        reconstructed_at_tick=created_tick,
        policy_id=policy_id,
        policy_version=policy_version,
        used_provider=False,
        fallback_used=False,
    )
    evidence = evidence_from_reconstructed_memory(
        run_id=run_id, reconstructed=reconstructed
    )
    return ReconstructionEvidence(
        reconstruction_id=evidence.reconstruction_id,
        run_id=evidence.run_id,
        owner_id=evidence.owner_id,
        source_memory_ids=evidence.source_memory_ids,
        concepts=evidence.concepts,
        entity_ids=evidence.entity_ids,
        entity_labels=evidence.entity_labels,
        relations=evidence.relations,
        context_tags=evidence.context_tags,
        location_id=evidence.location_id,
        confidence=evidence.confidence,
        emotional_salience=evidence.emotional_salience,
        generation=evidence.generation,
        created_tick=evidence.created_tick,
        policy_id=evidence.policy_id,
        policy_version=evidence.policy_version,
        narrative_fingerprint=payload_sha256,
        content_available=True,
    )
