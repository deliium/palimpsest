"""AgentInitializationRecorded requires event schema v10."""

from __future__ import annotations

import logging

import pytest

from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V9,
    EVENT_SCHEMA_REPLAY_V10,
    AgentInitializationRecorded,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

_LOG = logging.getLogger("tests.new_agent_events_schema_v10")

_INITIAL = {
    "carry_capacity": 10.0,
    "dependency_status": "independent",
    "fatigue": 0.0,
    "health": 1.0,
    "hunger": 0.0,
    "location_id": "loc-1",
    "stage": "infant",
    "temperature": 20.0,
    "thirst": 0.0,
}


def _event(*, schema_version: int):
    details = AgentInitializationRecorded(
        body_id=EntityId("body-new"),
        agent_id="agent-new",
        creation_reason="demographic_policy",
        origin_refs=(),
        initial_conditions=_INITIAL,
        creation_config_id="nai-deadbeefdeadbeefdeadbeefdeadbeef",
    )
    return make_physical_replayable_event(
        event_id=EventId("evt-init-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=5,
        sequence=0,
        cause=SystemCause(
            RequestId("sys-init-1"),
            SystemEffectFamily.LIFECYCLE,
            EntityId("body-new"),
            1,
        ),
        resulting_revision=WorldRevision(1),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId("loc-1")
        ),
        schema_version=schema_version,
    )


def test_initialization_recorded_illegal_on_schema_v9() -> None:
    _LOG.debug("case_id=init_requires_v10")
    with pytest.raises(ValueError):
        _event(schema_version=EVENT_SCHEMA_REPLAY_V9)


def test_initialization_recorded_legal_on_schema_v10() -> None:
    _LOG.debug("case_id=init_accepts_v10")
    event = _event(schema_version=EVENT_SCHEMA_REPLAY_V10)
    assert event.details.kind == "agent_initialization_recorded"
    assert event.schema_version == EVENT_SCHEMA_REPLAY_V10
