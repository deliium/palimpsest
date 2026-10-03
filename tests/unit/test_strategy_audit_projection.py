"""Per-event communication-strategy audit projection (presentation only)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from observer.strategy_audit import project_strategy_audit_overlay
from world.communications import origin_utterance
from world.events import (
    EVENT_SCHEMA_REPLAY_V5,
    ActionCause,
    OccurrenceContext,
    Searched,
    Talked,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def _cited(event_id: str) -> WorldEvent:
    request = RequestId(f"r-{event_id}")
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-audit",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=request,
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V5,
        details=Searched(success=False),
        actor_id=EntityId("body-ada"),
        cause=ActionCause(request, EntityId("body-ada")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _talked(event_id: str, *, tick: int = 1) -> WorldEvent:
    request = RequestId(f"r-{event_id}")
    utterance = origin_utterance(text="hello", speaker_id=EntityId("body-ada"))
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-audit",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=0,
        request_id=request,
        resulting_revision=WorldRevision(2),
        schema_version=EVENT_SCHEMA_REPLAY_V5,
        details=Talked(EntityId("body-bo"), utterance),
        actor_id=EntityId("body-ada"),
        target_id=EntityId("body-bo"),
        cause=ActionCause(request, EntityId("body-ada")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _audit(**overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "stance": "assert_match",
        "strategy": "truthful",
        "divergence": "none",
        "source_atom_tokens": ("search", "body-ada"),
        "cited_event_id": "seen-1",
        "owner_id": SimpleNamespace(value="ada"),
        "recipient_id": SimpleNamespace(value="bo"),
        "tick": 1,
        "delivered": True,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_maps_committed_communication_event_to_category() -> None:
    # Source tokens covered by public tokens of the cited searched event.
    overlay = project_strategy_audit_overlay(
        (_audit(source_atom_tokens=("search", "body-ada")),),
        (_cited("seen-1"), _talked("evt-talk-1")),
        agent_entity_ids={"ada": "body-ada", "bo": "body-bo"},
    )
    assert overlay.layer == "research_strategy_audit"
    assert overlay.evidence_class == "ANALYTICAL_INFERRED"
    assert overlay.count == 1
    assert overlay.entries[0].event_id == "evt-talk-1"
    assert overlay.entries[0].category == "veridical"


def test_skips_undelivered_audits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="observer.strategy_audit")
    overlay = project_strategy_audit_overlay(
        (_audit(delivered=False),),
        (_talked("evt-talk-1"),),
        agent_entity_ids={"ada": "body-ada", "bo": "body-bo"},
    )
    assert overlay.count == 0
    assert any(
        "strategy_audit_projected count=0" in record.getMessage()
        for record in caplog.records
    )


def test_deception_category_is_analytical_only() -> None:
    overlay = project_strategy_audit_overlay(
        (
            _audit(
                stance="diverge",
                strategy="deliberate_false_statement",
                cited_event_id=None,
            ),
        ),
        (_talked("evt-talk-2"),),
        agent_entity_ids={"ada": "body-ada", "bo": "body-bo"},
    )
    assert overlay.count == 1
    assert overlay.entries[0].category == "deliberate_deception"
    assert overlay.entries[0].evidence_class == "ANALYTICAL_INFERRED"
