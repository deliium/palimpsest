# mypy: ignore-errors
"""Closed scientific-hypothesis analysis vocabulary and token determinism."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pytest

from analysis.scientific_hypotheses_contract import (
    CLAIM_TOKEN_PREFIX,
    EVIDENCE_TOKEN_PREFIX,
    HYPOTHESIS_TOKEN_PREFIX,
    NONE_TOKEN,
    OWNER_TOKEN_PREFIX,
    SCIENTIFIC_HYPOTHESES_ERROR_CODES,
    SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS,
    SCIENTIFIC_HYPOTHESES_POLICY_VERSION,
    TOKEN_HEX_LEN,
    ScientificHypothesesError,
    ScientificHypothesisAvailability,
    ScientificHypothesisConditionSlot,
    ScientificHypothesisCoverage,
    ScientificHypothesisLayer,
    ScientificHypothesisRevisionReason,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
    assert_scientific_hypothesis_layer_separation,
    mint_claim_token,
    mint_hypothesis_token,
    mint_owner_token,
)
from analysis.scientific_hypotheses_rows import (
    HypothesisConditionFact,
    HypothesisFact,
    ScientificCoverageRow,
    ScientificObjectiveEvidenceRow,
    ScientificOutcomeRow,
)
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
)

pytestmark = pytest.mark.unit


@dataclass(frozen=True, slots=True)
class _RowWithTruth:
    truth: str = "yes"


def test_policy_token_and_prefixes() -> None:
    assert SCIENTIFIC_HYPOTHESES_POLICY_VERSION == "scientific-hypotheses.v1"
    assert HYPOTHESIS_TOKEN_PREFIX == "schyp-"
    assert OWNER_TOKEN_PREFIX == "owner-"
    assert CLAIM_TOKEN_PREFIX == "claim-"
    assert EVIDENCE_TOKEN_PREFIX == "evt:"
    assert NONE_TOKEN == "none"
    assert TOKEN_HEX_LEN == 16


def test_every_closed_enum_value() -> None:
    assert {value.value for value in ScientificHypothesisStatus} == {
        "provisional",
        "supported",
        "contradicted",
        "inconclusive",
        "superseded",
        "retired",
    }
    assert {value.value for value in ScientificHypothesisSourceKind} == {
        "self_formulated",
        "observed",
        "remembered",
        "communicated",
        "recorded",
        "unknown",
    }
    assert {value.value for value in ScientificHypothesisRevisionReason} == {
        "formulated",
        "prediction_revised",
        "condition_revised",
        "support_added",
        "contradiction_added",
        "confidence_revised",
        "source_adopted",
        "test_formulated",
        "superseded",
        "retired",
    }
    assert {value.value for value in ScientificHypothesisConditionSlot} == {
        "location",
        "day_phase",
        "weather",
        "held_item_kind",
        "counterpart",
        "season",
        "temperature_band",
        "hazard",
        "action",
        "concept",
    }
    assert {value.value for value in ScientificHypothesisLayer} == {
        "objective_evidence",
        "owner_hypothesis",
        "analytical_summary",
    }
    assert {value.value for value in ScientificHypothesisCoverage} == {
        "complete",
        "partial",
        "missing",
    }
    assert {value.value for value in ScientificHypothesisAvailability} == {
        "available",
        "insufficient_samples",
        "unavailable",
    }


def test_forbidden_keys_cover_rules_truth_and_scoring() -> None:
    for key in (
        "law",
        "laws",
        "rule",
        "rules",
        "objective_rule",
        "probability",
        "delta",
        "product_id",
        "harm_band",
        "truth",
        "verified",
        "proven",
        "proof",
        "score",
        "accuracy",
        "calibration",
    ):
        assert key in SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS
    assert "scientific_hypotheses_forbidden_key" in SCIENTIFIC_HYPOTHESES_ERROR_CODES


def test_token_minting_is_content_addressed_and_stable() -> None:
    owner = mint_owner_token("agent-1")
    assert owner.startswith(OWNER_TOKEN_PREFIX)
    assert owner == mint_owner_token("agent-1")
    assert owner != mint_owner_token("agent-2")

    claim = mint_claim_token(
        ExperimentOperator.COMBINE,
        "item:material",
        "resource:material",
        "none",
        ExperimentOutcomeClass.SUCCESS,
    )
    assert claim.startswith(CLAIM_TOKEN_PREFIX)
    assert claim == mint_claim_token(
        "combine", "item:material", "resource:material", "none", "success"
    )

    hypothesis = mint_hypothesis_token(owner, claim, 7)
    assert hypothesis.startswith(HYPOTHESIS_TOKEN_PREFIX)
    assert hypothesis == mint_hypothesis_token(owner, claim, 7)
    assert hypothesis != mint_hypothesis_token(owner, claim, 8)

    digest = hashlib.sha256(
        "\x1f".join(("agent-1",)).encode("utf-8")
    ).hexdigest()[:TOKEN_HEX_LEN]
    assert owner == f"{OWNER_TOKEN_PREFIX}{digest}"


def test_token_minting_rejects_unstable_parts() -> None:
    with pytest.raises(ScientificHypothesesError) as excinfo:
        mint_owner_token("")
    assert excinfo.value.reason_code == "scientific_hypotheses_unstable_token"
    with pytest.raises(ScientificHypothesesError):
        mint_hypothesis_token("owner-x", "claim-x", -1)


def test_rows_reject_forbidden_keys_and_invalid_scalars() -> None:
    with pytest.raises(ScientificHypothesesError):
        assert_scientific_hypothesis_layer_separation((_RowWithTruth(),))

    with pytest.raises(ScientificHypothesesError):
        HypothesisConditionFact(
            slot=ScientificHypothesisConditionSlot.LOCATION, value_token=""
        )

    with pytest.raises(ScientificHypothesesError):
        ScientificObjectiveEvidenceRow(
            window_index=True,
            window_tick=0,
            sequence=0,
            event_token="evt:1",
            operator=ExperimentOperator.COMBINE,
            outcome_class=ExperimentOutcomeClass.SUCCESS,
            discovery_mode=DiscoveryMode.DELIBERATE,
            coverage=ScientificHypothesisCoverage.COMPLETE,
        )


def test_facts_expose_every_requested_representation() -> None:
    names = set(HypothesisFact.__dataclass_fields__)
    for required in (
        "claim_token",
        "conditions",
        "predicted_outcome",
        "confidence_milli",
        "revisions",
        "source_kind",
        "source_token",
        "trials",
        "status",
        "owner_token",
    ):
        assert required in names
    assert "law" not in names
    assert "truth" not in names
    assert "score" not in names


def test_coverage_row_rejects_bool_as_int() -> None:
    with pytest.raises(ScientificHypothesesError):
        ScientificCoverageRow(
            window_index=0,
            window_tick=0,
            window_count=True,
            event_count=0,
            owner_count=0,
            hypothesis_count=0,
            condition_count=0,
            revision_count=0,
            trial_count=0,
            truncated=False,
            coverage=ScientificHypothesisCoverage.COMPLETE,
            availability=ScientificHypothesisAvailability.AVAILABLE,
        )


def test_clean_three_layer_bundle_is_accepted() -> None:
    assert_scientific_hypothesis_layer_separation(
        (
            ScientificObjectiveEvidenceRow(
                window_index=0,
                window_tick=0,
                sequence=0,
                event_token="evt:1",
                operator=ExperimentOperator.COMBINE,
                outcome_class=ExperimentOutcomeClass.SUCCESS,
                discovery_mode=DiscoveryMode.DELIBERATE,
                coverage=ScientificHypothesisCoverage.COMPLETE,
            ),
        ),
        (
            HypothesisFact(
                owner_token=mint_owner_token("agent-1"),
                hypothesis_token="schyp-1",
                claim_token="claim-1",
                causal_hypothesis_token=NONE_TOKEN,
                status=ScientificHypothesisStatus.PROVISIONAL,
                predicted_outcome=ExperimentOutcomeClass.SUCCESS,
                confidence_milli=500,
                created_tick=0,
                active=True,
                source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
                source_token="self",
                conditions=(),
                revisions=(),
                trials=(),
            ),
        ),
        (
            ScientificOutcomeRow(
                window_index=0,
                window_tick=0,
                outcome_class=ExperimentOutcomeClass.SUCCESS,
                trial_count=0,
                matched_count=0,
                mismatched_count=0,
                share_milli=0,
                coverage=ScientificHypothesisCoverage.COMPLETE,
                availability=ScientificHypothesisAvailability.INSUFFICIENT_SAMPLES,
            ),
        ),
    )
