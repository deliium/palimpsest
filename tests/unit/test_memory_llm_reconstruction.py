"""LLM-backed reconstructive recall adapter tests."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.reconstruction import (
    LLMMemoryReconstructor,
    ReconstructedMemoryCandidate,
)
from agents.models import AgentId
from llm.errors import LLMError, LLMErrorCode
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryRecallContext,
    MemoryReconstructionPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MentionId,
    RecallEvidence,
    RecallSourceEvidence,
    ReconstructionFallbackMode,
    ReconstructionId,
)
from tests.fakes import FakeLLMProvider, ScriptedFailure, ScriptedSuccess

pytestmark = pytest.mark.unit


def _evidence(*, allow_provider: bool = True) -> RecallEvidence:
    return RecallEvidence(
        owner_id=AgentId("agent-1"),
        current_tick=5,
        reconstruction_id=ReconstructionId("recon-1"),
        policy=MemoryReconstructionPolicy(
            policy_id="recall",
            version="1",
            allow_provider=allow_provider,
            fallback_mode=ReconstructionFallbackMode.DETERMINISTIC,
        ),
        sources=(
            RecallSourceEvidence(
                memory_id=MemoryId("m-1"),
                owner_id=AgentId("agent-1"),
                rank=1,
                score=0.9,
                concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="gate"),),
                entities=(),
                relations=(),
                context=MemorySituationContext(),
                emotional_salience=0.5,
                confidence=0.8,
                source_confidence=0.8,
                episode_age_ticks=1,
                storage_age_ticks=1,
                generation=0,
                provenance_kind=MemorySourceKind.DIRECT_OBSERVATION,
            ),
        ),
        beliefs=(),
        recall_context=MemoryRecallContext(),
    )


def _candidate(**overrides: object) -> ReconstructedMemoryCandidate:
    payload: dict[str, object] = {
        "narrative": "I remember a gate",
        "concepts": ("gate",),
        "entity_labels": (),
        "entity_ids": (),
        "relation_predicates": (),
        "relation_subject_indexes": (),
        "relation_object_indexes": (),
        "relation_subject_kinds": (),
        "relation_object_kinds": (),
        "context_tags": (),
        "location_id": None,
        "confidence": 0.7,
        "emotional_salience": 0.4,
        "source_memory_ids": ("m-1",),
    }
    payload.update(overrides)
    return ReconstructedMemoryCandidate.model_validate(payload)


@pytest.mark.asyncio
async def test_llm_reconstructor_translates_validated_candidate() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "recall-recon-1",
        ScriptedSuccess(output=_candidate()),
    )
    reconstructor = LLMMemoryReconstructor(provider)
    result = await reconstructor.reconstruct(_evidence())
    assert result.used_provider is True
    assert result.fallback_used is False
    assert result.narrative == "I remember a gate"
    assert result.source_memory_ids == (MemoryId("m-1"),)
    assert result.prompt_version == "v1"


@pytest.mark.asyncio
async def test_llm_reconstructor_falls_back_on_unknown_source() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "recall-recon-1",
        ScriptedSuccess(output=_candidate(source_memory_ids=("m-missing",))),
    )
    reconstructor = LLMMemoryReconstructor(provider)
    result = await reconstructor.reconstruct(_evidence())
    assert result.used_provider is False
    assert result.fallback_used is True
    assert "m-1:gate" in result.narrative


@pytest.mark.asyncio
async def test_llm_reconstructor_falls_back_on_provider_error() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "recall-recon-1",
        ScriptedFailure(error=LLMError(LLMErrorCode.TIMEOUT, attempts=1)),
    )
    reconstructor = LLMMemoryReconstructor(provider)
    result = await reconstructor.reconstruct(_evidence())
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_llm_reconstructor_propagates_cancellation() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "recall-recon-1",
        ScriptedSuccess(output=_candidate(), delay_seconds=60.0),
    )
    reconstructor = LLMMemoryReconstructor(provider)
    task = __import__("asyncio").create_task(reconstructor.reconstruct(_evidence()))
    await __import__("asyncio").sleep(0)
    task.cancel()
    with pytest.raises(__import__("asyncio").CancelledError):
        await task


@pytest.mark.asyncio
async def test_llm_reconstructor_skips_provider_when_disallowed() -> None:
    provider = FakeLLMProvider()
    reconstructor = LLMMemoryReconstructor(provider)
    result = await reconstructor.reconstruct(_evidence(allow_provider=False))
    assert result.used_provider is False
    assert provider.calls() == ()


@pytest.mark.asyncio
async def test_llm_reconstructor_logs_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.reconstruction")
    provider = FakeLLMProvider()
    provider.enqueue(
        "recall-recon-1",
        ScriptedSuccess(output=_candidate()),
    )
    reconstructor = LLMMemoryReconstructor(provider)
    await reconstructor.reconstruct(_evidence())
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "recon-1" in text or any(
        getattr(record, "reconstruction_id", None) == "recon-1"
        or (isinstance(record.__dict__.get("reconstruction_id"), str))
        for record in caplog.records
    )
    assert "I remember a gate" not in text
    assert "secret" not in text


@pytest.mark.asyncio
async def test_llm_reconstructor_falls_back_on_validation_rejection() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "recall-recon-1",
        ScriptedSuccess(output=_candidate(source_memory_ids=())),
    )
    reconstructor = LLMMemoryReconstructor(provider)
    result = await reconstructor.reconstruct(_evidence())
    assert result.used_provider is False
    assert result.fallback_used is True
    assert result.source_memory_ids == (MemoryId("m-1"),)


@pytest.mark.asyncio
async def test_llm_provider_success_preserves_source_order_and_policy() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "recall-recon-1",
        ScriptedSuccess(
            output=_candidate(
                source_memory_ids=("m-1",),
                concepts=("gate", "latch"),
            )
        ),
    )
    reconstructor = LLMMemoryReconstructor(provider)
    result = await reconstructor.reconstruct(_evidence())
    assert result.used_provider is True
    assert result.policy_id == "recall"
    assert result.policy_version == "1"
    assert result.source_memory_ids == (MemoryId("m-1"),)
    assert {item.concept for item in result.concepts} == {"gate", "latch"}


@pytest.mark.asyncio
async def test_llm_cancellation_leaves_no_partial_reconstruction() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "recall-recon-1",
        ScriptedSuccess(output=_candidate(), delay_seconds=60.0),
    )
    reconstructor = LLMMemoryReconstructor(provider)
    task = __import__("asyncio").create_task(reconstructor.reconstruct(_evidence()))
    await __import__("asyncio").sleep(0)
    task.cancel()
    with pytest.raises(__import__("asyncio").CancelledError):
        await task
    assert provider.calls()  # request was attempted
    # No committed reconstruction artifact exists on the adapter itself.
    assert not hasattr(reconstructor, "_last_result")
