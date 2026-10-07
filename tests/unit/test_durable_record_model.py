"""Unit tests for durable record genre/integrity model fields."""

from __future__ import annotations

import pytest

from world.artifacts import (
    DURABLE_CAPABLE_ARTIFACT_KINDS,
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    InformationArtifact,
    RecordIntegrity,
    artifact_kind_is_durable_capable,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _eid(value: str) -> EntityId:
    return EntityId(value)


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(marks=marks)


def test_v2_constructor_defaults_remain_valid() -> None:
    artifact = InformationArtifact(
        artifact_id=_eid("art-a"),
        kind=ArtifactKind.NOTE,
        author_id=_eid("body-a"),
        created_tick=0,
        content=_content("water"),
        location_id=_eid("loc-a"),
    )
    assert artifact.record_genre is None
    assert artifact.parent_artifact_id is None
    assert artifact.source_artifact_id is None
    assert artifact.copy_generation == 0
    assert artifact.integrity is RecordIntegrity.INTACT
    assert artifact.annotation_revisions == 0
    assert artifact.lost_mark_count == 0


def test_durable_capable_kinds_exclude_mark() -> None:
    assert ArtifactKind.MARK not in DURABLE_CAPABLE_ARTIFACT_KINDS
    assert artifact_kind_is_durable_capable(ArtifactKind.RECORD) is True
    assert artifact_kind_is_durable_capable(ArtifactKind.MARK) is False


def test_genre_on_mark_rejected() -> None:
    with pytest.raises(ValueError, match="durable_genre_kind_mismatch"):
        InformationArtifact(
            artifact_id=_eid("art-mark"),
            kind=ArtifactKind.MARK,
            author_id=_eid("body-a"),
            created_tick=0,
            content=_content("glyph"),
            location_id=_eid("loc-a"),
            record_genre=DurableRecordGenre.WARNING,
        )


def test_map_genre_on_record_or_map_kind() -> None:
    record = InformationArtifact(
        artifact_id=_eid("art-rec"),
        kind=ArtifactKind.RECORD,
        author_id=_eid("body-a"),
        created_tick=1,
        content=_content("path"),
        location_id=_eid("loc-a"),
        record_genre=DurableRecordGenre.MAP,
    )
    note_map = InformationArtifact(
        artifact_id=_eid("art-map"),
        kind=ArtifactKind.MAP,
        author_id=_eid("body-a"),
        created_tick=1,
        content=_content("path"),
        location_id=_eid("loc-a"),
        record_genre=DurableRecordGenre.MAP,
    )
    assert record.record_genre is DurableRecordGenre.MAP
    assert note_map.record_genre is DurableRecordGenre.MAP


def test_copy_lineage_fields() -> None:
    child = InformationArtifact(
        artifact_id=_eid("art-child"),
        kind=ArtifactKind.NOTE,
        author_id=_eid("body-b"),
        created_tick=2,
        content=_content("water"),
        location_id=_eid("loc-a"),
        record_genre=DurableRecordGenre.INSTRUCTION,
        parent_artifact_id=_eid("art-parent"),
        source_artifact_id=_eid("art-root"),
        copy_generation=1,
    )
    assert child.copy_generation == 1
    assert child.parent_artifact_id == _eid("art-parent")
    assert child.source_artifact_id == _eid("art-root")


def test_original_cannot_have_nonzero_generation() -> None:
    with pytest.raises(ValueError, match="durable_lineage_invalid"):
        InformationArtifact(
            artifact_id=_eid("art-a"),
            kind=ArtifactKind.NOTE,
            author_id=_eid("body-a"),
            created_tick=0,
            content=_content("x"),
            location_id=_eid("loc-a"),
            copy_generation=1,
        )


def test_copy_requires_source_and_positive_generation() -> None:
    with pytest.raises(ValueError, match="durable_lineage_invalid"):
        InformationArtifact(
            artifact_id=_eid("art-child"),
            kind=ArtifactKind.NOTE,
            author_id=_eid("body-a"),
            created_tick=0,
            content=_content("x"),
            location_id=_eid("loc-a"),
            parent_artifact_id=_eid("art-parent"),
            copy_generation=1,
        )
    with pytest.raises(ValueError, match="durable_lineage_invalid"):
        InformationArtifact(
            artifact_id=_eid("art-child"),
            kind=ArtifactKind.NOTE,
            author_id=_eid("body-a"),
            created_tick=0,
            content=_content("x"),
            location_id=_eid("loc-a"),
            parent_artifact_id=_eid("art-parent"),
            source_artifact_id=_eid("art-root"),
            copy_generation=0,
        )


def test_destroyed_tombstone_may_clear_placement() -> None:
    tombstone = InformationArtifact(
        artifact_id=_eid("art-tomb"),
        kind=ArtifactKind.RECORD,
        author_id=_eid("body-a"),
        created_tick=3,
        content=_content("old"),
        record_genre=DurableRecordGenre.CHRONICLE,
        integrity=RecordIntegrity.DESTROYED,
    )
    assert tombstone.location_id is None
    assert tombstone.holder_id is None
    assert tombstone.integrity is RecordIntegrity.DESTROYED


def test_annotation_and_loss_counters() -> None:
    artifact = InformationArtifact(
        artifact_id=_eid("art-a"),
        kind=ArtifactKind.NOTE,
        author_id=_eid("body-a"),
        created_tick=0,
        content=_content("a", "b"),
        location_id=_eid("loc-a"),
        record_genre=DurableRecordGenre.STORY,
        integrity=RecordIntegrity.DAMAGED,
        annotation_revisions=2,
        lost_mark_count=1,
    )
    assert artifact.annotation_revisions == 2
    assert artifact.lost_mark_count == 1


def test_negative_counters_rejected() -> None:
    with pytest.raises(ValueError, match="durable_annotation_revisions_invalid"):
        InformationArtifact(
            artifact_id=_eid("art-a"),
            kind=ArtifactKind.NOTE,
            author_id=_eid("body-a"),
            created_tick=0,
            content=_content("a"),
            location_id=_eid("loc-a"),
            annotation_revisions=-1,
        )
    with pytest.raises(ValueError, match="durable_lost_mark_count_invalid"):
        InformationArtifact(
            artifact_id=_eid("art-a"),
            kind=ArtifactKind.NOTE,
            author_id=_eid("body-a"),
            created_tick=0,
            content=_content("a"),
            location_id=_eid("loc-a"),
            lost_mark_count=-1,
        )
