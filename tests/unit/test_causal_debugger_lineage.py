"""Unit tests for debugger lineage ports and prediction provenance."""

from __future__ import annotations

import pytest

from agents.cognition.trace import (
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
)
from agents.models import AgentId
from simulation import (
    CausalDebuggerError,
    CausalTraceAvailability,
    CounterfactualNodeMaterial,
    CounterfactualSourceKind,
    DebuggerFocusHandle,
    DebuggerLineageEntry,
    DebuggerLineageKind,
    DebuggerLineageResponse,
    InMemoryBeliefEvidenceLineage,
    InMemoryPredictionProvenance,
    RunId,
    assemble_prediction_provenance,
    build_cognition_trace_invocation,
    project_goal_ancestry_from_checkpoint,
    project_narrative_lineage_from_checkpoint,
    require_lineage_kind,
)


def test_require_lineage_kind_closed() -> None:
    assert (
        require_lineage_kind("belief_evidence")
        is DebuggerLineageKind.BELIEF_EVIDENCE
    )
    with pytest.raises(CausalDebuggerError) as exc:
        require_lineage_kind("not_a_kind")
    assert exc.value.code == "invalid_kind"


@pytest.mark.asyncio
async def test_belief_evidence_fake_round_trip() -> None:
    run_id = RunId("run-lin")
    owner = AgentId("alice")
    port = InMemoryBeliefEvidenceLineage()
    focus = DebuggerFocusHandle(run_id=run_id, tick=3, sequence=1, event_id="e1")
    port.seed(
        DebuggerLineageResponse(
            run_id=run_id,
            owner_id=owner,
            kind=DebuggerLineageKind.BELIEF_EVIDENCE,
            subject_id="belief-1",
            availability=CausalTraceAvailability.AVAILABLE,
            entries=(
                DebuggerLineageEntry(
                    entry_id="belief-1",
                    kind=DebuggerLineageKind.BELIEF_EVIDENCE,
                    related_ids=("mem-1", "mem-2"),
                    focus_handles=(focus,),
                    counts={"evidence_count": 2},
                ),
            ),
        )
    )
    result = await port.belief_evidence(
        run_id=run_id, owner_id=owner, subject_id="belief-1"
    )
    assert result.availability is CausalTraceAvailability.AVAILABLE
    assert result.entries[0].related_ids == ("mem-1", "mem-2")
    assert result.entries[0].focus_handles[0].event_id == "e1"
    assert not hasattr(result.entries[0], "proposition_text")


@pytest.mark.asyncio
async def test_belief_evidence_missing_is_unavailable() -> None:
    port = InMemoryBeliefEvidenceLineage()
    result = await port.belief_evidence(
        run_id=RunId("run-x"),
        owner_id=AgentId("alice"),
        subject_id="missing",
    )
    assert result.availability is CausalTraceAvailability.UNAVAILABLE
    assert result.reason_code == "lineage_not_found"


def test_prediction_provenance_honors_task_1c() -> None:
    invocation = build_cognition_trace_invocation(
        run_id=RunId("run-pred"),
        agent_id=AgentId("alice"),
        tick=4,
        invocation_id="inv-1",
        stage_summaries=(
            CognitionTraceStageSummary(
                stage_kind=CognitionTraceStageKind.IMAGINED_FUTURES,
                status=CognitionTraceStageStatus.COMPLETED,
                ordinal=0,
                confidence=0.4,
                selection_codes=("cf_branch_a",),
            ),
        ),
        command_kind="attack",
    )
    response = assemble_prediction_provenance(
        run_id=RunId("run-pred"),
        owner_id=AgentId("alice"),
        subject_id="pred-1",
        invocation=invocation,
        harvest=CounterfactualNodeMaterial(
            source=CounterfactualSourceKind.RESULT,
            reason_code=None,
            scenario_count=9,
        ),
    )
    assert response.availability is CausalTraceAvailability.AVAILABLE
    assert response.entries[0].status_code == "trace"
    assert response.entries[0].reason_codes == ("cf_branch_a",)


@pytest.mark.asyncio
async def test_prediction_port_unavailable_without_sources() -> None:
    port = InMemoryPredictionProvenance()
    result = await port.prediction_provenance(
        run_id=RunId("run-pred"),
        owner_id=AgentId("alice"),
        subject_id="pred-missing",
    )
    assert result.availability is CausalTraceAvailability.UNAVAILABLE
    assert result.reason_code == "cognition_trace_missing"


def test_narrative_lineage_from_checkpoint_parents_and_focus() -> None:
    run_id = RunId("run-narr")
    owner = AgentId("alice")

    class _Variant:
        def __init__(
            self,
            *,
            variant_id: str,
            parents: tuple[str, ...] = (),
            competing: tuple[str, ...] = (),
            source_event_id: str | None = None,
            last_tick: int | None = None,
            status: str = "active",
            origin: str = "observation",
        ) -> None:
            self.variant_id = variant_id
            self.parent_variant_ids = parents
            self.competing_variant_ids = competing
            self.source_event_id = source_event_id
            self.last_tick = last_tick
            self.first_tick = last_tick
            self.status = status
            self.origin = origin

    class _Ledger:
        variants = (
            _Variant(variant_id="parent-a", status="active"),
            _Variant(
                variant_id="child-1",
                parents=("parent-a",),
                competing=("rival-1",),
                source_event_id="evt-n1",
                last_tick=12,
            ),
        )

    class _Checkpoint:
        cultural_narratives = _Ledger()

    result = project_narrative_lineage_from_checkpoint(
        run_id=run_id,
        owner_id=owner,
        subject_id="child-1",
        checkpoint=_Checkpoint(),
    )
    assert result.availability is CausalTraceAvailability.AVAILABLE
    assert result.entries[0].parent_ids == ("parent-a",)
    assert "rival-1" in result.entries[0].related_ids
    assert result.entries[0].focus_handles[0].event_id == "evt-n1"
    assert result.entries[0].focus_handles[0].tick == 12
    assert not hasattr(result.entries[0], "narrative_text")
    assert not hasattr(result.entries[0], "content")


def test_goal_ancestry_from_checkpoint_walks_parents() -> None:
    run_id = RunId("run-goal")
    owner = AgentId("alice")

    class _GoalId:
        def __init__(self, value: str) -> None:
            self.value = value

    class _Goal:
        def __init__(
            self,
            goal_id: str,
            *,
            parent: str | None = None,
            status: str = "active",
        ) -> None:
            self.goal_id = _GoalId(goal_id)
            self.parent_goal_id = None if parent is None else _GoalId(parent)
            self.status = status
            self.description = "must-not-leak"

    class _Checkpoint:
        goals = (
            _Goal("root"),
            _Goal("mid", parent="root"),
            _Goal("leaf", parent="mid"),
            _Goal("sibling", parent="mid"),
        )

    result = project_goal_ancestry_from_checkpoint(
        run_id=run_id,
        owner_id=owner,
        subject_id="leaf",
        checkpoint=_Checkpoint(),
    )
    assert result.availability is CausalTraceAvailability.AVAILABLE
    assert result.entries[0].parent_ids == ("mid",)
    assert result.entries[0].counts == {"ancestor_count": 2, "child_count": 0}
    assert "root" in result.entries[0].related_ids
    assert not hasattr(result.entries[0], "description")


def test_checkpoint_lineage_missing_reasons() -> None:
    run_id = RunId("run-miss")
    owner = AgentId("alice")
    missing_cp = project_narrative_lineage_from_checkpoint(
        run_id=run_id, owner_id=owner, subject_id="v1", checkpoint=None
    )
    assert missing_cp.reason_code == "checkpoint_unavailable"

    class _Empty:
        cultural_narratives = None
        goals = ()

    no_ledger = project_narrative_lineage_from_checkpoint(
        run_id=run_id, owner_id=owner, subject_id="v1", checkpoint=_Empty()
    )
    assert no_ledger.reason_code == "narrative_ledger_missing"
    no_goal = project_goal_ancestry_from_checkpoint(
        run_id=run_id, owner_id=owner, subject_id="g1", checkpoint=_Empty()
    )
    assert no_goal.reason_code == "lineage_not_found"
