"""Read-only analysis ports. No live aggregates or mutable repositories."""

from __future__ import annotations

from typing import Protocol

from simulation.models import SimulationExport
from world.events import WorldEvent


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
