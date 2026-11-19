# mypy: ignore-errors
"""V4-28 detached replication analysis and metric families."""

from __future__ import annotations

import pytest

from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_contract import REPLICATION_POLICY_VERSION
from analysis.replication_metrics import (
    compute_replication_conditions,
    compute_replication_design_lineage,
    compute_replication_relationships,
    compute_replication_results,
    compute_replication_social_interpretation,
    compute_replication_uncertainty,
)
from analysis.replication_rows import (
    ReplicationAttemptFact,
    ReplicationConditionFact,
    ReplicationDesignFact,
    ReplicationExecutionFact,
    ReplicationFacts,
    ReplicationMeasurementFact,
    ReplicationReportFact,
    ReplicationSelectorFact,
)
from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId

pytestmark = pytest.mark.unit

TOKEN = "a" * 32
DESIGN = "rdes-" + TOKEN
SOURCE_TRIAL = "rtrl-" + TOKEN
CHILD_ROOT = "rpr-" + TOKEN


def _design(*, parent: str | None = None) -> ReplicationDesignFact:
    return ReplicationDesignFact(
        design_token=DESIGN,
        source_design_digest="0" * 64,
        origin_token="rorg-" + TOKEN,
        parent_design_token=parent,
        source_hypothesis_token="rhyp-" + TOKEN,
        source_trial_token=SOURCE_TRIAL,
        created_tick=1,
        operator="apply_tool",
        process_token="craft",
        operand_a_selector=ReplicationSelectorFact(
            "item", "tool", "same_kind"
        ),
        operand_b_selector=None,
        predicted_outcome="success",
        conditions=(ReplicationConditionFact("weather", "rain"),),
    )


def _execution(
    root: str, outcome: str, tick: int, token: str
) -> ReplicationExecutionFact:
    return ReplicationExecutionFact(
        execution_token="rpe-" + token * 32,
        result_root_token=root,
        participant_token="rpp-" + TOKEN,
        execution_tick=tick,
        operator="apply_tool",
        process_token="craft",
        operand_a_token="rpen-" + TOKEN,
        operand_b_token=None,
        outcome=outcome,
    )


def _attempt(
    condition: str = "matched",
    *,
    root: str | None = CHILD_ROOT,
) -> ReplicationAttemptFact:
    return ReplicationAttemptFact(
        attempt_token="rpa-" + TOKEN,
        participant_token="rpp-" + TOKEN,
        design_token=DESIGN,
        source_trial_token=SOURCE_TRIAL,
        collaboration_token=None,
        hypothesis_token="rph-" + TOKEN,
        request_tick=3,
        submission_tick=3,
        observation_tick=4,
        operand_a_token="rpen-" + TOKEN,
        operand_b_token=None,
        condition_snapshot=(ReplicationConditionFact("weather", "rain"),),
        condition_comparison=condition,
        state="observed",
        result_root_token=root,
        reason_codes=(),
    )


def test_conflicting_categories_are_preserved_and_qualified() -> None:
    facts = ReplicationFacts(
        designs=(_design(),),
        attempts=(_attempt(),),
        executions=(
            _execution(SOURCE_TRIAL, "success", 2, "b"),
            _execution(CHILD_ROOT, "failure", 4, "c"),
        ),
    )
    analysis = harvest_replication_analysis(facts)
    assert analysis.policy_version == REPLICATION_POLICY_VERSION
    assert len(analysis.comparisons) == 1
    row = analysis.comparisons[0]
    assert row.appraisal == "conflicting"
    assert row.category_difference is True
    assert row.evidence_qualification == "execution_backed"
    assert row.source_outcome == "success"
    assert row.child_outcome == "failure"


def test_changed_and_unknown_conditions_are_excluded_from_exact_comparison() -> None:
    changed = harvest_replication_analysis(
        ReplicationFacts(
            designs=(_design(),),
            attempts=(_attempt("different"),),
            executions=(
                _execution(SOURCE_TRIAL, "success", 2, "b"),
                _execution(CHILD_ROOT, "failure", 4, "c"),
            ),
        )
    )
    assert changed.comparisons[0].appraisal == "not_comparable"
    assert changed.comparisons[0].excluded_reason == "condition_different"
    unknown = harvest_replication_analysis(
        ReplicationFacts(
            designs=(_design(),),
            attempts=(_attempt("unknown"),),
        )
    )
    assert unknown.comparisons[0].appraisal == "inconclusive"
    assert unknown.comparisons[0].excluded_reason == "condition_unknown"


def test_reported_pairs_stay_declared_only() -> None:
    measurement = ReplicationMeasurementFact(
        outcome="success",
        resolution="outcome_class",
        uncertainty_kind="unreported",
        possible_outcomes=(),
        basis="own_observation",
    )
    def report(token: str, root: str) -> ReplicationReportFact:
        return ReplicationReportFact(
            local_report_token="rlrep-" + token * 32,
            origin_report_token="rpr-" + token * 32,
            participant_token="rpp-" + TOKEN,
            performer_claim_token="rpart-" + TOKEN,
            design_token=DESIGN,
            attempt_token="rpa-" + TOKEN,
            source_trial_token=SOURCE_TRIAL,
            result_root_token=root,
            report_tick=2,
            measurement=measurement,
            declared_measurement_basis="own_observation",
            condition_snapshot=(ReplicationConditionFact("weather", "rain"),),
            collaboration_token=None,
            delivery_token=None,
            provenance_kind="own_observation",
            claim_digest="d" * 32,
        )

    analysis = harvest_replication_analysis(
        ReplicationFacts(
            designs=(_design(),),
            attempts=(_attempt(),),
            reports=(report("e", SOURCE_TRIAL), report("f", CHILD_ROOT)),
        )
    )
    assert analysis.comparisons[0].basis == "reported"
    assert analysis.comparisons[0].evidence_qualification == "declared_only"


def test_six_metric_families_append_after_the_unchanged_science_slice() -> None:
    assert METRIC_FAMILY_COUNT == 262
    assert tuple(item.value for item in MetricFamilyId)[244:250] == (
        "scientific_hypothesis_structure",
        "scientific_hypothesis_evidence",
        "scientific_hypothesis_test_activity",
        "scientific_hypothesis_revisions",
        "scientific_hypothesis_provenance",
        "scientific_hypothesis_prediction_outcomes",
    )
    assert tuple(item.value for item in MetricFamilyId)[250:256] == (
        "scientific_replication_design_lineage",
        "scientific_replication_conditions",
        "scientific_replication_results",
        "scientific_replication_uncertainty",
        "scientific_replication_relationships",
        "scientific_replication_social_interpretation",
    )


def test_metric_values_exclude_unknown_comparisons_and_have_closed_keys() -> None:
    analysis = harvest_replication_analysis(
        ReplicationFacts(
            designs=(_design(),),
            attempts=(_attempt(), _attempt("unknown")),
            executions=(
                _execution(SOURCE_TRIAL, "success", 2, "b"),
                _execution(CHILD_ROOT, "failure", 4, "c"),
            ),
        )
    )
    lineage = compute_replication_design_lineage(
        analysis, run_id="run", input_revision="rev"
    )
    conditions = compute_replication_conditions(
        analysis, run_id="run", input_revision="rev"
    )
    results = compute_replication_results(
        analysis, run_id="run", input_revision="rev"
    )
    uncertainty = compute_replication_uncertainty(
        analysis, run_id="run", input_revision="rev"
    )
    relationships = compute_replication_relationships(
        analysis, run_id="run", input_revision="rev"
    )
    social = compute_replication_social_interpretation(
        analysis, run_id="run", input_revision="rev"
    )
    assert lineage.values["design_count"] == 1
    assert conditions.values["unknown_count"] == 1
    assert results.values["paired_count"] == 1
    assert results.values["conflicting_count"] == 1
    assert uncertainty.values["measurement_count"] == 0
    assert relationships.values["attempt_count"] == 2
    assert social.values["interpretation_count"] == 0
    for document in (lineage, conditions, results, uncertainty, relationships, social):
        assert "truth" not in document.values
        assert "scientific_score" not in document.values
