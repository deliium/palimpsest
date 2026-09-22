"""PostgreSQL stream resume proofs (Task 21)."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import create_run_repository, create_stream_repository
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import hash_snapshot
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
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


async def _seed_run(database_resources: DatabaseResources) -> str:
    run_id = _unique("stream-resume")
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(f"snap-{run_id}"),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=31,
        config=SimulationRunConfig(seed=31),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(make_location("loc-1", name="Camp"),),
        bodies=(
            AgentBody(
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
            ),
        ),
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
    bootstrap = WorldSnapshot(
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
    await create_run_repository(database_resources.session_factory).create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=WorldId("world-1"),
            seed=bootstrap.seed,
            config=bootstrap.config,
            bootstrap=bootstrap,
        )
    )
    return run_id


@pytest.mark.asyncio
async def test_stream_resume_without_gaps_or_duplicates(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _seed_run(database_resources)
    stream = create_stream_repository(database_resources.session_factory)
    run = RunId(run_id)
    published = await stream.publish(
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
    )
    assert [item.cursor for item in published] == [1, 2, 3, 4]
    head = await stream.high_water(run_id=run)
    assert head == 4
    first = await stream.read_after(run_id=run, after_cursor=0, limit=2)
    assert [item.cursor for item in first] == [1, 2]
    second = await stream.read_after(run_id=run, after_cursor=2, limit=10)
    assert [item.cursor for item in second] == [3, 4]
    assert {item.cursor for item in first}.isdisjoint({item.cursor for item in second})
