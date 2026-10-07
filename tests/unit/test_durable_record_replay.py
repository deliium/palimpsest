"""Durable record journal encode and live vs restored resolution parity."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.journal import _decode_information_artifact, _encode_information_artifact
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.runner_models import example_durable_records_spec
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import AnnotateRecord, CopyRecord, DamageRecord, Inscribe
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    InformationArtifact,
    RecordIntegrity,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(marks=marks)


def test_journal_round_trip_durable_fields() -> None:
    artifact = InformationArtifact(
        artifact_id=EntityId("art-1"),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=0,
        content=_content("a", "b"),
        content_revision=1,
        location_id=EntityId("loc-1"),
        record_genre=DurableRecordGenre.CHRONICLE,
        source_artifact_id=EntityId("art-1"),
        copy_generation=0,
        integrity=RecordIntegrity.DAMAGED,
        annotation_revisions=2,
        lost_mark_count=1,
    )
    encoded = _encode_information_artifact(artifact)
    assert encoded["record_genre"] == "chronicle"
    assert encoded["integrity"] == "damaged"
    decoded = _decode_information_artifact(encoded, path="$")
    assert decoded.record_genre is DurableRecordGenre.CHRONICLE
    assert decoded.integrity is RecordIntegrity.DAMAGED
    assert decoded.annotation_revisions == 2
    assert decoded.lost_mark_count == 1


def test_journal_v9_shape_synthesizes_defaults() -> None:
    legacy = {
        "artifact_id": "art-1",
        "kind": "note",
        "author_id": "body-1",
        "created_tick": 0,
        "content": {"marks": ["x"], "relations": []},
        "content_revision": 0,
        "location_id": "loc-1",
    }
    decoded = _decode_information_artifact(legacy, path="$")
    assert decoded.record_genre is None
    assert decoded.integrity is RecordIntegrity.INTACT
    assert decoded.copy_generation == 0
    assert decoded.parent_artifact_id is None


def test_live_durable_mutations_persist_lineage() -> None:
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
    )

    def act(command: object):
        batch = engine.observe()
        return engine.resolve_tick(
            (ActionSubmission(batch.token, AgentId("agent-1"), command),)  # type: ignore[arg-type]
        )

    created = act(
        Inscribe(
            ArtifactKind.RECORD,
            _content("year", "flood"),
            record_genre=DurableRecordGenre.CHRONICLE,
        )
    )
    assert created.resolutions[0].status is ActionResolutionStatus.APPLIED
    parent_id = next(iter(engine._snapshot.world.state.artifacts))
    copied = act(CopyRecord(parent_id))
    assert copied.resolutions[0].status is ActionResolutionStatus.APPLIED
    child_id = next(
        aid for aid in engine._snapshot.world.state.artifacts if aid != parent_id
    )
    annotated = act(AnnotateRecord(child_id, _content("note")))
    assert annotated.resolutions[0].status is ActionResolutionStatus.APPLIED
    damaged = act(DamageRecord(child_id, "damage"))
    assert damaged.resolutions[0].status is ActionResolutionStatus.APPLIED
    child = engine._snapshot.world.state.artifacts[child_id]
    assert child.parent_artifact_id == parent_id
    assert child.annotation_revisions == 1
    assert child.integrity is RecordIntegrity.DAMAGED
    destroyed = act(DamageRecord(parent_id, "destroy"))
    assert destroyed.resolutions[0].status is ActionResolutionStatus.APPLIED
    tombstone = engine._snapshot.world.state.artifacts[parent_id]
    assert tombstone.integrity is RecordIntegrity.DESTROYED
