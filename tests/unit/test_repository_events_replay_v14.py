"""Replay-v14 knowledge repository event details and encode/decode."""

from __future__ import annotations

import pytest

from simulation.serialization import decode_domain, encode_domain
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V13,
    EVENT_SCHEMA_REPLAY_V14,
    OccurrenceContext,
    RepositoryEstablished,
    RepositoryIndexed,
    RepositoryMaintained,
    RepositoryMemberDeposited,
    RepositoryMemberRetrieved,
    RepositoryNeglected,
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


def _action_cause() -> ActionCause:
    return ActionCause(
        request_id=RequestId("req-1"),
        actor_id=EntityId("body-1"),
    )


def _system_cause() -> SystemCause:
    return SystemCause(
        RequestId("sys-repo-1"),
        SystemEffectFamily.KNOWLEDGE_REPOSITORY,
        EntityId("repo-1"),
        0,
    )


def _event(details: object, *, schema_version: int, cause: object | None = None):
    return make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=cause if cause is not None else _action_cause(),
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=schema_version,
    )


def test_repository_details_require_v14() -> None:
    details = RepositoryEstablished(
        EntityId("repo-1"),
        EntityId("loc-1"),
        None,
        (EntityId("body-1"),),
        "open",
        0,
    )
    with pytest.raises(ValueError):
        _event(details, schema_version=EVENT_SCHEMA_REPLAY_V13)
    ok = _event(details, schema_version=EVENT_SCHEMA_REPLAY_V14)
    assert ok.schema_version == EVENT_SCHEMA_REPLAY_V14


def test_repository_detail_round_trip() -> None:
    samples = (
        RepositoryEstablished(
            EntityId("repo-1"),
            EntityId("loc-1"),
            EntityId("struct-1"),
            (EntityId("body-1"),),
            "founder_list",
            3,
        ),
        RepositoryMemberDeposited(
            EntityId("repo-1"), EntityId("art-1"), 1, EntityId("body-1")
        ),
        RepositoryMemberRetrieved(
            EntityId("repo-1"), EntityId("art-1"), 0, EntityId("body-1"), True
        ),
        RepositoryMaintained(
            EntityId("repo-1"), "maintain", "neglected", "intact", 4
        ),
        RepositoryIndexed(EntityId("repo-1"), 2, 1),
        RepositoryNeglected(EntityId("repo-1"), 1, "intact", "neglected", 1),
    )
    for details in samples:
        cause = (
            _system_cause()
            if type(details) is RepositoryNeglected
            else _action_cause()
        )
        event = _event(
            details, schema_version=EVENT_SCHEMA_REPLAY_V14, cause=cause
        )
        encoded = encode_domain(event)
        decoded = decode_domain(encoded)
        assert type(decoded.details) is type(details)
        assert decoded.schema_version == EVENT_SCHEMA_REPLAY_V14
