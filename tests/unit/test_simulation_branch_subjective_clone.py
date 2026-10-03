"""Unit proofs for research-fork subjective cloning."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from simulation.branch_service import BranchService, InMemorySubjectiveClonePort
from simulation.branching import BranchError
from simulation.models import RunId
from simulation.subjective_state import SubjectiveOwnerSnapshot
from tests.unit.test_goal_manager import _belief, _goal
from world.identifiers import EntityId, WorldRevision

pytestmark = pytest.mark.unit


def _trace(*, memory_id: str, tick: int) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-a"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="camp"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(location_id=EntityId("loc-1")),
        emotional_salience=0.2,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=tick,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
    )


@pytest.mark.asyncio
async def test_subjective_clone_copies_as_of_tick_and_preserves_parent() -> None:
    port = InMemorySubjectiveClonePort()
    owner = AgentId("agent-a")
    parent = RunId("parent-run")
    child = RunId("child-run")
    early = _trace(memory_id="mem-early", tick=1)
    late = _trace(memory_id="mem-late", tick=5)
    belief = _belief(predicate="at_location", belief_id="belief-1")
    goal = _goal(goal_id="goal-1")
    parent_snap = SubjectiveOwnerSnapshot(
        memories=(early, late),
        semantic_beliefs=(belief,),
        relationships=(),
        reconstruction_count=0,
    )
    port.seed_parent_owner(
        run_id=parent,
        owner_id=owner,
        snapshot=parent_snap,
        goals=(goal,),
    )

    service = BranchService(
        runs=object(),  # unused for clone path
        journal=object(),
        snapshots=object(),
        subjective_clone=port,
    )
    result = await service.clone_subjective_state(
        parent_run_id=parent,
        child_run_id=child,
        fork_tick=3,
    )
    assert result.owner_count == 1
    assert result.memory_rows == 1
    assert result.belief_rows == 1
    assert result.goal_rows == 1

    child_snap = port.child_snapshot(run_id=child, owner_id=owner)
    assert child_snap is not None
    assert {trace.memory_id.value for trace in child_snap.memories} == {"mem-early"}
    assert port.child_goals(run_id=child, owner_id=owner) == (goal,)

    still_parent = port.parent_snapshot(run_id=parent, owner_id=owner)
    assert still_parent is not None
    assert len(still_parent.memories) == 2


@pytest.mark.asyncio
async def test_subjective_clone_incomplete_fails_closed() -> None:
    port = InMemorySubjectiveClonePort()
    port._force_incomplete = True
    service = BranchService(
        runs=object(),
        journal=object(),
        snapshots=object(),
        subjective_clone=port,
    )
    with pytest.raises(BranchError) as exc:
        await service.clone_subjective_state(
            parent_run_id=RunId("parent-run"),
            child_run_id=RunId("child-run"),
            fork_tick=0,
        )
    assert exc.value.reason_code == "subjective_clone_incomplete"
