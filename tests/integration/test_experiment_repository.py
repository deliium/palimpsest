"""PostgreSQL integration for experiment definition/assignment/result records."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from experiments.persistence import (
    ExperimentAssignmentRecord,
    ExperimentDefinitionRecord,
    ExperimentResultRecord,
)
from infrastructure.database import DatabaseResources
from persistence import (
    create_experiment_record_repository,
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

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64


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


def _bootstrap(*, run_id: str, seed: int) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(_unique("snap")),
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


async def _create_run(factory, *, run_id: str, seed: int) -> None:
    runs = create_run_repository(factory)
    bootstrap = _bootstrap(run_id=run_id, seed=seed)
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=WorldId("world-1"),
            seed=bootstrap.seed,
            config=bootstrap.config,
            bootstrap=bootstrap,
        )
    )


@pytest.mark.asyncio
async def test_experiment_record_idempotent_and_ordered(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    repo = create_experiment_record_repository(factory)
    experiment_id = _unique("exp")
    definition = ExperimentDefinitionRecord(
        experiment_id=experiment_id,
        schema_version="experiment-record-v1",
        payload_hash=_HASH_A,
        definition_fingerprint=_HASH_B,
    )
    await repo.append_definition(definition)
    await repo.append_definition(definition)

    with pytest.raises(PersistenceConflictError):
        await repo.append_definition(
            ExperimentDefinitionRecord(
                experiment_id=experiment_id,
                schema_version="experiment-record-v1",
                payload_hash=_HASH_C,
                definition_fingerprint=_HASH_B,
            )
        )

    run_ids = {
        "c-b-1": _unique("run-b1"),
        "c-a-0": _unique("run-a0"),
        "c-b-0": _unique("run-b0"),
    }
    for seed, run_id in enumerate(run_ids.values(), start=3):
        await _create_run(factory, run_id=run_id, seed=seed)

    assignments = [
        ExperimentAssignmentRecord(
            experiment_id=experiment_id,
            condition_id="c-b",
            seed_ordinal=1,
            replicate_index=0,
            run_id=run_ids["c-b-1"],
            seed=7,
            config_fingerprint=_HASH_A,
        ),
        ExperimentAssignmentRecord(
            experiment_id=experiment_id,
            condition_id="c-a",
            seed_ordinal=0,
            replicate_index=0,
            run_id=run_ids["c-a-0"],
            seed=3,
            config_fingerprint=_HASH_A,
        ),
        ExperimentAssignmentRecord(
            experiment_id=experiment_id,
            condition_id="c-b",
            seed_ordinal=0,
            replicate_index=0,
            run_id=run_ids["c-b-0"],
            seed=5,
            config_fingerprint=_HASH_A,
        ),
    ]
    for item in assignments:
        await repo.append_assignment(item)

    listed = await repo.list_assignments(experiment_id)
    assert [item.condition_id for item in listed] == ["c-a", "c-b", "c-b"]
    assert [item.seed_ordinal for item in listed] == [0, 0, 1]

    membership = await repo.get_membership(
        experiment_id=experiment_id, run_id=listed[0].run_id
    )
    assert membership is not None
    assert membership.source == "assignment"

    first = listed[0]
    await repo.append_result(
        ExperimentResultRecord(
            run_id=first.run_id,
            experiment_id=experiment_id,
            condition_id=first.condition_id,
            payload_hash=_HASH_C,
            stop_reason="max_ticks",
            ticks_committed=2,
        )
    )
    await repo.append_result(
        ExperimentResultRecord(
            run_id=first.run_id,
            experiment_id=experiment_id,
            condition_id=first.condition_id,
            payload_hash=_HASH_C,
            stop_reason="max_ticks",
            ticks_committed=2,
        )
    )
    with pytest.raises(PersistenceConflictError):
        await repo.append_result(
            ExperimentResultRecord(
                run_id=first.run_id,
                experiment_id=experiment_id,
                condition_id=first.condition_id,
                payload_hash=_HASH_A,
                stop_reason="max_ticks",
                ticks_committed=2,
            )
        )

    loaded = await repo.get_definition(experiment_id)
    assert loaded == definition
