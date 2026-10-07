"""Neglect, inaccessible helper, and destroy orphan paths."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.runner_models import (
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import (
    DepositRecord,
    EstablishRepository,
    IndexRepository,
    Inscribe,
    MaintainRepository,
    RetrieveRecord,
    Wait,
)
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre
from world.identifiers import EntityId
from world.repositories import RepositoryStatus

pytestmark = pytest.mark.unit


def _engine(*, seed: int = 1, neglect_ticks: int = 2) -> WorldEngine:
    return WorldEngine(
        config=physical_config(seed),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
        knowledge_repositories_spec=example_knowledge_repositories_spec(
            neglect_ticks=neglect_ticks
        ),
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _wait(engine: WorldEngine, ticks: int = 1) -> None:
    for _ in range(ticks):
        result = _act(engine, "agent-1", Wait())
        assert result.resolutions[0].status is ActionResolutionStatus.APPLIED


def _establish_with_index(engine: WorldEngine) -> tuple[EntityId, EntityId]:
    _act(engine, "agent-1", EstablishRepository(location_id=EntityId("loc-1")))
    repository_id = next(iter(engine._snapshot.world.state.repositories))
    # Refresh maintenance so short neglect_ticks arms do not fire mid-setup.
    _act(
        engine,
        "agent-1",
        MaintainRepository(repository_id=repository_id, mode="maintain"),
    )
    inscribed = _act(
        engine,
        "agent-1",
        Inscribe(
            kind=ArtifactKind.NOTE,
            content=ArtifactContent(marks=("a", "b", "c")),
            hold=True,
            record_genre=DurableRecordGenre.CHRONICLE,
        ),
    )
    assert inscribed.resolutions[0].status is ActionResolutionStatus.APPLIED
    artifact_id = next(
        aid
        for aid, art in engine._snapshot.world.state.artifacts.items()
        if art.record_genre is DurableRecordGenre.CHRONICLE
    )
    _act(
        engine,
        "agent-1",
        DepositRecord(repository_id=repository_id, artifact_id=artifact_id),
    )
    indexed = _act(
        engine,
        "agent-1",
        IndexRepository(
            repository_id=repository_id,
            entries=(
                {"entry_id": "e1", "artifact_id": artifact_id.value},
                {"entry_id": "e2", "artifact_id": artifact_id.value},
            ),
        ),
    )
    assert indexed.resolutions[0].status is ActionResolutionStatus.APPLIED
    return repository_id, artifact_id


def test_neglect_after_n_ticks_and_maintain_resets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(neglect_ticks=2)
    repository_id, _artifact_id = _establish_with_index(engine)
    # establish + inscribe + deposit + index consume ticks; reset via maintain
    maintained = _act(
        engine,
        "agent-1",
        MaintainRepository(repository_id=repository_id, mode="maintain"),
    )
    assert maintained.resolutions[0].status is ActionResolutionStatus.APPLIED
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert repo.status is RepositoryStatus.INTACT
    assert repo.neglect_streak == 0

    with caplog.at_level(logging.INFO, logger="simulation.engine"):
        _wait(engine, 2)
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert repo.status is RepositoryStatus.NEGLECTED
    assert repo.neglect_streak >= 1
    assert any(
        "repository_status_transition" in r.getMessage() for r in caplog.records
    )

    reset = _act(
        engine,
        "agent-1",
        MaintainRepository(repository_id=repository_id, mode="maintain"),
    )
    assert reset.resolutions[0].status is ActionResolutionStatus.APPLIED
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert repo.status is RepositoryStatus.INTACT
    assert repo.neglect_streak == 0


def test_same_seed_same_index_drops() -> None:
    def _run(seed: int) -> tuple[str, ...]:
        engine = _engine(seed=seed, neglect_ticks=1)
        repository_id, _ = _establish_with_index(engine)
        _act(
            engine,
            "agent-1",
            MaintainRepository(repository_id=repository_id, mode="maintain"),
        )
        before = engine._snapshot.world.state.repositories[repository_id]
        assert len(before.index_entries) == 2
        _wait(engine, 1)
        after = engine._snapshot.world.state.repositories[repository_id]
        assert after.status is RepositoryStatus.NEGLECTED
        assert len(after.index_entries) == 1
        return tuple(entry.entry_id for entry in after.index_entries)

    assert _run(7) == _run(7)
    # Different seeds may diverge; same seed must match (already asserted).


def test_inaccessible_blocks_access() -> None:
    engine = _engine(neglect_ticks=100)
    repository_id, artifact_id = _establish_with_index(engine)
    engine.mark_repository_inaccessible(repository_id)
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert repo.status is RepositoryStatus.INACCESSIBLE

    retrieve = _act(
        engine,
        "agent-1",
        RetrieveRecord(
            repository_id=repository_id, artifact_id=artifact_id, hold=True
        ),
    )
    assert retrieve.resolutions[0].status is ActionResolutionStatus.REJECTED

    engine.clear_repository_inaccessible(repository_id)
    assert (
        engine._snapshot.world.state.repositories[repository_id].status
        is RepositoryStatus.INTACT
    )
    retrieve_ok = _act(
        engine,
        "agent-1",
        RetrieveRecord(
            repository_id=repository_id, artifact_id=artifact_id, hold=True
        ),
    )
    assert retrieve_ok.resolutions[0].status is ActionResolutionStatus.APPLIED


def test_destroy_orphans_members_at_location() -> None:
    engine = _engine(neglect_ticks=100)
    repository_id, artifact_id = _establish_with_index(engine)
    destroyed = _act(
        engine,
        "agent-1",
        MaintainRepository(repository_id=repository_id, mode="destroy"),
    )
    assert destroyed.resolutions[0].status is ActionResolutionStatus.APPLIED
    repo = engine._snapshot.world.state.repositories[repository_id]
    assert repo.status is RepositoryStatus.DESTROYED
    assert repo.member_artifact_ids == ()
    orphan = engine._snapshot.world.state.artifacts[artifact_id]
    assert orphan.custodian_repository_id is None
    assert orphan.location_id == EntityId("loc-1")
