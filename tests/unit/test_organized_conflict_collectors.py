# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from types import SimpleNamespace

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.organized_conflict_events import ConflictEventRow
from analysis.organized_conflict_rows import OrganizedConflictHarvestRows

FAMILIES = {
    "organized_conflict_participation",
    "organized_conflict_persistence",
    "organized_conflict_outcomes",
    "organized_conflict_interpretation",
}


def test_completed_run_assembly_emits_all_four_families() -> None:
    objective = (
        ConflictEventRow(
            tick=1,
            sequence=0,
            event_class="attack",
            actor_token="a" * 16,
            other_token="b" * 16,
            success=True,
            magnitude=10,
        ),
    )
    interpretation = SimpleNamespace(
        kind="individual_violence",
        tick=1,
        interpretation_id="oci-" + "a" * 16,
        owner_token="c" * 16,
    )
    rows = OrganizedConflictHarvestRows(
        objective_events=objective,
        objective_windows=(objective,),
        owner_interpretations=(interpretation,),
        owner_tokens=("c" * 16,),
    )
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-conflict-assembly",
            input_revision="rev-1",
            window_end=10,
            organized_conflict_rows=rows,
            organized_conflict_objective_rows=objective,
        )
    )
    emitted = {document.metric_family for document in bundle.documents}
    assert FAMILIES <= emitted
