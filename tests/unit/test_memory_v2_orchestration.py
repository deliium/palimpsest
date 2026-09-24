"""Orchestration tests for V2 reconstructive recall vs frozen V1 path."""

from __future__ import annotations

import pytest

from agents.cognition.memory import ScopedMemoryRetriever
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    InterpretedPerception,
)
from agents.models import AgentId
from memory.models import (
    ConceptMention,
    MemoryDynamicsPolicy,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryRecallRequest,
    MemoryReconstructionPolicy,
    MemoryRetrieveRequest,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    ReconstructionId,
    default_memory_dynamics_policy,
)
from memory.service import InMemoryMemoryService
from tests.simulation_helpers import alive_body
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf

pytestmark = pytest.mark.unit


def _trace(
    memory_id: str,
    *,
    concept: str,
    tick: int,
    tags: tuple[str, ...] = (),
    salience: float = 0.5,
    access_count: int = 0,
) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(
            ConceptMention(
                mention_id=MentionId(f"{memory_id}-c"),
                concept=concept,
            ),
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(tags=tags, location_id=EntityId("loc-1")),
        emotional_salience=salience,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=tick,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=access_count,
    )


def _retrieve(*, tick: int = 10, limit: int = 8) -> MemoryRetrieveRequest:
    return MemoryRetrieveRequest(
        current_tick=tick,
        limit=limit,
        scoring_policy=MemoryScoringPolicy(
            policy_id="score",
            version="1",
            weights=MemoryScoreWeights(recency=1.0, emotional_salience=0.5),
        ),
    )


def _observation(*, tick: int = 10) -> Observation:
    body = alive_body()
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=body.life_status,
            carry_capacity=body.carry_capacity,
        ),
    )


@pytest.mark.asyncio
async def test_v1_recall_leaves_audits_empty() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    await service.apply(
        MemoryMutationBatch(
            writes=(
                _trace("m-1", concept="gate", tick=4, tags=("camp",)),
                _trace("m-2", concept="door", tick=2, tags=("camp",)),
            )
        )
    )
    result = await service.recall(
        MemoryRecallRequest(
            retrieve=_retrieve(),
            reconstruction_id=ReconstructionId("recon-v1"),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall", version="1"
            ),
        )
    )
    assert result.audits == ()
    assert len(result.reconstructions) == 1


@pytest.mark.asyncio
async def test_v2_recall_emits_audit_and_is_deterministic() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    await service.apply(
        MemoryMutationBatch(
            writes=(
                _trace("m-1", concept="gate", tick=4, tags=("camp",), salience=0.7),
                _trace("m-2", concept="gate", tick=3, tags=("camp",), salience=0.6),
                _trace("m-3", concept="river", tick=2, tags=("river",), salience=0.4),
            )
        )
    )
    policy = default_memory_dynamics_policy()
    request = MemoryRecallRequest(
        retrieve=_retrieve(),
        reconstruction_id=ReconstructionId("recon-v2"),
        reconstruction_policy=MemoryReconstructionPolicy(
            policy_id="recall", version="1"
        ),
        dynamics_policy=policy,
    )
    first = await service.recall(request)
    second = await service.recall(request)
    assert len(first.audits) == 1
    assert first.audits == second.audits
    assert first.reconstructions == second.reconstructions
    audit = first.audits[0]
    assert audit.owner_id == AgentId("agent-1")
    assert audit.source_memory_ids
    assert audit.reconstruction_id.value == "recon-v2"


@pytest.mark.asyncio
async def test_v2_adapter_strips_audits_from_agent_context() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    await service.apply(
        MemoryMutationBatch(
            writes=(
                _trace("m-1", concept="gate", tick=4, tags=("camp",)),
                _trace("m-2", concept="wall", tick=3, tags=("camp",)),
            )
        )
    )
    retriever = ScopedMemoryRetriever(
        service,
        scoring_policy=MemoryScoringPolicy(
            policy_id="score",
            version="1",
            weights=MemoryScoreWeights(recency=1.0),
        ),
        dynamics_policy=default_memory_dynamics_policy(),
    )
    observation = _observation(tick=10)
    loop_input = CognitiveLoopInput(
        agent_id=AgentId("agent-1"),
        observation=observation,
        internal_state=InternalAgentState(owner_id=AgentId("agent-1")),
    )
    perception = InterpretedPerception(
        owner_id=AgentId("agent-1"),
        observer_id=observation.observer_id,
        tick=observation.tick,
        revision=observation.revision,
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(),
        counts={},
        confidence=1.0,
    )
    context = await retriever.retrieve(loop_input, perception)
    assert not hasattr(context, "audits")
    assert context.reconstructions
    raw = await service.recall(
        MemoryRecallRequest(
            retrieve=_retrieve(),
            reconstruction_id=ReconstructionId("recon-check"),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall", version="1"
            ),
            dynamics_policy=default_memory_dynamics_policy(),
        )
    )
    assert raw.audits


def test_invalid_dynamics_policy_fails_closed_at_request() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        MemoryDynamicsPolicy(version="nope")


@pytest.mark.asyncio
async def test_v2_semanticization_pending_maps_to_belief_revision() -> None:
    from agents.cognition.memory import _belief_revision_from_semanticization
    from memory.models import PendingSemanticizationIntent

    scope = MemoryScope(run_id=MemoryRunId("run-sem"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    await service.apply(
        MemoryMutationBatch(
            writes=(
                _trace(
                    "m-1",
                    concept="gate",
                    tick=1,
                    tags=("camp",),
                    access_count=5,
                ),
                _trace(
                    "m-2",
                    concept="gate",
                    tick=2,
                    tags=("camp",),
                    access_count=5,
                ),
            )
        )
    )
    policy = MemoryDynamicsPolicy(
        semanticization_similarity_threshold=0.5,
        semanticization_repeat_threshold=2,
        source_confusion_mass=0.0,
    )
    result = await service.recall(
        MemoryRecallRequest(
            retrieve=_retrieve(tick=10),
            reconstruction_id=ReconstructionId("recon-sem"),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall", version="1"
            ),
            dynamics_policy=policy,
        )
    )
    assert result.pending_semanticization is not None
    revision = _belief_revision_from_semanticization(
        result.pending_semanticization,
        owner_id=AgentId("agent-1"),
    )
    assert revision is not None
    assert revision.owner_id == AgentId("agent-1")
    assert revision.belief_id is not None

    with pytest.raises(ValueError, match="owner"):
        _belief_revision_from_semanticization(
            PendingSemanticizationIntent(
                owner_id=AgentId("other"),
                tick=10,
                source_memory_ids=(MemoryId("m-1"),),
                gist_concepts=("gate",),
            ),
            owner_id=AgentId("agent-1"),
        )


def test_v1_never_emits_pending_semanticization_on_request_without_dynamics() -> None:
    assert (
        MemoryRecallRequest(
            retrieve=_retrieve(),
            reconstruction_id=ReconstructionId("recon-x"),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall", version="1"
            ),
        ).dynamics_policy
        is None
    )
