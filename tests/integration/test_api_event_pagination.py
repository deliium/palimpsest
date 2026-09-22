"""PostgreSQL event pagination proofs (Task 21)."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import (
    create_objective_evidence_loader,
    create_run_repository,
    create_tick_journal_repository,
)
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.inspection import EventKeysetCursor
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
from world.effects import ActionCause
from world.events import OccurrenceContext, Waited, make_physical_replayable_event
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
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


def _bootstrap(*, run_id: str) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(f"snap-{run_id}"),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=41,
        config=SimulationRunConfig(seed=41),
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


def _wait_event(*, run_id: str, tick: int, sequence: int, revision: int) -> object:
    actor = EntityId("body-1")
    request_id = RequestId(f"req-{tick}-{sequence}")
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id=run_id,
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=ActionCause(request_id, actor),
        resulting_revision=WorldRevision(revision),
        details=Waited(),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            private_recipient_ids=(),
            affected_entity_ids=(actor,),
        ),
    )


@pytest.mark.asyncio
async def test_api_event_keyset_pagination_no_gaps_duplicates(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    loader = create_objective_evidence_loader(factory)
    run_id = _unique("api-page")
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
    predecessor = None
    base_revision = 0
    for tick in range(3):
        events = (
            _wait_event(
                run_id=run_id, tick=tick, sequence=0, revision=base_revision + 1
            ),
            _wait_event(
                run_id=run_id, tick=tick, sequence=1, revision=base_revision + 2
            ),
        )
        commit = await journal.append_tick(
            TickAppendRequest(
                run_id=RunId(run_id),
                tick=Tick(tick),
                expected_base_revision=WorldRevision(base_revision),
                expected_predecessor_commit_hash=predecessor,
                idempotency_key=_unique(f"idem-{tick}"),
                events=events,
            )
        )
        predecessor = commit.commit_hash
        base_revision = commit.resulting_revision.value

    first = await loader.load_events_page(run_id=run_id, limit=2)
    second = await loader.load_events_page(
        run_id=run_id, after=first.next_cursor, limit=2
    )
    third = await loader.load_events_page(
        run_id=run_id, after=second.next_cursor, limit=2
    )
    ids = [
        event.event_id.value
        for page in (first, second, third)
        for event in page.events
    ]
    assert len(ids) == len(set(ids))
    assert len(ids) == 6
    assert isinstance(first.next_cursor, EventKeysetCursor)
