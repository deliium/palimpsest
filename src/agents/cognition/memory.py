"""Owner-scoped cognition reconstructive memory adapter.

Observational only: maps a bound ``MemoryService.recall`` result into
``RetrievedMemoryContext`` and never mutates stores. Access receipts and
optional reconsolidation intents remain pending until ``AgentRuntime`` applies
them after successful cognition.
"""

from __future__ import annotations

import logging
from typing import Final

from agents.cognition.models import (
    CognitiveLoopInput,
    DecisionMetadata,
    InterpretedPerception,
    RetrievedMemoryContext,
)
from memory.contracts import BeliefReader, MemoryService
from memory.models import (
    Belief,
    BeliefId,
    MemoryId,
    MemoryQueryContext,
    MemoryQueryFilters,
    MemoryRecallContext,
    MemoryRecallRequest,
    MemoryReconstructionPolicy,
    MemoryRetrieveRequest,
    MemoryScoringPolicy,
    ReconstructionId,
)

__all__ = [
    "ScopedMemoryRetriever",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.memory")
_DEFAULT_LIMIT: Final[int] = 8


class ScopedMemoryRetriever:
    """Production ``MemoryRetriever`` bound to one owner-scoped ``MemoryService``."""

    __slots__ = (
        "_belief_reader",
        "_limit",
        "_reconstruction_policy",
        "_scoring_policy",
        "_service",
    )

    def __init__(
        self,
        memory_service: MemoryService,
        *,
        scoring_policy: MemoryScoringPolicy,
        reconstruction_policy: MemoryReconstructionPolicy | None = None,
        belief_reader: BeliefReader | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> None:
        if type(scoring_policy) is not MemoryScoringPolicy:
            raise TypeError("scoring_policy must be MemoryScoringPolicy")
        if scoring_policy.weights.semantic_relevance > 0.0:
            raise ValueError(
                "ScopedMemoryRetriever V1 requires non-semantic scoring_policy"
            )
        if reconstruction_policy is None:
            reconstruction_policy = MemoryReconstructionPolicy(
                policy_id="cognition-recall",
                version="1",
                allow_provider=False,
            )
        elif type(reconstruction_policy) is not MemoryReconstructionPolicy:
            raise TypeError("reconstruction_policy must be MemoryReconstructionPolicy")
        if limit < 1:
            raise ValueError("limit must be positive")
        self._service = memory_service
        self._scoring_policy = scoring_policy
        self._reconstruction_policy = reconstruction_policy
        self._belief_reader = belief_reader
        self._limit = limit

    async def retrieve(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
    ) -> RetrievedMemoryContext:
        if type(loop_input) is not CognitiveLoopInput:
            raise TypeError("loop_input must be CognitiveLoopInput")
        if type(perception) is not InterpretedPerception:
            raise TypeError("perception must be InterpretedPerception")
        if loop_input.agent_id != perception.owner_id:
            raise ValueError("perception owner must match loop agent")
        if self._service.scope.owner_id != loop_input.agent_id:
            raise ValueError("memory service scope owner mismatch")

        tags = tuple(code.value for code in perception.claim_codes[:16])
        beliefs: tuple[Belief, ...] = ()
        belief_ids: tuple[BeliefId, ...] = ()
        if self._belief_reader is not None:
            beliefs = self._belief_reader.snapshot()
            for belief in beliefs:
                if belief.owner_id != loop_input.agent_id:
                    raise ValueError("foreign-owner belief snapshot rejected")
            belief_ids = tuple(belief.belief_id for belief in beliefs)

        retrieve = MemoryRetrieveRequest(
            current_tick=perception.tick,
            limit=self._limit,
            scoring_policy=self._scoring_policy,
            filters=MemoryQueryFilters(
                location_id=perception.location_id,
                require_active=True,
            ),
            context=MemoryQueryContext(
                location_id=perception.location_id,
                tags=tags,
            ),
            operation_id=(
                f"cog:{loop_input.agent_id.value}:t{perception.tick}:"
                f"{self._scoring_policy.version}"
            ),
        )
        policy = self._reconstruction_policy
        reconstruction_id = ReconstructionId(
            f"recon-{loop_input.agent_id.value}-t{perception.tick}-{policy.version}"
        )
        derived_id: MemoryId | None = None
        if policy.reconsolidate:
            derived_id = MemoryId(
                f"derived-{loop_input.agent_id.value}-t{perception.tick}-"
                f"{policy.version}"
            )
        recall_request = MemoryRecallRequest(
            retrieve=retrieve,
            reconstruction_id=reconstruction_id,
            reconstruction_policy=policy,
            beliefs=beliefs,
            recall_context=MemoryRecallContext(
                location_id=perception.location_id,
                tags=tags,
            ),
            derived_memory_id=derived_id,
        )
        result = await self._service.recall(recall_request)

        # Scientific ranked evidence: rebuild hits from evidence sources only as
        # ID metadata. Full ranked_hits require a retrieve; recall already ran
        # retrieve once, so re-rank from evidence without a second service call
        # by mapping source ranks. Downstream keeps traces out of "remembered".
        from memory.models import (
            MemoryRankedHit,
            MemoryScoreBreakdown,
        )

        ranked_hits: list[MemoryRankedHit] = []
        # Prefer loading traces for scientific metadata via get (no access bump).
        for source in result.evidence.sources:
            trace = await self._service.get(source.memory_id)
            if trace is None:
                continue
            if trace.owner_id != loop_input.agent_id:
                _LOG.error(
                    "memory_recall_foreign_owner",
                    extra={
                        "cognition": {
                            "owner_id": loop_input.agent_id.value,
                            "tick": perception.tick,
                            "reason_code": "ownership",
                        }
                    },
                )
                raise ValueError("foreign-owner memory result rejected")
            ranked_hits.append(
                MemoryRankedHit(
                    rank=source.rank,
                    trace=trace,
                    score=source.score,
                    breakdown=MemoryScoreBreakdown(),
                    matched_concept_mention_ids=(),
                    matched_entity_mention_ids=(),
                    scoring_policy_id=self._scoring_policy.policy_id,
                    scoring_policy_version=self._scoring_policy.version,
                    retrieval_tick=perception.tick,
                )
            )

        for reconstructed in result.reconstructions:
            if reconstructed.owner_id != loop_input.agent_id:
                raise ValueError("foreign-owner reconstruction rejected")

        memory_ids = tuple(hit.trace.memory_id for hit in ranked_hits)
        generation = (
            result.reconstructions[0].generation if result.reconstructions else 0
        )
        _LOG.debug(
            "memory_recall_mapped",
            extra={
                "cognition": {
                    "owner_id": loop_input.agent_id.value,
                    "tick": perception.tick,
                    "policy_version": self._scoring_policy.version,
                    "reconstruction_policy_version": policy.version,
                    "enabled_components": list(
                        self._scoring_policy.weights.enabled_components()
                    ),
                    "candidate_count": result.evidence.policy.max_source_traces,
                    "source_count": len(result.evidence.sources),
                    "result_count": len(ranked_hits),
                    "reconstruction_count": len(result.reconstructions),
                    "pending_write_count": 1 if result.reconsolidation else 0,
                    "generation": generation,
                    "used_provider": (
                        result.reconstructions[0].used_provider
                        if result.reconstructions
                        else False
                    ),
                    "fallback_used": (
                        result.reconstructions[0].fallback_used
                        if result.reconstructions
                        else False
                    ),
                }
            },
        )
        return RetrievedMemoryContext(
            owner_id=loop_input.agent_id,
            memory_ids=memory_ids,
            belief_ids=belief_ids,
            confidence=(
                result.reconstructions[0].confidence if result.reconstructions else 1.0
            ),
            decision_metadata=DecisionMetadata(
                candidate_count=len(result.evidence.sources),
                selection_codes=tuple(
                    f"recon:{item.reconstruction_id.value}"
                    for item in result.reconstructions
                )
                or tuple(f"rank:{hit.rank}" for hit in ranked_hits),
            ),
            ranked_hits=tuple(ranked_hits),
            pending_accesses=result.pending_accesses,
            candidate_count=len(result.evidence.sources),
            retrieval_tick=perception.tick,
            scoring_policy_version=self._scoring_policy.version,
            reconstructions=result.reconstructions,
            reconsolidation=result.reconsolidation,
            reconstruction_policy_version=policy.version,
        )
