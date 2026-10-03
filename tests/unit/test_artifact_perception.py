"""Observed artifacts are objective marks only — no interpretation or icons."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.serialization import decode_domain, encode_domain
from tests.physical_helpers import (
    PhysicalWorldFixture,
    physical_config,
    two_location_fixture,
)
from tests.simulation_helpers import alive_body
from world.actions import Inscribe, TransferArtifact
from world.artifacts import ArtifactContent, ArtifactKind, ArtifactRelation
from world.events import ArtifactCreated
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import (
    CONTENT_VISIBILITY_THRESHOLD,
    Observation,
    ObservedArtifact,
    ObservedItemPlacement,
)
from world.values import UnitInterval

pytestmark = pytest.mark.unit


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(
        marks=marks,
        relations=(ArtifactRelation("water", "at", "north"),) if marks else (),
    )


def _world(*, visible: bool = True) -> PhysicalWorldFixture:
    base = two_location_fixture()
    locations = base.locations
    if not visible:
        locations = tuple(
            replace(location, visibility_factor=UnitInterval(0.0))
            for location in base.locations
        )
    return PhysicalWorldFixture(
        world_id=base.world_id,
        locations=locations,
        bodies=(
            alive_body("body-1"),
            alive_body("body-2"),
        ),
        items=base.items,
        resources=base.resources,
        weather=base.weather,
        registrations=base.registrations,
    )


def _engine(fixture: PhysicalWorldFixture | None = None) -> WorldEngine:
    world = fixture if fixture is not None else _world()
    return WorldEngine(
        config=physical_config(1),
        bootstrap=world.as_bootstrap(),
        artifacts_enabled=True,
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _created_id(result: object) -> EntityId:
    details = [
        record.event.details
        for record in result.events  # type: ignore[attr-defined]
        if type(record.event.details) is ArtifactCreated
    ]
    assert len(details) == 1
    return details[0].artifact_id


def test_content_visibility_threshold_is_half() -> None:
    assert CONTENT_VISIBILITY_THRESHOLD == 0.5


def test_ground_artifact_visible_to_colocated_observers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(_world())
    result = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.SIGN, content=_content("water", "north")),
    )
    artifact_id = _created_id(result)
    with caplog.at_level(logging.DEBUG, logger="world._perception"):
        batch = engine.observe()
    actor = batch.for_observer(EntityId("body-1"))
    bystander = batch.for_observer(EntityId("body-2"))
    assert len(actor.artifacts) == 1
    seen = actor.artifacts[0]
    assert type(seen) is ObservedArtifact
    assert seen.entity_id == artifact_id
    assert seen.kind is ArtifactKind.SIGN
    assert seen.author_id == EntityId("body-1")
    assert seen.created_tick == 0
    assert seen.content.marks == ("water", "north")
    assert seen.content_revision == 0
    assert seen.placement is ObservedItemPlacement.GROUND_HERE
    assert bystander.artifacts == actor.artifacts
    assert not hasattr(actor, "icon_key")
    assert not hasattr(actor, "display_label")
    assert not hasattr(seen, "icon_key")
    assert not hasattr(seen, "display_label")
    assert "artifacts_observed count=1" in caplog.text


def test_low_visibility_hides_ground_artifacts() -> None:
    engine = _engine(_world(visible=False))
    _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.RECORD, content=_content("cue")),
    )
    batch = engine.observe()
    actor = batch.for_observer(EntityId("body-1"))
    bystander = batch.for_observer(EntityId("body-2"))
    assert actor.artifacts == ()
    assert bystander.artifacts == ()


def test_held_by_self_always_visible_foreign_held_omitted() -> None:
    engine = _engine(_world(visible=False))
    created = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.NOTE, content=_content("private"), hold=True),
    )
    artifact_id = _created_id(created)
    batch = engine.observe()
    holder = batch.for_observer(EntityId("body-1"))
    other = batch.for_observer(EntityId("body-2"))
    assert len(holder.artifacts) == 1
    assert holder.artifacts[0].entity_id == artifact_id
    assert holder.artifacts[0].placement is ObservedItemPlacement.HELD_BY_SELF
    assert other.artifacts == ()


def test_artifact_occurrence_public_facts_exclude_marks() -> None:
    engine = _engine(_world())
    result = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.SIGN, content=_content("water", "north")),
    )
    artifact_id = _created_id(result)
    batch = engine.observe()
    actor = batch.for_observer(EntityId("body-1"))
    bystander = batch.for_observer(EntityId("body-2"))
    actor_facts = [
        occurrence.public_facts
        for occurrence in actor.occurrences
        if occurrence.kind == "artifact_created"
    ]
    bystander_facts = [
        occurrence.public_facts
        for occurrence in bystander.occurrences
        if occurrence.kind == "artifact_created"
    ]
    assert len(actor_facts) == 1
    assert len(bystander_facts) == 1
    for facts in (actor_facts[0], bystander_facts[0]):
        assert facts["artifact_id"] == artifact_id.value
        assert facts["artifact_kind"] == "sign"
        assert facts["content_revision"] == 0
        assert "marks" not in facts
        assert "relations" not in facts
        assert "water" not in facts.values()
        assert "north" not in facts.values()
        assert set(facts) == {
            "kind",
            "artifact_id",
            "artifact_kind",
            "content_revision",
        }


def test_observation_encode_always_writes_artifacts_decode_missing_as_empty() -> None:
    empty = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
    )
    encoded = encode_domain(empty)
    assert b'"artifacts":[]' in encoded
    payload = decode_domain(encoded)
    assert type(payload) is Observation
    assert payload.artifacts == ()

    import json

    raw = json.loads(encoded.decode("utf-8"))
    del raw["data"]["artifacts"]
    missing = decode_domain(json.dumps(raw, separators=(",", ":")).encode("utf-8"))
    assert type(missing) is Observation
    assert missing.artifacts == ()


def test_observed_artifact_round_trips_with_content() -> None:
    engine = _engine(_world())
    result = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.MAP, content=_content("trail"), hold=True),
    )
    artifact_id = _created_id(result)
    batch = engine.observe()
    observation = batch.for_observer(EntityId("body-1"))
    encoded = encode_domain(observation)
    decoded = decode_domain(encoded)
    assert type(decoded) is Observation
    assert len(decoded.artifacts) == 1
    seen = decoded.artifacts[0]
    assert seen.entity_id == artifact_id
    assert seen.kind is ArtifactKind.MAP
    assert seen.content.marks == ("trail",)
    assert seen.placement is ObservedItemPlacement.HELD_BY_SELF
    assert encode_domain(decoded) == encoded


def test_transfer_claim_makes_ground_artifact_visible_to_claimer() -> None:
    engine = _engine(_world())
    created = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.NOTE, content=_content("shared")),
    )
    note_id = _created_id(created)
    _act(
        engine,
        "agent-2",
        TransferArtifact(artifact_id=note_id, mode="claim"),
    )
    batch = engine.observe()
    claimer = batch.for_observer(EntityId("body-2"))
    prior_holder = batch.for_observer(EntityId("body-1"))
    assert len(claimer.artifacts) == 1
    assert claimer.artifacts[0].placement is ObservedItemPlacement.HELD_BY_SELF
    assert prior_holder.artifacts == ()
