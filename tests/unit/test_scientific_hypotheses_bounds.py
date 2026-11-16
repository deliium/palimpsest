# mypy: ignore-errors
"""Independent caps and monotone bounds for scientific-hypothesis data."""

from __future__ import annotations

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    HypothesisCondition,
    HypothesisConditionSlot,
    HypothesisStatus,
    admit_hypothesis,
    apply_test_outcome,
    confidence_milli_from_masses,
    derive_hypothesis_status,
    empty_experiment_ledger,
    formulate_hypothesis,
)
from agents.models import AgentId
from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_policy import policy_with
from analysis.scientific_hypotheses_rows import HypothesisFact
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")


def _fact(index: int) -> HypothesisFact:
    return HypothesisFact(
        owner_token=f"owner-{index}",
        hypothesis_token=f"schyp-{index}",
        claim_token=f"claim-{index}",
        causal_hypothesis_token=NONE_TOKEN,
        status=ScientificHypothesisStatus.PROVISIONAL,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        confidence_milli=500,
        created_tick=index,
        active=True,
        source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
        source_token="self",
        conditions=(),
        revisions=(),
        trials=(),
    )


def test_hypothesis_cap_truncates_independently() -> None:
    facts = tuple(_fact(index) for index in range(5))
    analysis = harvest_scientific_hypotheses_analysis(
        events=(), facts=facts, policy=policy_with(max_hypotheses=2)
    )
    assert len(analysis.hypothesis_rows) == 2
    assert analysis.hypothesis_rows[0].coverage.value == "partial"
    assert "hypotheses" in analysis.notices


def test_confidence_is_bounded_and_monotone() -> None:
    values = [confidence_milli_from_masses(support, 0) for support in range(20)]
    assert all(0 <= value <= 1000 for value in values)
    assert values == sorted(values)


def test_status_is_always_in_the_closed_set() -> None:
    allowed = {item.value for item in HypothesisStatus}
    for support in range(8):
        for counter in range(8):
            assert derive_hypothesis_status(support, counter).value in allowed


def test_revision_indexes_stay_strictly_increasing() -> None:
    ledger = empty_experiment_ledger(
        OWNER,
        ExperimentCognitionBinding(
            max_hypotheses=8,
            max_trials_per_tick=4,
            repeat_threshold=2,
            learn_into_genealogy=False,
            allow_provider=False,
        ),
    )
    row = formulate_hypothesis(
        owner_id=OWNER,
        hypothesis_id="hyp:bounds",
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item-material",
        operand_b_id="resource-material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
    )
    ledger = admit_hypothesis(ledger, row)
    for index in range(20):
        ledger = apply_test_outcome(
            ledger,
            "hyp:bounds",
            outcome_class=ExperimentOutcomeClass.FAILURE,
            event_id=f"evt:{index}",
            tick=index,
            discovery_mode=DiscoveryMode.DELIBERATE,
        )
    indexes = [revision.revision_index for revision in ledger.hypotheses[0].revisions]
    assert indexes == sorted(indexes)
    assert len(indexes) <= 32


def test_condition_count_is_bounded() -> None:
    with pytest.raises(ValueError):
        formulate_hypothesis(
            owner_id=OWNER,
            hypothesis_id="hyp:conditions",
            operator=ExperimentOperator.COMBINE,
            operand_a_id="item-material",
            operand_b_id="resource-material",
            process_token=ExperimentProcessToken.NONE,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS,
            conditions=tuple(
                HypothesisCondition(slot, f"v-{index}")
                for index, slot in enumerate(
                    list(HypothesisConditionSlot) + list(HypothesisConditionSlot)[:1]
                )
            ),
        )


def test_counter_greater_than_support_is_never_supported() -> None:
    assert derive_hypothesis_status(1, 4) is not HypothesisStatus.SUPPORTED
    assert derive_hypothesis_status(0, 3) is HypothesisStatus.CONTRADICTED


def test_trial_rows_never_exceed_the_cap() -> None:
    analysis = harvest_scientific_hypotheses_analysis(
        events=(), facts=tuple(_fact(index) for index in range(4)),
        policy=policy_with(max_trials=1),
    )
    assert len(analysis.trial_rows) <= 1
