"""Reflection is planned after the command and applied only on finalize."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import CognitionReflectionMode
from agents.cognition.consolidation import OfflineConsolidationPlan
from agents.cognition.reflection import (
    ReflectionContext,
    ReflectionCursor,
    ReflectionPolicy,
    ReflectionTriggerKind,
    ReflectionTriggerResult,
    commit_reflection_cursor,
    plan_reflection,
    reflection_operation_ids,
)
from agents.models import AgentId, GoalId
from memory.models import (
    OFFLINE_CONSOLIDATION_POLICY_VERSION,
    EntityMention,
    MemoryId,
    MemoryProvenance,
    MemoryRelation,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    OfflineConsolidationAudit,
    OfflineConsolidationReasonCode,
    OfflineConsolidationSelection,
    RelationEndpoint,
    RelationEndpointKind,
)
from simulation.agent_runtime import _extend_reflection_writes
from simulation.runner_models import ConsolidationMode
from tests.unit.test_agent_runtime import _runtime, _self, _token
from world.identifiers import EntityId, WorldRevision


def _help_trace(memory_id: str) -> MemoryTrace:
    subject = MentionId(f"s-{memory_id}")
    obj = MentionId(f"o-{memory_id}")
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(),
        entities=(
            EntityMention(
                mention_id=subject,
                label="subject",
                entity_id=EntityId("bob"),
            ),
            EntityMention(
                mention_id=obj,
                label="object",
                entity_id=EntityId("agent-1"),
            ),
        ),
        relations=(
            MemoryRelation(
                relation_id=MentionId(f"r-{memory_id}"),
                predicate="help_received",
                subject=RelationEndpoint(
                    kind=RelationEndpointKind.ENTITY, mention_id=subject
                ),
                object=RelationEndpoint(
                    kind=RelationEndpointKind.ENTITY, mention_id=obj
                ),
            ),
        ),
        context=MemorySituationContext(),
        emotional_salience=0.2,
        confidence=0.8,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=1,
    )


def _plan():
    owner = AgentId("agent-1")
    policy = ReflectionPolicy(interval_ticks=1, min_gap_ticks=1, min_pattern_count=3)
    context = ReflectionContext(
        owner_id=owner,
        tick=4,
        policy=policy,
        memories=tuple(_help_trace(f"m-{index}") for index in range(3)),
        owner_entity_id=EntityId("agent-1"),
    )
    triggers = ReflectionTriggerResult(
        matched=(ReflectionTriggerKind.ELAPSED_TICKS,),
        skipped=(),
        gap_elapsed=True,
    )
    plan = plan_reflection(
        context=context,
        triggers=triggers,
        mode="deterministic",
        acknowledged_goal_ids=(GoalId("goal-done"),),
    )
    assert plan is not None
    return plan


def test_repeated_operation_ids_are_not_written_twice() -> None:
    plan = _plan()
    applied: set[str] = set()
    beliefs: list[object] = []
    relationships: list[object] = []
    _extend_reflection_writes(
        plan,
        belief_revisions=beliefs,
        relationship_revisions=relationships,
        applied=applied,
    )
    assert beliefs
    assert relationships
    applied.update(reflection_operation_ids(plan))
    again_beliefs: list[object] = []
    again_relationships: list[object] = []
    _extend_reflection_writes(
        plan,
        belief_revisions=again_beliefs,
        relationship_revisions=again_relationships,
        applied=applied,
    )
    assert again_beliefs == []
    assert again_relationships == []
    cursor = commit_reflection_cursor(
        ReflectionCursor(owner_id=AgentId("agent-1")),
        tick=4,
        acknowledged_goal_ids=plan.acknowledged_goal_ids,
    )
    assert cursor.last_reflection_tick == 4
    assert cursor.acknowledged_goal_ids[0].value == "goal-done"


def test_consolidation_overlap_drops_the_belief_conclusion() -> None:
    plan = _plan()
    belief = plan.belief_revisions[0]
    consolidation = OfflineConsolidationPlan(
        selection=OfflineConsolidationSelection(
            owner_id=AgentId("agent-1"),
            tick=4,
            policy_version=OFFLINE_CONSOLIDATION_POLICY_VERSION,
        ),
        audit=OfflineConsolidationAudit(
            owner_id=AgentId("agent-1"),
            tick=4,
            mode=ConsolidationMode.DETERMINISTIC.value,
            reason_codes=(OfflineConsolidationReasonCode.BELIEF_CANDIDATE,),
        ),
        belief_revisions=(belief,),
        relationship_revisions=(),
        goal_intents=(),
        self_model_belief_ids=(),
    )
    owner = AgentId("agent-1")
    filtered = plan_reflection(
        context=ReflectionContext(
            owner_id=owner,
            tick=4,
            policy=ReflectionPolicy(
                interval_ticks=1, min_gap_ticks=1, min_pattern_count=3
            ),
            memories=tuple(_help_trace(f"m-{index}") for index in range(3)),
            owner_entity_id=EntityId("agent-1"),
        ),
        triggers=ReflectionTriggerResult(
            matched=(ReflectionTriggerKind.ELAPSED_TICKS,),
            skipped=(),
            gap_elapsed=True,
        ),
        mode="deterministic",
        consolidation=consolidation,
    )
    assert filtered is not None
    assert filtered.belief_revisions == ()
    assert filtered.relationship_revisions


def _enable(runtime, *, interval: int) -> None:
    runtime._loop._reflection_mode = CognitionReflectionMode.DETERMINISTIC
    runtime._loop._reflection_policy = ReflectionPolicy(
        interval_ticks=interval, min_gap_ticks=interval
    )


@pytest.mark.asyncio
async def test_finalize_applies_one_pass_and_repeat_does_not() -> None:
    reflecting, _, _ = _runtime()
    reflecting.start()
    _enable(reflecting, interval=1)
    prepared = await reflecting.prepare_observation(_self(tick=0), token=_token(0))
    pending = await reflecting.bind_effective_command(prepared)
    assert pending.loop_result.reflection is not None
    command_type = type(pending.submission.command)
    stages = tuple(
        record.component_kind.value for record in pending.loop_result.boundary_records
    )
    await reflecting.finalize_pending(pending)
    await reflecting.finalize_pending(pending)
    cursor = reflecting._reflection_cursor
    assert cursor is not None
    assert cursor.last_reflection_tick == 0
    assert len(reflecting.export_reflection_audits()) == 1
    assert reflecting._decision_journal is not None
    assert len(reflecting._decision_journal) == 1

    disabled, _, _ = _runtime()
    disabled.start()
    disabled_prepared = await disabled.prepare_observation(
        _self(tick=0), token=_token(0)
    )
    disabled_pending = await disabled.bind_effective_command(disabled_prepared)
    assert disabled_pending.loop_result.reflection is None
    assert type(disabled_pending.submission.command) is command_type
    assert (
        tuple(
            record.component_kind.value
            for record in disabled_pending.loop_result.boundary_records
        )
        == stages
    )
    await disabled.finalize_pending(disabled_pending)
    assert disabled._reflection_cursor is None
    assert disabled._decision_journal is None


@pytest.mark.asyncio
async def test_quiet_tick_does_not_move_the_reflection_cursor() -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    _enable(runtime, interval=100)
    prepared = await runtime.prepare_observation(_self(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    assert pending.loop_result.reflection is None
    await runtime.finalize_pending(pending)
    cursor = runtime._reflection_cursor
    assert cursor is not None
    assert cursor.last_reflection_tick is None
    assert runtime._decision_journal is not None
    assert len(runtime._decision_journal) == 1
