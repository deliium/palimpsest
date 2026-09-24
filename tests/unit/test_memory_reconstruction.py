"""Contract tests for reconstructive recall and lineage models."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.models import (
    Belief,
    BeliefId,
    ConceptMention,
    MemoryAgeSemantics,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemoryRecallContext,
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
    RecallEvidence,
    RecallSourceEvidence,
    ReconstructedMemory,
    ReconstructionFallbackMode,
    ReconstructionId,
    ReconstructionRecord,
    validate_reconstructed_memory,
)
from world.identifiers import WorldRevision

pytestmark = pytest.mark.unit


def _policy() -> MemoryReconstructionPolicy:
    return MemoryReconstructionPolicy(policy_id="recall", version="1")


def _retrieve() -> MemoryRetrieveRequest:
    return MemoryRetrieveRequest(
        current_tick=5,
        limit=3,
        scoring_policy=MemoryScoringPolicy(
            policy_id="score",
            version="1",
            weights=MemoryScoreWeights(recency=1.0),
        ),
    )


def _source(*, memory_id: str = "m-1", rank: int = 1) -> RecallSourceEvidence:
    return RecallSourceEvidence(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        rank=rank,
        score=0.8,
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.4,
        confidence=0.9,
        source_confidence=0.9,
        episode_age_ticks=2,
        storage_age_ticks=3,
        generation=0,
        provenance_kind=MemorySourceKind.DIRECT_OBSERVATION,
    )


def _reconstructed(*, sources: tuple[str, ...] = ("m-1",)) -> ReconstructedMemory:
    return ReconstructedMemory(
        reconstruction_id=ReconstructionId("recon-1"),
        owner_id=AgentId("agent-1"),
        narrative="subjective gate memory",
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        confidence=0.7,
        emotional_salience=0.4,
        source_memory_ids=tuple(MemoryId(item) for item in sources),
        generation=1,
        reconstructed_at_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )


def test_lineage_requires_sources_for_reconstruction_and_dense_generation() -> None:
    with pytest.raises(ValueError, match="required_for_reconstruction"):
        MemoryLineage(
            generation=1,
            reconstruction_id=ReconstructionId("recon-1"),
        )
    with pytest.raises(ValueError, match="derived_requires_positive"):
        MemoryLineage(source_memory_ids=(MemoryId("m-1"),), generation=0)
    lineage = MemoryLineage(
        supersedes_memory_id=MemoryId("m-1"),
        source_memory_ids=(MemoryId("m-1"), MemoryId("m-2")),
        generation=2,
        reconstruction_id=ReconstructionId("recon-1"),
    )
    assert lineage.source_memory_ids[0].value == "m-1"
    assert "recon-1" not in repr(lineage)
    assert lineage.reconstruction_id is not None


def test_lineage_rejects_supersedes_outside_sources() -> None:
    with pytest.raises(ValueError, match="not_in_sources"):
        MemoryLineage(
            supersedes_memory_id=MemoryId("m-9"),
            source_memory_ids=(MemoryId("m-1"),),
            generation=1,
            reconstruction_id=ReconstructionId("recon-1"),
        )


def test_trace_rejects_self_source_in_lineage() -> None:
    with pytest.raises(ValueError, match="self_reference"):
        MemoryTrace(
            memory_id=MemoryId("m-1"),
            owner_id=AgentId("agent-1"),
            world_revision=WorldRevision(0),
            concepts=(),
            entities=(),
            relations=(),
            context=MemorySituationContext(),
            emotional_salience=0.0,
            confidence=1.0,
            provenance=MemoryProvenance(
                kind=MemorySourceKind.DIRECT_OBSERVATION,
                source_tick=0,
            ),
            created_tick=0,
            source_tick=0,
            last_access_tick=0,
            access_count=0,
            lineage=MemoryLineage(
                source_memory_ids=(MemoryId("m-1"),),
                generation=1,
                reconstruction_id=ReconstructionId("recon-1"),
            ),
        )


def test_recall_request_requires_derived_id_when_reconsolidating() -> None:
    request = MemoryRecallRequest(
        retrieve=_retrieve(),
        reconstruction_id=ReconstructionId("recon-1"),
        reconstruction_policy=_policy(),
        beliefs=(
            Belief(
                belief_id=BeliefId("b-1"),
                owner_id=AgentId("agent-1"),
                proposition="gate exists",
                confidence=0.5,
                evidence_memory_ids=(MemoryId("m-1"),),
            ),
        ),
        recall_context=MemoryRecallContext(emotional_significance=0.2),
    )
    assert request.retrieve.current_tick == 5
    assert "gate exists" not in repr(request)
    with pytest.raises(ValueError, match="required_for_reconsolidate"):
        MemoryRecallRequest(
            retrieve=_retrieve(),
            reconstruction_id=ReconstructionId("recon-1"),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall",
                version="1",
                reconsolidate=True,
            ),
        )


def test_recall_evidence_enforces_owner_and_dense_ranks() -> None:
    evidence = RecallEvidence(
        owner_id=AgentId("agent-1"),
        current_tick=5,
        reconstruction_id=ReconstructionId("recon-1"),
        policy=_policy(),
        sources=(_source(),),
        beliefs=(),
        recall_context=MemoryRecallContext(),
    )
    assert evidence.sources[0].episode_age_ticks == 2
    with pytest.raises(ValueError, match="owner_mismatch"):
        RecallEvidence(
            owner_id=AgentId("agent-1"),
            current_tick=5,
            reconstruction_id=ReconstructionId("recon-1"),
            policy=_policy(),
            sources=(
                RecallSourceEvidence(
                    memory_id=MemoryId("m-1"),
                    owner_id=AgentId("agent-2"),
                    rank=1,
                    score=0.5,
                    concepts=(),
                    entities=(),
                    relations=(),
                    context=MemorySituationContext(),
                    emotional_salience=0.0,
                    confidence=1.0,
                    source_confidence=1.0,
                    episode_age_ticks=0,
                    storage_age_ticks=0,
                    generation=0,
                    provenance_kind=MemorySourceKind.DIRECT_OBSERVATION,
                ),
            ),
            beliefs=(),
            recall_context=MemoryRecallContext(),
        )


def test_reconstructed_memory_safe_repr_and_semantic_validation() -> None:
    reconstructed = _reconstructed()
    assert "subjective gate memory" not in repr(reconstructed)
    evidence = RecallEvidence(
        owner_id=AgentId("agent-1"),
        current_tick=5,
        reconstruction_id=ReconstructionId("recon-1"),
        policy=_policy(),
        sources=(_source(),),
        beliefs=(),
        recall_context=MemoryRecallContext(),
    )
    assert (
        validate_reconstructed_memory(reconstructed, evidence=evidence) is reconstructed
    )
    with pytest.raises(ValueError, match="unknown_source"):
        validate_reconstructed_memory(
            _reconstructed(sources=("m-missing",)),
            evidence=evidence,
        )


def test_reconstruction_record_aligns_with_reconstructed_episode() -> None:
    reconstructed = _reconstructed()
    record = ReconstructionRecord(
        reconstruction_id=ReconstructionId("recon-1"),
        run_id=MemoryRunId("run-1"),
        owner_id=AgentId("agent-1"),
        source_memory_ids=(MemoryId("m-1"),),
        reconstructed=reconstructed,
        created_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    assert record.source_memory_ids == reconstructed.source_memory_ids
    with pytest.raises(ValueError, match="mismatch"):
        ReconstructionRecord(
            reconstruction_id=ReconstructionId("recon-1"),
            run_id=MemoryRunId("run-1"),
            owner_id=AgentId("agent-1"),
            source_memory_ids=(MemoryId("m-1"),),
            reconstructed=reconstructed,
            created_tick=9,
            policy_id="recall",
            policy_version="1",
            used_provider=False,
            fallback_used=False,
        )


def test_reconstruction_policy_age_semantics_and_bounds() -> None:
    policy = MemoryReconstructionPolicy(
        policy_id="recall",
        version="1",
        age_semantics=MemoryAgeSemantics.STORAGE,
        fallback_mode=ReconstructionFallbackMode.REJECT,
        generation_weight=0.25,
    )
    assert policy.age_semantics is MemoryAgeSemantics.STORAGE
    with pytest.raises(ValueError, match="out_of_range"):
        MemoryReconstructionPolicy(
            policy_id="recall",
            version="1",
            max_narrative_chars=0,
        )


@pytest.mark.asyncio
async def test_deterministic_recall_projects_ranked_sources_without_invention() -> None:
    from memory.models import (
        MemoryMutationBatch,
        MemoryRetrieveRequest,
        MemoryScoreWeights,
        MemoryScoringPolicy,
    )
    from memory.service import InMemoryMemoryService

    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    older = MemoryTrace(
        memory_id=MemoryId("m-old"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-old"), concept="door"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.2,
        confidence=0.5,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=0,
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
    )
    newer = MemoryTrace(
        memory_id=MemoryId("m-new"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-new"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.8,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=4,
        ),
        created_tick=4,
        source_tick=4,
        last_access_tick=4,
        access_count=0,
    )
    await service.apply(MemoryMutationBatch(writes=(older, newer)))
    result = await service.recall(
        MemoryRecallRequest(
            retrieve=MemoryRetrieveRequest(
                current_tick=5,
                limit=2,
                scoring_policy=MemoryScoringPolicy(
                    policy_id="score",
                    version="1",
                    weights=MemoryScoreWeights(recency=1.0),
                ),
            ),
            reconstruction_id=ReconstructionId("recon-1"),
            reconstruction_policy=_policy(),
        )
    )
    reconstructed = result.reconstructions[0]
    assert reconstructed.source_memory_ids[0].value == "m-new"
    assert "gate" in reconstructed.narrative
    assert reconstructed.used_provider is False
    assert result.reconsolidation is None
    assert result.audits == ()


@pytest.mark.asyncio
async def test_reconsolidation_requires_fresh_id_and_dense_generation() -> None:
    from memory.models import (
        MemoryMutationBatch,
        MemoryRetrieveRequest,
        MemoryScoreWeights,
        MemoryScoringPolicy,
    )
    from memory.service import InMemoryMemoryService

    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    source = MemoryTrace(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
    )
    await service.apply(MemoryMutationBatch(writes=(source,)))
    result = await service.recall(
        MemoryRecallRequest(
            retrieve=MemoryRetrieveRequest(
                current_tick=5,
                limit=1,
                scoring_policy=MemoryScoringPolicy(
                    policy_id="score",
                    version="1",
                    weights=MemoryScoreWeights(recency=1.0),
                ),
            ),
            reconstruction_id=ReconstructionId("recon-1"),
            reconstruction_policy=MemoryReconstructionPolicy(
                policy_id="recall",
                version="1",
                reconsolidate=True,
            ),
            derived_memory_id=MemoryId("m-derived"),
        )
    )
    assert result.reconsolidation is not None
    derived = result.reconsolidation.derived_trace
    assert derived.memory_id.value == "m-derived"
    assert derived.lineage.generation == 1
    assert derived.lineage.source_memory_ids == (MemoryId("m-1"),)
    assert derived.lineage.reconstruction_id == ReconstructionId("recon-1")
    # Source remains unchanged in store.
    stored = await service.get(MemoryId("m-1"))
    assert stored is not None
    assert stored.forgotten_at_tick is None
    assert stored.lineage.generation == 0


def test_ancestry_dedup_and_episode_age_semantics() -> None:
    from memory.models import (
        MemoryAgeSemantics,
        MemoryQueryContext,
        MemoryQueryFilters,
        MemoryScoreWeights,
        MemoryScoringPolicy,
    )
    from memory.scoring import logical_age_ticks, rank_traces

    root = MemoryTrace(
        memory_id=MemoryId("m-root"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=1.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=0,
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
    )
    derived = MemoryTrace(
        memory_id=MemoryId("m-derived"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=1.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=0,
        ),
        created_tick=2,
        source_tick=0,
        last_access_tick=2,
        access_count=0,
        lineage=MemoryLineage(
            supersedes_memory_id=MemoryId("m-root"),
            source_memory_ids=(MemoryId("m-root"),),
            generation=1,
            reconstruction_id=ReconstructionId("recon-1"),
        ),
    )
    policy = MemoryScoringPolicy(
        policy_id="score",
        version="1",
        weights=MemoryScoreWeights(emotional_salience=1.0),
        ancestry_dedup=True,
    )
    hits, count = rank_traces(
        (root, derived),
        policy=policy,
        current_tick=5,
        filters=MemoryQueryFilters(),
        context=MemoryQueryContext(),
        query_embedding=None,
        embeddings=None,
        limit=2,
    )
    assert count == 2
    assert [hit.trace.memory_id.value for hit in hits] == ["m-derived"]
    assert (
        logical_age_ticks(
            derived, current_tick=5, age_semantics=MemoryAgeSemantics.EPISODE
        )
        == 5
    )
    assert (
        logical_age_ticks(
            derived, current_tick=5, age_semantics=MemoryAgeSemantics.STORAGE
        )
        == 3
    )


@pytest.mark.asyncio
async def test_atomic_apply_reconsolidation_persists_record_and_leaves_source() -> None:
    from memory.errors import MemoryServiceError
    from memory.models import MemoryMutationBatch
    from memory.service import InMemoryMemoryService

    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    source = MemoryTrace(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=0,
    )
    await service.apply(MemoryMutationBatch(writes=(source,)))
    reconstructed = _reconstructed()
    record = ReconstructionRecord(
        reconstruction_id=ReconstructionId("recon-1"),
        run_id=MemoryRunId("run-1"),
        owner_id=AgentId("agent-1"),
        source_memory_ids=(MemoryId("m-1"),),
        reconstructed=reconstructed,
        created_tick=5,
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
        emotional_salience=reconstructed.emotional_salience,
        confidence=reconstructed.confidence,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
        ),
        created_tick=5,
        source_tick=1,
        last_access_tick=5,
        access_count=0,
        lineage=MemoryLineage(
            supersedes_memory_id=MemoryId("m-1"),
            generation=1,
            source_memory_ids=(MemoryId("m-1"),),
            reconstruction_id=ReconstructionId("recon-1"),
        ),
    )
    result = await service.apply(
        MemoryMutationBatch(writes=(derived,), reconstructions=(record,))
    )
    assert result.written_count == 1
    assert result.reconstruction_written_count == 1
    stored_source = await service.get(MemoryId("m-1"))
    assert stored_source is not None
    assert stored_source.forgotten_at_tick is None
    assert stored_source.lineage.generation == 0
    stored_derived = await service.get(MemoryId("m-derived"))
    assert stored_derived is not None
    assert stored_derived.lineage.source_memory_ids == (MemoryId("m-1"),)
    assert stored_derived.lineage.reconstruction_id == ReconstructionId("recon-1")

    # Idempotent retry of the same reconstruction payload succeeds.
    retry = await service.apply(
        MemoryMutationBatch(writes=(derived,), reconstructions=(record,))
    )
    assert retry.reconstruction_idempotent_count == 1
    assert retry.written_count == 0

    # Conflicting reconstruction payload is rejected without mutating sources.
    conflicting = ReconstructionRecord(
        reconstruction_id=ReconstructionId("recon-1"),
        run_id=MemoryRunId("run-1"),
        owner_id=AgentId("agent-1"),
        source_memory_ids=(MemoryId("m-1"),),
        reconstructed=ReconstructedMemory(
            reconstruction_id=ReconstructionId("recon-1"),
            owner_id=AgentId("agent-1"),
            narrative="different subjective narrative",
            concepts=reconstructed.concepts,
            entities=(),
            relations=(),
            context=MemorySituationContext(),
            confidence=0.7,
            emotional_salience=0.4,
            source_memory_ids=(MemoryId("m-1"),),
            generation=1,
            reconstructed_at_tick=5,
            policy_id="recall",
            policy_version="1",
            used_provider=False,
            fallback_used=False,
        ),
        created_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    with pytest.raises(MemoryServiceError, match="conflict"):
        await service.apply(MemoryMutationBatch(reconstructions=(conflicting,)))
    assert (await service.get(MemoryId("m-1"))) == stored_source


@pytest.mark.asyncio
async def test_atomic_apply_rejects_dangling_reconstruction_sources() -> None:
    from memory.errors import MemoryServiceError
    from memory.models import MemoryMutationBatch
    from memory.service import InMemoryMemoryService

    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    record = ReconstructionRecord(
        reconstruction_id=ReconstructionId("recon-1"),
        run_id=MemoryRunId("run-1"),
        owner_id=AgentId("agent-1"),
        source_memory_ids=(MemoryId("m-missing"),),
        reconstructed=_reconstructed(sources=("m-missing",)),
        created_tick=5,
        policy_id="recall",
        policy_version="1",
        used_provider=False,
        fallback_used=False,
    )
    with pytest.raises(MemoryServiceError, match="not_found"):
        await service.apply(MemoryMutationBatch(reconstructions=(record,)))
