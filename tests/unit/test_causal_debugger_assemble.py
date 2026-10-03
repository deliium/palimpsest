"""Unit tests for researcher causal-chain assembly."""

from __future__ import annotations

from agents.cognition.trace import (
    SCIENTIFIC_TRACE_STAGE_SEQUENCE,
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
    unavailable_stage_summary,
)
from agents.models import AgentId
from simulation import (
    RESEARCHER_CHAIN_SEQUENCE,
    CausalNodeStatus,
    CausalTraceAvailability,
    CounterfactualNodeMaterial,
    CounterfactualSourceKind,
    DebuggerEventAddress,
    RunId,
    assemble_causal_trace,
    build_cognition_trace_invocation,
)


def _full_stage_summaries(*, command_kind: str = "attack") -> list:
    summaries: list[CognitionTraceStageSummary] = []
    for ordinal, kind in enumerate(SCIENTIFIC_TRACE_STAGE_SEQUENCE):
        if kind is CognitionTraceStageKind.THEORY_OF_MIND:
            summaries.append(
                unavailable_stage_summary(
                    kind, ordinal=ordinal, reason_code="tom_not_implemented"
                )
            )
            continue
        if kind is CognitionTraceStageKind.PLANNED_ACTION:
            summaries.append(
                CognitionTraceStageSummary(
                    stage_kind=kind,
                    status=CognitionTraceStageStatus.COMPLETED,
                    ordinal=ordinal,
                    confidence=0.8,
                    command_kind=command_kind,
                )
            )
            continue
        summaries.append(
            CognitionTraceStageSummary(
                stage_kind=kind,
                status=CognitionTraceStageStatus.COMPLETED,
                ordinal=ordinal,
                confidence=0.5,
            )
        )
    return summaries


def test_assemble_projects_researcher_order_with_unavailable_counterfactuals() -> None:
    invocation = build_cognition_trace_invocation(
        run_id=RunId("run-asm"),
        agent_id=AgentId("alice"),
        tick=1832,
        invocation_id="inv-1",
        stage_summaries=_full_stage_summaries(),
        command_kind="attack",
    )
    address = DebuggerEventAddress(
        run_id=RunId("run-asm"),
        tick=1832,
        event_id="evt-attack-1",
        sequence=17,
        agent_id=AgentId("alice"),
    )
    trace = assemble_causal_trace(invocation, address=address)
    assert trace.availability is CausalTraceAvailability.AVAILABLE
    assert [node.stage_code for node in trace.nodes] == [
        stage.value for stage in RESEARCHER_CHAIN_SEQUENCE
    ]
    by_code = {node.stage_code: node for node in trace.nodes}
    assert by_code["observation"].status is CausalNodeStatus.AVAILABLE
    assert by_code["theory_of_mind"].status is CausalNodeStatus.UNAVAILABLE
    assert by_code["theory_of_mind"].reason_code == "tom_not_implemented"
    assert by_code["counterfactuals"].status is CausalNodeStatus.UNAVAILABLE
    assert by_code["counterfactuals"].reason_code == "counterfactual_unavailable"
    assert by_code["action"].command_kind == "attack"
    assert by_code["action"].focus_handles[0].event_id == "evt-attack-1"
    assert by_code["action"].focus_handles[0].sequence == 17
    supporting_codes = {node.stage_code for node in trace.supporting_nodes}
    assert "situation_model" in supporting_codes
    assert "budget_summary" in supporting_codes


def test_assemble_uses_harvested_counterfactuals() -> None:
    invocation = build_cognition_trace_invocation(
        run_id=RunId("run-asm-cf"),
        agent_id=AgentId("alice"),
        tick=2,
        invocation_id="inv-cf",
        stage_summaries=_full_stage_summaries(),
        command_kind="attack",
    )
    harvest = CounterfactualNodeMaterial(
        source=CounterfactualSourceKind.RESULT,
        reason_code=None,
        scenario_count=2,
        regret_count=1,
        relief_count=0,
        neutral_count=1,
        confidence_band="medium",
    )
    trace = assemble_causal_trace(invocation, counterfactual_source=harvest)
    cf = next(node for node in trace.nodes if node.stage_code == "counterfactuals")
    assert cf.status is CausalNodeStatus.AVAILABLE
    assert cf.counts is not None
    assert cf.counts["scenario_count"] == 2
    assert cf.uncertainty_band == "medium"


def test_assemble_missing_stage_is_unavailable_not_omitted() -> None:
    stages = [
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.OBSERVATION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=0,
            confidence=0.5,
        ),
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.PLANNED_ACTION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=1,
            confidence=0.9,
            command_kind="wait",
        ),
    ]
    invocation = build_cognition_trace_invocation(
        run_id=RunId("run-partial"),
        agent_id=AgentId("bob"),
        tick=1,
        invocation_id="inv-partial",
        stage_summaries=stages,
        command_kind="wait",
    )
    trace = assemble_causal_trace(invocation)
    assert len(trace.nodes) == len(RESEARCHER_CHAIN_SEQUENCE)
    beliefs = next(node for node in trace.nodes if node.stage_code == "beliefs")
    assert beliefs.status is CausalNodeStatus.UNAVAILABLE
    assert beliefs.reason_code == "stage_missing"


def test_assemble_forbids_payload_attributes_on_nodes() -> None:
    invocation = build_cognition_trace_invocation(
        run_id=RunId("run-forbid"),
        agent_id=AgentId("alice"),
        tick=0,
        invocation_id="inv-forbid",
        stage_summaries=_full_stage_summaries(command_kind="wait"),
        command_kind="wait",
    )
    trace = assemble_causal_trace(invocation)
    for node in trace.nodes:
        assert not hasattr(node, "rationale")
        assert not hasattr(node, "prompt")
        assert not hasattr(node, "observation_text")
