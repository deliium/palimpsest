# mypy: ignore-errors
"""Hard layer-separation guard for scientific-hypothesis analysis."""

from __future__ import annotations

from dataclasses import field, make_dataclass

import pytest

from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesesError,
    ScientificHypothesisAvailability,
    ScientificHypothesisCoverage,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
    assert_scientific_hypothesis_layer_separation,
    mint_owner_token,
)
from analysis.scientific_hypotheses_rows import (
    HypothesisFact,
    ScientificObjectiveEvidenceRow,
    ScientificOutcomeRow,
)
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
)

pytestmark = pytest.mark.unit


def _row(name: str, **fields: object) -> object:
    return make_dataclass(
        name,
        [
            (key, str, field(default=value))
            for key, value in fields.items()
        ],
        frozen=True,
        slots=True,
    )()


def _objective_row() -> ScientificObjectiveEvidenceRow:
    return ScientificObjectiveEvidenceRow(
        window_index=0,
        window_tick=0,
        sequence=0,
        event_token="evt:1",
        operator=ExperimentOperator.COMBINE,
        outcome_class=ExperimentOutcomeClass.SUCCESS,
        discovery_mode=DiscoveryMode.DELIBERATE,
        coverage=ScientificHypothesisCoverage.COMPLETE,
    )


def _owner_row() -> HypothesisFact:
    return HypothesisFact(
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
    )


def _analytical_row() -> ScientificOutcomeRow:
    return ScientificOutcomeRow(
        window_index=0,
        window_tick=0,
        outcome_class=ExperimentOutcomeClass.SUCCESS,
        trial_count=0,
        matched_count=0,
        mismatched_count=0,
        share_milli=0,
        coverage=ScientificHypothesisCoverage.COMPLETE,
        availability=ScientificHypothesisAvailability.INSUFFICIENT_SAMPLES,
    )


def test_clean_three_layer_bundle_is_accepted() -> None:
    assert_scientific_hypothesis_layer_separation(
        (_objective_row(),), (_owner_row(),), (_analytical_row(),)
    )


def test_objective_row_with_claim_token_is_rejected() -> None:
    row = _row("ScientificObjectiveEvidenceRow", claim_token="claim-1")
    with pytest.raises(ScientificHypothesesError) as excinfo:
        assert_scientific_hypothesis_layer_separation((row,))
    assert excinfo.value.reason_code == "scientific_hypotheses_layer_violation"


def test_analytical_row_with_owner_token_is_rejected() -> None:
    row = _row("ScientificTrialRow", owner_token="owner-1")
    with pytest.raises(ScientificHypothesesError) as excinfo:
        assert_scientific_hypothesis_layer_separation((row,))
    assert excinfo.value.reason_code == "scientific_hypotheses_layer_violation"


def test_owner_row_with_law_key_is_rejected() -> None:
    row = _row("HypothesisExampleFact", law="objective")
    with pytest.raises(ScientificHypothesesError) as excinfo:
        assert_scientific_hypothesis_layer_separation((row,))
    assert excinfo.value.reason_code == "scientific_hypotheses_forbidden_key"


def test_mixed_group_is_rejected() -> None:
    with pytest.raises(ScientificHypothesesError) as excinfo:
        assert_scientific_hypothesis_layer_separation(
            (_objective_row(), _analytical_row())
        )
    assert excinfo.value.reason_code == "scientific_hypotheses_layer_violation"


def test_non_sequence_group_is_rejected() -> None:
    with pytest.raises(ScientificHypothesesError):
        assert_scientific_hypothesis_layer_separation("not-a-group")  # type: ignore[arg-type]
