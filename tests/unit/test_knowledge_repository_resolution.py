"""WorldEngine resolution for establish/deposit/retrieve/maintain/index."""

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
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)
from tests.physical_helpers import (
    PhysicalWorldFixture,
    physical_config,
    two_location_fixture,
)
from world.actions import (
    DepositRecord,
    EstablishRepository,
    IndexRepository,
    Inscribe,
    MaintainRepository,
    RetrieveRecord,
)
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import EntityId
from world.repositories import RepositoryStatus

pytestmark = pytest.mark.unit


def _content(*marks: str) -> ArtifactContent:
    return ArtifactContent(marks=marks)


def _engine(
    fixture: PhysicalWorldFixture | None = None,
    *,
    seed: int = 1,
    repositories: bool = True,
) -> WorldEngine:
    world = fixture if fixture is not None else two_location_fixture()
    return WorldEngine(
        config=physical_config(seed),
        bootstrap=world.as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
        knowledge_repositories_spec=(
            example_knowledge_repositories_spec() if repositories else None
        ),
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
            kind=ArtifactKind.NOTE,
            content=_content("year", "one", "flood"),
            hold=True,
            record_genre=DurableRecordGenre.CHRONICLE,
        ),
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    for artifact_id, artifact in engine._snapshot.world.state.artifacts.items():
        if artifact.record_genre is DurableRecordGenre.CHRONICLE:
            return artifact_id
    raise AssertionError("chronicle not found")


def test_establish_deposit_retrieve_maintain_index(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    loc = EntityId("loc-1")
    with caplog.at_level(logging.INFO, logger="world._operations"):
        established = _act(engine, "agent-1", EstablishRepository(location_id=loc))
    assert established.resolutions[0].status is ActionResolutionStatus.APPLIED
    repos = engine._snapshot.world.state.repositories
    assert len(repos) == 1
    repository_id = next(iter(repos))
    repository = repos[repository_id]
    assert repository.status is RepositoryStatus.INTACT
    assert repository.founder_ids == (EntityId("body-1"),)
    assert repository.location_id == loc
    assert any("repository_established" in r.getMessage() for r in caplog.records)

    artifact_id = _inscribe_chronicle(engine)
    deposited = _act(
        engine,
        "agent-1",
        DepositRecord(repository_id=repository_id, artifact_id=artifact_id),
    )
    assert deposited.resolutions[0].status is ActionResolutionStatus.APPLIED
    member = engine._snapshot.world.state.artifacts[artifact_id]
    assert member.custodian_repository_id == repository_id
    assert member.holder_id is None
    assert member.location_id == loc
    assert artifact_id in engine._snapshot.world.state.repositories[
        repository_id
    ].member_artifact_ids

    indexed = _act(
        engine,
        "agent-1",
        IndexRepository(
            repository_id=repository_id,
            entries=({"entry_id": "e1", "artifact_id": artifact_id.value},),
        ),
    )
    assert indexed.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert (
        len(engine._snapshot.world.state.repositories[repository_id].index_entries)
        == 1
    )

    maintained = _act(
        engine,
        "agent-1",
        MaintainRepository(repository_id=repository_id, mode="maintain"),
    )
    assert maintained.resolutions[0].status is ActionResolutionStatus.APPLIED

    retrieved = _act(
        engine,
        "agent-1",
        RetrieveRecord(
            repository_id=repository_id, artifact_id=artifact_id, hold=True
        ),
    )
    assert retrieved.resolutions[0].status is ActionResolutionStatus.APPLIED
    held = engine._snapshot.world.state.artifacts[artifact_id]
    assert held.custodian_repository_id is None
    assert held.holder_id == EntityId("body-1")
    assert (
        artifact_id
        not in engine._snapshot.world.state.repositories[
            repository_id
        ].member_artifact_ids
    )


def test_destroy_orphans_members_at_location() -> None:
    engine = _engine()
    loc = EntityId("loc-1")
    _act(engine, "agent-1", EstablishRepository(location_id=loc))
    repository_id = next(iter(engine._snapshot.world.state.repositories))
    artifact_id = _inscribe_chronicle(engine)
    _act(
        engine,
        "agent-1",
        DepositRecord(repository_id=repository_id, artifact_id=artifact_id),
    )
    destroyed = _act(
        engine,
        "agent-1",
        MaintainRepository(repository_id=repository_id, mode="destroy"),
    )
    assert destroyed.resolutions[0].status is ActionResolutionStatus.APPLIED
    repository = engine._snapshot.world.state.repositories[repository_id]
    assert repository.status is RepositoryStatus.DESTROYED
    assert repository.member_artifact_ids == ()
    orphan = engine._snapshot.world.state.artifacts[artifact_id]
    assert orphan.custodian_repository_id is None
    assert orphan.location_id == loc
    assert orphan.holder_id is None
    assert orphan.integrity is RecordIntegrity.INTACT


def test_channel_off_rejects_repository_commands(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(repositories=False)
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        result = _act(
            engine,
            "agent-1",
            EstablishRepository(location_id=EntityId("loc-1")),
        )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert (
        result.resolutions[0].reason is ActionResolutionReason.STRUCTURAL_REJECTION
    )
    assert any(
        "knowledge_repositories_inactive" in r.getMessage() for r in caplog.records
    )
