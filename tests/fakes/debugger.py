"""In-memory debugger event lookup fake for unit tests."""

from __future__ import annotations

from simulation.causal_debugger import (
    DebuggerEventRecord,
    InMemoryDebuggerEventLookup,
)
from simulation.models import RunId

__all__ = [
    "DebuggerEventRecord",
    "InMemoryDebuggerEventLookup",
    "seed_attack_event",
]


def seed_attack_event(
    lookup: InMemoryDebuggerEventLookup,
    *,
    run_id: RunId,
    event_id: str = "evt-attack-1",
    tick: int = 1832,
    sequence: int = 17,
    actor_id: str = "alice",
) -> DebuggerEventRecord:
    """Seed a canonical Alice-attacked-Bob style committed event record."""
    record = DebuggerEventRecord(
        event_id=event_id,
        tick=tick,
        sequence=sequence,
        actor_id=actor_id,
        agent_id=actor_id,
        detail_kind="attack",
        semantic_type="AGENT_ATTACKED",
        detail_type_name="Attacked",
    )
    lookup.seed(run_id=run_id, record=record)
    return record
