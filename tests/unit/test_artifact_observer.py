"""Observer projects objective artifacts without per-agent readings."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from api.observer_service import _frame_out
from observer.adapt import adapt_event, adapt_events
from observer.contracts import (
    ObserverContractError,
    ObserverEvent,
    ObserverWorldState,
)
from observer.layout import catalog_from_mapping
from observer.presentation import entity_presentation
from observer.project import project_frame
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
from simulation.bootstrap import WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.observer_facts import ObjectiveFacts, scene_from_facts
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import Amend, Erase, Inscribe, TransferArtifact
from world.artifacts import ArtifactContent, ArtifactKind, InformationArtifact
from world.events import (
    EVENT_SCHEMA_REPLAY_V8,
    ArtifactCreated,
    ArtifactDestroyed,
    ArtifactModified,
    ArtifactMoved,
    OccurrenceContext,
    WorldEvent,
    make_physical_replayable_event,
)
from world.effects import ActionCause
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_FORBIDDEN = frozenset(
    {"screen_x", "screen_y", "pixels", "sprite", "animation", "dx", "dy"}
)
_LAYOUT = catalog_from_mapping(
    {
        "schema_version": "observer-layout-v1",
        "layout_id": "artifact-empty",
        "locations": [],
    }
)
_ARTIFACT_SEMANTIC = (
    "ARTIFACT_CREATED",
    "ARTIFACT_MODIFIED",
    "ARTIFACT_MOVED",
    "ARTIFACT_DESTROYED",
)


def _names(value: object) -> set[str]:
    slots = getattr(type(value), "__slots__", ())
    return {str(item) for item in slots}


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(marks=marks)


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _cause() -> ActionCause:
    return ActionCause(request_id=RequestId("req-1"), actor_id=EntityId("body-1"))


def _world_event(details: object, *, sequence: int = 0) -> WorldEvent:
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{sequence}"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=sequence,
        cause=_cause(),
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V8,
    )


def test_semantic_catalog_appends_four_artifact_types() -> None:
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert len(SEMANTIC_EVENT_TYPES) == 36
    assert SEMANTIC_EVENT_TYPES[-4:] == _ARTIFACT_SEMANTIC
    assert SEMANTIC_EVENT_TYPES[:32] == (
        "AGENT_MOVED",
        "AGENT_SEARCHED",
        "AGENT_TOOK_ITEM",
        "AGENT_DROPPED_ITEM",
        "AGENT_GAVE_ITEM",
        "AGENT_ATE_ITEM",
        "AGENT_DRANK",
        "AGENT_SLEPT",
        "AGENT_TALKED",
        "AGENT_ASKED",
        "AGENT_TOLD",
        "AGENT_HELPED",
        "AGENT_ATTACKED",
        "AGENT_FLED",
        "AGENT_WAITED",
        "WEATHER_CHANGED",
        "RESOURCE_REGENERATED",
        "NEEDS_APPLIED",
        "EXPOSURE_APPLIED",
        "AGENT_DIED",
        "RESOURCE_HARVESTED",
        "CRAFT_STARTED",
        "ITEM_CRAFTED",
        "STRUCTURE_BUILT",
        "STRUCTURE_REPAIRED",
        "ITEM_STORED",
        "SEASON_CHANGED",
        "TEMPERATURE_BAND_CHANGED",
        "RESOURCE_NODE_DEPLETED",
        "RESOURCE_NODE_RECOVERED",
        "ENVIRONMENTAL_HAZARD_STARTED",
        "ENVIRONMENTAL_HAZARD_ENDED",
    )


def test_artifact_presentation_catalog_rows() -> None:
    for kind in ("mark", "sign", "note", "map", "record", "memorial"):
        presentation = entity_presentation(kind, kind)
        assert presentation is not None
        assert presentation.visual_category == "artifact"
        assert presentation.icon_key == f"artifact_{kind}"
        assert presentation.size_category == "small"
        assert presentation.display_label == kind


def test_adapt_event_maps_artifact_kinds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    details = (
        ArtifactCreated(
            EntityId("art-1"),
            ArtifactKind.SIGN,
            EntityId("body-1"),
            0,
            resulting_location_id=EntityId("loc-1"),
        ),
        ArtifactModified(
            EntityId("art-1"),
            ArtifactKind.SIGN,
            1,
            resulting_location_id=EntityId("loc-1"),
        ),
        ArtifactMoved(
            EntityId("art-2"),
            ArtifactKind.NOTE,
            0,
            resulting_holder_id=EntityId("body-1"),
        ),
        ArtifactDestroyed(EntityId("art-1"), ArtifactKind.SIGN, 1),
    )
    with caplog.at_level(logging.DEBUG, logger="observer.adapt"):
        adapted = [adapt_event(_world_event(item, sequence=index)) for index, item in enumerate(details)]
    assert [item.type for item in adapted] == list(_ARTIFACT_SEMANTIC)
    assert all(item.artifact_id is not None for item in adapted)
    assert adapted[0].public_mapping()["artifact_id"] == "art-1"
    wait = ObserverEvent(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        type="AGENT_WAITED",
        domain_kind="wait",
        event_id="evt-wait",
        tick=0,
        sequence=0,
    )
    assert "artifact_id" not in wait.public_mapping()
    assert any("artifacts_projected count=1" in record.getMessage() for record in caplog.records)


def test_project_frame_orders_artifacts_without_readings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture = two_location_fixture()
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=fixture.as_bootstrap(),
        artifacts_enabled=True,
    )
    created = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.SIGN, content=_content("water", "north")),
    )
    sign_id = next(
        record.event.details.artifact_id
        for record in created.events
        if type(record.event.details) is ArtifactCreated
    )
    _act(
        engine,
        "agent-1",
        Amend(artifact_id=sign_id, content=_content("water", "east")),
    )
    note = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.NOTE, content=_content("memo"), hold=True),
    )
    note_id = next(
        record.event.details.artifact_id
        for record in note.events
        if type(record.event.details) is ArtifactCreated
    )
    _act(
        engine,
        "agent-1",
        TransferArtifact(artifact_id=note_id, mode="deposit"),
    )
    _act(engine, "agent-1", Erase(artifact_id=sign_id))

    state = engine._snapshot.world.state
    for event in engine._snapshot.event_history:
        assert _names(event).isdisjoint(_FORBIDDEN)
        assert _names(event.details).isdisjoint(_FORBIDDEN)
    assert _names(state).isdisjoint(_FORBIDDEN)

    facts = ObjectiveFacts(
        run_id=engine.run_id.value,
        world_id=engine.world_id.value,
        tick=engine._snapshot.tick.value,
        revision=state.revision.value,
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        weather=tuple(state.weather.values()),
        registrations=engine._registrations,
        artifacts=tuple(state.artifacts.values()),
    )
    with caplog.at_level(logging.DEBUG, logger="observer.project"):
        frame = project_frame(
            scene_from_facts(facts),
            _LAYOUT,
            mode="live",
            events=adapt_events(engine._snapshot.event_history),
        )
    assert frame.protocol_version == OBSERVER_PROTOCOL_VERSION
    semantic = {event.type for event in frame.events or ()}
    assert set(_ARTIFACT_SEMANTIC) <= semantic
    assert len(frame.world.artifacts) == 1
    artifact = frame.world.artifacts[0]
    assert artifact.artifact_id == note_id.value
    assert artifact.kind == "note"
    assert artifact.location_id == "loc-1"
    assert artifact.holder_id is None
    assert artifact.marks == ("memo",)
    assert artifact.presentation is not None
    assert artifact.presentation.icon_key == "artifact_note"
    assert artifact.presentation.display_label == "note"
    assert not hasattr(frame.world, "artifact_interpretations")
    assert "reading" not in frame.world.__dataclass_fields__
    assert any(
        "artifacts_projected count=1" in record.getMessage() for record in caplog.records
    )
    empty = ObserverWorldState(tick=0, revision=0)
    assert empty.artifacts == ()

    payload = _frame_out(frame)
    dumped = payload.model_dump()
    assert "artifacts" in dumped["world"]
    presented = dumped["world"]["artifacts"][0]["presentation"]
    assert presented["display_label"] == "note"
    assert presented["icon_key"] == "artifact_note"
    assert "pixels" not in dumped
    assert "sprite" not in dumped


def test_detached_facts_include_seeded_artifacts() -> None:
    fixture = two_location_fixture()
    seeded = InformationArtifact(
        artifact_id=EntityId("art-record-1"),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=0,
        content=_content("water", "north"),
        location_id=EntityId("loc-1"),
    )
    engine = WorldEngine(
        config=physical_config(2),
        bootstrap=WorldBootstrap(
            world_id=fixture.world_id,
            revision=fixture.revision,
            locations=fixture.locations,
            items=fixture.items,
            resources=fixture.resources,
            bodies=fixture.bodies,
            weather=fixture.weather,
            registrations=fixture.registrations,
            artifacts=(seeded,),
        ),
    )
    facts = engine.detached_objective_facts()
    assert len(facts.artifacts) == 1
    assert facts.artifacts[0].artifact_id == EntityId("art-record-1")
    frame = project_frame(scene_from_facts(facts), _LAYOUT, mode="live")
    assert frame.world.artifacts[0].kind == "record"
    assert frame.world.artifacts[0].marks == ("water", "north")


def test_rejects_presentation_instructions_on_events() -> None:
    with pytest.raises(ObserverContractError) as pixels:
        ObserverEvent(
            protocol_version=OBSERVER_PROTOCOL_VERSION,
            type="ARTIFACT_CREATED",
            domain_kind="artifact_created",
            event_id="evt-1",
            tick=0,
            sequence=0,
            artifact_id="art-1",
            pixels=1,  # type: ignore[call-arg]
        )
    assert pixels.value.reason_code == "presentation_instruction_forbidden"
    with pytest.raises(ObserverContractError) as inverse:
        ObserverEvent(
            protocol_version=OBSERVER_PROTOCOL_VERSION,
            type="AGENT_UNMOVED",
            domain_kind="move",
            event_id="evt-2",
            tick=0,
            sequence=0,
        )
    assert inverse.value.reason_code == "presentation_instruction_forbidden"
