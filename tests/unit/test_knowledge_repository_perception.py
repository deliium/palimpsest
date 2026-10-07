"""Knowledge repository Observation projection and inspection rows."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.inspection import DetachedInspectionProjector
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.runner_models import (
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import (
    DepositRecord,
    EstablishRepository,
    Inscribe,
    MaintainRepository,
)
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre
from world.identifiers import EntityId
from world.repositories import RepositoryStatus

pytestmark = pytest.mark.unit
_LOG = logging.getLogger(__name__)


def _engine(*, perception_mode: str = "container_and_meta") -> WorldEngine:
    return WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
        knowledge_repositories_spec=example_knowledge_repositories_spec(
            perception_mode=perception_mode
        ),
    )


def _act(engine: WorldEngine, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), command),)  # type: ignore[arg-type]
    )


def test_container_and_meta_projects_repository_fields() -> None:
    engine = _engine(perception_mode="container_and_meta")
    result = _act(engine, EstablishRepository(location_id=EntityId("loc-1")))
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    obs = engine.observe().observations[0]
    assert len(obs.repositories) == 1
    seen = obs.repositories[0]
    assert seen.status == RepositoryStatus.INTACT.value
    assert seen.member_count == 0
    assert seen.access_mode == "open"
    assert seen.founder_ids is not None
    assert seen.index_entry_count == 0
    assert seen.neglect_streak == 0
    for forbidden in ("library", "archive", "sacred", "family_records"):
        assert forbidden not in seen.__dataclass_fields__
        assert not any(
            forbidden == getattr(seen, name, None)
            for name in seen.__dataclass_fields__
        )
    _LOG.debug("container_and_meta ok repository_count=1")


def test_container_only_omits_meta_fields() -> None:
    engine = _engine(perception_mode="container_only")
    _act(engine, EstablishRepository(location_id=EntityId("loc-1")))
    obs = engine.observe().observations[0]
    assert len(obs.repositories) == 1
    seen = obs.repositories[0]
    assert seen.access_mode is None
    assert seen.founder_ids is None
    assert seen.index_entry_count is None
    assert seen.neglect_streak is None
    assert seen.structure_id is None


def test_destroyed_omitted_from_observation_present_in_inspection() -> None:
    engine = _engine()
    _act(engine, EstablishRepository(location_id=EntityId("loc-1")))
    repository_id = next(iter(engine._snapshot.world.state.repositories))
    destroyed = _act(
        engine,
        MaintainRepository(repository_id=repository_id, mode="destroy"),
    )
    assert destroyed.resolutions[0].status is ActionResolutionStatus.APPLIED
    obs = engine.observe().observations[0]
    assert obs.repositories == ()
    document = DetachedInspectionProjector().project_knowledge_repositories(engine)
    assert document.channel_active is True
    assert len(document.repositories) == 1
    assert document.repositories[0].status == RepositoryStatus.DESTROYED.value
    assert document.repositories[0].repository_id == repository_id.value


def test_custodian_projected_on_member_artifact_when_meta_on() -> None:
    engine = _engine(perception_mode="container_and_meta")
    _act(engine, EstablishRepository(location_id=EntityId("loc-1")))
    repository_id = next(iter(engine._snapshot.world.state.repositories))
    _act(
        engine,
        Inscribe(
            kind=ArtifactKind.NOTE,
            content=ArtifactContent(marks=("a",)),
            hold=True,
            record_genre=DurableRecordGenre.CHRONICLE,
        ),
    )
    artifact_id = next(
        aid
        for aid, art in engine._snapshot.world.state.artifacts.items()
        if art.record_genre is DurableRecordGenre.CHRONICLE
    )
    deposited = _act(
        engine,
        DepositRecord(repository_id=repository_id, artifact_id=artifact_id),
    )
    assert deposited.resolutions[0].status is ActionResolutionStatus.APPLIED
    obs = engine.observe().observations[0]
    assert len(obs.repositories) == 1
    assert obs.repositories[0].member_count == 1
    member = next(art for art in obs.artifacts if art.entity_id == artifact_id)
    assert member.custodian_repository_id == repository_id


def test_channel_off_omits_repositories() -> None:
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
    )
    obs = engine.observe().observations[0]
    assert obs.repositories == ()
    document = DetachedInspectionProjector().project_knowledge_repositories(engine)
    assert document.channel_active is False
    assert document.repositories == ()
