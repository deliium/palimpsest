"""PostgreSQL integration for the unified run stream repository."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from infrastructure.database import DatabaseResources, session_scope
from persistence import (
    create_run_repository,
    create_scientific_evidence_repository,
    create_stream_repository,
)
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.evidence import (
    ACTION_RESOLUTION_SCHEMA_VERSION,
    ActionResolutionRecord,
    EvidenceHighWaterMarks,
    build_evidence_manifest,
    opaque_envelope_from_payload,
)
from simulation.journal import hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    FinalizedBoundaryBatch,
    PayloadHash,
    RunCreateRequest,
    SnapshotId,
    WorldSnapshot,
)
from simulation.run_control import (
    StreamRecordDraft,
    StreamRecordKind,
    make_stream_envelope,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _alive() -> AgentBody:
    return AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _bootstrap(*, run_id: str, seed: int = 31) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(f"snap-{run_id}"),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(make_location("loc-1", name="Camp"),),
        bodies=(_alive(),),
        items=(),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
    )
    return WorldSnapshot(
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
    )


async def _seed_run(database_resources: DatabaseResources) -> str:
    run_id = _unique("stream-run")
    runs = create_run_repository(database_resources.session_factory)
    bootstrap = _bootstrap(run_id=run_id)
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=WorldId("world-1"),
            seed=bootstrap.seed,
            config=bootstrap.config,
            bootstrap=bootstrap,
        )
    )
    return run_id


async def test_stream_publish_resume_and_finalized_boundary(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _seed_run(database_resources)
    stream = create_stream_repository(database_resources.session_factory)
    evidence = create_scientific_evidence_repository(
        database_resources.session_factory
    )
    run = RunId(run_id)

    first = await stream.publish(
        run_id=run,
        drafts=(
            StreamRecordDraft(
                kind=StreamRecordKind.STATUS,
                envelope=make_stream_envelope(b'{"status":"running"}'),
            ),
            StreamRecordDraft(
                kind=StreamRecordKind.EVENTLESS_TICK,
                envelope=make_stream_envelope(b'{"tick":0}'),
                related_tick=0,
            ),
        ),
    )
    assert [item.cursor for item in first] == [1, 2]
    assert await stream.high_water(run_id=run) == 2

    manifest = build_evidence_manifest(
        run_id=run_id,
        objective_commit_hash="d" * 64,
        high_water=EvidenceHighWaterMarks(
            direct_memories=0,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=1,
            truth_specs=0,
        ),
    )
    resolution = ActionResolutionRecord(
        run_id=run_id,
        tick=1,
        ordinal=0,
        envelope=opaque_envelope_from_payload(
            schema_version=ACTION_RESOLUTION_SCHEMA_VERSION,
            payload=b'{"tick":1,"ordinal":0}',
        ),
    )
    boundary = await evidence.publish_finalized_boundary(
        FinalizedBoundaryBatch(
            run_id=run,
            tick=1,
            resolutions=(resolution,),
            stream_drafts=(
                StreamRecordDraft(
                    kind=StreamRecordKind.EVENT,
                    envelope=make_stream_envelope(b'{"event":1}'),
                    related_tick=1,
                ),
                StreamRecordDraft(
                    kind=StreamRecordKind.COMPLETION,
                    envelope=make_stream_envelope(b'{"done":true}'),
                ),
            ),
            manifest=manifest,
        )
    )
    assert [item.cursor for item in boundary] == [3, 4]
    resumed = await stream.read_after(run_id=run, after_cursor=2, limit=10)
    assert [item.kind for item in resumed] == [
        StreamRecordKind.EVENT,
        StreamRecordKind.COMPLETION,
    ]
    assert await evidence.get_manifest(run_id=run_id) == manifest
    resolutions = await evidence.list_action_resolutions(run_id=run_id, tick=1)
    assert len(resolutions) == 1


async def test_stream_records_are_append_only(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _seed_run(database_resources)
    stream = create_stream_repository(database_resources.session_factory)
    await stream.publish(
        run_id=RunId(run_id),
        drafts=(
            StreamRecordDraft(
                kind=StreamRecordKind.RESULT,
                envelope=make_stream_envelope(b'{"result":1}'),
            ),
        ),
    )
    async with session_scope(database_resources.session_factory) as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text(
                    "UPDATE run_stream_records SET record_kind = 'status' "
                    "WHERE run_id = :run_id AND cursor_value = 1"
                ),
                {"run_id": run_id},
            )
            await session.commit()
