# mypy: ignore-errors
"""Property-level invariants for scientific-hypothesis analysis windows and caps."""

from __future__ import annotations

import random

import pytest

from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
    scientific_hypotheses_analysis_digest,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_policy import (
    default_policy,
    policy_with,
    window_bounds,
    window_index,
)
from analysis.scientific_hypotheses_rows import (
    HypothesisFact,
    HypothesisTrialFact,
)
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
)

pytestmark = pytest.mark.unit


def _fact(index: int) -> HypothesisFact:
    return HypothesisFact(
        owner_token=f"owner-{index % 3}",
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


def test_shuffled_facts_produce_the_same_digest() -> None:
    facts = [_fact(index) for index in range(8)]
    baseline = harvest_scientific_hypotheses_analysis(events=(), facts=tuple(facts))
    digest = scientific_hypotheses_analysis_digest(baseline)
    for seed in range(3):
        shuffled = list(facts)
        random.Random(seed).shuffle(shuffled)
        candidate = harvest_scientific_hypotheses_analysis(
            events=(), facts=tuple(shuffled)
        )
        assert scientific_hypotheses_analysis_digest(candidate) == digest


def test_caps_are_monotone() -> None:
    facts = tuple(_fact(index) for index in range(6))
    for limit in range(1, 7):
        analysis = harvest_scientific_hypotheses_analysis(
            events=(), facts=facts, policy=policy_with(max_hypotheses=limit)
        )
        assert len(analysis.hypothesis_rows) == min(limit, len(facts))


def test_window_bounds_are_exact() -> None:
    policy = default_policy()
    assert window_index(0, policy) == 0
    assert window_index(31, policy) == 0
    assert window_index(32, policy) == 1
    assert window_bounds(63, policy) == (32, 64)
    assert window_bounds(64, policy) == (64, 96)


def test_trial_cap_truncates_analytical_rows() -> None:
    trials = tuple(
        HypothesisTrialFact(
            tick=index,
            event_token=f"evt:{index}",
            outcome_class=ExperimentOutcomeClass.SUCCESS,
            discovery_mode=DiscoveryMode.DELIBERATE,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
            matched=True,
        )
        for index in range(5)
    )
    fact = HypothesisFact(
        owner_token="owner-1",
        hypothesis_token="schyp-1",
        claim_token="claim-1",
        causal_hypothesis_token=NONE_TOKEN,
        status=ScientificHypothesisStatus.PROVISIONAL,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        confidence_milli=500,
        created_tick=0,
        active=True,
        source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
        source_token="self",
        conditions=(),
        revisions=(),
        trials=trials,
    )
    second = HypothesisFact(
        owner_token="owner-2",
        hypothesis_token="schyp-2",
        claim_token="claim-2",
        causal_hypothesis_token=NONE_TOKEN,
        status=ScientificHypothesisStatus.PROVISIONAL,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        confidence_milli=500,
        created_tick=0,
        active=True,
        source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
        source_token="self",
        conditions=(),
        revisions=(),
        trials=trials,
    )
    analysis = harvest_scientific_hypotheses_analysis(
        events=(), facts=(fact, second), policy=policy_with(max_trials=1)
    )
    assert len(analysis.trial_rows) == 1
    assert "trials" in analysis.notices


def test_operator_enum_is_closed() -> None:
    assert {
        item.value for item in ExperimentOperator
    } == {"combine", "apply_tool", "vary_process"}
