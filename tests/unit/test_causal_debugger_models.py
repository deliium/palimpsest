"""Unit tests for causal debugger address / chain DTOs."""

from __future__ import annotations

import pytest

from agents.cognition.trace import FORBIDDEN_TRACE_ATTRIBUTES, CognitionTraceStageKind
from agents.models import AgentId
from simulation import (
    FORBIDDEN_DEBUGGER_ATTRIBUTES,
    RESEARCHER_CHAIN_SEQUENCE,
    STAGE_KIND_TO_RESEARCHER,
    CausalNodeStatus,
    CausalTrace,
    CausalTraceAvailability,
    CausalTraceNode,
    DebuggerEventAddress,
    DebuggerFocusHandle,
    DebuggerLineageKind,
    ResearcherChainStage,
    RunId,
)
from simulation.causal_debugger import (
    CausalDebuggerError,
    reject_forbidden_debugger_attributes,
)


def test_researcher_chain_order_matches_plan() -> None:
    assert RESEARCHER_CHAIN_SEQUENCE == (
        ResearcherChainStage.OBSERVATION,
        ResearcherChainStage.RELEVANT_MEMORIES,
        ResearcherChainStage.RECONSTRUCTION,
        ResearcherChainStage.BELIEFS,
        ResearcherChainStage.EMOTIONAL_STATE,
        ResearcherChainStage.GOALS,
        ResearcherChainStage.THEORY_OF_MIND,
        ResearcherChainStage.IMAGINED_FUTURES,
        ResearcherChainStage.COUNTERFACTUALS,
        ResearcherChainStage.SELECTED_INTENTION,
        ResearcherChainStage.ACTION,
    )


def test_stage_kind_mapping_covers_scientific_primary_stages() -> None:
    assert (
        STAGE_KIND_TO_RESEARCHER[CognitionTraceStageKind.OBSERVATION]
        is ResearcherChainStage.OBSERVATION
    )
    assert (
        STAGE_KIND_TO_RESEARCHER[CognitionTraceStageKind.RETRIEVED_MEMORIES]
        is ResearcherChainStage.RELEVANT_MEMORIES
    )
    assert (
        STAGE_KIND_TO_RESEARCHER[CognitionTraceStageKind.RECONSTRUCTED_MEMORIES]
        is ResearcherChainStage.RECONSTRUCTION
    )
    assert (
        STAGE_KIND_TO_RESEARCHER[CognitionTraceStageKind.PLANNED_ACTION]
        is ResearcherChainStage.ACTION
    )
    assert CognitionTraceStageKind.SITUATION_MODEL not in STAGE_KIND_TO_RESEARCHER
    assert CognitionTraceStageKind.BUDGET_SUMMARY not in STAGE_KIND_TO_RESEARCHER


def test_forbid_attributes_mirror_and_extend_trace_forbid_list() -> None:
    assert FORBIDDEN_TRACE_ATTRIBUTES <= FORBIDDEN_DEBUGGER_ATTRIBUTES
    assert "rationale" in FORBIDDEN_DEBUGGER_ATTRIBUTES
    assert "chain_of_thought" in FORBIDDEN_DEBUGGER_ATTRIBUTES
    assert "utterance_text" in FORBIDDEN_DEBUGGER_ATTRIBUTES


def test_address_documents_sequence_as_ui_event_n() -> None:
    address = DebuggerEventAddress(
        run_id=RunId("run-1"),
        tick=1832,
        event_id="evt-17",
        sequence=17,
        agent_id=AgentId("alice"),
    )
    assert address.sequence == 17
    assert address.event_id == "evt-17"
    assert "event N" in DebuggerEventAddress.__doc__


def test_focus_handle_and_node_reject_forbidden_fields() -> None:
    handle = DebuggerFocusHandle(
        run_id=RunId("run-1"), tick=1, sequence=0, event_id="e1"
    )
    node = CausalTraceNode(
        stage_code="observation",
        status=CausalNodeStatus.AVAILABLE,
        focus_handles=(handle,),
        counts={"claim_count": 1},
    )
    for name in FORBIDDEN_DEBUGGER_ATTRIBUTES:
        assert not hasattr(node, name)
        assert not hasattr(handle, name)


def test_causal_trace_metadata_only_repr_fields() -> None:
    address = DebuggerEventAddress(run_id=RunId("run-1"), tick=3, sequence=1)
    trace = CausalTrace(
        address=address,
        availability=CausalTraceAvailability.UNAVAILABLE,
        nodes=(
            CausalTraceNode(
                stage_code="observation",
                status=CausalNodeStatus.UNAVAILABLE,
                reason_code="cognition_trace_missing",
            ),
        ),
        reason_code="cognition_trace_missing",
    )
    assert trace.availability is CausalTraceAvailability.UNAVAILABLE
    assert DebuggerLineageKind.BELIEF_EVIDENCE.value == "belief_evidence"


def test_reject_forbidden_raises_on_injected_attribute() -> None:
    class _Bad:
        rationale = "secret"

    with pytest.raises(CausalDebuggerError) as exc:
        reject_forbidden_debugger_attributes(_Bad(), type_name="_Bad")
    assert exc.value.code == "forbidden_attribute"
