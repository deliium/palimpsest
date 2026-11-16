# mypy: ignore-errors
"""No objective-rule, owner, truth, or score leakage across every layer."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    HypothesisCondition,
    HypothesisConditionSlot,
    admit_hypothesis,
    empty_experiment_ledger,
    formulate_hypothesis,
)
from agents.models import AgentId
from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_rows import HypothesisFact
from experiments.scientific_hypotheses_completed_run import (
    scientific_hypothesis_facts,
)
from experiments.scientific_hypotheses_publication import (
    compose_scientific_hypotheses_snapshot,
)
from simulation.scientific_hypotheses_codec import (
    encode_scientific_hypotheses_snapshot,
)
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

pytestmark = pytest.mark.unit

FORBIDDEN = (
    "law",
    "laws",
    "rule",
    "rules",
    "delta",
    "product_id",
    "harm_band",
    "health_delta",
    "truth",
    "verified",
    "proven",
    "accuracy",
    "calibration",
    "score",
    "owner_id",
)


def _analysis():
    fact = HypothesisFact(
        owner_token="owner-abcdef",
        hypothesis_token="schyp-1",
        claim_token="claim-1",
        causal_hypothesis_token="none",
        status=ScientificHypothesisStatus.PROVISIONAL,
        predicted_outcome="success",
        confidence_milli=500,
        created_tick=0,
        active=True,
        source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
        source_token="self",
        conditions=(),
        revisions=(),
        trials=(),
    )
    return harvest_scientific_hypotheses_analysis(events=(), facts=(fact,))


def test_rows_snapshot_and_bytes_contain_no_forbidden_key() -> None:
    analysis = _analysis()
    snapshot = compose_scientific_hypotheses_snapshot(analysis, run_id="run-1")
    rendered = (str(dataclasses.asdict(analysis)) + str(dataclasses.asdict(snapshot))).lower()  # noqa: E501
    payload_bytes = encode_scientific_hypotheses_snapshot(snapshot)
    payload = payload_bytes.decode("utf-8").lower()
    for token in FORBIDDEN:
        assert token not in rendered
        assert token not in payload
    assert b"owner-abcdef" not in payload_bytes


def test_counterpart_values_are_tokenized() -> None:
    ledger = empty_experiment_ledger(
        AgentId("agent-1"),
        ExperimentCognitionBinding(
            max_hypotheses=8,
            max_trials_per_tick=1,
            repeat_threshold=2,
            learn_into_genealogy=False,
            allow_provider=False,
        ),
    )
    row = formulate_hypothesis(
        owner_id=AgentId("agent-1"),
        hypothesis_id="hyp:counterpart",
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item-material",
        operand_b_id="resource-material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(
            HypothesisCondition(HypothesisConditionSlot.COUNTERPART, "agent-2"),
        ),
    )
    ledger = admit_hypothesis(ledger, row)
    from types import SimpleNamespace

    facts = scientific_hypothesis_facts(
        SimpleNamespace(experiment_ledgers=(ledger,), runner_config=None)
    )
    dumped = str(dataclasses.asdict(facts[0]))
    assert "agent-2" not in dumped
    assert facts[0].conditions[0].value_token.startswith("owner-")


def test_communicated_hypothesis_has_no_evidence() -> None:
    from agents.cognition.experimentation import (
        ExperimentCognitionBinding as Binding,
    )
    from agents.cognition.scientific_hypothesis_communication import (
        adopt_communicated_hypothesis,
        encode_scientific_hypothesis_claim,
        parse_scientific_hypothesis_claim_relation,
    )

    ledger = empty_experiment_ledger(AgentId("agent-1"), Binding(
        max_hypotheses=8,
        max_trials_per_tick=1,
        repeat_threshold=2,
        learn_into_genealogy=False,
        allow_provider=False,
    ))
    source = formulate_hypothesis(
        owner_id=AgentId("agent-2"),
        hypothesis_id="hyp:source",
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item-material",
        operand_b_id="resource-material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
    )
    claim = parse_scientific_hypothesis_claim_relation(
        encode_scientific_hypothesis_claim(source)
    )
    adopted = adopt_communicated_hypothesis(
        ledger, claim, source_token="evt:delivery-1", tick=2
    )
    row = adopted.hypotheses[0]
    assert row.support == 0
    assert row.counter == 0
    assert row.evidence_event_ids == ()
    assert row.counter_evidence_event_ids == ()
