"""Sleep is the only command that plans offline consolidation."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import (
    CognitionConsolidationMode,
    CognitionLoopConfig,
    build_cognitive_loop,
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
from memory.models import (
    ConceptMention,
    MemoryAccessReceipt,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryRunId,
    MemoryScope,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from memory.service import InMemoryMemoryService
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
from world.actions import Move, Sleep, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation


def _trace(
    memory_id: str,
    *,
    concepts: tuple[str, ...],
    confidence: float = 0.9,
    salience: float = 0.6,
    created_tick: int = 0,
    access_count: int = 1,
) -> MemoryTrace:
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
        emotional_salience=salience,
        confidence=confidence,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=created_tick,
        ),
        created_tick=created_tick,
        source_tick=created_tick,
        last_access_tick=created_tick,
        access_count=access_count,
    )


def _loop_input() -> CognitiveLoopInput:
    owner = AgentId("agent-1")
    faint = _trace(
        "m-faint",
        concepts=("dust",),
        confidence=0.0,
        salience=0.0,
        created_tick=0,
        access_count=0,
    )
    return CognitiveLoopInput(
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
            memories=(
                _trace(
                    "m-a", concepts=("path", "water", "night", "only-a")
                ),
                _trace(
                    "m-b", concepts=("path", "water", "night", "only-b")
                ),
                faint,
            ),
            legacy_beliefs=(),
            semantic_beliefs=(),
            relationships=(),
            goals=(),
        ),
    )


def _loop(*, mode: CognitionConsolidationMode) -> CognitiveLoop:
    return CognitiveLoop(
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
        consolidation_mode=mode,
    )


def _stage_kinds(result: object) -> tuple[str, ...]:
    return tuple(
        record.component_kind.value for record in result.boundary_records  # type: ignore[attr-defined]
    )


@pytest.mark.asyncio
async def test_disabled_sleep_adds_no_consolidation_plan() -> None:
    loop = _loop(mode=CognitionConsolidationMode.DISABLED)
    proposal = await loop.prepare(_loop_input(), invocation_id="inv-disabled")
    result = await loop.complete(proposal, effective_command=Sleep())
    assert result.offline_consolidation is None
    disabled_stages = _stage_kinds(result)

    enabled = _loop(mode=CognitionConsolidationMode.DETERMINISTIC)
    enabled_proposal = await enabled.prepare(
        _loop_input(), invocation_id="inv-enabled"
    )
    enabled_result = await enabled.complete(
        enabled_proposal, effective_command=Sleep()
    )
    assert enabled_result.offline_consolidation is not None
    assert _stage_kinds(enabled_result) == disabled_stages
    plan = enabled_result.offline_consolidation
    assert plan.selection.derived_traces
    assert any(item.value == "m-faint" for item in plan.selection.soft_forget_ids)
    receipts = [
        receipt
        for receipt in enabled_result.pending_accesses
        if receipt.operation_id.startswith("offline-consolidation:")
    ]
    assert receipts
    assert all(
        receipt.operation_id
        == f"offline-consolidation:4:{receipt.memory_id.value}"
        for receipt in receipts
    )


@pytest.mark.asyncio
async def test_wait_and_replaced_sleep_do_not_consolidate() -> None:
    loop = _loop(mode=CognitionConsolidationMode.DETERMINISTIC)
    proposal = await loop.prepare(_loop_input(), invocation_id="inv-wait")
    waiting = await loop.complete(proposal, effective_command=Wait())
    assert waiting.offline_consolidation is None
    moved = await loop.complete(
        proposal, effective_command=Move(destination_id=EntityId("loc-2"))
    )
    assert moved.offline_consolidation is None


@pytest.mark.asyncio
async def test_selected_forget_and_access_receipts_are_idempotent() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    kept = _trace("m-a", concepts=("path", "water", "night"))
    dropped = _trace(
        "m-faint",
        concepts=("dust",),
        confidence=0.0,
        salience=0.0,
        access_count=0,
    )
    await service.apply(MemoryMutationBatch(writes=(kept, dropped)))
    forgotten = await service.forget_selected_ids(
        (MemoryId("m-faint"),), tick=4
    )
    assert forgotten == 1
    again = await service.forget_selected_ids((MemoryId("m-faint"),), tick=5)
    assert again == 0
    active = await service.snapshot()
    assert [trace.memory_id.value for trace in active] == ["m-a"]
    stored = await service.get(MemoryId("m-faint"))
    assert stored is not None
    assert stored.forgotten_at_tick == 4

    receipt = MemoryAccessReceipt(
        memory_id=MemoryId("m-a"),
        access_tick=4,
        operation_id="offline-consolidation:4:m-a",
    )
    first = await service.apply(MemoryMutationBatch(accesses=(receipt,)))
    second = await service.apply(MemoryMutationBatch(accesses=(receipt,)))
    assert first.access_applied_count == 1
    assert second.access_applied_count == 0
    assert second.access_idempotent_count == 1
    remembered = await service.get(MemoryId("m-a"))
    assert remembered is not None
    assert remembered.access_count == kept.access_count + 1


@pytest.mark.asyncio
async def test_abort_drops_pending_and_finalize_commits_selected_ids() -> None:
    from memory.models import BeliefStore, MemoryStore
    from simulation.agent_runtime import AgentRuntime
    from simulation.bootstrap import registration_translator
    from tests.unit.test_agent_runtime import (
        _agent,
        _bootstrap,
        _self,
        _token,
    )

    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    scope = MemoryScope(
        run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1")
    )
    service = InMemoryMemoryService(scope)
    traces = (
        _trace("m-a", concepts=("path", "water", "night", "only-a")),
        _trace("m-b", concepts=("path", "water", "night", "only-b")),
        _trace(
            "m-faint",
            concepts=("dust",),
            confidence=0.0,
            salience=0.0,
            access_count=0,
        ),
    )
    await service.apply(MemoryMutationBatch(writes=traces))
    runtime = AgentRuntime(
        agent=_agent(),
        translator=registration_translator(_bootstrap()),
        cognitive_loop=build_cognitive_loop(
            CognitionLoopConfig(
                consolidation_mode=CognitionConsolidationMode.DETERMINISTIC
            )
        ),
        memory_reader=service.as_reader(),
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
        memory_service=service,
    )
    runtime.start()
    prepared = await runtime.prepare_observation(_self(tick=4), token=_token(4))
    pending = await runtime.bind_effective_command(
        prepared, effective_command=Sleep()
    )
    assert pending.loop_result.offline_consolidation is not None
    runtime.abort_pending(pending)
    assert runtime.export_offline_consolidation_audits() == ()
    active = {trace.memory_id.value for trace in await service.snapshot()}
    assert active == {"m-a", "m-b", "m-faint"}

    prepared_again = await runtime.prepare_observation(
        _self(tick=5), token=_token(5)
    )
    committed = await runtime.bind_effective_command(
        prepared_again, effective_command=Sleep()
    )
    await runtime.finalize_pending(committed)
    stored_ids = [trace.memory_id.value for trace in await service.snapshot()]
    assert any(memory_id.startswith("consol-") for memory_id in stored_ids)
    assert "m-faint" not in stored_ids
    forgotten = await service.get(MemoryId("m-faint"))
    assert forgotten is not None
    assert forgotten.forgotten_at_tick == 5
    audits = runtime.export_offline_consolidation_audits()
    assert len(audits) == 1
    assert audits[0].soft_forget_count == 1
