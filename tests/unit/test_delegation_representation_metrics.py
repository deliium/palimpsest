"""V4-09 representation metric family math and emission."""

from __future__ import annotations

from typing import Any

import pytest

from agents.cognition import (
    RepresentationDurationKind,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    default_representation_policy,
)
from agents.cognition.delegation_representation import apply_representation_update
from agents.cognition.delegation_representation_communication import (
    RepresentationAct,
    RepresentationFrame,
)
from analysis.delegation_representation_alignment import summarize_representation
from analysis.delegation_representation_identity import derive_representation_lineage
from analysis.delegation_representation_layers import project_representation_layers
from analysis.delegation_representation_metrics import (
    compute_representation_mandate_structure,
    compute_representation_recognition_support,
    compute_representation_scope_alignment,
)
from analysis.delegation_representation_objective import build_representation_windows
from analysis.delegation_representation_rows import harvest_representation_rows
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents

pytestmark = pytest.mark.unit

_OWNER = "agent-owner"
_PRINCIPAL = "agent-principal"
_REP = "agent-representative"


def _frame(
    act: RepresentationAct = RepresentationAct.CLAIM, **overrides: object
) -> RepresentationFrame:
    values: dict[str, object] = {
        "act": act,
        "mandate_ref": None,
        "principal_kind": RepresentationPrincipalKind.AGENT,
        "principal_ref": _PRINCIPAL,
        "representative_ref": _REP,
        "scope_kind": RepresentationScopeKind.SPEAK_FOR,
        "scope_subject": "border",
        "duration_kind": RepresentationDurationKind.UNTIL_REVOKED,
        "provenance": RepresentationProvenance.SELF_DECLARED,
        "actor_ref": _REP,
    }
    values.update(overrides)
    return RepresentationFrame(**values)  # type: ignore[arg-type]


def _pipeline() -> tuple[Any, Any, Any, Any]:
    ledger = apply_representation_update(
        owner_id=_OWNER,
        tick=1,
        observation=None,
        prior=None,
        frames=(_frame(),),
        policy=default_representation_policy(),
    )
    mandate_id = ledger.mandates[0].mandate_id
    ledger = apply_representation_update(
        owner_id=_OWNER,
        tick=2,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                RepresentationAct.SUPPORT,
                mandate_ref=mandate_id,
                actor_ref="agent-c",
            ),
        ),
        policy=default_representation_policy(),
    )
    ledger = apply_representation_update(
        owner_id=_OWNER,
        tick=3,
        observation=None,
        prior=ledger,
        frames=(
            _frame(
                RepresentationAct.SUPPORT,
                mandate_ref=mandate_id,
                actor_ref="agent-d",
            ),
        ),
        policy=default_representation_policy(),
    )
    rows = harvest_representation_rows([ledger], entity_to_agent={})
    analysis = derive_representation_lineage(rows)
    windows = build_representation_windows(rows)
    summary = summarize_representation(rows, analysis, windows=windows)
    layers = project_representation_layers(rows, analysis, summary, windows=windows)
    return rows, analysis, summary, layers


def test_three_documents_have_expected_values() -> None:
    rows, analysis, summary, layers = _pipeline()
    documents = [
        compute_representation_mandate_structure(
            rows, analysis, summary, layers, run_id="run-1", input_revision="rev-1"
        ),
        compute_representation_recognition_support(
            rows, analysis, summary, layers, run_id="run-1", input_revision="rev-1"
        ),
        compute_representation_scope_alignment(
            rows, analysis, summary, layers, run_id="run-1", input_revision="rev-1"
        ),
    ]
    assert [document.metric_family for document in documents] == [
        "representation_mandate_structure",
        "representation_recognition_support",
        "representation_scope_alignment",
    ]
    structure, recognition, alignment = documents
    assert structure.values["mandate_count"] == 1
    assert structure.values["status_histogram"] == '{"recognized":1}'
    assert recognition.values["recognized_count"] == 1
    assert recognition.values["support_root_total"] == 2
    assert alignment.values["not_applicable_count"] == 0


def test_absent_rows_emit_no_values() -> None:
    documents = [
        compute_representation_mandate_structure(
            None, None, None, None, run_id="run-1", input_revision="rev-1"
        ),
        compute_representation_recognition_support(
            None, None, None, None, run_id="run-1", input_revision="rev-1"
        ),
        compute_representation_scope_alignment(
            None, None, None, None, run_id="run-1", input_revision="rev-1"
        ),
    ]
    assert all(document.values == {} for document in documents)
    assert {document.availability.value for document in documents} == {"absent"}


def test_metric_service_emits_three_documents_for_representation_rows() -> None:
    rows, _, _, _ = _pipeline()
    inputs = MetricComputationInputs(
        run_id="run-representation-metrics",
        input_revision="revision-1",
        window_end=10,
        representation_rows=rows,
        representation_objective_rows=(),
    )
    bundle = assemble_metric_documents(inputs)
    families = {
        document.metric_family
        for document in bundle.documents
        if document.metric_family.startswith("representation_")
    }
    assert families == {
        "representation_mandate_structure",
        "representation_recognition_support",
        "representation_scope_alignment",
    }


def test_metric_service_emits_nothing_without_rows() -> None:
    inputs = MetricComputationInputs(
        run_id="run-representation-empty",
        input_revision="revision-1",
        window_end=10,
    )
    bundle = assemble_metric_documents(inputs)
    assert not any(
        document.metric_family.startswith("representation_")
        for document in bundle.documents
    )
