# mypy: ignore-errors
"""Closed vocabulary tests for detached economic-inequality analysis."""

from __future__ import annotations

import pytest

from analysis.economic_inequality_contract import (
    ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION,
    ECONOMIC_INEQUALITY_FORBIDDEN_KEYS,
    EconomicInequalityAvailability,
    EconomicInequalityComparisonKind,
    EconomicInequalityDimension,
    EconomicInequalityError,
    EconomicInequalityLayer,
    EconomicInequalityMeasure,
    EconomicInequalityTrend,
    assert_economic_inequality_layer_separation,
    economic_inequality_cohort_token,
    economic_inequality_measures_for,
    economic_inequality_owner_token,
    economic_inequality_society_token,
    economic_inequality_token_hash,
)


def test_policy_token_is_locked() -> None:
    assert ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION == "economic-inequality.v1"


def test_dimensions_are_closed_and_exact() -> None:
    assert {dimension.value for dimension in EconomicInequalityDimension} == {
        "resource_possession",
        "productive_tool_access",
        "infrastructure_access",
        "storage_access",
        "credit_relationship",
        "organizational_resource_control",
    }


def test_measures_are_closed_and_exact() -> None:
    assert {measure.value for measure in EconomicInequalityMeasure} == {
        "observed_item_count",
        "observed_tool_count",
        "accessible_infrastructure_count",
        "accessible_storage_count",
        "claimed_principal_quantity",
        "observed_repayment_quantity",
        "claimed_relationship_count",
        "claimed_resource_control_count",
        "claimed_storage_control_count",
    }


def test_dimension_measure_mapping_is_stable() -> None:
    assert economic_inequality_measures_for(
        EconomicInequalityDimension.RESOURCE_POSSESSION
    ) == (EconomicInequalityMeasure.OBSERVED_ITEM_COUNT,)
    assert economic_inequality_measures_for(
        EconomicInequalityDimension.CREDIT_RELATIONSHIP
    ) == (
        EconomicInequalityMeasure.CLAIMED_PRINCIPAL_QUANTITY,
        EconomicInequalityMeasure.OBSERVED_REPAYMENT_QUANTITY,
        EconomicInequalityMeasure.CLAIMED_RELATIONSHIP_COUNT,
    )
    with pytest.raises(EconomicInequalityError):
        economic_inequality_measures_for("resource_possession")  # type: ignore[arg-type]


def test_availability_trend_and_comparison_kinds_are_closed() -> None:
    assert {value.value for value in EconomicInequalityAvailability} == {
        "available",
        "insufficient_samples",
        "unavailable",
    }
    assert {value.value for value in EconomicInequalityTrend} == {
        "rising",
        "falling",
        "stable",
        "insufficient_samples",
        "unavailable",
    }
    assert {value.value for value in EconomicInequalityComparisonKind} == {
        "cohort",
        "society",
    }


def test_layers_are_strictly_separated() -> None:
    assert {layer.value for layer in EconomicInequalityLayer} == {
        "objective_possession",
        "objective_access",
        "owner_claim",
        "analytical_comparison",
    }


def test_forbidden_keys_reject_wealth_and_legitimacy_vocabulary() -> None:
    for key in (
        "wealth",
        "net_worth",
        "ownership",
        "ownership_score",
        "legitimate_owner",
        "merit",
        "poverty",
        "rank",
        "score",
    ):
        assert key in ECONOMIC_INEQUALITY_FORBIDDEN_KEYS


def test_error_exposes_stable_reason_code() -> None:
    assert (
        EconomicInequalityError("economic_inequality_invalid_row").reason_code
        == "economic_inequality_invalid_row"
    )
    assert EconomicInequalityError().reason_code == (
        "economic_inequality_invalid_input"
    )


def test_owner_tokens_are_deterministic_and_prefixed() -> None:
    first = economic_inequality_owner_token("agent-1")
    second = economic_inequality_owner_token("agent-1")
    assert first == second
    assert first.startswith("eio-")
    assert len(first) == 20
    assert first != economic_inequality_owner_token("agent-2")
    assert economic_inequality_token_hash("x-", "a") != (
        economic_inequality_token_hash("x-", "b")
    )


def test_cohort_and_society_tokens_are_prefixed() -> None:
    assert economic_inequality_cohort_token(0).startswith("eic-")
    assert economic_inequality_cohort_token(1) != (economic_inequality_cohort_token(0))
    assert economic_inequality_society_token("msoc-abc").startswith("eis-")
    with pytest.raises(EconomicInequalityError):
        economic_inequality_owner_token("")
    with pytest.raises(EconomicInequalityError):
        economic_inequality_cohort_token(-1)


def test_layer_separation_accepts_one_layer_and_rejects_mixed() -> None:
    class _Row:
        def __init__(self, layer: EconomicInequalityLayer) -> None:
            self.source_layers = (layer,)

    assert_economic_inequality_layer_separation(
        _Row(EconomicInequalityLayer.OBJECTIVE_ACCESS),
        _Row(EconomicInequalityLayer.OBJECTIVE_ACCESS),
    )
    with pytest.raises(EconomicInequalityError, match="layer_leak"):
        assert_economic_inequality_layer_separation(
            _Row(EconomicInequalityLayer.OBJECTIVE_ACCESS),
            _Row(EconomicInequalityLayer.OWNER_CLAIM),
        )
