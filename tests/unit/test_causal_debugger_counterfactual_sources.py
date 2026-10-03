"""Unit tests for counterfactual / prediction read-source selection."""

from __future__ import annotations

from agents.cognition.trace import (
    CognitionTraceIdRef,
    CognitionTraceRefKind,
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
)
from agents.models import AgentId
from simulation import (
    CounterfactualNodeMaterial,
    CounterfactualSourceKind,
    RunId,
    build_cognition_trace_invocation,
    select_counterfactual_material,
)
from simulation.cognition_trace import CognitionTraceInvocation


def _invocation_with_optional_cf_refs(
    *, with_trace_refs: bool
) -> CognitionTraceInvocation:
    stages = [
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.OBSERVATION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=0,
            confidence=0.5,
        ),
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.IMAGINED_FUTURES,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=1,
            confidence=0.4,
            id_refs=(
                CognitionTraceIdRef(
                    kind=CognitionTraceRefKind.FUTURE, value="future-1"
                ),
            ),
            selection_codes=("cf_regret_branch",) if with_trace_refs else (),
        ),
    ]
    return build_cognition_trace_invocation(
        run_id=RunId("run-cf"),
        agent_id=AgentId("alice"),
        tick=10,
        invocation_id="inv-cf-1",
        stage_summaries=stages,
        command_kind="attack",
    )


def test_trace_refs_preferred_over_result_harvest() -> None:
    invocation = _invocation_with_optional_cf_refs(with_trace_refs=True)
    harvest = CounterfactualNodeMaterial(
        source=CounterfactualSourceKind.RESULT,
        reason_code=None,
        scenario_count=99,
    )
    material = select_counterfactual_material(invocation, harvest=harvest)
    assert material.source is CounterfactualSourceKind.TRACE
    assert material.scenario_count == 1
    assert "cf_regret_branch" in material.selection_codes


def test_result_harvest_used_when_trace_empty() -> None:
    invocation = _invocation_with_optional_cf_refs(with_trace_refs=False)
    harvest = CounterfactualNodeMaterial(
        source=CounterfactualSourceKind.RESULT,
        reason_code=None,
        scenario_count=2,
        regret_count=1,
        relief_count=0,
        neutral_count=1,
    )
    material = select_counterfactual_material(invocation, harvest=harvest)
    assert material.source is CounterfactualSourceKind.RESULT
    assert material.scenario_count == 2


def test_unavailable_when_no_trace_or_harvest() -> None:
    invocation = _invocation_with_optional_cf_refs(with_trace_refs=False)
    material = select_counterfactual_material(invocation, harvest=None)
    assert material.source is CounterfactualSourceKind.NONE
    assert material.reason_code == "counterfactual_unavailable"


def test_incomplete_harvest_yields_unavailable() -> None:
    invocation = _invocation_with_optional_cf_refs(with_trace_refs=False)
    harvest = CounterfactualNodeMaterial(
        source=CounterfactualSourceKind.RESULT,
        reason_code=None,
        scenario_count=None,
        id_refs=(),
    )
    material = select_counterfactual_material(invocation, harvest=harvest)
    assert material.source is CounterfactualSourceKind.NONE
    assert material.reason_code == "counterfactual_result_harvest_incomplete"
