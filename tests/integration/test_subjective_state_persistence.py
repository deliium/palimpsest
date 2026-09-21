"""Integration: atomic subjective state commit (memory + belief) on PostgreSQL."""

from __future__ import annotations

import uuid

import pytest
from tests.simulation_helpers import make_location, make_weather

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from memory.belief_formation import BeliefFormationPolicy
from memory.beliefs import (
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticClaim,
)
from memory.models import (
    ConceptMention,
    MemoryId,
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
from persistence import (
    create_memory_service,
    create_run_repository,
    create_subjective_state_service,
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
    WorldSnapshot,
)
from simulation.subjective_state import SubjectiveMutationBatch
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


def _policy() -> MemoryScoringPolicy:
    return MemoryScoringPolicy(
        policy_id="structured",
        version="1",
        weights=MemoryScoreWeights(recency=1.0, emotional_salience=0.5),
    )


def _trace(*, memory_id: str, owner_id: str, tick: int) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner_id),
        world_revision=WorldRevision(0),
        concepts=(
            ConceptMention(mention_id=MentionId(f"c-{memory_id}"), concept="food"),
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(location_id=EntityId("loc-1"), tags=("night",)),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=tick,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
    )


def _belief_request(*, tick: int, memory_id: str, op: str) -> BeliefRevisionRequest:
    from memory.belief_formation import (
        DEFAULT_BELIEF_FORMATION_POLICY,
        belief_id_for_claim,
    )

    claim = SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=AgentId("agent-1")),
        predicate="experienced_concept",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="food"),
    )
    evidence = BeliefEvidenceBundle(
        supporting=(
            BeliefEvidenceContribution(
                memory_id=MemoryId(memory_id),
                stance=EvidenceStance.SUPPORTING,
                contribution=0.5,
                ordinal=0,
                lineage_root_id=MemoryId(memory_id),
            ),
        ),
        contradicting=(),
    )
    return BeliefRevisionRequest(
        owner_id=AgentId("agent-1"),
        operation_id=op,
        logical_tick=tick,
        claim=claim,
        evidence=evidence,
        policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
        belief_id=belief_id_for_claim(owner_id=AgentId("agent-1"), claim=claim),
    )


async def _prepare_run(database_resources: DatabaseResources) -> str:
    run_id = _unique("subj-run")
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


async def test_subjective_commit_memory_and_belief_revision(
    database_resources: DatabaseResources,
) -> None:
    run_id = await _prepare_run(database_resources)
    scope = MemoryScope(run_id=MemoryRunId(run_id), owner_id=AgentId("agent-1"))
    memory = create_memory_service(
        scope=scope,
        session_factory=database_resources.session_factory,
        scoring_policy=_policy(),
    )
    service = create_subjective_state_service(
        scope=scope,
        session_factory=database_resources.session_factory,
        memory_service=memory,
        belief_policy=BeliefFormationPolicy(
            policy_id="test-belief",
            version="1",
            min_independent_observations=1,
        ),
    )
    memory_id = _unique("mem")
    batch = SubjectiveMutationBatch(
        operation_id=_unique("op"),
        logical_tick=0,
        memory_writes=(_trace(memory_id=memory_id, owner_id="agent-1", tick=0),),
        belief_revisions=(_belief_request(tick=0, memory_id=memory_id, op="b-1"),),
        expected_revision=0,
    )
    receipt = await service.commit(batch)
    assert receipt.revision == 1
    assert receipt.memory_written_count == 1
    assert receipt.belief_revision_count == 1
    assert receipt.idempotent is False
    assert await memory.get(MemoryId(memory_id)) is not None

    again = await service.commit(batch)
    assert again.revision == 1
    assert again.idempotent is True
    assert service.revision == 1
