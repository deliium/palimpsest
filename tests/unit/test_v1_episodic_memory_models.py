"""Episodic memory service/query/scoring contract models."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.models import (
    SCORE_QUANTUM,
    AccessHistoryMode,
    ConceptMention,
    MemoryAccessReceipt,
    MemoryEmbedding,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryQueryFilters,
    MemoryRankedHit,
    MemoryRetrieveRequest,
    MemoryRunId,
    MemoryScope,
    MemoryScoreBreakdown,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    diagnostic_projection,
    normalize_score_weights,
    quantize_score,
)
from world.identifiers import WorldRevision


def _trace(owner: str = "agent-1") -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId("m-1"),
        owner_id=AgentId(owner),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.5,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=0,
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
    )


def test_memory_scope_is_exact_typed() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    assert scope.run_id.value == "run-1"
    with pytest.raises(TypeError):
        MemoryScope(run_id="run-1", owner_id=AgentId("agent-1"))  # type: ignore[arg-type]


def test_score_weight_normalization_and_quantization() -> None:
    weights = MemoryScoreWeights(recency=1.0, emotional_salience=3.0)
    normalized = normalize_score_weights(weights)
    assert normalized.recency == 0.25
    assert normalized.emotional_salience == 0.75
    assert quantize_score(0.1234567) == pytest.approx(
        round(0.1234567 / SCORE_QUANTUM) * SCORE_QUANTUM
    )
    with pytest.raises(ValueError, match="no_active_weights"):
        normalize_score_weights(MemoryScoreWeights())


def test_scoring_policy_requires_embedding_dimension_for_semantic() -> None:
    with pytest.raises(ValueError, match="embedding_dimension_required"):
        MemoryScoringPolicy(
            policy_id="default",
            version="1",
            weights=MemoryScoreWeights(semantic_relevance=1.0),
        )
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(semantic_relevance=1.0, recency=1.0),
        embedding_dimension=4,
        access_history_mode=AccessHistoryMode.NOVELTY,
    )
    assert policy.weights.semantic_relevance == 0.5
    assert policy.access_history_mode is AccessHistoryMode.NOVELTY


def test_retrieve_request_enforces_embedding_dimension() -> None:
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )
    request = MemoryRetrieveRequest(
        current_tick=3,
        limit=10,
        scoring_policy=policy,
    )
    assert request.limit == 10
    semantic_policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(semantic_relevance=1.0),
        embedding_dimension=2,
    )
    with pytest.raises(ValueError, match="required_for_semantic"):
        MemoryRetrieveRequest(
            current_tick=0,
            limit=5,
            scoring_policy=semantic_policy,
        )
    embedding = MemoryEmbedding(vector=(1.0, 0.0), model="fake", version="1")
    ok = MemoryRetrieveRequest(
        current_tick=0,
        limit=5,
        scoring_policy=semantic_policy,
        query_embedding=embedding,
    )
    assert ok.query_embedding is not None
    with pytest.raises(ValueError, match="dimension_mismatch"):
        MemoryRetrieveRequest(
            current_tick=0,
            limit=5,
            scoring_policy=semantic_policy,
            query_embedding=MemoryEmbedding(
                vector=(1.0, 0.0, 0.0), model="fake", version="1"
            ),
        )


def test_query_filters_reject_inverted_ranges_and_payload_repr() -> None:
    with pytest.raises(ValueError, match="inverted_range"):
        MemoryQueryFilters(created_tick_min=5, created_tick_max=1)
    filters = MemoryQueryFilters(concepts=("secret-concept",))
    assert "secret-concept" not in repr(filters)


def test_ranked_hit_and_batch_validation() -> None:
    hit = MemoryRankedHit(
        rank=1,
        trace=_trace(),
        score=0.5,
        breakdown=MemoryScoreBreakdown(recency=0.5),
        matched_concept_mention_ids=(MentionId("c-1"),),
        matched_entity_mention_ids=(),
        scoring_policy_id="default",
        scoring_policy_version="1",
        retrieval_tick=2,
    )
    assert "gate" not in repr(hit)
    receipt = MemoryAccessReceipt(
        memory_id=MemoryId("m-1"),
        access_tick=2,
        operation_id="op-1",
    )
    batch = MemoryMutationBatch(writes=(_trace(),), accesses=(receipt,))
    assert batch.write_count if False else len(batch.writes) == 1
    with pytest.raises(ValueError, match="duplicate_memory_id"):
        MemoryMutationBatch(writes=(_trace(), _trace()))


def test_memory_lineage_defaults_remain_root_compatible() -> None:
    from memory.models import MemoryLineage, ReconstructionId

    root = MemoryLineage()
    assert root.generation == 0
    assert root.source_memory_ids == ()
    assert root.reconstruction_id is None
    derived = MemoryLineage(
        supersedes_memory_id=MemoryId("m-0"),
        source_memory_ids=(MemoryId("m-0"),),
        generation=1,
        reconstruction_id=ReconstructionId("recon-1"),
    )
    assert derived.source_memory_ids == (MemoryId("m-0"),)


def test_diagnostic_projection_allowlist() -> None:
    safe = diagnostic_projection(
        {
            "operation": "retrieve",
            "run_id": "run-1",
            "owner_id": "agent-1",
            "tick": 3,
            "policy_version": "1",
            "enabled_components": ["recency"],
            "candidate_count": 4,
            "result_count": 2,
        }
    )
    assert safe["candidate_count"] == 4
    with pytest.raises(ValueError, match="disallowed_key"):
        diagnostic_projection({"trace": "secret"})
    with pytest.raises(ValueError, match="disallowed_key"):
        diagnostic_projection({"query": "secret"})
