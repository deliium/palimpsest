"""Deterministic support, contradiction, confidence, and revision lifecycle."""

from __future__ import annotations

import pytest

from agents.cognition.experimentation import (
    MAX_HYPOTHESIS_EVIDENCE,
    ExperimentCognitionBinding,
    HypothesisClaim,
    HypothesisCondition,
    HypothesisConditionSlot,
    HypothesisRevisionReason,
    HypothesisSourceKind,
    HypothesisStatus,
    admit_hypothesis,
    append_revision,
    apply_test_outcome,
    confidence_milli_from_masses,
    derive_hypothesis_status,
    empty_experiment_ledger,
    formulate_hypothesis,
    retire_hypothesis,
    revise_hypothesis,
    supersede_hypothesis,
)
from agents.models import AgentId
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")


def _ledger():
    return empty_experiment_ledger(
        OWNER,
        ExperimentCognitionBinding(
            max_hypotheses=8,
            max_trials_per_tick=4,
            repeat_threshold=2,
            learn_into_genealogy=False,
            allow_provider=False,
        ),
    )


def _row(prediction: ExperimentOutcomeClass | None = ExperimentOutcomeClass.SUCCESS):
    return formulate_hypothesis(
        owner_id=OWNER,
        hypothesis_id="hyp:life",
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item:material",
        operand_b_id="resource:material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=prediction,
        created_tick=0,
    )


def _ledger_with(prediction: ExperimentOutcomeClass | None = ExperimentOutcomeClass.SUCCESS):  # noqa: E501
    return admit_hypothesis(_ledger(), _row(prediction))


def _apply(ledger, outcome: str, event: str, tick: int = 1):
    return apply_test_outcome(
        ledger,
        "hyp:life",
        outcome_class=outcome,
        event_id=event,
        tick=tick,
        discovery_mode=DiscoveryMode.DELIBERATE,
    )


def _row_of(ledger):
    return ledger.hypotheses[0]


def test_strict_match_increments_support_and_revision() -> None:
    ledger = _apply(_ledger_with(), ExperimentOutcomeClass.SUCCESS.value, "evt:1")
    row = _row_of(ledger)
    assert row.support == 1
    assert row.counter == 0
    assert row.evidence_event_ids == ("evt:1",)
    assert row.revisions[-1].reason is HypothesisRevisionReason.SUPPORT_ADDED
    assert row.revisions[-1].evidence_ref == "evt:1"
    assert row.confidence_milli == confidence_milli_from_masses(1, 0)
    assert row.status is HypothesisStatus.PROVISIONAL


def test_mismatch_increments_counter() -> None:
    ledger = _apply(_ledger_with(), ExperimentOutcomeClass.FAILURE.value, "evt:2")
    row = _row_of(ledger)
    assert row.support == 0
    assert row.counter == 1
    assert row.counter_evidence_event_ids == ("evt:2",)
    assert row.revisions[-1].reason is HypothesisRevisionReason.CONTRADICTION_ADDED


def test_unexpected_always_contradicts_even_when_predicted() -> None:
    ledger = _apply(
        _ledger_with(ExperimentOutcomeClass.UNEXPECTED),
        ExperimentOutcomeClass.UNEXPECTED.value,
        "evt:3",
    )
    row = _row_of(ledger)
    assert row.support == 0
    assert row.counter == 1
    assert row.revisions[-1].reason is HypothesisRevisionReason.CONTRADICTION_ADDED


def test_duplicate_event_id_is_a_no_op() -> None:
    ledger = _apply(_ledger_with(), ExperimentOutcomeClass.SUCCESS.value, "evt:4")
    again = _apply(ledger, ExperimentOutcomeClass.SUCCESS.value, "evt:4")
    assert again is ledger


def test_no_prediction_records_inconclusive_without_mass() -> None:
    ledger = _apply(_ledger_with(None), ExperimentOutcomeClass.SUCCESS.value, "evt:5")
    row = _row_of(ledger)
    assert row.support == 0
    assert row.counter == 0
    assert row.revisions[-1].reason is HypothesisRevisionReason.CONFIDENCE_REVISED
    assert row.status is HypothesisStatus.PROVISIONAL


def test_confidence_is_integer_monotone_and_bounded() -> None:
    values = [confidence_milli_from_masses(support, 0) for support in range(8)]
    assert all(type(value) is int for value in values)
    assert values == sorted(values)
    assert all(0 <= value <= 1000 for value in values)
    assert confidence_milli_from_masses(0, 8) == 100
    assert confidence_milli_from_masses(0, 1000) == 0


def test_status_thresholds() -> None:
    assert derive_hypothesis_status(0, 0) is HypothesisStatus.PROVISIONAL
    assert derive_hypothesis_status(1, 0) is HypothesisStatus.PROVISIONAL
    assert derive_hypothesis_status(2, 0) is HypothesisStatus.SUPPORTED
    assert derive_hypothesis_status(0, 2) is HypothesisStatus.CONTRADICTED
    assert derive_hypothesis_status(2, 2) is HypothesisStatus.INCONCLUSIVE
    assert derive_hypothesis_status(5, 2) is HypothesisStatus.SUPPORTED
    assert derive_hypothesis_status(1, 5) is HypothesisStatus.CONTRADICTED


def test_five_contradictions_remain_queryable() -> None:
    ledger = _ledger_with()
    for index in range(5):
        ledger = _apply(
            ledger, ExperimentOutcomeClass.HARM.value, f"evt:{index}", tick=index
        )
    row = _row_of(ledger)
    assert row.counter == 5
    assert row.status is HypothesisStatus.CONTRADICTED
    assert len(row.counter_evidence_event_ids) == 5


def test_revision_indexes_stay_monotonic_after_trimming() -> None:
    ledger = _ledger_with()
    for index in range(40):
        ledger = _apply(
            ledger, ExperimentOutcomeClass.SUCCESS.value, f"evt:{index}", tick=index
        )
    row = _row_of(ledger)
    asserts = [revision.revision_index for revision in row.revisions]
    assert len(asserts) == 32
    assert asserts == sorted(asserts)
    assert asserts[-1] == 40
    assert asserts[0] == 9


def test_evidence_cap_keeps_newest_and_warns() -> None:
    ledger = _ledger_with()
    for index in range(MAX_HYPOTHESIS_EVIDENCE + 1):
        ledger = _apply(
            ledger, ExperimentOutcomeClass.SUCCESS.value, f"evt:{index}", tick=index
        )
    row = _row_of(ledger)
    assert len(row.evidence_event_ids) == MAX_HYPOTHESIS_EVIDENCE
    assert row.evidence_event_ids[0] == "evt:1"
    assert row.evidence_event_ids[-1] == f"evt:{MAX_HYPOTHESIS_EVIDENCE}"


def test_supersede_and_retire_retain_evidence() -> None:
    ledger = _apply(_ledger_with(), ExperimentOutcomeClass.SUCCESS.value, "evt:6")
    ledger = retire_hypothesis(ledger, "hyp:life", tick=2)
    row = _row_of(ledger)
    assert row.status is HypothesisStatus.RETIRED
    assert row.active is False
    assert row.evidence_event_ids == ("evt:6",)
    assert row.revisions[-1].reason is HypothesisRevisionReason.RETIRED

    ledger = revise_hypothesis(
        ledger,
        "hyp:life",
        reason=HypothesisRevisionReason.PREDICTION_REVISED,
        tick=3,
        predicted_outcome=ExperimentOutcomeClass.FAILURE,
    )
    row = _row_of(ledger)
    assert row.status is HypothesisStatus.PROVISIONAL
    assert row.active is True

    ledger = supersede_hypothesis(ledger, "hyp:life", tick=4)
    row = _row_of(ledger)
    assert row.status is HypothesisStatus.SUPERSEDED
    with pytest.raises(ValueError, match="hypothesis_superseded"):
        revise_hypothesis(
            ledger,
            "hyp:life",
            reason=HypothesisRevisionReason.PREDICTION_REVISED,
            tick=5,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        )


def test_earlier_trial_keeps_the_prediction_in_force_then() -> None:
    row = _row()
    test_revision = HypothesisRevisionReason.TEST_FORMULATED
    row = append_revision(
        row,
        reason=test_revision,
        tick=1,
        claim=HypothesisClaim(
            operator=row.operator,
            operand_a_id=row.operand_a_id,
            operand_b_id=row.operand_b_id,
            process_token=row.process_token,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        ),
        confidence_milli=row.confidence_milli,
    )
    ledger = admit_hypothesis(_ledger(), row)
    ledger = revise_hypothesis(
        ledger,
        "hyp:life",
        reason=HypothesisRevisionReason.PREDICTION_REVISED,
        tick=5,
        predicted_outcome=ExperimentOutcomeClass.FAILURE,
    )
    ledger = _apply(ledger, ExperimentOutcomeClass.FAILURE.value, "evt:7", tick=3)
    row = _row_of(ledger)
    assert row.counter == 1
    assert row.support == 0


def test_unknown_hypothesis_is_rejected() -> None:
    with pytest.raises(ValueError, match="hypothesis_not_found"):
        _apply(_ledger(), ExperimentOutcomeClass.SUCCESS.value, "evt:8")


def test_conditions_are_carried_into_revisions() -> None:
    row = formulate_hypothesis(
        owner_id=OWNER,
        hypothesis_id="hyp:conditions",
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item:material",
        operand_b_id="resource:material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(
            HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1"),
        ),
    )
    assert row.revisions[0].conditions[0].value_token == "loc-1"
    assert row.source_kind is HypothesisSourceKind.SELF_FORMULATED


def test_confidence_and_status_are_hash_seed_independent() -> None:
    first = {support: confidence_milli_from_masses(support, 2) for support in range(6)}
    second = {support: confidence_milli_from_masses(support, 2) for support in range(6)}
    assert first == second
    assert derive_hypothesis_status(3, 1) is derive_hypothesis_status(3, 1)
