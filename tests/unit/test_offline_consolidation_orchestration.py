"""Cognition orchestration for sleep consolidation intents."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.consolidation import orchestrate_offline_consolidation
from agents.cognition.models import (
    MemoryUpdateIntent,
    MemoryUpdateKind,
    SubjectiveSnapshot,
    project_self_model,
)
from agents.models import AgentId, Goal, GoalId, GoalStatus
from memory.models import (
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipConfidence,
    RelationshipDimension,
    RelationshipDimensionState,
    RelationshipEvidenceItem,
    RelationshipId,
    RelationshipPolicyRef,
    RelationshipRevisionId,
)
from world.identifiers import EntityId, WorldRevision


def _trace(
    *,
    memory_id: str,
    concepts: tuple[str, ...],
    entity_id: str | None = None,
    confidence: float = 0.9,
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
        entities=(
            ()
            if entity_id is None
            else (
                EntityMention(
                    mention_id=MentionId(f"{memory_id}-e"),
                    label=entity_id,
                    entity_id=EntityId(entity_id),
                ),
            )
        ),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.6,
        confidence=confidence,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=0,
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=1,
    )


def _profile() -> DirectedRelationshipProfile:
    policy = RelationshipPolicyRef(policy_id="relationship-formation", version="1")
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-1"),
        source_id=AgentId("agent-1"),
        target_id=AgentId("agent-2"),
        dimensions=(
            RelationshipDimensionState(
                dimension=RelationshipDimension.TRUST,
                value=0.25,
                confidence=RelationshipConfidence(
                    confidence=0.5, support_mass=0.5, contradiction_mass=0.0
                ),
                evidence=(
                    RelationshipEvidenceItem(
                        memory_ref="m-a",
                        contribution=0.4,
                        ordinal=0,
                        lineage_root_ref="m-a",
                    ),
                ),
                logical_tick=1,
                policy=policy,
            ),
        ),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rr-1"),
        revision_ordinal=0,
        created_tick=0,
        updated_tick=1,
        policy=policy,
    )


def _goal(*, goal_id: str, belief_ref: str, deadline_tick: int | None = None) -> Goal:
    return Goal(
        goal_id=GoalId(goal_id),
        owner_id=AgentId("agent-1"),
        description="keep the path",
        priority=0.5,
        status=GoalStatus.ACTIVE,
        belief_refs=(belief_ref,),
        deadline_tick=deadline_tick,
    )


def _snapshot(
    *,
    memories: tuple[MemoryTrace, ...] = (),
    relationships: tuple[object, ...] = (),
    goals: tuple[Goal, ...] = (),
) -> SubjectiveSnapshot:
    return SubjectiveSnapshot(
        owner_id=AgentId("agent-1"),
        revision=0,
        memories=memories,
        legacy_beliefs=(),
        semantic_beliefs=(),
        relationships=relationships,
        goals=goals,
    )


def test_empty_stores_emit_zero_counts() -> None:
    plan = orchestrate_offline_consolidation(
        snapshot=_snapshot(),
        self_model=project_self_model(
            owner_id=AgentId("agent-1"), life_status=None, beliefs=()
        ),
        write_intents=(),
        tick=1,
        mode="deterministic",
    )
    assert plan.audit.trace_count == 0
    assert plan.audit.relationship_count == 0
    assert plan.audit.goal_count == 0
    assert plan.audit.belief_count == 0
    assert plan.relationship_revisions == ()
    assert plan.goal_intents == ()
    assert "keep the path" not in repr(plan)


def test_merge_revises_forward_relationship_and_suspends_goal() -> None:
    left = _trace(
        memory_id="m-a",
        concepts=("path", "water", "night", "only-a"),
        entity_id="agent-2",
    )
    right = _trace(
        memory_id="m-b",
        concepts=("path", "water", "night", "only-b"),
        entity_id="agent-2",
    )
    plan = orchestrate_offline_consolidation(
        snapshot=_snapshot(
            memories=(left, right),
            relationships=(_profile(),),
            goals=(_goal(goal_id="goal-1", belief_ref="m-a"),),
        ),
        self_model=project_self_model(
            owner_id=AgentId("agent-1"), life_status=None, beliefs=()
        ),
        write_intents=(),
        tick=2,
        mode="deterministic",
    )
    assert plan.audit.merge_count == 1
    assert plan.relationship_revisions
    for request in plan.relationship_revisions:
        assert request.source_id == AgentId("agent-1")
        assert request.target_id == AgentId("agent-2")
    assert plan.goal_intents[0].to_status is GoalStatus.SUSPENDED
    assert plan.goal_intents[0].to_status is not GoalStatus.COMPLETED
    assert plan.self_model_belief_ids


def test_strengthen_only_pass_does_not_revise_relationships_or_goals() -> None:
    lonely = _trace(memory_id="m-a", concepts=("path",), entity_id="agent-2")
    plan = orchestrate_offline_consolidation(
        snapshot=_snapshot(
            memories=(lonely,),
            relationships=(_profile(),),
            goals=(_goal(goal_id="goal-1", belief_ref="m-a"),),
        ),
        self_model=project_self_model(
            owner_id=AgentId("agent-1"), life_status=None, beliefs=()
        ),
        write_intents=(),
        tick=1,
        mode="deterministic",
    )
    assert plan.selection.merge_groups == ()
    assert plan.selection.soft_forget_ids == ()
    assert plan.relationship_revisions == ()
    assert plan.goal_intents == ()
    assert plan.audit.relationship_count == 0
    assert plan.audit.goal_count == 0


def test_deadline_goal_is_left_to_the_goal_manager() -> None:
    stale = _trace(
        memory_id="m-old",
        concepts=("dust",),
        confidence=0.01,
    )
    stale = MemoryTrace(
        memory_id=stale.memory_id,
        owner_id=stale.owner_id,
        world_revision=stale.world_revision,
        concepts=stale.concepts,
        entities=(
            EntityMention(
                mention_id=MentionId("m-old-e"),
                label="agent-2",
                entity_id=EntityId("agent-2"),
            ),
        ),
        relations=(),
        context=stale.context,
        emotional_salience=0.0,
        confidence=0.01,
        provenance=stale.provenance,
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
    )
    plan = orchestrate_offline_consolidation(
        snapshot=_snapshot(
            memories=(stale,),
            relationships=(_profile(),),
            goals=(
                _goal(goal_id="goal-due", belief_ref="m-old", deadline_tick=0),
            ),
        ),
        self_model=project_self_model(
            owner_id=AgentId("agent-1"), life_status=None, beliefs=()
        ),
        write_intents=(),
        tick=3,
        mode="deterministic",
    )
    assert stale.memory_id in plan.selection.soft_forget_ids
    assert plan.goal_intents == ()


def test_write_memory_intents_join_the_snapshot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stored = _trace(memory_id="m-a", concepts=("path", "water", "night", "only-a"))
    pending = MemoryUpdateIntent(
        owner_id=AgentId("agent-1"),
        kind=MemoryUpdateKind.WRITE_MEMORY,
        memory=_trace(
            memory_id="m-b", concepts=("path", "water", "night", "only-b")
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.consolidation"):
        plan = orchestrate_offline_consolidation(
            snapshot=_snapshot(memories=(stored,)),
            self_model=project_self_model(
                owner_id=AgentId("agent-1"), life_status=None, beliefs=()
            ),
            write_intents=(pending,),
            tick=2,
            mode="deterministic",
        )
    assert plan.selection.merge_groups
    messages = [record.message for record in caplog.records]
    assert any("offline_consolidation_candidates" in message for message in messages)
    assert "only-a" not in " ".join(record.message for record in caplog.records)


def test_owner_mismatch_fails_closed(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="agents.cognition.consolidation"):
        with pytest.raises(ValueError, match="owner_mismatch"):
            orchestrate_offline_consolidation(
                snapshot=_snapshot(),
                self_model=project_self_model(
                    owner_id=AgentId("agent-2"), life_status=None, beliefs=()
                ),
                write_intents=(),
                tick=1,
                mode="deterministic",
            )
    assert any(
        getattr(record, "reason_code", None) == "owner_mismatch"
        or "owner_mismatch" in record.message
        for record in caplog.records
    )
