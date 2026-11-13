# mypy: ignore-errors
"""Deterministic per-window detection for economic-inequality dimensions."""

from __future__ import annotations

import pytest

from analysis.economic_inequality_contract import (
    EconomicInequalityAvailability,
    EconomicInequalityCoverage,
    EconomicInequalityDimension,
    EconomicInequalityMeasure,
)
from analysis.economic_inequality_detection import (
    detect_economic_inequality_rows,
)
from analysis.economic_inequality_rows import (
    EconomicAccessRow,
    EconomicControlClaimRow,
    EconomicCreditClaimRow,
    EconomicPossessionRow,
)


def _possession(
    owner: int, window: int, items: int, tools: int
) -> EconomicPossessionRow:
    return EconomicPossessionRow(
        owner_token=f"eio-{owner:016x}",
        tick=window * 32 + 5,
        window_index=window,
        observed_item_count=items,
        observed_tool_count=tools,
    )


def _access(owner: int, window: int, infra: int, storage: int) -> EconomicAccessRow:
    return EconomicAccessRow(
        owner_token=f"eio-{owner:016x}",
        tick=window * 32 + 5,
        window_index=window,
        accessible_infrastructure_count=infra,
        accessible_storage_count=storage,
        location_known=True,
    )


def _credit(owner: int, window: int, principal: int) -> EconomicCreditClaimRow:
    return EconomicCreditClaimRow(
        owner_token=f"eio-{owner:016x}",
        tick=window * 32 + 5,
        window_index=window,
        claimed_principal_quantity=principal,
        observed_repayment_quantity=principal // 2,
        claimed_relationship_count=1,
    )


def _control(owner: int, window: int, resources: int) -> EconomicControlClaimRow:
    return EconomicControlClaimRow(
        owner_token=f"eio-{owner:016x}",
        tick=window * 32 + 5,
        window_index=window,
        claimed_resource_control_count=resources,
        claimed_storage_control_count=0,
    )


def _fixture(window: int = 0) -> dict[str, tuple[object, ...]]:
    return {
        "possession_rows": tuple(
            _possession(owner, window, owner, owner) for owner in range(4)
        ),
        "access_rows": tuple(
            _access(owner, window, owner, owner + 1) for owner in range(4)
        ),
        "credit_rows": tuple(_credit(owner, window, owner * 2) for owner in range(4)),
        "control_rows": tuple(_control(owner, window, owner) for owner in range(4)),
    }


def test_available_dimensions_carry_distributions_and_indices() -> None:
    result = detect_economic_inequality_rows(**_fixture())
    assert result.coverage is EconomicInequalityCoverage.COMPLETE
    assert result.window_count == 1
    keys = {(row.dimension, row.measure) for row in result.rows}
    assert (
        EconomicInequalityDimension.RESOURCE_POSSESSION,
        EconomicInequalityMeasure.OBSERVED_ITEM_COUNT,
    ) in keys
    assert (
        EconomicInequalityDimension.PRODUCTIVE_TOOL_ACCESS,
        EconomicInequalityMeasure.OBSERVED_TOOL_COUNT,
    ) in keys
    assert (
        EconomicInequalityDimension.INFRASTRUCTURE_ACCESS,
        EconomicInequalityMeasure.ACCESSIBLE_INFRASTRUCTURE_COUNT,
    ) in keys
    assert (
        EconomicInequalityDimension.STORAGE_ACCESS,
        EconomicInequalityMeasure.ACCESSIBLE_STORAGE_COUNT,
    ) in keys
    assert (
        EconomicInequalityDimension.CREDIT_RELATIONSHIP,
        EconomicInequalityMeasure.CLAIMED_PRINCIPAL_QUANTITY,
    ) in keys
    assert (
        EconomicInequalityDimension.ORGANIZATIONAL_RESOURCE_CONTROL,
        EconomicInequalityMeasure.CLAIMED_RESOURCE_CONTROL_COUNT,
    ) in keys
    for row in result.rows:
        assert row.availability is EconomicInequalityAvailability.AVAILABLE
        assert row.observed_owner_count == 4
        assert row.gini_milli is not None
        assert 0 <= row.gini_milli <= 1_000
        assert sum(row.bin_shares_milli) == (1_000 if row.maximum else 0)


def test_fewer_than_four_owners_is_insufficient() -> None:
    fixture = _fixture()
    fixture["possession_rows"] = fixture["possession_rows"][:3]
    result = detect_economic_inequality_rows(**fixture)
    possession = next(
        row
        for row in result.rows
        if row.dimension is EconomicInequalityDimension.RESOURCE_POSSESSION
    )
    assert (
        possession.availability is EconomicInequalityAvailability.INSUFFICIENT_SAMPLES
    )
    assert possession.observed_owner_count == 3
    assert possession.gini_milli is None
    assert possession.bin_shares_milli == (0, 0, 0, 0, 0)


def test_missing_dimension_emits_no_row() -> None:
    fixture = _fixture()
    fixture["control_rows"] = ()
    result = detect_economic_inequality_rows(**fixture)
    assert not any(
        row.dimension is EconomicInequalityDimension.ORGANIZATIONAL_RESOURCE_CONTROL
        for row in result.rows
    )


def test_access_without_location_is_partial_and_excluded() -> None:
    fixture = _fixture()
    fixture["access_rows"] = (
        _access(0, 0, 1, 1),
        _access(1, 0, 1, 1),
        _access(2, 0, 1, 1),
        EconomicAccessRow(
            owner_token="eio-0000000000000003",
            tick=5,
            window_index=0,
            accessible_infrastructure_count=0,
            accessible_storage_count=0,
            location_known=False,
        ),
    )
    result = detect_economic_inequality_rows(**fixture)
    infra = next(
        row
        for row in result.rows
        if row.dimension is EconomicInequalityDimension.INFRASTRUCTURE_ACCESS
    )
    assert infra.coverage is EconomicInequalityCoverage.PARTIAL
    assert infra.observed_owner_count == 3
    assert infra.availability is EconomicInequalityAvailability.INSUFFICIENT_SAMPLES
    assert result.coverage is EconomicInequalityCoverage.PARTIAL


def test_two_windows_are_sorted_and_independent() -> None:
    first = _fixture(0)
    second = _fixture(1)
    result = detect_economic_inequality_rows(
        **{name: first[name] + second[name] for name in first}
    )
    assert result.window_count == 2
    assert [row.window_index for row in result.rows] == sorted(
        row.window_index for row in result.rows
    )
    assert {row.window_index for row in result.rows} == {0, 1}


def test_invalid_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_policy"):
        detect_economic_inequality_rows(policy=object())  # type: ignore[arg-type]
