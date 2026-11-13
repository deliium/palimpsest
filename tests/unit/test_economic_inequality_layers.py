# mypy: ignore-errors
"""Token-only row and layer-separation tests for economic inequality."""

from __future__ import annotations

import pytest

from analysis.economic_inequality_contract import (
    EconomicInequalityAvailability,
    EconomicInequalityCoverage,
    EconomicInequalityDimension,
    EconomicInequalityError,
    EconomicInequalityLayer,
    EconomicInequalityMeasure,
    EconomicInequalityTrend,
)
from analysis.economic_inequality_rows import (
    EconomicAccessRow,
    EconomicCohortMembership,
    EconomicCohortRow,
    EconomicControlClaimRow,
    EconomicCreditClaimRow,
    EconomicDimensionWindowRow,
    EconomicLayerBundle,
    EconomicPossessionRow,
    EconomicSocietyMembership,
    EconomicSocietyRow,
)


def _possession(**changes: object) -> EconomicPossessionRow:
    values: dict[str, object] = {
        "owner_token": "eio-0000000000000001",
        "tick": 3,
        "window_index": 0,
        "observed_item_count": 4,
        "observed_tool_count": 1,
        "unknown_kind_count": 0,
    }
    values.update(changes)
    return EconomicPossessionRow(**values)  # type: ignore[arg-type]


def _access(**changes: object) -> EconomicAccessRow:
    values: dict[str, object] = {
        "owner_token": "eio-0000000000000002",
        "tick": 3,
        "window_index": 0,
        "accessible_infrastructure_count": 1,
        "accessible_storage_count": 2,
        "location_known": True,
    }
    values.update(changes)
    return EconomicAccessRow(**values)  # type: ignore[arg-type]


def test_objective_rows_carry_objective_layers_only() -> None:
    possession = _possession()
    access = _access()
    assert possession.source_layers == (EconomicInequalityLayer.OBJECTIVE_POSSESSION,)
    assert access.source_layers == (EconomicInequalityLayer.OBJECTIVE_ACCESS,)


def test_claim_rows_carry_the_owner_claim_layer() -> None:
    credit = EconomicCreditClaimRow(
        owner_token="eio-0000000000000003",
        tick=4,
        window_index=0,
        claimed_principal_quantity=3,
        observed_repayment_quantity=1,
        claimed_relationship_count=2,
        contested_count=0,
    )
    control = EconomicControlClaimRow(
        owner_token="eio-0000000000000003",
        tick=4,
        window_index=0,
        claimed_resource_control_count=2,
        claimed_storage_control_count=1,
        contested_count=1,
    )
    assert credit.source_layers == (EconomicInequalityLayer.OWNER_CLAIM,)
    assert control.source_layers == (EconomicInequalityLayer.OWNER_CLAIM,)


def test_bundle_rejects_cross_layer_mixing() -> None:
    bundle = EconomicLayerBundle(
        possession_rows=(_possession(),),
        access_rows=(_access(),),
    )
    assert set(bundle.source_layers) == {
        EconomicInequalityLayer.OBJECTIVE_POSSESSION,
        EconomicInequalityLayer.OBJECTIVE_ACCESS,
    }
    # Objective possession and access are both objective evidence, so the
    # bundle can hold them together; claims stay in their own rows.
    assert bundle.credit_claim_rows == ()
    assert bundle.control_claim_rows == ()


def test_bundle_rejects_claim_rows_inside_objective_slots() -> None:
    credit = EconomicCreditClaimRow(
        owner_token="eio-0000000000000003",
        tick=4,
        window_index=0,
        claimed_principal_quantity=3,
        observed_repayment_quantity=1,
        claimed_relationship_count=2,
    )
    with pytest.raises(EconomicInequalityError, match="layer_leak"):
        EconomicLayerBundle(
            possession_rows=(_possession(),),
            credit_claim_rows=(credit,),  # type: ignore[arg-type]
        )


def test_dimension_rows_are_analytical_and_validate_distribution() -> None:
    row = EconomicDimensionWindowRow(
        dimension=EconomicInequalityDimension.RESOURCE_POSSESSION,
        measure=EconomicInequalityMeasure.OBSERVED_ITEM_COUNT,
        window_index=0,
        window_tick=32,
        owner_count=4,
        observed_owner_count=4,
        minimum=0,
        p25=1,
        median=2,
        p75=3,
        maximum=4,
        iqr=2,
        dispersion=4,
        bin_shares_milli=(250, 250, 250, 250, 0),
        gini_milli=250,
        theil_t_milli=120,
        atkinson_eps_1_milli=90,
        top_share_milli=400,
        availability=EconomicInequalityAvailability.AVAILABLE,
        coverage=EconomicInequalityCoverage.COMPLETE,
    )
    assert row.source_layers == (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)
    with pytest.raises(EconomicInequalityError, match="invalid_row"):
        EconomicDimensionWindowRow(
            dimension=EconomicInequalityDimension.RESOURCE_POSSESSION,
            measure=EconomicInequalityMeasure.OBSERVED_ITEM_COUNT,
            window_index=0,
            window_tick=32,
            owner_count=4,
            observed_owner_count=0,
            minimum=None,
            p25=None,
            median=None,
            p75=None,
            maximum=None,
            iqr=None,
            dispersion=None,
            bin_shares_milli=(0, 0, 0, 0, 0),
            gini_milli=None,
            theil_t_milli=None,
            atkinson_eps_1_milli=None,
            top_share_milli=None,
            availability=EconomicInequalityAvailability.AVAILABLE,
            coverage=EconomicInequalityCoverage.COMPLETE,
        )


def test_memberships_are_analytical_and_society_windows_are_unique() -> None:
    cohort = EconomicCohortMembership(
        owner_token="eio-0000000000000001",
        generation_index=0,
        first_tick=0,
    )
    society = EconomicSocietyMembership(
        owner_token="eio-0000000000000001",
        society_token="eis-0000000000000001",
        window_indexes=(0, 1),
    )
    assert cohort.source_layers == (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)
    assert society.source_layers == (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)
    with pytest.raises(EconomicInequalityError, match="invalid_row"):
        EconomicSocietyMembership(
            owner_token="eio-0000000000000001",
            society_token="eis-0000000000000001",
            window_indexes=(0, 0),
        )


def test_comparison_rows_are_analytical() -> None:
    cohort = EconomicCohortRow(
        cohort_token="eic-0000000000000001",
        generation_index=0,
        window_index=0,
        owner_count=5,
        comparable=True,
        gini_milli=200,
        median_milli=3,
        iqr_milli=1,
        trend=EconomicInequalityTrend.STABLE,
        availability=EconomicInequalityAvailability.AVAILABLE,
    )
    society = EconomicSocietyRow(
        society_token="eis-0000000000000001",
        window_index=0,
        owner_count=4,
        comparable=True,
        gini_milli=300,
        median_milli=2,
        iqr_milli=1,
        trend=EconomicInequalityTrend.RISING,
        availability=EconomicInequalityAvailability.AVAILABLE,
    )
    assert cohort.source_layers == (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)
    assert society.source_layers == (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: _possession(observed_item_count=1, observed_tool_count=2),
        lambda: _possession(owner_token=""),
        lambda: _access(location_known="yes"),
    ],
)
def test_invalid_rows_fail_closed(factory: object) -> None:
    with pytest.raises(EconomicInequalityError, match="invalid_row"):
        factory()  # type: ignore[operator]
