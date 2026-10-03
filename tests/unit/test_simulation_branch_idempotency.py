"""Unit proofs for research fork idempotency against an in-memory lineage store."""

from __future__ import annotations

import pytest

from simulation.branching import (
    BranchCreateRequest,
    BranchError,
    BranchLineage,
    InMemoryBranchLineageRepository,
    ResearchIntervention,
    ResearchInterventionKind,
    canonical_intervention_document,
    encode_branch_lineage,
    intervention_fingerprint,
    resolve_idempotent_create,
)
from simulation.identifiers import derive_branch_id, derive_branch_run_id
from simulation.models import RunId
from simulation.runner_models import MemoryMode


def _request() -> BranchCreateRequest:
    return BranchCreateRequest(
        parent_run_id=RunId("parent-run"),
        fork_tick=5,
        intervention=ResearchIntervention(
            kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
            agent_ids=("agent-a",),
            memory_mode=MemoryMode.REFERENCE,
        ),
    )


def _lineage_for(request: BranchCreateRequest) -> BranchLineage:
    fingerprint = intervention_fingerprint(request.intervention)
    token = "inherit"
    child = derive_branch_run_id(
        request.parent_run_id, request.fork_tick, fingerprint, token
    )
    branch_id = derive_branch_id(
        request.parent_run_id, request.fork_tick, fingerprint, token
    )
    return BranchLineage(
        child_run_id=child,
        parent_run_id=request.parent_run_id,
        fork_tick=request.fork_tick,
        intervention_kind=request.intervention.kind,
        intervention_fingerprint=fingerprint,
        intervention_canonical=canonical_intervention_document(request.intervention),
        branch_id=branch_id,
        created_as_of_parent_head=12,
    )


@pytest.mark.asyncio
async def test_first_create_put_and_get() -> None:
    repo = InMemoryBranchLineageRepository()
    request = _request()
    lineage = _lineage_for(request)
    assert (
        resolve_idempotent_create(
            child_run_id=lineage.child_run_id,
            request=request,
            existing=None,
        )
        is None
    )
    stored = await repo.put_lineage(lineage)
    assert stored == lineage
    loaded = await repo.get_lineage(child_run_id=lineage.child_run_id)
    assert loaded == lineage
    children = await repo.list_children(parent_run_id=request.parent_run_id)
    assert children == (lineage,)
    round_trip = encode_branch_lineage(lineage)
    assert round_trip["child_run_id"] == lineage.child_run_id.value


@pytest.mark.asyncio
async def test_idempotent_hit_on_matching_fingerprint() -> None:
    repo = InMemoryBranchLineageRepository()
    request = _request()
    lineage = _lineage_for(request)
    await repo.put_lineage(lineage)
    again = await repo.put_lineage(lineage)
    assert again == lineage
    hit = resolve_idempotent_create(
        child_run_id=lineage.child_run_id,
        request=request,
        existing=lineage,
    )
    assert hit is not None
    assert hit.idempotent_hit is True


@pytest.mark.asyncio
async def test_identity_conflict_on_fingerprint_mismatch() -> None:
    repo = InMemoryBranchLineageRepository()
    request = _request()
    lineage = _lineage_for(request)
    await repo.put_lineage(lineage)
    conflicting = BranchLineage(
        child_run_id=lineage.child_run_id,
        parent_run_id=lineage.parent_run_id,
        fork_tick=lineage.fork_tick,
        intervention_kind=lineage.intervention_kind,
        intervention_fingerprint="f" * 64,
        intervention_canonical={"kind": "memory_architecture"},
        branch_id=lineage.branch_id,
        created_as_of_parent_head=lineage.created_as_of_parent_head,
    )
    with pytest.raises(BranchError) as exc:
        await repo.put_lineage(conflicting)
    assert exc.value.reason_code == "branch_identity_conflict"
