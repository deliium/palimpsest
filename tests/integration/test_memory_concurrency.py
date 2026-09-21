"""Integration: concurrent idempotent access updates on episodic memory."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from memory.models import (
    ConceptMention,
    MemoryAccessReceipt,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from persistence import create_memory_service, create_run_repository
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
        snapshot_id=SnapshotId(_unique("snap")),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=17,
        config=SimulationRunConfig(seed=17),
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


async def test_concurrent_same_operation_id_applies_once(
    database_resources: DatabaseResources,
) -> None:
    run_id = _unique("mem-conc")
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
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )
    service = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-1")),
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
    )
    await service.apply(
        MemoryMutationBatch(
            writes=(
                MemoryTrace(
                    memory_id=MemoryId("shared"),
                    owner_id=AgentId("agent-1"),
                    world_revision=WorldRevision(0),
                    concepts=(
                        ConceptMention(mention_id=MentionId("c1"), concept="signal"),
                    ),
                    entities=(),
                    relations=(),
                    context=MemorySituationContext(),
                    emotional_salience=0.4,
                    confidence=0.8,
                    provenance=MemoryProvenance(
                        kind=MemorySourceKind.DIRECT_OBSERVATION,
                        source_tick=1,
                    ),
                    created_tick=1,
                    source_tick=1,
                    last_access_tick=1,
                    access_count=0,
                ),
            )
        )
    )

    receipt = MemoryAccessReceipt(
        memory_id=MemoryId("shared"),
        access_tick=5,
        operation_id="same-op",
    )

    async def _once() -> int:
        result = await service.apply(MemoryMutationBatch(accesses=(receipt,)))
        return result.access_applied_count

    counts = await asyncio.gather(*(_once() for _ in range(8)))
    assert sum(counts) == 1
    loaded = await service.get(MemoryId("shared"))
    assert loaded is not None
    assert loaded.access_count == 1


async def test_concurrent_reconsolidation_idempotent(
    database_resources: DatabaseResources,
) -> None:
    from memory.models import (
        MemoryLineage,
        ReconstructedMemory,
        ReconstructionId,
        ReconstructionRecord,
    )

    run_id = _unique("mem-recon")
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
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )
    service = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-1")),
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
    )
    root = MemoryTrace(
        memory_id=MemoryId("m-root"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c1"), concept="signal"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.4,
        confidence=0.8,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
    )
    await service.apply(MemoryMutationBatch(writes=(root,)))
    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-conc"),
        owner_id=AgentId("agent-1"),
        narrative="concurrent subjective",
        concepts=root.concepts,
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=0.5,
        emotional_salience=0.3,
        source_memory_ids=(MemoryId("m-root"),),
        generation=1,
        reconstructed_at_tick=2,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    derived = MemoryTrace(
        memory_id=MemoryId("m-derived"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=reconstructed.concepts,
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.3,
        confidence=0.5,
        provenance=root.provenance,
        created_tick=2,
        source_tick=1,
        last_access_tick=2,
        access_count=0,
        lineage=MemoryLineage(
            supersedes_memory_id=MemoryId("m-root"),
            generation=1,
            source_memory_ids=(MemoryId("m-root"),),
            reconstruction_id=ReconstructionId("recon-conc"),
        ),
    )
    batch = MemoryMutationBatch(
        writes=(derived,),
        reconstructions=(
            ReconstructionRecord(
                reconstruction_id=ReconstructionId("recon-conc"),
                run_id=MemoryRunId(run_id),
                owner_id=AgentId("agent-1"),
                source_memory_ids=(MemoryId("m-root"),),
                reconstructed=reconstructed,
                created_tick=2,
                policy_id="recall",
                policy_version="1",
                used_provider=False,
                fallback_used=False,
            ),
        ),
    )

    async def _once() -> tuple[int, int]:
        result = await service.apply(batch)
        return (
            result.reconstruction_written_count,
            result.reconstruction_idempotent_count,
        )

    outcomes = await asyncio.gather(*(_once() for _ in range(6)))
    assert sum(item[0] for item in outcomes) == 1
    assert sum(item[1] for item in outcomes) == 5
    loaded = await service.get(MemoryId("m-root"))
    assert loaded is not None
    assert loaded.concepts == root.concepts
