"""Custody × artifact command matrix for knowledge repositories."""

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
    Amend,
    AnnotateRecord,
    CopyRecord,
    DamageRecord,
    DepositRecord,
    Erase,
    EstablishRepository,
    Inscribe,
    RetrieveRecord,
    TransferArtifact,
)
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _engine() -> WorldEngine:
    return WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
        knowledge_repositories_spec=example_knowledge_repositories_spec(),
    )


def _act(engine: WorldEngine, agent: str, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId(agent), command),)  # type: ignore[arg-type]
    )


def _setup_member(engine: WorldEngine) -> tuple[EntityId, EntityId]:
    _act(engine, "agent-1", EstablishRepository(location_id=EntityId("loc-1")))
    repository_id = next(iter(engine._snapshot.world.state.repositories))
    result = _act(
        engine,
        "agent-1",
        Inscribe(
            kind=ArtifactKind.NOTE,
            content=ArtifactContent(marks=("a", "b")),
            hold=True,
            record_genre=DurableRecordGenre.CHRONICLE,
        ),
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    artifact_id = next(
        aid
        for aid, art in engine._snapshot.world.state.artifacts.items()
        if art.record_genre is DurableRecordGenre.CHRONICLE
    )
    deposited = _act(
        engine,
        "agent-1",
        DepositRecord(repository_id=repository_id, artifact_id=artifact_id),
    )
    assert deposited.resolutions[0].status is ActionResolutionStatus.APPLIED
    return repository_id, artifact_id


def test_transfer_and_erase_blocked_while_in_custody(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    _repository_id, artifact_id = _setup_member(engine)
    with caplog.at_level(logging.WARNING, logger="world._operations"):
        claim = _act(
            engine,
            "agent-1",
            TransferArtifact(artifact_id=artifact_id, mode="claim"),
        )
        erase = _act(engine, "agent-1", Erase(artifact_id))
    assert claim.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert erase.resolutions[0].status is ActionResolutionStatus.REJECTED
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "repository_custody_blocks_transfer" in messages
    assert "repository_custody_blocks_erase" in messages


def test_retrieve_then_transfer_succeeds() -> None:
    engine = _engine()
    repository_id, artifact_id = _setup_member(engine)
    retrieved = _act(
        engine,
        "agent-1",
        RetrieveRecord(
            repository_id=repository_id, artifact_id=artifact_id, hold=True
        ),
    )
    assert retrieved.resolutions[0].status is ActionResolutionStatus.APPLIED
    # Already held after retrieve — deposit to floor then claim.
    dropped = _act(
        engine,
        "agent-1",
        TransferArtifact(artifact_id=artifact_id, mode="deposit"),
    )
    assert dropped.resolutions[0].status is ActionResolutionStatus.APPLIED
    claim = _act(
        engine,
        "agent-1",
        TransferArtifact(artifact_id=artifact_id, mode="claim"),
    )
    assert claim.resolutions[0].status is ActionResolutionStatus.APPLIED
    held = engine._snapshot.world.state.artifacts[artifact_id]
    assert held.holder_id == EntityId("body-1")
    assert held.custodian_repository_id is None


def test_amend_annotate_copy_damage_allowed_in_custody() -> None:
    engine = _engine()
    _repository_id, artifact_id = _setup_member(engine)

    amended = _act(
        engine,
        "agent-1",
        Amend(artifact_id, ArtifactContent(marks=("rewritten",))),
    )
    assert amended.resolutions[0].status is ActionResolutionStatus.APPLIED

    annotated = _act(
        engine,
        "agent-1",
        AnnotateRecord(artifact_id, ArtifactContent(marks=("margin",))),
    )
    assert annotated.resolutions[0].status is ActionResolutionStatus.APPLIED

    copied = _act(engine, "agent-1", CopyRecord(artifact_id))
    assert copied.resolutions[0].status is ActionResolutionStatus.APPLIED
    children = [
        art
        for aid, art in engine._snapshot.world.state.artifacts.items()
        if aid != artifact_id
    ]
    assert len(children) == 1
    assert children[0].custodian_repository_id is None

    damaged = _act(engine, "agent-1", DamageRecord(artifact_id, "damage"))
    assert damaged.resolutions[0].status is ActionResolutionStatus.APPLIED
    member = engine._snapshot.world.state.artifacts[artifact_id]
    assert member.integrity is RecordIntegrity.DAMAGED
    assert member.custodian_repository_id == _repository_id
