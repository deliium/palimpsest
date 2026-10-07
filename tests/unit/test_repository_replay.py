"""Replay projectors for repository event details on V14."""

from __future__ import annotations

import logging

import pytest

from tests.physical_helpers import two_location_fixture
from world._replay import project_events
from world._state import WorldState
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    InformationArtifact,
    RecordIntegrity,
)
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V14,
    OccurrenceContext,
    RepositoryEstablished,
    RepositoryMaintained,
    RepositoryMemberDeposited,
    RepositoryMemberRetrieved,
    RepositoryNeglected,
    make_physical_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.repositories import (
    KnowledgeRepository,
    RepositoryAccessMode,
    RepositoryIndexEntry,
    RepositoryStatus,
)

pytestmark = pytest.mark.unit
_LOG = logging.getLogger(__name__)


def _cause() -> ActionCause:
    return ActionCause(
        request_id=RequestId("req-1"),
        actor_id=EntityId("body-1"),
    )


def _event(
    details: object,
    *,
    sequence: int = 0,
    tick: int = 1,
    resulting_revision: int = 1,
):
    cause: object = _cause()
    if type(details) is RepositoryNeglected:
        cause = SystemCause(
            RequestId(f"sys-repo-{sequence}"),
            SystemEffectFamily.KNOWLEDGE_REPOSITORY,
            EntityId("repo-1"),
            tick,
        )
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{sequence}"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=cause,  # type: ignore[arg-type]
        resulting_revision=WorldRevision(resulting_revision),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V14,
    )


def _base_state(*, with_artifact: bool = False) -> WorldState:
    fixture = two_location_fixture()
    artifacts = ()
    if with_artifact:
        artifacts = (
            InformationArtifact(
                artifact_id=EntityId("art-1"),
                kind=ArtifactKind.NOTE,
                author_id=EntityId("body-1"),
                created_tick=0,
                content=ArtifactContent(marks=("a",)),
                content_revision=0,
                holder_id=EntityId("body-1"),
                record_genre=DurableRecordGenre.CHRONICLE,
                integrity=RecordIntegrity.INTACT,
            ),
        )
    return WorldState(
        fixture.revision,
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        artifacts=artifacts,
    )


def test_project_repository_established() -> None:
    state = _base_state()
    event = _event(
        RepositoryEstablished(
            EntityId("repo-1"),
            EntityId("loc-1"),
            None,
            (EntityId("body-1"),),
            "open",
            0,
        )
    )
    projected = project_events(
        state,
        (event,),
        expected_run_id="run-1",
        expected_world_id=WorldId("world-1"),
    )
    assert EntityId("repo-1") in projected.repositories
    repo = projected.repositories[EntityId("repo-1")]
    assert repo.status is RepositoryStatus.INTACT
    assert repo.access_mode is RepositoryAccessMode.OPEN
    _LOG.debug("replay_established ok")


def test_project_deposit_and_retrieve_custody() -> None:
    state = _base_state(with_artifact=True)
    established = _event(
        RepositoryEstablished(
            EntityId("repo-1"),
            EntityId("loc-1"),
            None,
            (EntityId("body-1"),),
            "open",
            0,
        ),
        sequence=0,
    )
    deposited = _event(
        RepositoryMemberDeposited(
            EntityId("repo-1"), EntityId("art-1"), 1, EntityId("body-1")
        ),
        sequence=1,
    )
    retrieved = _event(
        RepositoryMemberRetrieved(
            EntityId("repo-1"), EntityId("art-1"), 0, EntityId("body-1"), True
        ),
        sequence=2,
    )
    final = project_events(
        state,
        (established, deposited, retrieved),
        expected_run_id="run-1",
        expected_world_id=WorldId("world-1"),
    )
    art = final.artifacts[EntityId("art-1")]
    assert art.custodian_repository_id is None
    assert art.holder_id == EntityId("body-1")
    assert final.repositories[EntityId("repo-1")].member_artifact_ids == ()
    # Mid-fold custody after deposit only.
    mid = project_events(
        state,
        (established, deposited),
        expected_run_id="run-1",
        expected_world_id=WorldId("world-1"),
    )
    assert mid.artifacts[EntityId("art-1")].custodian_repository_id == EntityId(
        "repo-1"
    )
    _LOG.debug("replay_deposit_retrieve ok")


def test_project_maintain_destroy_clears_custody() -> None:
    state = _base_state(with_artifact=True)
    events = (
        _event(
            RepositoryEstablished(
                EntityId("repo-1"),
                EntityId("loc-1"),
                None,
                (EntityId("body-1"),),
                "open",
                0,
            ),
            sequence=0,
        ),
        _event(
            RepositoryMemberDeposited(
                EntityId("repo-1"), EntityId("art-1"), 1, EntityId("body-1")
            ),
            sequence=1,
        ),
        _event(
            RepositoryMaintained(
                EntityId("repo-1"), "destroy", "intact", "destroyed", 2
            ),
            sequence=2,
        ),
    )
    projected = project_events(
        state,
        events,
        expected_run_id="run-1",
        expected_world_id=WorldId("world-1"),
    )
    repo = projected.repositories[EntityId("repo-1")]
    assert repo.status is RepositoryStatus.DESTROYED
    assert repo.member_artifact_ids == ()
    assert (
        projected.artifacts[EntityId("art-1")].custodian_repository_id is None
    )


def test_project_neglect_drops_index_entries() -> None:
    fixture = two_location_fixture()
    repo = KnowledgeRepository(
        repository_id=EntityId("repo-1"),
        location_id=EntityId("loc-1"),
        founder_ids=(EntityId("body-1"),),
        established_tick=0,
        access_mode=RepositoryAccessMode.OPEN,
        status=RepositoryStatus.INTACT,
        index_entries=(
            RepositoryIndexEntry(
                entry_id="idx-a",
                artifact_id=EntityId("art-1"),
                label_tokens=("token-a",),
                revision=0,
            ),
            RepositoryIndexEntry(
                entry_id="idx-b",
                artifact_id=None,
                label_tokens=("token-b",),
                revision=0,
            ),
        ),
    )
    state = WorldState(
        fixture.revision,
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        repositories=(repo,),
    )
    event = _event(
        RepositoryNeglected(EntityId("repo-1"), 1, "intact", "neglected", 1)
    )
    projected = project_events(
        state,
        (event,),
        expected_run_id="run-1",
        expected_world_id=WorldId("world-1"),
    )
    next_repo = projected.repositories[EntityId("repo-1")]
    assert next_repo.status is RepositoryStatus.NEGLECTED
    assert next_repo.neglect_streak == 1
    assert len(next_repo.index_entries) == 1
    assert next_repo.index_entries[0].entry_id == "idx-a"
