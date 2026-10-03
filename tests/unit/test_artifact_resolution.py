"""WorldEngine resolution for Inscribe/Amend/Erase/TransferArtifact."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from observer.adapt import adapt_event
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import (
    PhysicalWorldFixture,
    physical_config,
    two_location_fixture,
)
from tests.simulation_helpers import alive_body
from world.actions import (
    Amend,
    Erase,
    Inscribe,
    Take,
    TransferArtifact,
)
from world.artifacts import (
    MAX_HELD_ARTIFACTS_PER_BODY,
    ArtifactContent,
    ArtifactKind,
    ArtifactRelation,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V8,
    ArtifactCreated,
    ArtifactDestroyed,
    ArtifactModified,
    ArtifactMoved,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_ARTIFACT_DETAILS = (
    ArtifactCreated,
    ArtifactModified,
    ArtifactMoved,
    ArtifactDestroyed,
)


def _content(*marks: str, relations: tuple[ArtifactRelation, ...] = ()) -> ArtifactContent:
    return ArtifactContent(marks=marks, relations=relations)


def _engine(
    fixture: PhysicalWorldFixture | None = None,
    *,
    seed: int = 1,
) -> WorldEngine:
    world = fixture if fixture is not None else two_location_fixture()
    return WorldEngine(
        config=physical_config(seed),
        bootstrap=world.as_bootstrap(),
        artifacts_enabled=True,
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _artifact_details(result: object) -> list[object]:
    return [
        record.event.details
        for record in result.events  # type: ignore[attr-defined]
        if type(record.event.details) in _ARTIFACT_DETAILS
    ]


def _created_id(result: object) -> EntityId:
    details = _artifact_details(result)
    assert len(details) == 1
    assert type(details[0]) is ArtifactCreated
    return details[0].artifact_id


def test_inscribe_ground_creates_with_author_and_revision_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    with caplog.at_level(logging.INFO, logger="simulation.engine"):
        result = _act(
            engine,
            "agent-1",
            Inscribe(kind=ArtifactKind.SIGN, content=_content("water", "north")),
        )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    details = _artifact_details(result)
    assert len(details) == 1
    created = details[0]
    assert type(created) is ArtifactCreated
    assert created.author_id == EntityId("body-1")
    assert created.content_revision == 0
    assert created.resulting_location_id == EntityId("loc-1")
    assert created.resulting_holder_id is None
    assert created.artifact_kind is ArtifactKind.SIGN
    artifact = engine._snapshot.world.state.artifacts[created.artifact_id]
    assert artifact.author_id == EntityId("body-1")
    assert artifact.created_tick == 0
    assert artifact.content_revision == 0
    assert created.artifact_id not in engine._snapshot.world.state.bodies[
        EntityId("body-1")
    ].inventory
    assert all(record.event.schema_version == EVENT_SCHEMA_REPLAY_V8 for record in result.events)
    assert any(
        "artifact_event_committed" in record.getMessage()
        and "kind=artifact_created" in record.getMessage()
        for record in caplog.records
    )


def test_inscribe_hold_places_outside_inventory() -> None:
    engine = _engine()
    result = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.NOTE, content=_content("memo"), hold=True),
    )
    created = _artifact_details(result)[0]
    assert type(created) is ArtifactCreated
    assert created.resulting_holder_id == EntityId("body-1")
    assert created.resulting_location_id is None
    body = engine._snapshot.world.state.bodies[EntityId("body-1")]
    assert created.artifact_id not in body.inventory
    held = engine._snapshot.world.state.artifacts[created.artifact_id]
    assert held.holder_id == EntityId("body-1")


def test_inscribe_hold_cap_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    for _ in range(MAX_HELD_ARTIFACTS_PER_BODY):
        result = _act(
            engine,
            "agent-1",
            Inscribe(kind=ArtifactKind.MARK, content=_content("dot"), hold=True),
        )
        assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        rejected = _act(
            engine,
            "agent-1",
            Inscribe(kind=ArtifactKind.NOTE, content=_content("overflow"), hold=True),
        )
    assert rejected.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert _artifact_details(rejected) == []
    assert any("artifact_hold_cap" in record.getMessage() for record in caplog.records)


def test_amend_increments_revision_and_emits_modified() -> None:
    engine = _engine()
    first = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.RECORD, content=_content("old")),
    )
    artifact_id = _created_id(first)
    second = _act(
        engine,
        "agent-1",
        Amend(artifact_id=artifact_id, content=_content("new")),
    )
    assert second.resolutions[0].status is ActionResolutionStatus.APPLIED
    details = _artifact_details(second)
    assert len(details) == 1
    modified = details[0]
    assert type(modified) is ArtifactModified
    assert modified.content_revision == 1
    assert modified.artifact_id == artifact_id
    stored = engine._snapshot.world.state.artifacts[artifact_id]
    assert stored.content.marks == ("new",)
    assert stored.content_revision == 1


def test_erase_removes_entity_and_emits_destroyed() -> None:
    engine = _engine()
    first = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.MEMORIAL, content=_content("name")),
    )
    artifact_id = _created_id(first)
    erased = _act(engine, "agent-1", Erase(artifact_id=artifact_id))
    assert erased.resolutions[0].status is ActionResolutionStatus.APPLIED
    details = _artifact_details(erased)
    assert len(details) == 1
    assert type(details[0]) is ArtifactDestroyed
    assert details[0].artifact_id == artifact_id
    assert artifact_id not in engine._snapshot.world.state.artifacts


def test_transfer_claim_deposit_give_and_fixed_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    note = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.NOTE, content=_content("pass")),
    )
    note_id = _created_id(note)

    claimed = _act(
        engine,
        "agent-1",
        TransferArtifact(artifact_id=note_id, mode="claim"),
    )
    assert claimed.resolutions[0].status is ActionResolutionStatus.APPLIED
    moved = _artifact_details(claimed)[0]
    assert type(moved) is ArtifactMoved
    assert moved.resulting_holder_id == EntityId("body-1")
    assert moved.resulting_location_id is None
    moved_world_event = next(
        record.event
        for record in claimed.events
        if type(record.event.details) is ArtifactMoved
    )
    assert adapt_event(moved_world_event).type == "ARTIFACT_MOVED"

    deposited = _act(
        engine,
        "agent-1",
        TransferArtifact(artifact_id=note_id, mode="deposit"),
    )
    assert deposited.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert _artifact_details(deposited)[0].resulting_location_id == EntityId("loc-1")

    _act(engine, "agent-1", TransferArtifact(artifact_id=note_id, mode="claim"))
    given = _act(
        engine,
        "agent-1",
        TransferArtifact(
            artifact_id=note_id,
            mode="give",
            recipient_id=EntityId("body-2"),
        ),
    )
    assert given.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert _artifact_details(given)[0].resulting_holder_id == EntityId("body-2")
    assert note_id not in engine._snapshot.world.state.bodies[EntityId("body-2")].inventory

    sign = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.SIGN, content=_content("fixed")),
    )
    sign_id = _created_id(sign)
    rejected = _act(
        engine,
        "agent-1",
        TransferArtifact(artifact_id=sign_id, mode="claim"),
    )
    assert rejected.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert rejected.resolutions[0].reason.value == "structural_rejection"

    memorial = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.MEMORIAL, content=_content("stone")),
    )
    memorial_id = _created_id(memorial)
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        memorial_rejected = _act(
            engine,
            "agent-1",
            TransferArtifact(artifact_id=memorial_id, mode="claim"),
        )
    assert memorial_rejected.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert memorial_rejected.resolutions[0].reason.value == "structural_rejection"
    assert any(
        "artifact_not_portable" in record.getMessage() for record in caplog.records
    )


def test_take_on_artifact_id_rejects_not_an_item(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    created = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.MAP, content=_content("trail")),
    )
    artifact_id = _created_id(created)
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        rejected = _act(engine, "agent-1", Take(artifact_id))
    assert rejected.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert _artifact_details(rejected) == []
    assert any("not_an_item" in record.getMessage() for record in caplog.records)


def test_amend_requires_colocation_or_hold() -> None:
    base = two_location_fixture()
    fixture = PhysicalWorldFixture(
        world_id=base.world_id,
        locations=base.locations,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-2"),
        ),
        items=base.items,
        resources=base.resources,
        weather=base.weather,
        registrations=base.registrations,
    )
    engine = _engine(fixture)
    first = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.NOTE, content=_content("here")),
    )
    artifact_id = _created_id(first)
    far = _act(
        engine,
        "agent-2",
        Amend(artifact_id=artifact_id, content=_content("elsewhere")),
    )
    assert far.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_give_requires_living_colocated_recipient() -> None:
    base = two_location_fixture()
    fixture = PhysicalWorldFixture(
        world_id=base.world_id,
        locations=base.locations,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-2"),
        ),
        items=base.items,
        resources=base.resources,
        weather=base.weather,
        registrations=base.registrations,
    )
    engine = _engine(fixture)
    held = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.NOTE, content=_content("gift"), hold=True),
    )
    artifact_id = _created_id(held)
    rejected = _act(
        engine,
        "agent-1",
        TransferArtifact(
            artifact_id=artifact_id,
            mode="give",
            recipient_id=EntityId("body-2"),
        ),
    )
    assert rejected.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_unknown_artifact_rejects() -> None:
    engine = _engine()
    result = _act(
        engine,
        "agent-1",
        Erase(artifact_id=EntityId("missing-art")),
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert _artifact_details(result) == []
