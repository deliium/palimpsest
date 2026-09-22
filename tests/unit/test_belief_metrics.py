"""Belief accuracy and false-belief persistence metric tests."""

from __future__ import annotations

from analysis.belief_metrics import (
    ClaimEvaluationOutcome,
    compute_belief_accuracy,
    compute_false_belief_persistence,
    evaluate_claim_against_truth,
)
from analysis.models import BeliefClaimRow, MetricAvailability
from analysis.serialization import metric_document_fingerprint
from analysis.truth import (
    CLAIM_TRUTH_SCHEMA_VERSION,
    ClaimExpectedValue,
    ClaimTruthSpec,
    ClaimValueKind,
    TruthEvaluatorPolicy,
)


def _spec(
    claim_id: str,
    *,
    kind: ClaimValueKind = ClaimValueKind.BOOLEAN,
    boolean: bool = True,
    categorical: str | None = None,
    numeric: float | None = None,
    policy: TruthEvaluatorPolicy = TruthEvaluatorPolicy.EXACT_MATCH,
    tolerance: float | None = None,
    valid_from: int = 0,
    valid_to: int | None = 100,
) -> ClaimTruthSpec:
    if kind is ClaimValueKind.BOOLEAN:
        expected = ClaimExpectedValue(kind=kind, boolean_value=boolean)
    elif kind is ClaimValueKind.CATEGORICAL:
        expected = ClaimExpectedValue(kind=kind, categorical_value=categorical)
    else:
        expected = ClaimExpectedValue(kind=kind, numeric_value=numeric)
    return ClaimTruthSpec(
        claim_id=claim_id,
        schema_version=CLAIM_TRUTH_SCHEMA_VERSION,
        expected=expected,
        valid_from_tick=valid_from,
        valid_to_tick=valid_to,
        unit=None,
        tolerance=tolerance,
        evaluator_policy=policy,
        intervention_id=None,
        objective_provenance=None,
    )


def test_evaluate_boolean_and_unknown_exclusion() -> None:
    spec = _spec("claim-gate")
    correct = BeliefClaimRow(
        owner_id="a1",
        belief_id="b1",
        claim_id="claim-gate",
        logical_tick=1,
        activation_state="active",
        confidence=0.8,
        value_kind="boolean",
        bool_value=True,
    )
    wrong = BeliefClaimRow(
        owner_id="a1",
        belief_id="b1",
        claim_id="claim-gate",
        logical_tick=2,
        activation_state="active",
        confidence=0.5,
        value_kind="boolean",
        bool_value=False,
    )
    other = BeliefClaimRow(
        owner_id="a1",
        belief_id="b2",
        claim_id="uncovered",
        logical_tick=1,
        activation_state="active",
        confidence=1.0,
        value_kind="boolean",
        bool_value=True,
    )
    assert evaluate_claim_against_truth(correct, spec) is ClaimEvaluationOutcome.CORRECT
    assert evaluate_claim_against_truth(wrong, spec) is ClaimEvaluationOutcome.INCORRECT
    assert (
        evaluate_claim_against_truth(other, spec) is ClaimEvaluationOutcome.UNKNOWN
    )


def test_belief_accuracy_known_answer() -> None:
    specs = (_spec("c1"),)
    claims = (
        BeliefClaimRow(
            owner_id="a",
            belief_id="b",
            claim_id="c1",
            logical_tick=1,
            activation_state="active",
            confidence=1.0,
            value_kind="boolean",
            bool_value=True,
        ),
        BeliefClaimRow(
            owner_id="a",
            belief_id="b",
            claim_id="c1",
            logical_tick=2,
            activation_state="active",
            confidence=0.5,
            value_kind="boolean",
            bool_value=False,
        ),
        BeliefClaimRow(
            owner_id="a",
            belief_id="b2",
            claim_id="other",
            logical_tick=1,
            activation_state="active",
            confidence=1.0,
            value_kind="boolean",
            bool_value=True,
        ),
    )
    doc = compute_belief_accuracy(
        claims, specs, run_id="run-b", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["evaluable_count"] == 2
    assert doc.values["unknown_excluded_count"] == 1
    assert doc.values["accuracy"] == 0.5
    # weighted: (1.0*1 + 0.5*0) / 1.5 = 2/3
    from analysis.numerical import quantize_float

    assert doc.values["confidence_weighted_accuracy"] == quantize_float(2.0 / 3.0)


def test_belief_accuracy_no_truth_absent() -> None:
    doc = compute_belief_accuracy([], [], run_id="run-b", input_revision="rev-1")
    assert doc.availability is MetricAvailability.ABSENT


def test_false_belief_persistence_onset_correction_and_censor() -> None:
    specs = (_spec("c1", boolean=True),)
    claims = (
        BeliefClaimRow(
            owner_id="a",
            belief_id="b",
            claim_id="c1",
            logical_tick=1,
            activation_state="active",
            confidence=0.9,
            value_kind="boolean",
            bool_value=False,
        ),
        BeliefClaimRow(
            owner_id="a",
            belief_id="b",
            claim_id="c1",
            logical_tick=5,
            activation_state="active",
            confidence=0.9,
            value_kind="boolean",
            bool_value=True,
        ),
        BeliefClaimRow(
            owner_id="b",
            belief_id="b2",
            claim_id="c1",
            logical_tick=2,
            activation_state="active",
            confidence=0.4,
            value_kind="boolean",
            bool_value=False,
        ),
    )
    doc = compute_false_belief_persistence(
        claims,
        specs,
        run_id="run-f",
        input_revision="rev-1",
        run_end_tick=10,
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["onset_count"] == 2
    assert doc.values["correction_rate"] == 0.5
    assert doc.values["censored_fraction"] == 0.5


def test_belief_metrics_permutation_invariant() -> None:
    specs = (_spec("c1"), _spec("c2", kind=ClaimValueKind.CATEGORICAL, categorical="red"))
    claims = [
        BeliefClaimRow(
            owner_id="a",
            belief_id="b1",
            claim_id="c1",
            logical_tick=1,
            activation_state="active",
            confidence=0.7,
            value_kind="boolean",
            bool_value=True,
        ),
        BeliefClaimRow(
            owner_id="a",
            belief_id="b2",
            claim_id="c2",
            logical_tick=2,
            activation_state="active",
            confidence=0.3,
            value_kind="categorical",
            categorical_value="red",
        ),
    ]
    first = compute_belief_accuracy(
        claims, specs, run_id="run-p", input_revision="rev-1"
    )
    second = compute_belief_accuracy(
        list(reversed(claims)), specs, run_id="run-p", input_revision="rev-1"
    )
    assert metric_document_fingerprint(first) == metric_document_fingerprint(second)
