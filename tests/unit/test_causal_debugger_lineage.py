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
