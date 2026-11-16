"""Owner experiment-ledger extension: claim, conditions, source, revisions."""

from __future__ import annotations

import pytest

from agents.cognition.experimentation import (
    MAX_HYPOTHESIS_CONDITIONS,
    MAX_HYPOTHESIS_REVISIONS,
    ExperimentCognitionBinding,
    ExperimentHypothesis,
    ExperimentLedger,
    HypothesisClaim,
    HypothesisCondition,
    HypothesisConditionSlot,
    HypothesisRevision,
    HypothesisRevisionReason,
    HypothesisSourceKind,
    HypothesisStatus,
    admit_hypothesis,
    confidence_milli_from_masses,
    empty_experiment_ledger,
)
from agents.models import AgentId
from analysis.scientific_hypotheses_contract import (
    ScientificHypothesisConditionSlot,
)
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")


def _hypothesis(**overrides: object) -> ExperimentHypothesis:
    payload: dict[str, object] = {
        "owner_id": OWNER,
        "hypothesis_id": "hyp:1",
        "operator": ExperimentOperator.COMBINE,
        "operand_a_id": "item:material",
        "operand_b_id": "resource:material",
        "process_token": ExperimentProcessToken.NONE,
        "predicted_outcome": ExperimentOutcomeClass.SUCCESS.value,
        "created_tick": 0,
    }
    payload.update(overrides)
    return ExperimentHypothesis(**payload)  # type: ignore[arg-type]


def _ledger(max_hypotheses: int = 8) -> ExperimentLedger:
    return empty_experiment_ledger(
        OWNER,
        ExperimentCognitionBinding(
            max_hypotheses=max_hypotheses,
            max_trials_per_tick=1,
            repeat_threshold=2,
            learn_into_genealogy=False,
            allow_provider=False,
        ),
    )


def _claim() -> HypothesisClaim:
    return HypothesisClaim(
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item:material",
        operand_b_id="resource:material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
    )


def test_legacy_construction_keeps_defaults() -> None:
    row = _hypothesis()
    assert row.source_kind is HypothesisSourceKind.SELF_FORMULATED
    assert row.source_token == "self"
    assert row.conditions == ()
    assert row.revisions == ()
    assert row.counter_evidence_event_ids == ()
    assert row.confidence_milli == 500
    assert row.status is HypothesisStatus.PROVISIONAL
    assert row.causal_hypothesis_id == ""


def test_claim_projection_round_trips() -> None:
    row = _hypothesis()
    claim = row.claim
    assert claim.operator is ExperimentOperator.COMBINE
    assert claim.operand_a_id == "item:material"
    assert claim.operand_b_id == "resource:material"
    assert claim.process_token is ExperimentProcessToken.NONE
    assert claim.predicted_outcome is ExperimentOutcomeClass.SUCCESS
    assert claim == _claim()


def test_conditions_reject_duplicates_empty_and_oversize() -> None:
    with pytest.raises(ValueError, match="conditions: duplicate"):
        _hypothesis(
            conditions=(
                HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1"),
                HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-2"),
            )
        )
    with pytest.raises(ValueError, match="condition: invalid_value"):
        HypothesisCondition(HypothesisConditionSlot.WEATHER, "")
    with pytest.raises(ValueError, match="condition: invalid_separator"):
        HypothesisCondition(HypothesisConditionSlot.CONCEPT, "a=b")
    with pytest.raises(ValueError, match="slot: invalid_type"):
        HypothesisCondition("location", "loc-1")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="conditions: invalid_cap"):
        _hypothesis(
            conditions=tuple(
                HypothesisCondition(slot, f"v-{index}")
                for index, slot in enumerate(HypothesisConditionSlot)
            )[: MAX_HYPOTHESIS_CONDITIONS + 1]
        )


def test_condition_slots_match_analysis_contract() -> None:
    assert {value.value for value in HypothesisConditionSlot} == {
        value.value for value in ScientificHypothesisConditionSlot
    }


def test_revisions_require_monotonic_indexes_and_cap() -> None:
    first = HypothesisRevision(
        revision_index=0,
        tick=0,
        reason=HypothesisRevisionReason.FORMULATED,
        claim=_claim(),
    )
    second = HypothesisRevision(
        revision_index=1,
        tick=1,
        reason=HypothesisRevisionReason.PREDICTION_REVISED,
        claim=_claim(),
    )
    row = _hypothesis(revisions=(first, second))
    assert tuple(item.revision_index for item in row.revisions) == (0, 1)

    with pytest.raises(ValueError, match="revisions: out_of_order"):
        _hypothesis(revisions=(second, first))
    with pytest.raises(ValueError, match="revisions: invalid_cap"):
        _hypothesis(
            revisions=tuple(
                HypothesisRevision(
                    revision_index=index,
                    tick=index,
                    reason=HypothesisRevisionReason.FORMULATED,
                    claim=_claim(),
                )
                for index in range(MAX_HYPOTHESIS_REVISIONS + 1)
            )
        )


def test_communicated_source_requires_receiver_token_and_no_evidence() -> None:
    row = _hypothesis(
        source_kind=HypothesisSourceKind.COMMUNICATED,
        source_token="evt:delivery-1",
    )
    assert row.evidence_event_ids == ()
    assert row.counter_evidence_event_ids == ()
    assert row.support == 0
    assert row.counter == 0

    with pytest.raises(ValueError, match="source_token: invalid_source_token"):
        _hypothesis(source_kind=HypothesisSourceKind.COMMUNICATED, source_token="self")
    with pytest.raises(ValueError, match="source_token: invalid_type"):
        _hypothesis(source_kind=HypothesisSourceKind.RECORDED, source_token="")


def test_ledger_rejects_foreign_owner() -> None:
    foreign = _hypothesis(owner_id=AgentId("agent-2"), hypothesis_id="hyp:2")
    with pytest.raises(ValueError, match="hypothesis: owner_mismatch"):
        admit_hypothesis(_ledger(), foreign)


def test_eviction_is_lowest_confidence_then_oldest_then_id() -> None:
    ledger = _ledger(max_hypotheses=2)
    low = _hypothesis(hypothesis_id="hyp:low", support=1, counter=1, created_tick=0)
    high = _hypothesis(
        hypothesis_id="hyp:high", support=5, counter=0, created_tick=1
    )
    ledger = admit_hypothesis(ledger, low)
    ledger = admit_hypothesis(ledger, high)
    assert {row.hypothesis_id for row in ledger.hypotheses} == {"hyp:low", "hyp:high"}

    newest = _hypothesis(
        hypothesis_id="hyp:newest", support=10, counter=0, created_tick=2
    )
    ledger = admit_hypothesis(ledger, newest)
    ids = {row.hypothesis_id for row in ledger.hypotheses}
    assert "hyp:low" not in ids
    assert ids == {"hyp:high", "hyp:newest"}


def test_confidence_is_integer_bounded_support_ratio() -> None:
    assert confidence_milli_from_masses(0, 0) == 500
    assert confidence_milli_from_masses(1, 0) == 666
    assert confidence_milli_from_masses(0, 1) == 333
    assert confidence_milli_from_masses(1000, 0) == 999
    assert confidence_milli_from_masses(0, 1000) == 0
    with pytest.raises(ValueError):
        confidence_milli_from_masses(True, 0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        confidence_milli_from_masses(-1, 0)


def test_no_objective_rule_attribute_is_reachable() -> None:
    row = _hypothesis()
    assert not hasattr(row, "law")
    assert not hasattr(row, "rules")
    assert not hasattr(row, "probability")
    assert not hasattr(_ledger(), "law")
    assert not hasattr(_ledger(), "probability")
