"""Lifecycle event schema v9 and write-pair priority."""

from __future__ import annotations

import logging

import pytest

from simulation.persistence import checkpoint_schema_for_production
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V5,
    EVENT_SCHEMA_REPLAY_V8,
    EVENT_SCHEMA_REPLAY_V9,
    AgentCreated,
    AgentEnteredWorld,
    LifecycleStageChanged,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.lifecycle import DependencyStatus, OriginProvenance

_LOG = logging.getLogger("tests.lifecycle_events_schema_v9")


def _system_cause() -> SystemCause:
    return SystemCause(
        RequestId("sys-lifecycle-1"),
        SystemEffectFamily.LIFECYCLE,
        EntityId("body-1"),
        0,
    )


def _event(details: object, *, schema_version: int):
    return make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=5,
        sequence=0,
        cause=_system_cause(),
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=build_occurrence_context(
            details,  # type: ignore[arg-type]
            origin_location_id=EntityId("loc-1"),
        ),
        schema_version=schema_version,
    )


def test_write_pair_priority_lifecycle_over_artifacts() -> None:
    _LOG.debug("case_id=write_pair_lifecycle")
    assert checkpoint_schema_for_production(
        production_active=True,
        dynamics_active=True,
        artifacts_active=True,
        lifecycle_active=True,
    ) == (EVENT_SCHEMA_REPLAY_V9, "v6")
    assert checkpoint_schema_for_production(
        production_active=True,
        dynamics_active=True,
        artifacts_active=True,
        lifecycle_active=False,
    ) == (EVENT_SCHEMA_REPLAY_V8, "v5")


def test_lifecycle_details_require_schema_v9() -> None:
    _LOG.debug("case_id=lifecycle_requires_v9")
    details = AgentCreated(
        body_id=EntityId("body-new"),
        agent_id="agent-new",
        generation_index=1,
        cohort_id="cohort-0005",
        provenance=OriginProvenance.DEMOGRAPHIC_POLICY.value,
    )
    with pytest.raises(ValueError):
        _event(details, schema_version=EVENT_SCHEMA_REPLAY_V5)


def test_lifecycle_details_accept_schema_v9() -> None:
    _LOG.debug("case_id=lifecycle_accept_v9")
    created = AgentCreated(
        body_id=EntityId("body-new"),
        agent_id="agent-new",
        generation_index=1,
        cohort_id="cohort-0005",
        provenance=OriginProvenance.DEMOGRAPHIC_POLICY.value,
    )
    entered = AgentEnteredWorld(
        body_id=EntityId("body-new"),
        agent_id="agent-new",
        location_id=EntityId("loc-1"),
        entry_tick=5,
    )
    stage = LifecycleStageChanged(
        body_id=EntityId("body-1"),
        previous_stage="infant",
        new_stage="juvenile",
        chronological_age=3,
        dependency_status=DependencyStatus.INDEPENDENT.value,
    )
    for details in (created, entered, stage):
        event = _event(details, schema_version=EVENT_SCHEMA_REPLAY_V9)
        assert event.schema_version == EVENT_SCHEMA_REPLAY_V9
        assert event.details.kind == details.kind


def test_agent_created_forbids_bootstrap_provenance() -> None:
    _LOG.debug("case_id=created_forbids_bootstrap")
    with pytest.raises(ValueError, match="lifecycle_bootstrap_no_created_event"):
        AgentCreated(
            body_id=EntityId("body-1"),
            agent_id="agent-1",
            generation_index=0,
            cohort_id="cohort-bootstrap",
            provenance=OriginProvenance.BOOTSTRAP.value,
        )
