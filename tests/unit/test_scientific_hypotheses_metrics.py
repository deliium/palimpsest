# mypy: ignore-errors
"""Six scientific-hypothesis metric families over the detached analysis."""

from __future__ import annotations

import pytest

from analysis.models import MetricAvailability
from analysis.scientific_hypotheses_analysis import (
    empty_scientific_hypotheses_analysis,
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisRevisionReason,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_metrics import (
    compute_scientific_hypothesis_evidence,
    compute_scientific_hypothesis_prediction_outcomes,
    compute_scientific_hypothesis_provenance,
    compute_scientific_hypothesis_revisions,
    compute_scientific_hypothesis_structure,
    compute_scientific_hypothesis_test_activity,
)
from analysis.scientific_hypotheses_rows import (
    HypothesisFact,
    HypothesisRevisionFact,
    HypothesisTrialFact,
)
from world.experimentation import DiscoveryMode, ExperimentOutcomeClass

pytestmark = pytest.mark.unit

FORBIDDEN_VALUES = {
    "score",
    "accuracy",
    "calibration",
    "truth",
    "verified",
    "proven",
    "law",
    "rule",
}


def _fact(index: int, *, matched: bool = True) -> HypothesisFact:
    trials = tuple(
        HypothesisTrialFact(
            tick=index,
            event_token=f"evt:{index}-{trial}",
            outcome_class=ExperimentOutcomeClass.SUCCESS,
            discovery_mode=DiscoveryMode.DELIBERATE,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
            matched=matched,
        )
        for trial in range(3)
    )
    revisions = (
        HypothesisRevisionFact(
            revision_index=0,
            tick=index,
            reason=ScientificHypothesisRevisionReason.FORMULATED,
            claim_token=f"claim-{index}",
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
            condition_pairs=(),
            confidence_milli=500,
            evidence_ref="",
        ),
        HypothesisRevisionFact(
            revision_index=1,
            tick=index,
            reason=ScientificHypothesisRevisionReason.TEST_FORMULATED,
            claim_token=f"claim-{index}",
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
            condition_pairs=(),
            confidence_milli=500,
            evidence_ref="",
        ),
    )
    return HypothesisFact(
        owner_token=f"owner-{index}",
        hypothesis_token=f"schyp-{index}",
        claim_token=f"claim-{index}",
        causal_hypothesis_token=NONE_TOKEN,
        status=(
            ScientificHypothesisStatus.SUPPORTED
            if matched
            else ScientificHypothesisStatus.CONTRADICTED
        ),
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        confidence_milli=500,
        created_tick=index,
        active=True,
        source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
        source_token="self",
        conditions=(),
        revisions=revisions,
        trials=trials,
    )


def _analysis(*, matched: bool = True):
    return harvest_scientific_hypotheses_analysis(
        events=(), facts=tuple(_fact(index, matched=matched) for index in range(3))
    )


def test_six_documents_with_analysis() -> None:
    analysis = _analysis()
    documents = (
        compute_scientific_hypothesis_structure(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_scientific_hypothesis_evidence(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_scientific_hypothesis_test_activity(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_scientific_hypothesis_revisions(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_scientific_hypothesis_provenance(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
        compute_scientific_hypothesis_prediction_outcomes(
            analysis, run_id="run-1", input_revision="rev-1"
        ),
    )
    families = {document.metric_family for document in documents}
    assert families == {
        "scientific_hypothesis_structure",
        "scientific_hypothesis_evidence",
        "scientific_hypothesis_test_activity",
        "scientific_hypothesis_revisions",
        "scientific_hypothesis_provenance",
        "scientific_hypothesis_prediction_outcomes",
    }
    for document in documents:
        assert document.values
        assert not (set(document.values) & FORBIDDEN_VALUES)


def test_structure_values() -> None:
    document = compute_scientific_hypothesis_structure(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    assert document.values["hypothesis_count"] == 3
    assert document.values["supported_count"] == 3
    assert document.values["active_count"] == 3
    assert document.values["claim_count"] == 3


def test_evidence_values_and_confidence() -> None:
    document = compute_scientific_hypothesis_evidence(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    assert document.values["support_observation_count"] == 9
    assert document.values["contradiction_count"] == 0
    assert document.values["hypotheses_with_support"] == 3
    assert document.values["confidence_mean_milli"] == 500


def test_test_activity_and_revisions() -> None:
    activity = compute_scientific_hypothesis_test_activity(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    assert activity.values["trial_count"] == 9
    assert activity.values["deliberate_trial_count"] == 9
    assert activity.values["accidental_trial_count"] == 0
    assert activity.values["tested_hypothesis_count"] == 3
    revisions = compute_scientific_hypothesis_revisions(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    assert revisions.values["revision_count"] == 6
    assert revisions.values["formulated_revision_count"] == 3
    assert revisions.values["max_revision_depth"] == 2


def test_provenance_values() -> None:
    document = compute_scientific_hypothesis_provenance(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    assert document.values["self_formulated_count"] == 3
    assert document.values["communicated_count"] == 0
    assert document.values["communicated_share_milli"] == 0


def test_prediction_outcomes_count_mismatch_never_success() -> None:
    document = compute_scientific_hypothesis_prediction_outcomes(
        _analysis(matched=False), run_id="run-1", input_revision="rev-1"
    )
    assert document.values["mismatched_count"] == 9
    assert document.values["matched_count"] == 0
    assert document.values["matched_share_milli"] == 0


def test_absent_analysis_is_unavailable() -> None:
    analysis = empty_scientific_hypotheses_analysis()
    for compute in (
        compute_scientific_hypothesis_structure,
        compute_scientific_hypothesis_evidence,
        compute_scientific_hypothesis_test_activity,
        compute_scientific_hypothesis_revisions,
        compute_scientific_hypothesis_provenance,
        compute_scientific_hypothesis_prediction_outcomes,
    ):
        document = compute(analysis, run_id="run-1", input_revision="rev-1")
        assert document.availability is MetricAvailability.UNKNOWN
        assert document.values == {}


def test_insufficient_samples_is_explicit() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(), facts=(_fact(0),)
    )
    document = compute_scientific_hypothesis_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability is MetricAvailability.PARTIAL
