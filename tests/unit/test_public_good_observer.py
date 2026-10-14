"""Public-good events remain read-only observer facts."""

from __future__ import annotations

import logging

import pytest

from observer.adapt import adapt_event
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V20,
    PublicGoodBenefit,
    PublicGoodMaintained,
    PublicGoodOpposed,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def _event(details: object, *, event_id: str):
    actor_id = details.actor_id  # type: ignore[attr-defined]
    cause = ActionCause(RequestId(f"request-{event_id}"), actor_id)
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id="run-public-goods",
        world_id=WorldId("world-public-goods"),
        tick=3,
        sequence=0,
        cause=cause,
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=build_occurrence_context(
            details,  # type: ignore[arg-type]
            origin_location_id=EntityId("loc-1"),
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V20,
    )


def test_public_good_semantics_keep_actor_project_and_location(
    caplog: pytest.LogCaptureFixture,
) -> None:
    project_id = EntityId("project-well")
    actor_id = EntityId("body-a")
    details = (
        PublicGoodBenefit(
            project_id=project_id,
            actor_id=actor_id,
            project_kind="well",
            benefit_code="draw",
            source="command",
            integrity_millis=1000,
            resulting_thirst=4.0,
        ),
        PublicGoodMaintained(
            project_id=project_id,
            actor_id=actor_id,
            accepted=True,
            integrity_millis=1000,
        ),
        PublicGoodOpposed(
            project_id=project_id,
            actor_id=actor_id,
            status="completed",
            integrity_millis=750,
        ),
    )

    with caplog.at_level(logging.DEBUG, logger="observer.adapt"):
        rows = tuple(
            adapt_event(_event(detail, event_id=f"event-{index}"))
            for index, detail in enumerate(details)
        )

    assert tuple(row.type for row in rows) == (
        "PUBLIC_GOOD_BENEFIT",
        "PUBLIC_GOOD_MAINTAINED",
        "PUBLIC_GOOD_OPPOSED",
    )
    assert all(row.actor_id == actor_id.value for row in rows)
    assert all(row.target_id == project_id.value for row in rows)
    assert all(row.origin_location_id == "loc-1" for row in rows)
    assert "observer_event_adapted kind=public_good_benefit" in caplog.text
