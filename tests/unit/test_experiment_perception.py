"""Experiment occurrences redact the hypothesis and the law table."""

from __future__ import annotations

import logging

import pytest

from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
from world._perception import (
    _project_event_window,
    _public_facts_for_role,
    _success_fact,
)
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V15,
    ExperimentResolved,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import ObservationAudienceRole

pytestmark = pytest.mark.unit


def _event(outcome: str) -> object:
    details = ExperimentResolved(
        operator="combine",
        operand_a_id=EntityId("item-1"),
        process_token="none",
        outcome_class=outcome,
        delta="none",
        discovery_mode="deliberate",
    )
    return make_physical_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        cause=ActionCause(request_id=RequestId("req-1"), actor_id=EntityId("body-1")),
        resulting_revision=WorldRevision(1),
        details=details,
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V15,
    )


def test_actor_facts_include_operator_and_discovery_mode() -> None:
    event = _event("success")
    facts = _public_facts_for_role(event, ObservationAudienceRole.ACTOR)
    assert set(facts) == {
        "kind",
        "outcome_class",
        "delta",
        "operator",
        "discovery_mode",
    }
    assert facts["discovery_mode"] == "deliberate"
    assert "hypothesis_id" not in facts


def test_bystander_facts_omit_operator_and_discovery_mode() -> None:
    event = _event("failure")
    facts = _public_facts_for_role(event, ObservationAudienceRole.BYSTANDER)
    assert set(facts) == {"kind", "outcome_class", "delta"}


@pytest.mark.parametrize(
    ("outcome", "success"),
    [
        ("success", True),
        ("partial_success", True),
        ("failure", False),
        ("harm", False),
        ("unexpected", None),
    ],
)
def test_success_bool_follows_outcome_class(outcome: str, success: bool | None) -> None:
    assert _success_fact(_event(outcome)) is success


def test_distant_agent_receives_no_occurrence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = _event("unexpected")
    with caplog.at_level(logging.DEBUG, logger="world._perception"):
        actor_rows, _ = _project_event_window(
            observer_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            content_visible=True,
            prior_events=(event,),  # type: ignore[arg-type]
        )
        bystander_rows, _ = _project_event_window(
            observer_id=EntityId("body-2"),
            location_id=EntityId("loc-1"),
            content_visible=True,
            prior_events=(event,),  # type: ignore[arg-type]
        )
        distant_rows, _ = _project_event_window(
            observer_id=EntityId("body-3"),
            location_id=EntityId("loc-2"),
            content_visible=True,
            prior_events=(event,),  # type: ignore[arg-type]
        )
    assert actor_rows[0].audience_role is ObservationAudienceRole.ACTOR
    assert "operator" in actor_rows[0].public_facts
    assert bystander_rows[0].audience_role is ObservationAudienceRole.BYSTANDER
    assert "operator" not in bystander_rows[0].public_facts
    assert distant_rows == ()
    assert "viewer_role=actor" in caplog.text
    assert "viewer_role=bystander" in caplog.text


def test_semantic_type_count_is_54_and_protocol_unchanged() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 54
    assert "EXPERIMENT_RESOLVED" in SEMANTIC_EVENT_TYPES
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
