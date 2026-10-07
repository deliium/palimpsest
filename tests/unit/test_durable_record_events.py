"""Replay-v13 durable record event details and schema gates."""

from __future__ import annotations

import pytest

from simulation.serialization import decode_domain, encode_domain
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V8,
    EVENT_SCHEMA_REPLAY_V12,
    EVENT_SCHEMA_REPLAY_V13,
    ArtifactAnnotated,
    ArtifactCopied,
    ArtifactDamaged,
    ArtifactDestroyed,
    ArtifactPartiallyLost,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)

pytestmark = pytest.mark.unit


def _cause() -> ActionCause:
    return ActionCause(
        request_id=RequestId("req-1"),
        actor_id=EntityId("body-1"),
    )


def _event(details: object, *, schema_version: int):
    return make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=_cause(),
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=schema_version,
    )


def test_durable_details_require_v13() -> None:
    details = ArtifactCopied(
        child_artifact_id=EntityId("art-child"),
        parent_artifact_id=EntityId("art-parent"),
        source_artifact_id=EntityId("art-parent"),
        fidelity_mode="perfect",
        copy_generation=1,
        content_revision=0,
        record_genre="chronicle",
    )
    with pytest.raises(ValueError):
        _event(details, schema_version=EVENT_SCHEMA_REPLAY_V12)
    with pytest.raises(ValueError):
        _event(details, schema_version=EVENT_SCHEMA_REPLAY_V8)
    ok = _event(details, schema_version=EVENT_SCHEMA_REPLAY_V13)
    assert ok.schema_version == EVENT_SCHEMA_REPLAY_V13


def test_tombstone_destroy_requires_v13() -> None:
    details = ArtifactDestroyed(
        EntityId("art-1"),
        __import__("world.artifacts", fromlist=["ArtifactKind"]).ArtifactKind.RECORD,
        0,
        tombstone=True,
    )
    with pytest.raises(ValueError):
        _event(details, schema_version=EVENT_SCHEMA_REPLAY_V8)
    ok = _event(details, schema_version=EVENT_SCHEMA_REPLAY_V13)
    assert ok.details.tombstone is True  # type: ignore[attr-defined]


def test_durable_detail_round_trip() -> None:
    from world.artifacts import ArtifactKind

    samples = (
        ArtifactCopied(
            EntityId("c"),
            EntityId("p"),
            EntityId("s"),
            "lossy",
            2,
            0,
            "story",
        ),
        ArtifactAnnotated(EntityId("a"), 1, 2, "intact"),
        ArtifactDamaged(EntityId("a"), "intact", "damaged", 1, 3),
        ArtifactPartiallyLost(EntityId("a"), 1, 2, 4, "partially_lost"),
        ArtifactDestroyed(
            EntityId("a"), ArtifactKind.NOTE, 1, tombstone=True, integrity="destroyed"
        ),
    )
    for details in samples:
        event = _event(details, schema_version=EVENT_SCHEMA_REPLAY_V13)
        encoded = encode_domain(event)
        decoded = decode_domain(encoded)
        assert type(decoded) is type(event)
        assert type(decoded.details) is type(details)  # type: ignore[union-attr]
        assert decoded.schema_version == EVENT_SCHEMA_REPLAY_V13  # type: ignore[union-attr]
