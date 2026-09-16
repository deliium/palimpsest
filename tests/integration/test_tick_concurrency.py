"""Integration: concurrent tick writers serialize via advisory locks."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import (
    PersistenceConflictError,
    create_run_repository,
    create_tick_journal_repository,
)
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
    TickAppendRequest,
    WorldSnapshot,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _bootstrap(run_id: str) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(_unique("snap")),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=3,
        config=SimulationRunConfig(seed=3),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
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
            ),
        ),
        items=(),
        resources=(),
        weather=(),
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


async def test_concurrent_first_tick_writers_one_wins(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    run_id = _unique("run")
    bootstrap = _bootstrap(run_id)
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=WorldId("world-1"),
            seed=3,
            config=SimulationRunConfig(seed=3),
            bootstrap=bootstrap,
        )
    )

    async def _append(key: str) -> object:
        request = TickAppendRequest(
            run_id=RunId(run_id),
            tick=Tick(0),
            expected_base_revision=WorldRevision(0),
            expected_predecessor_commit_hash=None,
            idempotency_key=key,
            events=(),
        )
        return await journal.append_tick(request)

    results = await asyncio.gather(
        _append(_unique("idem-a")),
        _append(_unique("idem-b")),
        return_exceptions=True,
    )
    successes = [item for item in results if not isinstance(item, BaseException)]
    failures = [item for item in results if isinstance(item, BaseException)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], PersistenceConflictError)

    stored = await journal.get_tick_commit(RunId(run_id), Tick(0))
    assert stored is not None
    assert stored.event_count == 0
