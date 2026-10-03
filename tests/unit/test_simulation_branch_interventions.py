"""Unit proofs for closed research-intervention application."""

from __future__ import annotations

import json

import pytest

from agents.models import AgentId
from memory.beliefs import BeliefId
from simulation.branch_service import (
    InMemorySubjectiveClonePort,
    apply_belief_patch,
    apply_research_intervention,
)
from simulation.branching import (
    BeliefPatchPayload,
    BranchError,
    CommunicationRemoveTarget,
    ResearchIntervention,
    ResearchInterventionKind,
    SeedStreamPolicy,
)
from simulation.models import RunId, StochasticIdentity
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V22,
    CognitiveBudgetLimits,
    CognitiveBudgetMode,
    MemoryMode,
    MortalityMode,
)
from simulation.runner_serialization import encode_runner_config
from simulation.subjective_state import SubjectiveOwnerSnapshot
from tests.unit.test_goal_manager import _belief
from tests.unit.test_runner_serialization import _config
from world.communications import origin_utterance
from world.events import Talked, WorldEvent, make_replayable_event
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def _limits() -> CognitiveBudgetLimits:
    return CognitiveBudgetLimits(
        max_llm_calls_per_tick=1,
        max_tokens_per_tick=100,
        max_imagination_branches=1,
        max_planning_depth=1,
        max_recalled_memories=4,
        max_tom_targets=1,
        reflection_interval_ticks=8,
        timeout_seconds=1.0,
    )


def _talked(*, tick: int, sequence: int = 0, event_id: str = "evt-talk") -> WorldEvent:
    return make_replayable_event(
        event_id=EventId(event_id),
        run_id="parent-run",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(0),
        details=Talked(
            EntityId("body-2"),
            origin_utterance(text="hello", speaker_id=EntityId("body-1")),
        ),
        actor_id=EntityId("body-1"),
    )


def test_memory_architecture_updates_target_agent() -> None:
    base = _config()
    result = apply_research_intervention(
        base,
        ResearchIntervention(
            kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
            agent_ids=("agent-1",),
            memory_mode=MemoryMode.RECONSTRUCTIVE,
        ),
        fork_tick=3,
    )
    assert result.seed_stream_policy is SeedStreamPolicy.INHERIT
    assert result.runner_config.stochastic_identity == base.stochastic_identity
    assert (
        result.runner_config.agents[0].cognition.memory_mode
        is MemoryMode.RECONSTRUCTIVE
    )


def test_mortality_disabled_on_child_config() -> None:
    base = _config()
    assert base.mortality_mode is MortalityMode.ENABLED
    result = apply_research_intervention(
        base,
        ResearchIntervention(kind=ResearchInterventionKind.MORTALITY_DISABLED),
        fork_tick=0,
    )
    assert result.runner_config.mortality_mode is MortalityMode.DISABLED
    assert result.runner_config.stochastic_identity == base.stochastic_identity


def test_cognitive_budget_bumps_schema_v22() -> None:
    base = _config()
    result = apply_research_intervention(
        base,
        ResearchIntervention(
            kind=ResearchInterventionKind.COGNITIVE_BUDGET,
            agent_ids=("agent-1",),
            cognitive_budget_mode=CognitiveBudgetMode.ENFORCED,
            cognitive_budget_limits=_limits(),
        ),
        fork_tick=1,
    )
    cognition = result.runner_config.agents[0].cognition
    assert cognition.cognitive_budget_mode is CognitiveBudgetMode.ENFORCED
    assert result.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V22


def test_alternate_seed_stream_only_when_requested() -> None:
    base = _config(stochastic="parent-stream")
    inherit = apply_research_intervention(
        base,
        ResearchIntervention(
            kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
            agent_ids=("agent-1",),
            memory_mode=MemoryMode.REFERENCE,
        ),
        fork_tick=2,
    )
    assert inherit.seed_stream_policy is SeedStreamPolicy.INHERIT
    assert inherit.runner_config.stochastic_identity.value == "parent-stream"

    alternate = apply_research_intervention(
        base,
        ResearchIntervention(
            kind=ResearchInterventionKind.ALTERNATE_SEED_STREAM,
            alternate_stochastic_identity=StochasticIdentity("child-stream"),
        ),
        fork_tick=2,
    )
    assert alternate.seed_stream_policy is SeedStreamPolicy.ALTERNATE
    assert alternate.runner_config.stochastic_identity.value == "child-stream"


def test_agent_architecture_expands_without_architecture_id_key() -> None:
    base = _config()
    result = apply_research_intervention(
        base,
        ResearchIntervention(
            kind=ResearchInterventionKind.AGENT_ARCHITECTURE,
            agent_ids=("agent-1",),
            architecture_id="reactive_baseline",
        ),
        fork_tick=4,
    )
    document = json.loads(encode_runner_config(result.runner_config).decode("utf-8"))
    assert "architecture_id" not in document
    assert "architecture_id" not in document["agents"][0]["cognition"]
    assert (
        result.runner_config.agents[0].cognition.memory_mode is MemoryMode.REFERENCE
    )


def test_agent_architecture_unknown_fails_closed() -> None:
    with pytest.raises(BranchError) as exc:
        apply_research_intervention(
            _config(),
            ResearchIntervention(
                kind=ResearchInterventionKind.AGENT_ARCHITECTURE,
                agent_ids=("agent-1",),
                architecture_id="not-a-real-architecture",
            ),
            fork_tick=0,
        )
    assert exc.value.reason_code == "architecture_unknown"


def test_communication_remove_rejects_prefix_event() -> None:
    event = _talked(tick=2, event_id="evt-past")
    with pytest.raises(BranchError) as exc:
        apply_research_intervention(
            _config(),
            ResearchIntervention(
                kind=ResearchInterventionKind.COMMUNICATION_REMOVE,
                communication_remove=CommunicationRemoveTarget(event_id="evt-past"),
            ),
            fork_tick=5,
            parent_events=(event,),
        )
    assert exc.value.reason_code == "intervention_past_event"


def test_communication_remove_accepts_future_event() -> None:
    event = _talked(tick=7, event_id="evt-future")
    result = apply_research_intervention(
        _config(),
        ResearchIntervention(
            kind=ResearchInterventionKind.COMMUNICATION_REMOVE,
            communication_remove=CommunicationRemoveTarget(event_id="evt-future"),
        ),
        fork_tick=5,
        parent_events=(event,),
    )
    assert result.removed_communication is not None
    assert result.removed_communication["event_id"] == "evt-future"
    assert result.removed_communication["tick"] == 7


def test_belief_patch_revises_child_clone() -> None:
    owner = AgentId("agent-1")
    belief = _belief(predicate="at_location", belief_id="belief-1")
    snap = SubjectiveOwnerSnapshot(
        memories=(),
        semantic_beliefs=(belief,),
        relationships=(),
        reconstruction_count=0,
    )
    patch = BeliefPatchPayload(
        owner_id=owner.value,
        belief_id="belief-1",
        subject_kind="entity",
        subject_id="place-1",
        predicate="safe",
        value_kind="bool",
        bool_value=False,
    )
    revised = apply_belief_patch(snap, patch)
    assert revised.semantic_beliefs[0].claim.predicate == "safe"
    assert revised.semantic_beliefs[0].claim.value.bool_value is False
    assert belief.claim.predicate == "at_location"


def test_belief_patch_missing_fails_closed() -> None:
    snap = SubjectiveOwnerSnapshot(
        memories=(),
        semantic_beliefs=(),
        relationships=(),
        reconstruction_count=0,
    )
    with pytest.raises(BranchError) as exc:
        apply_belief_patch(
            snap,
            BeliefPatchPayload(
                owner_id="agent-1",
                belief_id="missing",
                subject_kind="entity",
                subject_id="place-1",
                predicate="safe",
                value_kind="bool",
                bool_value=True,
            ),
        )
    assert exc.value.reason_code == "belief_not_found"


@pytest.mark.asyncio
async def test_belief_patch_on_in_memory_clone_port() -> None:
    port = InMemorySubjectiveClonePort()
    owner = AgentId("agent-1")
    parent = RunId("parent-run")
    child = RunId("child-run")
    belief = _belief(predicate="at_location", belief_id="belief-1")
    port.seed_parent_owner(
        run_id=parent,
        owner_id=owner,
        snapshot=SubjectiveOwnerSnapshot(
            memories=(),
            semantic_beliefs=(belief,),
            relationships=(),
            reconstruction_count=0,
        ),
    )
    await port.clone_as_of(
        parent_run_id=parent, child_run_id=child, fork_tick=3
    )
    child_snap = port.child_snapshot(run_id=child, owner_id=owner)
    assert child_snap is not None
    patched = apply_belief_patch(
        child_snap,
        BeliefPatchPayload(
            owner_id=owner.value,
            belief_id="belief-1",
            subject_kind="entity",
            subject_id="place-1",
            predicate="hungry",
            value_kind="bool",
            bool_value=True,
        ),
    )
    port.replace_child_snapshot(run_id=child, owner_id=owner, snapshot=patched)
    assert port.child_snapshot(run_id=child, owner_id=owner) is not None
    assert (
        port.child_snapshot(run_id=child, owner_id=owner)
        .semantic_beliefs[0]
        .claim.predicate
        == "hungry"
    )
    assert BeliefId("belief-1") == belief.belief_id
