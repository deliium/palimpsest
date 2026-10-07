"""Codec v11 repository snapshot encode/decode and live vs restored parity."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import (
    decode_persistence,
    encode_persistence,
    hash_snapshot,
)
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import RunId
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from simulation.runner import _bootstrap_snapshot
from simulation.runner_models import (
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import DepositRecord, EstablishRepository, Inscribe
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre
from world.events import EVENT_SCHEMA_REPLAY_V13, EVENT_SCHEMA_REPLAY_V14
from world.identifiers import EntityId
from world.repositories import (
    KnowledgeRepository,
    RepositoryAccessMode,
    RepositoryStatus,
)

pytestmark = pytest.mark.unit
_LOG = logging.getLogger(__name__)


def _engine() -> WorldEngine:
    return WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
        knowledge_repositories_spec=example_knowledge_repositories_spec(),
    )


def _act(engine: WorldEngine, command: object):
    batch = engine.observe()
    return engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), command),)  # type: ignore[arg-type]
    )


def test_v11_repository_snapshot_round_trip() -> None:
    engine = _engine()
    _act(engine, EstablishRepository(location_id=EntityId("loc-1")))
    repo = next(iter(engine._snapshot.world.state.repositories.values()))
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-repo-v11"),
        run_id=RunId("run-repo-v11"),
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=tuple(engine._snapshot.world.state.items.values()),
        resources=tuple(engine._snapshot.world.state.resources.values()),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V14,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v11",
        derivation_version=engine._config.derivation_version or "v2",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        artifacts=(),
        repositories=(repo,),
    )
    snap = WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
        artifacts=draft.artifacts,
        repositories=draft.repositories,
    )
    encoded = encode_persistence(snap)
    decoded = decode_persistence(encoded, WorldSnapshot)
    assert decoded.persistence_codec_version == "v11"
    assert len(decoded.repositories) == 1
    assert decoded.repositories[0].repository_id == repo.repository_id
    assert decoded.repositories[0].access_mode is RepositoryAccessMode.OPEN
    _LOG.debug("codec_v11_round_trip ok repository_count=1")


def test_v10_snapshot_synthesizes_empty_repositories() -> None:
    engine = _engine()
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-repo-v10"),
        run_id=RunId("run-repo-v10"),
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=tuple(engine._snapshot.world.state.items.values()),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V13,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v10",
        derivation_version=engine._config.derivation_version or "v2",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        artifacts=(),
    )
    snap = WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
        artifacts=draft.artifacts,
    )
    encoded = encode_persistence(snap)
    payload = __import__("json").loads(encoded)
    assert "repositories" not in payload["data"]
    decoded = decode_persistence(encoded, WorldSnapshot)
    assert decoded.repositories == ()
    restored = WorldEngine.restore_from_snapshot(decoded)
    assert restored._snapshot.world.state.repositories == {}


def test_live_establish_deposit_survives_codec_v11_restore() -> None:
    engine = _engine()
    established = _act(
        engine, EstablishRepository(location_id=EntityId("loc-1"))
    )
    assert established.resolutions[0].status is ActionResolutionStatus.APPLIED
    repository_id = next(iter(engine._snapshot.world.state.repositories))
    inscribed = _act(
        engine,
        Inscribe(
            kind=ArtifactKind.NOTE,
            content=ArtifactContent(marks=("year", "flood")),
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
    deposited = _act(
        engine,
        DepositRecord(repository_id=repository_id, artifact_id=artifact_id),
    )
    assert deposited.resolutions[0].status is ActionResolutionStatus.APPLIED
    live_repo = engine._snapshot.world.state.repositories[repository_id]
    live_art = engine._snapshot.world.state.artifacts[artifact_id]
    assert live_art.custodian_repository_id == repository_id
    assert artifact_id in live_repo.member_artifact_ids

    snap = _bootstrap_snapshot(engine)
    assert snap.persistence_codec_version == "v11"
    assert len(snap.repositories) == 1
    encoded = encode_persistence(snap)
    decoded = decode_persistence(encoded, WorldSnapshot)
    assert len(decoded.repositories) == 1
    assert decoded.repositories[0].member_artifact_ids == (artifact_id,)
    restored_art = next(
        art for art in decoded.artifacts if art.artifact_id == artifact_id
    )
    assert restored_art.custodian_repository_id == repository_id

    restored = WorldEngine.restore_from_snapshot(decoded)
    assert restored._artifacts_enabled is True
    assert repository_id in restored._snapshot.world.state.repositories
    assert (
        restored._snapshot.world.state.repositories[repository_id].member_artifact_ids
        == (artifact_id,)
    )
    assert (
        restored._snapshot.world.state.artifacts[artifact_id].custodian_repository_id
        == repository_id
    )
    _LOG.debug(
        "live_vs_restored ok repository_id=%s artifact_id=%s",
        repository_id.value,
        artifact_id.value,
    )


def test_knowledge_repository_model_round_trips_index_entries() -> None:
    repo = KnowledgeRepository(
        repository_id=EntityId("repo-1"),
        location_id=EntityId("loc-1"),
        founder_ids=(EntityId("body-1"),),
        established_tick=0,
        access_mode=RepositoryAccessMode.FOUNDER_LIST,
        status=RepositoryStatus.NEGLECTED,
        neglect_streak=2,
    )
    engine = _engine()
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-repo-index"),
        run_id=RunId("run-repo-index"),
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=(),
        resources=(),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V14,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v11",
        derivation_version=engine._config.derivation_version or "v2",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        repositories=(repo,),
    )
    snap = WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
        repositories=draft.repositories,
    )
    decoded = decode_persistence(encode_persistence(snap), WorldSnapshot)
    assert decoded.repositories[0].status is RepositoryStatus.NEGLECTED
    assert decoded.repositories[0].neglect_streak == 2
    assert decoded.repositories[0].access_mode is RepositoryAccessMode.FOUNDER_LIST
