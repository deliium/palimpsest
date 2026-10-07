"""WorldEngine resolution for durable create/copy/annotate/damage/tombstone."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import (
    ActionResolutionReason,
    ActionResolutionStatus,
    ActionSubmission,
)
from simulation.runner_models import (
    DurableAnnotationPolicy,
    DurableCopyFidelityPolicy,
    DurableIntegrityPolicy,
    DurableLineagePolicy,
    example_durable_records_spec,
)
from tests.physical_helpers import (
    PhysicalWorldFixture,
    physical_config,
    two_location_fixture,
)
from world.actions import (
    AnnotateRecord,
    CopyRecord,
    DamageRecord,
    Erase,
    Inscribe,
)
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(marks=marks)


def _engine(
    fixture: PhysicalWorldFixture | None = None,
    *,
    seed: int = 1,
    durable: bool = True,
) -> WorldEngine:
    world = fixture if fixture is not None else two_location_fixture()
    return WorldEngine(
        config=physical_config(seed),
        bootstrap=world.as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec() if durable else None,
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _inscribe_chronicle(engine: WorldEngine) -> EntityId:
    result = _act(
        engine,
        "agent-1",
        Inscribe(
            kind=ArtifactKind.RECORD,
            content=_content("year", "one", "flood"),
            record_genre=DurableRecordGenre.CHRONICLE,
        ),
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    artifacts = engine._snapshot.world.state.artifacts
    assert len(artifacts) >= 1
    # Prefer the chronicle we just created (newest genre-bearing record).
    for artifact_id, artifact in artifacts.items():
        if artifact.record_genre is DurableRecordGenre.CHRONICLE:
            return artifact_id
    raise AssertionError("chronicle not found")


def test_inscribe_with_genre_sets_lineage_defaults(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    with caplog.at_level(logging.INFO, logger="world._operations"):
        artifact_id = _inscribe_chronicle(engine)
    artifact = engine._snapshot.world.state.artifacts[artifact_id]
    assert artifact.record_genre is DurableRecordGenre.CHRONICLE
    assert artifact.source_artifact_id == artifact_id
    assert artifact.parent_artifact_id is None
    assert artifact.copy_generation == 0
    assert artifact.integrity is RecordIntegrity.INTACT
    assert any("durable_record_created" in r.getMessage() for r in caplog.records)


def test_inscribe_durable_capable_requires_genre(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        result = _act(
            engine,
            "agent-1",
            Inscribe(kind=ArtifactKind.NOTE, content=_content("memo")),
        )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert (
        result.resolutions[0].reason is ActionResolutionReason.STRUCTURAL_REJECTION
    )
    assert any(
        "durable_genre_required" in r.getMessage() for r in caplog.records
    )


def test_copy_annotate_damage_partial_loss_destroy_tombstone() -> None:
    engine = _engine()
    parent_id = _inscribe_chronicle(engine)

    copy_result = _act(engine, "agent-1", CopyRecord(parent_id))
    assert copy_result.resolutions[0].status is ActionResolutionStatus.APPLIED
    children = [
        artifact
        for artifact_id, artifact in engine._snapshot.world.state.artifacts.items()
        if artifact_id != parent_id
    ]
    assert len(children) == 1
    child = children[0]
    assert child.parent_artifact_id == parent_id
    assert child.source_artifact_id == parent_id
    assert child.copy_generation == 1
    assert child.author_id == EntityId("body-1")
    assert child.content.marks == ("year", "one", "flood")
    assert child.record_genre is DurableRecordGenre.CHRONICLE

    annotate = _act(
        engine,
        "agent-1",
        AnnotateRecord(child.artifact_id, _content("margin")),
    )
    assert annotate.resolutions[0].status is ActionResolutionStatus.APPLIED
    annotated = engine._snapshot.world.state.artifacts[child.artifact_id]
    assert annotated.annotation_revisions == 1
    assert annotated.content.marks == ("year", "one", "flood", "margin")
    assert annotated.content_revision == 1

    damaged = _act(
        engine,
        "agent-1",
        DamageRecord(child.artifact_id, "damage"),
    )
    assert damaged.resolutions[0].status is ActionResolutionStatus.APPLIED
    after_damage = engine._snapshot.world.state.artifacts[child.artifact_id]
    assert after_damage.integrity is RecordIntegrity.DAMAGED
    assert after_damage.content_revision == 2
    assert after_damage.lost_mark_count >= 1

    partial = _act(
        engine,
        "agent-1",
        DamageRecord(child.artifact_id, "partial_loss"),
    )
    assert partial.resolutions[0].status is ActionResolutionStatus.APPLIED
    after_partial = engine._snapshot.world.state.artifacts[child.artifact_id]
    assert after_partial.integrity is RecordIntegrity.PARTIALLY_LOST
    assert after_partial.content.marks == ()

    destroy = _act(
        engine,
        "agent-1",
        DamageRecord(parent_id, "destroy"),
    )
    assert destroy.resolutions[0].status is ActionResolutionStatus.APPLIED
    tombstone = engine._snapshot.world.state.artifacts[parent_id]
    assert tombstone.integrity is RecordIntegrity.DESTROYED
    assert tombstone.location_id is None
    assert tombstone.holder_id is None


def test_erase_tombstones_when_durable_channel_on() -> None:
    engine = _engine()
    artifact_id = _inscribe_chronicle(engine)
    result = _act(engine, "agent-1", Erase(artifact_id))
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    tombstone = engine._snapshot.world.state.artifacts[artifact_id]
    assert tombstone.integrity is RecordIntegrity.DESTROYED


def test_channel_off_rejects_durable_commands(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(durable=False)
    created = _act(
        engine,
        "agent-1",
        Inscribe(kind=ArtifactKind.NOTE, content=_content("memo")),
    )
    assert created.resolutions[0].status is ActionResolutionStatus.APPLIED
    artifact_id = next(iter(engine._snapshot.world.state.artifacts))

    with caplog.at_level(logging.WARNING, logger="world._operations"):
        for command in (
            CopyRecord(artifact_id),
            AnnotateRecord(artifact_id, _content("x")),
            DamageRecord(artifact_id, "damage"),
            Inscribe(
                kind=ArtifactKind.NOTE,
                content=_content("g"),
                record_genre=DurableRecordGenre.STORY,
            ),
        ):
            result = _act(engine, "agent-1", command)
            assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
            assert (
                result.resolutions[0].reason
                is ActionResolutionReason.STRUCTURAL_REJECTION
            )
    assert any(
        "durable_records_inactive" in r.getMessage() for r in caplog.records
    )


def test_destroyed_parent_blocks_copy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    parent_id = _inscribe_chronicle(engine)
    _act(engine, "agent-1", DamageRecord(parent_id, "destroy"))
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        result = _act(engine, "agent-1", CopyRecord(parent_id))
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert any(
        "durable_parent_destroyed" in r.getMessage() for r in caplog.records
    )


def test_annotation_cap_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = example_durable_records_spec()
    capped = type(spec)(
        enabled_genres=spec.enabled_genres,
        copy_fidelity_policy=spec.copy_fidelity_policy,
        integrity_policy=spec.integrity_policy,
        annotation_policy=DurableAnnotationPolicy(max_annotations_per_record=1),
        lineage_policy=spec.lineage_policy,
        durable_records_mode=spec.durable_records_mode,
        perception_mode=spec.perception_mode,
        rng_namespace=spec.rng_namespace,
    )
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=capped,
    )
    artifact_id = _inscribe_chronicle(engine)
    first = _act(engine, "agent-1", AnnotateRecord(artifact_id, _content("a")))
    assert first.resolutions[0].status is ActionResolutionStatus.APPLIED
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        second = _act(engine, "agent-1", AnnotateRecord(artifact_id, _content("b")))
    assert second.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert any(
        "durable_annotation_cap" in r.getMessage() for r in caplog.records
    )


def test_copy_generation_cap_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = example_durable_records_spec()
    capped = type(spec)(
        enabled_genres=spec.enabled_genres,
        copy_fidelity_policy=DurableCopyFidelityPolicy(default_fidelity="perfect"),
        integrity_policy=DurableIntegrityPolicy(),
        annotation_policy=spec.annotation_policy,
        lineage_policy=DurableLineagePolicy(max_copy_generation=1),
        durable_records_mode=spec.durable_records_mode,
        perception_mode=spec.perception_mode,
        rng_namespace=spec.rng_namespace,
    )
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=capped,
    )
    parent_id = _inscribe_chronicle(engine)
    first = _act(engine, "agent-1", CopyRecord(parent_id))
    assert first.resolutions[0].status is ActionResolutionStatus.APPLIED
    child_id = next(
        aid
        for aid in engine._snapshot.world.state.artifacts
        if aid != parent_id
    )
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        second = _act(engine, "agent-1", CopyRecord(child_id))
    assert second.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert any(
        "durable_copy_generation_cap" in r.getMessage() for r in caplog.records
    )
