"""Mypy fixtures for episodic memory service contracts."""

from __future__ import annotations

from agents.models import AgentId
from memory.contracts import MemoryReconstructor, MemoryService
from memory.models import (
    MemoryApplyResult,
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryId,
    MemoryMutationBatch,
    MemoryRecallContext,
    MemoryRecallRequest,
    MemoryRecallResult,
    MemoryReconstructionPolicy,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemoryTrace,
    RecallEvidence,
    ReconstructedMemory,
    ReconstructionId,
)


class _StubMemoryService:
    def __init__(self) -> None:
        self._scope = MemoryScope(
            run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1")
        )

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    async def retrieve(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        _ = request
        return MemoryRetrieveResult(
            hits=(),
            pending_accesses=(),
            candidate_count=0,
            retrieval_tick=0,
            scoring_policy_version="1",
        )

    async def recall(self, request: MemoryRecallRequest) -> MemoryRecallResult:
        raise NotImplementedError(type(request).__name__)

    async def apply(self, batch: MemoryMutationBatch) -> MemoryApplyResult:
        _ = batch
        return MemoryApplyResult(
            written_count=0,
            access_applied_count=0,
            access_idempotent_count=0,
        )

    async def get(self, memory_id: MemoryId) -> MemoryTrace | None:
        _ = memory_id
        return None

    async def snapshot(self) -> tuple[MemoryTrace, ...]:
        return ()

    async def forget(self, request: MemoryForgetRequest) -> MemoryForgetResult:
        _ = request
        return MemoryForgetResult(forgotten_count=0, examined_count=0)


class _StubReconstructor:
    async def reconstruct(self, evidence: RecallEvidence) -> ReconstructedMemory:
        _ = evidence
        raise NotImplementedError


def _service_is_protocol() -> MemoryService:
    return _StubMemoryService()


def _reconstructor_is_protocol() -> MemoryReconstructor:
    return _StubReconstructor()


def _policy() -> MemoryScoringPolicy:
    return MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )


def _recall_evidence() -> RecallEvidence:
    return RecallEvidence(
        owner_id=AgentId("agent-1"),
        current_tick=0,
        reconstruction_id=ReconstructionId("recon-1"),
        policy=MemoryReconstructionPolicy(policy_id="recall", version="1"),
        sources=(),
        beliefs=(),
        recall_context=MemoryRecallContext(),
    )


def _empty_context() -> MemorySituationContext:
    return MemorySituationContext()
