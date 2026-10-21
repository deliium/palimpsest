"""Detached carrier projection and provenance classification."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.institutional_memory import (
    InstitutionalCarrierRow,
    institutional_memory_carrier_rows_from_events,
)


def _event(kind, *, actor, tick, sequence, details=None):
    return SimpleNamespace(
        kind=SimpleNamespace(value=kind),
        actor_id=SimpleNamespace(value=actor),
        tick=tick,
        sequence=sequence,
        event_id=SimpleNamespace(value=f"event-{sequence}"),
        run_id=SimpleNamespace(value="run"),
        details=details or SimpleNamespace(),
    )


def test_carrier_projection_keeps_delivery_and_artifact_revision() -> None:
    events = (
        _event(
            "told",
            actor="body-a",
            tick=1,
            sequence=2,
            details=SimpleNamespace(recipient_id=SimpleNamespace(value="body-b")),
        ),
        _event(
            "artifact_copied",
            actor="body-a",
            tick=2,
            sequence=1,
            details=SimpleNamespace(
                artifact_id=SimpleNamespace(value="child"),
                content_revision=0,
                parent_artifact_id=SimpleNamespace(value="parent"),
                source_artifact_id=SimpleNamespace(value="parent"),
            ),
        ),
        _event("waited", actor="body-a", tick=2, sequence=3),
    )
    rows = institutional_memory_carrier_rows_from_events(events)
    assert len(rows) == 2
    assert rows[0].kind == "told"
    assert rows[0].recipient_entity_id == "body-b"
    assert rows[1].artifact_id == "child"
    assert rows[1].parent_artifact_id == "parent"


def test_carrier_rows_are_deterministic_and_typed() -> None:
    first = _event("artifact_created", actor="body-a", tick=1, sequence=2)
    second = _event("artifact_created", actor="body-b", tick=1, sequence=1)
    rows = institutional_memory_carrier_rows_from_events((first, second))
    assert all(type(row) is InstitutionalCarrierRow for row in rows)
    assert [row.sequence for row in rows] == [1, 2]


def test_unrelated_events_are_ignored() -> None:
    rows = institutional_memory_carrier_rows_from_events(
        (_event("moved", actor="body-a", tick=1, sequence=1),)
    )
    assert rows == ()
