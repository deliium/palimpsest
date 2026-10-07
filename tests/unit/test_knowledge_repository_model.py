"""Unit tests for KnowledgeRepository domain model and custody fields."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import make_location, make_weather
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    InformationArtifact,
    RecordIntegrity,
)
from world.identifiers import EntityId, WorldRevision
from world.repositories import (
    KnowledgeRepository,
    RepositoryAccessMode,
    RepositoryIndexEntry,
    RepositoryStatus,
)
from world._state import WorldState

pytestmark = pytest.mark.unit


def _eid(value: str) -> EntityId:
    return EntityId(value)


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(marks=marks)


def test_v2_artifact_constructor_defaults_custodian_none() -> None:
    artifact = InformationArtifact(
        artifact_id=_eid("art-a"),
        kind=ArtifactKind.NOTE,
        author_id=_eid("body-a"),
        created_tick=0,
        content=_content("water"),
        location_id=_eid("loc-1"),
    )
    assert artifact.custodian_repository_id is None
    assert artifact.integrity is RecordIntegrity.INTACT


def test_repository_constructed_defaults() -> None:
    repo = KnowledgeRepository(
        repository_id=_eid("repo-1"),
        location_id=_eid("loc-1"),
        founder_ids=(_eid("body-a"),),
        established_tick=0,
        access_mode=RepositoryAccessMode.OPEN,
        last_maintained_tick=0,
    )
    assert repo.status is RepositoryStatus.INTACT
    assert repo.member_artifact_ids == ()
    assert repo.index_entries == ()
    assert repo.structure_id is None
    assert repo.neglect_streak == 0


def test_founder_ids_immutable_unique_nonempty() -> None:
    with pytest.raises(ValueError, match="repository_founder_empty"):
        KnowledgeRepository(
            repository_id=_eid("repo-1"),
            location_id=_eid("loc-1"),
            founder_ids=(),
            established_tick=0,
            access_mode=RepositoryAccessMode.OPEN,
        )
    with pytest.raises(ValueError, match="repository_founder_duplicate"):
        KnowledgeRepository(
            repository_id=_eid("repo-1"),
            location_id=_eid("loc-1"),
            founder_ids=(_eid("body-a"), _eid("body-a")),
            established_tick=0,
            access_mode=RepositoryAccessMode.OPEN,
        )


def test_index_entry_forbidden_token_rejected() -> None:
    with pytest.raises(ValueError, match="repository_index_forbidden_token"):
        RepositoryIndexEntry(
            entry_id="entry-1",
            artifact_id=_eid("art-a"),
            label_tokens=("library",),
            revision=0,
        )


def test_world_state_empty_repositories_default() -> None:
    state = WorldState(
        WorldRevision(0),
        locations=(make_location(),),
        weather=(make_weather(),),
    )
    assert dict(state.repositories) == {}


def test_custody_member_round_trip_in_world_state() -> None:
    repo_id = _eid("repo-1")
    art_id = _eid("art-a")
    artifact = InformationArtifact(
        artifact_id=art_id,
        kind=ArtifactKind.RECORD,
        author_id=_eid("body-a"),
        created_tick=1,
        content=_content("chronicle"),
        location_id=_eid("loc-1"),
        record_genre=DurableRecordGenre.CHRONICLE,
        custodian_repository_id=repo_id,
    )
    repo = KnowledgeRepository(
        repository_id=repo_id,
        location_id=_eid("loc-1"),
        founder_ids=(_eid("body-a"),),
        established_tick=1,
        access_mode=RepositoryAccessMode.OPEN,
        member_artifact_ids=(art_id,),
        last_maintained_tick=1,
    )
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        weather=(make_weather(),),
        artifacts=(artifact,),
        repositories=(repo,),
    )
    assert art_id in state.repositories[repo_id].member_artifact_ids
    assert state.artifacts[art_id].custodian_repository_id == repo_id


def test_custody_requires_location_not_hold() -> None:
    with pytest.raises(ValueError, match="repository_custody_blocks_hold"):
        InformationArtifact(
            artifact_id=_eid("art-a"),
            kind=ArtifactKind.NOTE,
            author_id=_eid("body-a"),
            created_tick=0,
            content=_content("water"),
            holder_id=_eid("body-a"),
            record_genre=DurableRecordGenre.WARNING,
            custodian_repository_id=_eid("repo-1"),
        )


def test_member_without_matching_custodian_rejected() -> None:
    art_id = _eid("art-a")
    artifact = InformationArtifact(
        artifact_id=art_id,
        kind=ArtifactKind.RECORD,
        author_id=_eid("body-a"),
        created_tick=1,
        content=_content("note"),
        location_id=_eid("loc-1"),
        record_genre=DurableRecordGenre.STORY,
    )
    repo = KnowledgeRepository(
        repository_id=_eid("repo-1"),
        location_id=_eid("loc-1"),
        founder_ids=(_eid("body-a"),),
        established_tick=1,
        access_mode=RepositoryAccessMode.OPEN,
        member_artifact_ids=(art_id,),
        last_maintained_tick=1,
    )
    with pytest.raises(ValueError, match="custodian_repository_id"):
        WorldState(
            WorldRevision(1),
            locations=(make_location(),),
            weather=(make_weather(),),
            artifacts=(artifact,),
            repositories=(repo,),
        )
