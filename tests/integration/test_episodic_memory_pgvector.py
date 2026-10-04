"""Integration: owner-scoped episodic memory with optional pgvector embeddings."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from memory.models import (
    ConceptMention,
    MemoryAccessReceipt,
    MemoryEmbedding,
    MemoryForgetRequest,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryQueryContext,
    MemoryQueryFilters,
    MemoryRetentionPolicy,
    MemoryRetrieveRequest,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from memory.service import InMemoryMemoryService, MemoryServiceError
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


def _bootstrap(*, run_id: str, seed: int = 11) -> WorldSnapshot:
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


def _policy(*, semantic: bool = False) -> MemoryScoringPolicy:
    if semantic:
        return MemoryScoringPolicy(
            policy_id="semantic",
            version="1",
            weights=MemoryScoreWeights(semantic_relevance=1.0, recency=0.0),
            embedding_dimension=2,
        )
    return MemoryScoringPolicy(
        policy_id="structured",
        version="1",
        weights=MemoryScoreWeights(recency=1.0, emotional_salience=0.5),
    )


def _trace(
    *,
    memory_id: str,
    owner_id: str,
    tick: int,
    salience: float = 0.5,
    embedding: MemoryEmbedding | None = None,
    concept: str = "campfire",
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner_id),
        world_revision=WorldRevision(0),
        concepts=(
            ConceptMention(mention_id=MentionId(f"c-{memory_id}"), concept=concept),
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(location_id=EntityId("loc-1"), tags=("night",)),
        emotional_salience=salience,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=tick,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
        embedding=embedding,
    )


async def _prepare_run(database_resources: DatabaseResources) -> str:
    run_id = _unique("mem-run")
    runs = create_run_repository(database_resources.session_factory)
    bootstrap = _bootstrap(run_id=run_id, seed=2**40 + uuid.uuid4().int % 1000)
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


async def test_sql_memory_round_trip_and_owner_isolation(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _prepare_run(database_resources)
    policy = _policy()
    alice = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("alice")),
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
    )
    bob = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("bob")),
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
    )

    await alice.apply(
        MemoryMutationBatch(
            writes=(
                _trace(memory_id="m-alice", owner_id="alice", tick=1, salience=0.8),
            )
        )
    )
    await bob.apply(
        MemoryMutationBatch(
            writes=(_trace(memory_id="m-bob", owner_id="bob", tick=1, salience=0.9),)
        )
    )

    alice_hits = await alice.retrieve(
        MemoryRetrieveRequest(
            current_tick=2,
            scoring_policy=policy,
            filters=MemoryQueryFilters(),
            context=MemoryQueryContext(),
            limit=10,
        )
    )
    assert [hit.trace.memory_id.value for hit in alice_hits.hits] == ["m-alice"]
    bob_get = await bob.get(MemoryId("m-alice"))
    assert bob_get is None


async def test_sql_and_python_ranking_parity_with_embeddings(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _prepare_run(database_resources)
    policy = _policy(semantic=True)
    scope = MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-1"))
    sql = create_memory_service(
        scope=scope,
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
    )
    ref = InMemoryMemoryService(scope)
    near = MemoryEmbedding(vector=(1.0, 0.0), model="fake", version="1")
    far = MemoryEmbedding(vector=(0.0, 1.0), model="fake", version="1")
    batch = MemoryMutationBatch(
        writes=(
            _trace(memory_id="near", owner_id="agent-1", tick=1, embedding=near),
            _trace(memory_id="far", owner_id="agent-1", tick=2, embedding=far),
        )
    )
    await sql.apply(batch)
    await ref.apply(batch)

    request = MemoryRetrieveRequest(
        current_tick=3,
        scoring_policy=policy,
        filters=MemoryQueryFilters(),
        context=MemoryQueryContext(),
        query_embedding=MemoryEmbedding(vector=(1.0, 0.0), model="fake", version="1"),
        limit=2,
    )
    sql_result = await sql.retrieve(request)
    ref_result = await ref.retrieve(request)
    assert [hit.trace.memory_id.value for hit in sql_result.hits] == [
        hit.trace.memory_id.value for hit in ref_result.hits
    ]
    assert [hit.score for hit in sql_result.hits] == [
        hit.score for hit in ref_result.hits
    ]


async def test_access_idempotency_and_forget(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _prepare_run(database_resources)
    policy = _policy()
    service = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-1")),
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
    )
    await service.apply(
        MemoryMutationBatch(
            writes=(_trace(memory_id="m1", owner_id="agent-1", tick=1),)
        )
    )
    receipt = MemoryAccessReceipt(
        memory_id=MemoryId("m1"),
        access_tick=2,
        operation_id="op-1",
    )
    first = await service.apply(MemoryMutationBatch(accesses=(receipt,)))
    second = await service.apply(MemoryMutationBatch(accesses=(receipt,)))
    assert first.access_applied_count == 1
    assert second.access_idempotent_count == 1
    loaded = await service.get(MemoryId("m1"))
    assert loaded is not None
    assert loaded.access_count == 1

    forgotten = await service.forget(
        MemoryForgetRequest(
            current_tick=100,
            retention_policy=MemoryRetentionPolicy(
                policy_id="retain",
                version="1",
                half_life_ticks=1,
                forget_threshold=0.99,
            ),
        )
    )
    assert forgotten.forgotten_count == 1
    assert await service.snapshot() == ()


async def test_conflicting_write_rolls_back_batch(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _prepare_run(database_resources)
    policy = _policy()
    service = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-1")),
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
    )
    await service.apply(
        MemoryMutationBatch(
            writes=(_trace(memory_id="m1", owner_id="agent-1", tick=1),)
        )
    )
    with pytest.raises(MemoryServiceError):
        await service.apply(
            MemoryMutationBatch(
                writes=(
                    _trace(memory_id="m1", owner_id="agent-1", tick=2),
                    _trace(memory_id="m2", owner_id="agent-1", tick=2),
                )
            )
        )
    assert await service.get(MemoryId("m2")) is None


async def test_sql_reconsolidation_idempotent_and_leaves_source_unchanged(
    database_resources: DatabaseResources,
) -> None:
    from memory.models import (
        MemoryLineage,
        ReconstructedMemory,
        ReconstructionId,
        ReconstructionRecord,
    )

    run_id = await _prepare_run(database_resources)
    policy = _policy()
    service = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-1")),
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
    )
    root = _trace(memory_id="m-root", owner_id="agent-1", tick=1)
    await service.apply(MemoryMutationBatch(writes=(root,)))
    reconstructed = ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-sql"),
        owner_id=AgentId("agent-1"),
        narrative="subjective sql recall",
        concepts=root.concepts,
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=0.6,
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
        confidence=0.6,
        provenance=root.provenance,
        created_tick=2,
        source_tick=1,
        last_access_tick=2,
        access_count=0,
        lineage=MemoryLineage(
            supersedes_memory_id=MemoryId("m-root"),
            generation=1,
            source_memory_ids=(MemoryId("m-root"),),
            reconstruction_id=ReconstructionId("recon-sql"),
        ),
    )
    record = ReconstructionRecord(
        reconstruction_id=ReconstructionId("recon-sql"),
        run_id=MemoryRunId(run_id),
        owner_id=AgentId("agent-1"),
        source_memory_ids=(MemoryId("m-root"),),
        reconstructed=reconstructed,
        created_tick=2,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    batch = MemoryMutationBatch(writes=(derived,), reconstructions=(record,))
    first = await service.apply(batch)
    second = await service.apply(batch)
    assert first.reconstruction_written_count == 1
    assert second.reconstruction_idempotent_count == 1
    stored_root = await service.get(MemoryId("m-root"))
    assert stored_root is not None
    assert stored_root.concepts == root.concepts
    assert stored_root.forgotten_at_tick is None
    stored_derived = await service.get(MemoryId("m-derived"))
    assert stored_derived is not None
    assert stored_derived.lineage.reconstruction_id == ReconstructionId("recon-sql")


async def test_retrieve_respects_candidate_cap(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _prepare_run(database_resources)
    policy = _policy()
    service = create_memory_service(
        scope=MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-1")),
        session_factory=database_resources.session_factory,
        scoring_policy=policy,
        max_candidates=5,
    )
    writes = tuple(
        _trace(memory_id=f"m-{index}", owner_id="agent-1", tick=index, salience=0.5)
        for index in range(1, 21)
    )
    await service.apply(MemoryMutationBatch(writes=writes))
    result = await service.retrieve(
        MemoryRetrieveRequest(
            current_tick=30,
            scoring_policy=policy,
            filters=MemoryQueryFilters(),
            context=MemoryQueryContext(),
            limit=10,
        )
    )
    assert result.candidate_count <= 5
    assert len(result.hits) <= 5


async def test_retrieve_rejects_limit_above_max_query_limit() -> None:
    with pytest.raises(ValueError, match="out_of_range"):
        MemoryRetrieveRequest(
            current_tick=1,
            scoring_policy=_policy(),
            filters=MemoryQueryFilters(),
            context=MemoryQueryContext(),
            limit=257,
        )
