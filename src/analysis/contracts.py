"""Read-only analysis ports. No live aggregates or mutable repositories.

Evidence composition (persistence readers → these ports) lives in
``experiments.composition``. Analysis must never import persistence; persistence
must never import analysis; API must never import analysis.
"""

from __future__ import annotations

from typing import Protocol

from analysis.models import ReconstructionEvidence, SubjectiveDerivationEdge
from memory.models import MemoryTrace
from simulation.models import SimulationExport
from world.events import WorldEvent
from world.identifiers import EventId

__all__ = [
    "EventSource",
    "ExportSource",
    "MemoryEvidenceSource",
    "ObjectiveEventSource",
]


class EventSource(Protocol):
    """Yields immutable objective events. Must not expose WorldState."""

    def events(self) -> tuple[WorldEvent, ...]:
        """Return a detached snapshot of world events."""
        ...


class ExportSource(Protocol):
    """Yields a versioned run export. Must not mutate simulation state."""

    def export(self) -> SimulationExport:
        """Return metadata plus immutable events for offline analysis."""
        ...


class ObjectiveEventSource(Protocol):
    """Experiment-only reader of immutable objective events by run.

    Must not be injected into agents, cognition, memory, or reconstruction.
    """

    def events_for_run(self, run_id: str) -> tuple[WorldEvent, ...]:
        """Return detached events for ``run_id`` (possibly empty)."""
        ...

    def event_by_id(self, run_id: str, event_id: EventId) -> WorldEvent | None:
        """Return one event when present in ``run_id``; never invent."""
        ...


class MemoryEvidenceSource(Protocol):
    """Read-only subjective memory/reconstruction evidence for one scope.

    Implementations must not expose WorldEvent payloads or world authority.
    """

    def traces(self, *, run_id: str, owner_id: str) -> tuple[MemoryTrace, ...]:
        """Return detached traces for the run/owner scope."""
        ...

    def reconstructions(
        self, *, run_id: str, owner_id: str
    ) -> tuple[ReconstructionEvidence, ...]:
        """Return reconstruction evidence for the run/owner scope."""
        ...

    def derivation_edges(
        self, *, run_id: str, owner_id: str
    ) -> tuple[SubjectiveDerivationEdge, ...]:
        """Return ordered derivation edges for provenance traversal."""
        ...
