"""Owner-scoped cognition memory retrieval adapter.

Observational only: maps a bound ``MemoryService.retrieve`` result into
``RetrievedMemoryContext`` and never mutates stores. Access receipts remain
pending until ``AgentRuntime`` applies them after successful cognition.
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
    BeliefId,
    MemoryQueryContext,
    MemoryQueryFilters,
    MemoryRetrieveRequest,
    MemoryScoringPolicy,
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
        "_scoring_policy",
        "_service",
    )

    def __init__(
        self,
        memory_service: MemoryService,
        *,
        scoring_policy: MemoryScoringPolicy,
        belief_reader: BeliefReader | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> None:
        if type(scoring_policy) is not MemoryScoringPolicy:
            raise TypeError("scoring_policy must be MemoryScoringPolicy")
        if scoring_policy.weights.semantic_relevance > 0.0:
            raise ValueError(
                "ScopedMemoryRetriever V1 requires non-semantic scoring_policy"
            )
        if limit < 1:
            raise ValueError("limit must be positive")
        self._service = memory_service
        self._scoring_policy = scoring_policy
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
        request = MemoryRetrieveRequest(
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
        result = await self._service.retrieve(request)
        for hit in result.hits:
            if hit.trace.owner_id != loop_input.agent_id:
                _LOG.error(
                    "memory_retrieve_foreign_owner",
                    extra={
                        "cognition": {
                            "owner_id": loop_input.agent_id.value,
                            "tick": perception.tick,
                            "reason_code": "ownership",
                        }
                    },
                )
                raise ValueError("foreign-owner memory result rejected")

        belief_ids: tuple[BeliefId, ...] = ()
        if self._belief_reader is not None:
            belief_ids = tuple(
                belief.belief_id for belief in self._belief_reader.snapshot()
            )

        memory_ids = tuple(hit.trace.memory_id for hit in result.hits)
        _LOG.debug(
            "memory_retrieve_mapped",
            extra={
                "cognition": {
                    "owner_id": loop_input.agent_id.value,
                    "tick": perception.tick,
                    "policy_version": result.scoring_policy_version,
                    "enabled_components": list(
                        self._scoring_policy.weights.enabled_components()
                    ),
                    "candidate_count": result.candidate_count,
                    "result_count": len(result.hits),
                }
            },
        )
        return RetrievedMemoryContext(
            owner_id=loop_input.agent_id,
            memory_ids=memory_ids,
            belief_ids=belief_ids,
            confidence=1.0,
            decision_metadata=DecisionMetadata(
                candidate_count=result.candidate_count,
                selection_codes=tuple(f"rank:{hit.rank}" for hit in result.hits),
            ),
            ranked_hits=result.hits,
            pending_accesses=result.pending_accesses,
            candidate_count=result.candidate_count,
            retrieval_tick=result.retrieval_tick,
            scoring_policy_version=result.scoring_policy_version,
        )
