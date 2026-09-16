"""Unit checks for persistence reader helpers and repository factories."""

from __future__ import annotations

from decimal import Decimal

import pytest

from agents.models import AgentId
from persistence import (
    PersistenceAdapterError,
    create_experiment_repository,
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from persistence.errors import PersistenceCorruptionError
from persistence.orm import WorldEventOrm
from persistence.readers import (
    advisory_lock_keys,
    canonical_payload_dict,
    event_details_payload,
    event_from_orm,
    nonneg_int_from_numeric,
    snapshot_from_canonical_payload,
)
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import hash_snapshot, hash_world_event
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from world.events import Waited, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

pytestmark = pytest.mark.unit


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
    )


def _snapshot(*, seed: int = 7) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-1"),
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=seed,
        config=SimulationRunConfig(seed=seed),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        bodies=(_alive(),),
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


def test_advisory_lock_keys_are_deterministic() -> None:
    assert advisory_lock_keys("run-1") == advisory_lock_keys("run-1")
    assert advisory_lock_keys("run-1") != advisory_lock_keys("run-2")


def test_nonneg_int_from_numeric_accepts_large_decimal() -> None:
    huge = 2**200
    assert nonneg_int_from_numeric(Decimal(huge), field="seed") == huge
    assert nonneg_int_from_numeric(huge, field="seed") == huge
    with pytest.raises(PersistenceCorruptionError):
        nonneg_int_from_numeric(Decimal("1.5"), field="seed")
    with pytest.raises(PersistenceCorruptionError):
        nonneg_int_from_numeric(-1, field="seed")


def test_canonical_payload_round_trip_and_event_details() -> None:
    snapshot = _snapshot(seed=2**90)
    payload = canonical_payload_dict(snapshot)
    rebuilt = snapshot_from_canonical_payload(
        payload, expected_integrity_hash=snapshot.integrity_hash.value
    )
    assert rebuilt.seed == 2**90
    assert rebuilt.integrity_hash == snapshot.integrity_hash
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    assert event_details_payload(event)["kind"] == "wait"


def test_event_from_orm_rebuilds_replayable_event() -> None:
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    row = WorldEventOrm(
        run_id=event.run_id,
        tick=event.tick,
        sequence=event.sequence,
        event_id=event.event_id.value,
        world_id=event.world_id.value,
        request_id=event.request_id.value,
        resulting_revision=event.resulting_revision.value,
        schema_version=event.schema_version,
        event_type=event.event_type,
        actor_id=event.actor_id.value if event.actor_id else None,
        target_id=None,
        details=event_details_payload(event),
        payload_hash=hash_world_event(event).value,
    )
    rebuilt = event_from_orm(row)
    assert rebuilt == event


def test_snapshot_integrity_mismatch_is_corruption() -> None:
    snapshot = _snapshot()
    payload = canonical_payload_dict(snapshot)
    with pytest.raises(PersistenceCorruptionError):
        snapshot_from_canonical_payload(
            payload, expected_integrity_hash="b" * 64
        )


def test_repository_factories_require_session_factory() -> None:
    with pytest.raises(PersistenceAdapterError) as err:
        create_run_repository()
    assert err.value.code == "missing_session_factory"
    with pytest.raises(PersistenceAdapterError):
        create_tick_journal_repository()
    with pytest.raises(PersistenceAdapterError):
        create_snapshot_repository()
    with pytest.raises(PersistenceAdapterError):
        create_experiment_repository()
