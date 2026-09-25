"""LLM-assisted sleep consolidation may only select candidate IDs."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import CognitionConsolidationMode
from agents.cognition.consolidation import (
    LLMOfflineConsolidationSelector,
    OfflineConsolidationSelectionOutput,
)
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    SubjectiveSnapshot,
)
from agents.models import AgentId
from llm import FinishReason, LLMResult, LLMResultMetadata, StructuredOutput
from memory.consolidation import plan_offline_consolidation
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    OfflineConsolidationPolicy,
)
from tests.typecheck.cognitive_loop import (
    ScriptedFutureImagination,
    ScriptedIntentionSelector,
    ScriptedMemoryRetriever,
    ScriptedMemoryUpdateHook,
    ScriptedMotivationEvaluator,
    ScriptedPerceptionInterpreter,
    ScriptedPlanner,
    ScriptedSelfStateProjector,
    ScriptedSituationModeler,
)
from world.actions import Sleep
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation


def _trace(memory_id: str, concepts: tuple[str, ...]) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=tuple(
            ConceptMention(
                mention_id=MentionId(f"{memory_id}-c{index}"), concept=concept
            )
            for index, concept in enumerate(concepts)
        ),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.6,
        confidence=0.9,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION, source_tick=0
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=1,
    )


def _selection():
    traces = (
        _trace("m-a", ("path", "water", "night", "only-a")),
        _trace("m-b", ("path", "water", "night", "only-b")),
    )
    _candidate, selection = plan_offline_consolidation(
        owner_id=AgentId("agent-1"),
        tick=4,
        traces=traces,
        policy=OfflineConsolidationPolicy(allow_provider=True),
    )
    return selection


class _WrongShape(StructuredOutput):
    """Closed shape that is not the consolidation selection schema."""

    marker: str = "shape"


def _consolidation_logs(
    caplog: pytest.LogCaptureFixture,
) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == "agents.cognition.consolidation"
    ]


def _joined(records: list[logging.LogRecord]) -> str:
    return " ".join(record.getMessage() for record in records)


class _ScriptedProvider:
    def __init__(self, output: OfflineConsolidationSelectionOutput | None) -> None:
        self.output = output
        self.calls = 0

    async def generate(self, request: object) -> LLMResult:
        self.calls += 1
        if self.output is None:
            raise RuntimeError("provider_down")
        return LLMResult(
            output=self.output,
            metadata=LLMResultMetadata(
                provider_name="fake",
                model_name="fake",
                finish_reason=FinishReason.STOP,
            ),
        )


@pytest.mark.asyncio
async def test_provider_subset_cannot_invent_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.consolidation")
    selection = _selection()
    kept = selection.strengthen_ids[0].value
    provider = _ScriptedProvider(
        OfflineConsolidationSelectionOutput(
            strengthen_ids=(kept,),
            soft_forget_ids=(),
            merge_group_keys=(),
            belief_source_ids=(),
        )
    )
    restricted = await LLMOfflineConsolidationSelector(provider).restrict(
        selection, policy=OfflineConsolidationPolicy(allow_provider=True)
    )
    assert provider.calls == 1
    assert restricted.used_provider is True
    assert restricted.fallback_used is False
    assert [item.value for item in restricted.strengthen_ids] == [kept]
    assert restricted.derived_traces == ()
    assert "invented" not in repr(restricted)
    records = _consolidation_logs(caplog)
    text = _joined(records)
    assert any(
        record.levelno == logging.DEBUG
        and "offline_consolidation_llm_start" in record.getMessage()
        and "prompt_version=v1" in record.getMessage()
        and "schema_version=offline_consolidation.selection.v1" in record.getMessage()
        for record in records
    )
    assert any(
        "offline_consolidation_llm_complete" in record.getMessage()
        and "used_provider=True" in record.getMessage()
        and "fallback_used=False" in record.getMessage()
        for record in records
    )
    assert "only-a" not in text
    assert "Select offline consolidation" not in text


@pytest.mark.asyncio
async def test_foreign_id_falls_back_to_deterministic_selection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.consolidation")
    selection = _selection()
    provider = _ScriptedProvider(
        OfflineConsolidationSelectionOutput(
            strengthen_ids=("not-a-candidate",),
            soft_forget_ids=(),
            merge_group_keys=(),
            belief_source_ids=(),
        )
    )
    restricted = await LLMOfflineConsolidationSelector(provider).restrict(
        selection, policy=OfflineConsolidationPolicy(allow_provider=True)
    )
    assert restricted.fallback_used is True
    assert restricted.used_provider is False
    assert restricted.strengthen_ids == selection.strengthen_ids
    assert restricted.derived_traces == selection.derived_traces
    records = _consolidation_logs(caplog)
    assert any(
        record.levelno == logging.ERROR
        and "offline_consolidation_llm_rejected" in record.getMessage()
        and "reason_code=foreign_id" in record.getMessage()
        for record in records
    )
    assert "not-a-candidate" not in _joined(records)
    assert "only-a" not in _joined(records)


@pytest.mark.asyncio
async def test_schema_invalid_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.consolidation")
    selection = _selection()
    provider = _ScriptedProvider(None)

    async def _generate(request: object) -> LLMResult:
        _ = request
        provider.calls += 1
        return LLMResult(
            output=_WrongShape(),
            metadata=LLMResultMetadata(
                provider_name="fake",
                model_name="fake",
                finish_reason=FinishReason.STOP,
            ),
        )

    provider.generate = _generate  # type: ignore[method-assign]
    restricted = await LLMOfflineConsolidationSelector(provider).restrict(
        selection, policy=OfflineConsolidationPolicy(allow_provider=True)
    )
    assert restricted.fallback_used is True
    assert restricted.strengthen_ids == selection.strengthen_ids
    records = _consolidation_logs(caplog)
    assert any(
        record.levelno == logging.ERROR
        and "reason_code=schema_invalid" in record.getMessage()
        for record in records
    )
    assert "only-a" not in _joined(records)


@pytest.mark.asyncio
async def test_provider_error_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.consolidation")
    selection = _selection()
    provider = _ScriptedProvider(None)
    restricted = await LLMOfflineConsolidationSelector(provider).restrict(
        selection, policy=OfflineConsolidationPolicy(allow_provider=True)
    )
    assert provider.calls == 1
    assert restricted.fallback_used is True
    records = _consolidation_logs(caplog)
    assert any(
        record.levelno == logging.ERROR
        and "reason_code=provider_error" in record.getMessage()
        for record in records
    )
    assert "only-a" not in _joined(records)


@pytest.mark.asyncio
async def test_missing_provider_falls_back_without_calls(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.consolidation")
    selection = _selection()
    restricted = await LLMOfflineConsolidationSelector(None).restrict(
        selection, policy=OfflineConsolidationPolicy(allow_provider=True)
    )
    assert restricted.fallback_used is True
    assert restricted.strengthen_ids == selection.strengthen_ids
    records = _consolidation_logs(caplog)
    assert any(
        "offline_consolidation_llm_complete" in record.getMessage()
        and "used_provider=False" in record.getMessage()
        and "fallback_used=True" in record.getMessage()
        for record in records
    )
    assert not any(
        "offline_consolidation_llm_start" in record.getMessage() for record in records
    )


@pytest.mark.asyncio
async def test_disallow_provider_never_calls(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.consolidation")
    selection = _selection()
    provider = _ScriptedProvider(None)
    restricted = await LLMOfflineConsolidationSelector(provider).restrict(
        selection, policy=OfflineConsolidationPolicy(allow_provider=False)
    )
    assert provider.calls == 0
    assert restricted.fallback_used is True
    records = _consolidation_logs(caplog)
    assert any(
        "offline_consolidation_llm_complete" in record.getMessage()
        and "fallback_used=True" in record.getMessage()
        and "used_provider=False" in record.getMessage()
        for record in records
    )
    assert "only-a" not in _joined(records)


@pytest.mark.asyncio
async def test_llm_sleep_without_provider_still_plans() -> None:
    owner = AgentId("agent-1")
    traces = (
        _trace("m-a", ("path", "water", "night", "only-a")),
        _trace("m-b", ("path", "water", "night", "only-b")),
    )
    loop = CognitiveLoop(
        perception=ScriptedPerceptionInterpreter(),
        memory=ScriptedMemoryRetriever(),
        situation=ScriptedSituationModeler(),
        self_state=ScriptedSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ScriptedFutureImagination(),
        motivation=ScriptedMotivationEvaluator(),
        intention=ScriptedIntentionSelector(),
        planner=ScriptedPlanner(),
        memory_updates=ScriptedMemoryUpdateHook(),
        consolidation_mode=CognitionConsolidationMode.LLM_ASSISTED,
        consolidation_policy=OfflineConsolidationPolicy(allow_provider=True),
    )
    proposal = await loop.prepare(
        CognitiveLoopInput(
            agent_id=owner,
            observation=Observation(
                world_id=WorldId("world-1"),
                observer_id=EntityId("body-1"),
                revision=WorldRevision(0),
                tick=4,
            ),
            internal_state=InternalAgentState(owner_id=owner),
            snapshot=SubjectiveSnapshot(
                owner_id=owner,
                revision=0,
                memories=traces,
                legacy_beliefs=(),
                semantic_beliefs=(),
                relationships=(),
                goals=(),
            ),
        ),
        invocation_id="inv-llm",
    )
    result = await loop.complete(proposal, effective_command=Sleep())
    assert result.offline_consolidation is not None
    assert result.offline_consolidation.selection.fallback_used is True
