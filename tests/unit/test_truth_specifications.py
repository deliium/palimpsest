"""Claim-level truth specifications for metric evaluation."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from analysis.truth import (
    CLAIM_TRUTH_SCHEMA_VERSION,
    ClaimExpectedValue,
    ClaimTruthSpec,
    ClaimValueKind,
    TruthEvaluatorPolicy,
)
from experiments.interventions import StoryTruthSpec, make_false_story_intervention
from world.identifiers import EntityId


def test_claim_truth_spec_boolean_exact() -> None:
    spec = ClaimTruthSpec(
        claim_id="claim-1",
        schema_version=CLAIM_TRUTH_SCHEMA_VERSION,
        expected=ClaimExpectedValue(kind=ClaimValueKind.BOOLEAN, boolean_value=False),
        valid_from_tick=0,
        valid_to_tick=10,
        unit=None,
        tolerance=None,
        evaluator_policy=TruthEvaluatorPolicy.EXACT_MATCH,
        intervention_id="e-1",
        objective_provenance="objective-commit",
        concept_codes=("well", "poison"),
    )
    assert spec.claim_id == "claim-1"
    assert spec.expected.boolean_value is False
    assert "well" in spec.concept_codes
    # Safe repr exposes IDs/counts/kinds only — never truth values.
    rendered = repr(spec)
    assert "boolean_value" not in rendered
    assert "False" not in rendered


def test_claim_truth_numeric_requires_tolerance_policy() -> None:
    with pytest.raises(ValueError):
        ClaimTruthSpec(
            claim_id="claim-n",
            schema_version=CLAIM_TRUTH_SCHEMA_VERSION,
            expected=ClaimExpectedValue(kind=ClaimValueKind.NUMERIC, numeric_value=1.5),
            valid_from_tick=0,
            valid_to_tick=None,
            unit="count",
            tolerance=None,
            evaluator_policy=TruthEvaluatorPolicy.NUMERIC_TOLERANCE,
            intervention_id=None,
            objective_provenance=None,
        )


def test_claim_expected_value_kind_exclusivity() -> None:
    with pytest.raises(ValueError):
        ClaimExpectedValue(
            kind=ClaimValueKind.BOOLEAN,
            boolean_value=True,
            categorical_value="x",
        )


def test_story_truth_spec_exports_claim_truth() -> None:
    truth = StoryTruthSpec(
        intervention_id="e-2",
        is_false=True,
        concept_codes=("gate",),
        valid_from_tick=3,
        valid_to_tick=20,
        objective_provenance="world-fact",
    )
    assert truth.claim_id == "e-2-claim"
    claim = truth.to_claim_truth()
    assert type(claim) is ClaimTruthSpec
    assert claim.claim_id == "e-2-claim"
    assert claim.expected.kind is ClaimValueKind.BOOLEAN
    assert claim.expected.boolean_value is False
    assert claim.intervention_id == "e-2"
    assert claim.valid_from_tick == 3
    assert claim.valid_to_tick == 20
    assert claim.concept_codes == ("gate",)


def test_make_false_story_intervention_claim_fields() -> None:
    intervention = make_false_story_intervention(
        intervention_id="e-3",
        tick=5,
        source_agent_id=AgentId("agent-1"),
        source_entity_id=EntityId("body-1"),
        recipient_entity_id=EntityId("body-2"),
        text="the well is poisoned",
        concepts=("well",),
    )
    assert intervention.truth.is_false is True
    assert intervention.truth.valid_from_tick == 5
    claim = intervention.truth.to_claim_truth()
    assert claim.expected.boolean_value is False
    assert not hasattr(intervention.utterance, "is_false")
