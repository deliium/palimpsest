"""Unit proofs for research branching contracts."""

from __future__ import annotations

import pytest

from simulation.branching import (
    INHERIT_SEED_STREAM_TOKEN,
    BeliefPatchPayload,
    BranchCreateRequest,
    BranchError,
    BranchLineage,
    CommunicationRemoveTarget,
    ResearchIntervention,
    ResearchInterventionKind,
    canonical_intervention_document,
    intervention_fingerprint,
    resolve_idempotent_create,
    seed_stream_token_for_intervention,
    validate_research_intervention,
)
from simulation.models import RunId, StochasticIdentity
from simulation.runner_models import (
    CognitiveBudgetLimits,
    CognitiveBudgetMode,
    MemoryMode,
    MortalityMode,
)


def _memory_intervention() -> ResearchIntervention:
    return ResearchIntervention(
        kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
        agent_ids=("agent-a",),
        memory_mode=MemoryMode.RECONSTRUCTIVE_V2,
    )


def test_memory_architecture_fingerprint_stable() -> None:
    left = _memory_intervention()
    right = _memory_intervention()
    assert intervention_fingerprint(left) == intervention_fingerprint(right)
    assert len(intervention_fingerprint(left)) == 64
    document = canonical_intervention_document(left)
    assert document == {
        "kind": "memory_architecture",
        "agent_ids": ["agent-a"],
        "memory_mode": "reconstructive_v2",
    }


def test_fingerprint_changes_when_mode_changes() -> None:
    left = _memory_intervention()
    right = ResearchIntervention(
        kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
        agent_ids=("agent-a",),
        memory_mode=MemoryMode.REFERENCE,
    )
    assert intervention_fingerprint(left) != intervention_fingerprint(right)


def test_reject_unknown_kind_field_mix() -> None:
    with pytest.raises(BranchError) as exc:
        validate_research_intervention(
            ResearchIntervention(
                kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
                agent_ids=("agent-a",),
                memory_mode=MemoryMode.REFERENCE,
                architecture_id="baseline",
            )
        )
    assert exc.value.reason_code == "invalid_intervention"


def test_reject_missing_agents() -> None:
    with pytest.raises(BranchError) as exc:
        validate_research_intervention(
            ResearchIntervention(
                kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
                memory_mode=MemoryMode.REFERENCE,
            )
        )
    assert exc.value.reason_code == "invalid_intervention"


def test_belief_patch_requires_closed_payload() -> None:
    with pytest.raises(BranchError) as exc:
        validate_research_intervention(
            ResearchIntervention(kind=ResearchInterventionKind.BELIEF_PATCH)
        )
    assert exc.value.reason_code == "empty_patch"

    patch = BeliefPatchPayload(
        owner_id="owner-1",
        belief_id="belief-1",
        subject_kind="agent",
        subject_id="owner-1",
        predicate="is_alive",
        value_kind="bool",
        bool_value=False,
    )
    intervention = ResearchIntervention(
        kind=ResearchInterventionKind.BELIEF_PATCH,
        belief_patch=patch,
    )
    assert intervention_fingerprint(intervention)


def test_communication_remove_locator_forms() -> None:
    by_event = ResearchIntervention(
        kind=ResearchInterventionKind.COMMUNICATION_REMOVE,
        communication_remove=CommunicationRemoveTarget(event_id="evt-1"),
    )
    by_coord = ResearchIntervention(
        kind=ResearchInterventionKind.COMMUNICATION_REMOVE,
        communication_remove=CommunicationRemoveTarget(tick=3, sequence=1),
    )
    validate_research_intervention(by_event)
    validate_research_intervention(by_coord)
    with pytest.raises(BranchError) as exc:
        CommunicationRemoveTarget(event_id="evt-1", tick=1, sequence=0)
    assert exc.value.reason_code == "invalid_intervention"


def test_mortality_disabled_defaults() -> None:
    intervention = ResearchIntervention(
        kind=ResearchInterventionKind.MORTALITY_DISABLED,
    )
    validated = validate_research_intervention(intervention)
    assert validated.mortality_mode is MortalityMode.DISABLED


def test_cognitive_budget_enforced_requires_limits() -> None:
    with pytest.raises(BranchError) as exc:
        validate_research_intervention(
            ResearchIntervention(
                kind=ResearchInterventionKind.COGNITIVE_BUDGET,
                agent_ids=("agent-a",),
                cognitive_budget_mode=CognitiveBudgetMode.ENFORCED,
            )
        )
    assert exc.value.reason_code == "invalid_intervention"

    limits = CognitiveBudgetLimits(
        max_llm_calls_per_tick=1,
        max_tokens_per_tick=100,
        max_imagination_branches=1,
        max_planning_depth=1,
        max_recalled_memories=1,
        max_tom_targets=0,
        reflection_interval_ticks=1,
        timeout_seconds=0.0,
    )
    intervention = ResearchIntervention(
        kind=ResearchInterventionKind.COGNITIVE_BUDGET,
        agent_ids=("agent-a",),
        cognitive_budget_mode=CognitiveBudgetMode.ENFORCED,
        cognitive_budget_limits=limits,
    )
    validate_research_intervention(intervention)


def test_alternate_seed_stream_token() -> None:
    inherit = _memory_intervention()
    assert seed_stream_token_for_intervention(inherit) == INHERIT_SEED_STREAM_TOKEN
    alternate = ResearchIntervention(
        kind=ResearchInterventionKind.ALTERNATE_SEED_STREAM,
        alternate_stochastic_identity=StochasticIdentity("alt-stream-1"),
    )
    assert seed_stream_token_for_intervention(alternate).startswith("alternate:")


def test_idempotent_hit_and_conflict() -> None:
    request = BranchCreateRequest(
        parent_run_id=RunId("parent-run"),
        fork_tick=4,
        intervention=_memory_intervention(),
    )
    fingerprint = intervention_fingerprint(request.intervention)
    lineage = BranchLineage(
        child_run_id=RunId("child-run"),
        parent_run_id=RunId("parent-run"),
        fork_tick=4,
        intervention_kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
        intervention_fingerprint=fingerprint,
        intervention_canonical=canonical_intervention_document(request.intervention),
        branch_id="branch-1",
        created_as_of_parent_head=10,
    )
    hit = resolve_idempotent_create(
        child_run_id=RunId("child-run"),
        request=request,
        existing=lineage,
    )
    assert hit is not None
    assert hit.idempotent_hit is True

    assert (
        resolve_idempotent_create(
            child_run_id=RunId("child-run"),
            request=request,
            existing=None,
        )
        is None
    )

    conflict_lineage = BranchLineage(
        child_run_id=RunId("child-run"),
        parent_run_id=RunId("parent-run"),
        fork_tick=4,
        intervention_kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
        intervention_fingerprint="0" * 64,
        intervention_canonical={"kind": "memory_architecture"},
        branch_id="branch-1",
        created_as_of_parent_head=10,
    )
    with pytest.raises(BranchError) as exc:
        resolve_idempotent_create(
            child_run_id=RunId("child-run"),
            request=request,
            existing=conflict_lineage,
        )
    assert exc.value.reason_code == "branch_identity_conflict"
