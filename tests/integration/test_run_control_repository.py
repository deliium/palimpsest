"""PostgreSQL integration for durable run-control repository."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import (
    create_run_control_repository,
    create_run_repository,
)
from persistence.errors import PersistenceConflictError
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
    ConfigAvailability,
    ExecutionLease,
    RunControlRecord,
    RunLifecycleState,
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

_HASH = "b" * 64


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


def _bootstrap(*, run_id: str, seed: int = 11) -> WorldSnapshot:
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


@pytest.mark.asyncio
async def test_run_control_configure_transition_and_lease(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    control = create_run_control_repository(factory)
    run_id = _unique("run")
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
    record = RunControlRecord(
        run_id=RunId(run_id),
        lifecycle_state=RunLifecycleState.CONFIGURED,
        lifecycle_version=0,
        config_availability=ConfigAvailability.AVAILABLE,
        ticks_committed=0,
        progress_cursor=0,
        config_schema_version="runner-config-v2",
        config_fingerprint=_HASH,
        config_payload=b'{"schema_version":"runner-config-v2"}',
    )
    stored = await control.upsert_configured(record)
    assert stored.config_availability is ConfigAvailability.AVAILABLE
    ready = await control.transition(
        run_id=RunId(run_id),
        expected_version=0,
        to_state=RunLifecycleState.READY,
        reason_code="arm",
        operation_id=_unique("op"),
    )
    claimed = await control.claim_lease(
        run_id=RunId(run_id),
        expected_version=ready.lifecycle_version,
        lease=ExecutionLease(
            lease_id=_unique("lease"),
            owner_id="owner-1",
            claimed_at_unix_ms=1_000,
            heartbeat_at_unix_ms=1_000,
            expires_at_unix_ms=5_000,
        ),
        operation_id=_unique("op"),
    )
    assert claimed.lease is not None
    with pytest.raises(PersistenceConflictError):
        await control.transition(
            run_id=RunId(run_id),
            expected_version=0,
            to_state=RunLifecycleState.STARTING,
            reason_code="stale",
            operation_id=_unique("op"),
        )
    loaded = await control.get(RunId(run_id))
    assert loaded is not None
    assert loaded.lifecycle_state is RunLifecycleState.READY
