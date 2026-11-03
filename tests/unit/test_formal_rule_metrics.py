"""V4-06 metric documents over formal-rule analysis."""

from __future__ import annotations

from typing import Any

import pytest

from agents.cognition import (
    FormalRuleConstraintKind,
    FormalRuleResponseKind,
    FormalRuleStage,
)
from analysis.formal_rule_contract import FormalRuleCoverage
from analysis.formal_rule_evidence import build_formal_rule_windows
from analysis.formal_rule_layers import FormalRuleLayerView, project_formal_rule_layers
from analysis.formal_rule_lineage import (
    FormalRuleSummary,
    derive_formal_rule_lineage,
    summarize_formal_rules,
)
from analysis.formal_rule_metrics import (
    compute_formal_rule_authority_metric,
    compute_formal_rule_development_metric,
    compute_formal_rule_response_metric,
)
from analysis.formal_rules import harvest_formal_rule_rows
from analysis.models import MetricAvailability
from tests.unit.formal_rule_helpers import make_ledger

pytestmark = pytest.mark.unit

RUN = "run-formal-rule-metric"
REVISION = "revision-1"


def _pipeline(*ledgers: Any, window_ticks: int = 100) -> Any:
    rows = harvest_formal_rule_rows(ledgers, window_ticks=window_ticks)
    windows = build_formal_rule_windows(rows, window_ticks=window_ticks)
    analysis = derive_formal_rule_lineage(rows, windows)
    summary = summarize_formal_rules(rows, analysis)
    view = project_formal_rule_layers(rows, analysis, summary, windows=windows)
    return summary, view


def _empty() -> Any:
    summary = FormalRuleSummary(
        candidates=(),
        development=(),
        authority=(),
        response=(),
        coverage=FormalRuleCoverage(observed=0, expected=0),
        determinism_digest="",
    )
    return summary, FormalRuleLayerView((), (), (), summary, summary.coverage)


def test_absent_when_no_rows() -> None:
    summary, view = _empty()
    for compute, family in (
        (compute_formal_rule_development_metric, "formal_rule_development"),
        (compute_formal_rule_authority_metric, "formal_rule_authority"),
        (compute_formal_rule_response_metric, "formal_rule_response"),
    ):
        document = compute(
            summary, view, run_id=RUN, input_revision=REVISION
        )
        assert document.metric_family == family
        assert document.availability is MetricAvailability.ABSENT
        assert document.values == {}


def test_partial_coverage_is_explicit() -> None:
    summary, view = _pipeline(make_ledger(ticks=(0, 250)))
    assert summary.coverage.partial is True
    document = compute_formal_rule_development_metric(
        summary, view, run_id=RUN, input_revision=REVISION
    )
    assert document.availability is MetricAvailability.PARTIAL
    coverage = document.coverage
    assert coverage is not None
    assert coverage.observed == 2
    assert coverage.expected == 3


def test_development_histograms_and_counts() -> None:
    summary, view = _pipeline(
        make_ledger(ticks=(0,), stage=FormalRuleStage.DOCUMENTED)
    )
    document = compute_formal_rule_development_metric(
        summary, view, run_id=RUN, input_revision=REVISION
    )
    assert document.availability is MetricAvailability.PRESENT
    assert set(document.values) == {
        "candidate_count",
        "active_count",
        "documented_count",
        "recognized_enforcement_count",
        "stage_histogram",
        "constraint_histogram",
        "written_representation_count",
        "mean_version_count",
        "coverage",
    }
    assert document.values["candidate_count"] == 1
    assert document.values["documented_count"] == 1
    assert '"documented":1' in str(document.values["stage_histogram"])


def test_authority_competing_and_contested_counts() -> None:
    summary, view = _pipeline(
        make_ledger(
            owner="agent-1",
            constraint=FormalRuleConstraintKind.PROHIBITION,
        ),
        make_ledger(
            owner="agent-2",
            constraint=FormalRuleConstraintKind.OBLIGATION,
        ),
    )
    document = compute_formal_rule_authority_metric(
        summary, view, run_id=RUN, input_revision=REVISION
    )
    assert set(document.values) == {
        "system_count",
        "proponent_count",
        "recognized_authority_count",
        "authority_histogram",
        "competing_system_count",
        "contested_system_count",
        "coverage",
    }
    assert document.values["competing_system_count"] == 2
    assert document.values["system_count"] == 2


def test_response_counts_and_sanctions() -> None:
    summary, view = _pipeline(
        make_ledger(
            ticks=(0,),
            response_kinds=(
                FormalRuleResponseKind.FOLLOW,
                FormalRuleResponseKind.VIOLATE,
            ),
        )
    )
    document = compute_formal_rule_response_metric(
        summary, view, run_id=RUN, input_revision=REVISION
    )
    assert set(document.values) == {
        "follow_count",
        "violate_count",
        "challenge_count",
        "reinterpret_count",
        "ignore_count",
        "response_histogram",
        "expected_sanction_histogram",
        "exception_count",
        "coverage",
    }
    assert document.values["follow_count"] == 1
    assert document.values["violate_count"] == 1
    assert document.values["challenge_count"] == 0


def test_documents_are_deterministic_under_permutation() -> None:
    first = _pipeline(
        make_ledger(owner="agent-1"),
        make_ledger(owner="agent-2", action="attack"),
    )
    second = _pipeline(
        make_ledger(owner="agent-2", action="attack"),
        make_ledger(owner="agent-1"),
    )
    first_doc = compute_formal_rule_development_metric(
        first[0], first[1], run_id=RUN, input_revision=REVISION
    )
    second_doc = compute_formal_rule_development_metric(
        second[0], second[1], run_id=RUN, input_revision=REVISION
    )
    assert first_doc.values == second_doc.values
    assert first_doc.coverage == second_doc.coverage
