"""V4-06 three-layer projection and hard leakage checks."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

import pytest

from analysis.formal_rule_contract import FormalRuleAnalysisError
from analysis.formal_rule_evidence import build_formal_rule_windows
from analysis.formal_rule_layers import (
    FormalRuleAnalyticalRow,
    FormalRuleLayerView,
    FormalRuleObjectiveRow,
    FormalRuleSubjectiveRow,
    assert_formal_rule_layer_separation,
    formal_rule_layer_digest,
    project_formal_rule_layers,
)
from analysis.formal_rule_lineage import (
    derive_formal_rule_lineage,
    summarize_formal_rules,
)
from analysis.formal_rules import harvest_formal_rule_rows
from tests.unit.formal_rule_helpers import make_ledger

pytestmark = pytest.mark.unit


def _view() -> Any:
    ledger = make_ledger(ticks=(0,), actors=("agent-1",))
    rows = harvest_formal_rule_rows([ledger], window_ticks=100)
    windows = build_formal_rule_windows(rows, window_ticks=100)
    analysis = derive_formal_rule_lineage(rows, windows)
    summary = summarize_formal_rules(rows, analysis)
    return rows, analysis, summary, project_formal_rule_layers(
        rows, analysis, summary, windows=windows
    )


def test_objective_layer_has_counts_only() -> None:
    _, _, _, view = _view()
    assert view.objective
    assert {field.name for field in fields(FormalRuleObjectiveRow)} == {
        "tick",
        "observed_artifact_count",
        "observed_repository_count",
        "observed_occurrence_count",
    }


def test_subjective_layer_contains_owner_local_ids() -> None:
    _, _, _, view = _view()
    assert view.subjective
    row = view.subjective[0]
    assert row.owner_id == "agent-1"
    assert row.rule_ids
    assert all(rule_id.startswith("frl-") for rule_id in row.rule_ids)
    assert all(system_id.startswith("frs-") for system_id in row.system_ids)


def test_analytical_layer_contains_only_frule_ids() -> None:
    _, _, _, view = _view()
    assert view.analytical
    for row in view.analytical:
        assert row.candidate_id.startswith("frule-")
        assert all(
            candidate.startswith("frule-")
            for candidate in row.competing_candidate_ids
        )


def test_leakage_is_a_hard_failure() -> None:
    _, analysis, summary, view = _view()
    leaked = FormalRuleLayerView(
        objective=view.objective,
        subjective=(
            FormalRuleSubjectiveRow(
                owner_id="agent-1",
                system_ids=(),
                rule_ids=("frule-0123456789abcdef",),
                stage_counts=(),
                status_counts=(),
                response_counts=(),
            ),
        ),
        analytical=view.analytical,
        summary=summary,
        coverage=view.coverage,
    )
    with pytest.raises(FormalRuleAnalysisError) as excinfo:
        assert_formal_rule_layer_separation(leaked)
    assert excinfo.value.code == "formal_rule_layer_leakage"

    with pytest.raises(FormalRuleAnalysisError):
        FormalRuleAnalyticalRow(
            candidate_id="org-0123456789abcdef",
            status=view.analytical[0].status,
            scope_kind="unspecified",
            action_token="maintain",
            constraint_kinds=("obligation",),
            stage="norm",
            rule_count=1,
            version_count=1,
            competing_candidate_ids=(),
        )
    assert analysis.records


def test_layer_digest_is_order_independent() -> None:
    _, _, summary, view = _view()
    reordered = FormalRuleLayerView(
        objective=tuple(reversed(view.objective)),
        subjective=tuple(reversed(view.subjective)),
        analytical=tuple(reversed(view.analytical)),
        summary=summary,
        coverage=view.coverage,
    )
    assert formal_rule_layer_digest(view) == formal_rule_layer_digest(reordered)
