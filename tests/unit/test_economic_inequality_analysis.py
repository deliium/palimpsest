# mypy: ignore-errors
"""Bounded economic-inequality harvest composition tests."""

from __future__ import annotations

import pytest

from analysis.economic_inequality_analysis import (
    ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION,
    economic_inequality_analysis_digest,
    empty_economic_inequality_analysis,
    harvest_economic_inequality_analysis,
)
from analysis.economic_inequality_contract import (
    EconomicInequalityCoverage,
    EconomicInequalityLayer,
)
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
)
from analysis.economic_inequality_rows import (
    EconomicAccessRow,
    EconomicCohortMembership,
    EconomicControlClaimRow,
    EconomicCreditClaimRow,
    EconomicPossessionRow,
    EconomicSocietyMembership,
)


def _possession(owner: int, window: int, items: int) -> EconomicPossessionRow:
    return EconomicPossessionRow(
        owner_token=f"eio-{owner:016x}",
        tick=window * 32 + 3,
        window_index=window,
        observed_item_count=items,
        observed_tool_count=0,
    )


def _fixture(window: int = 0) -> dict:
    return {
        "possession_rows": tuple(
            _possession(owner, window, owner + window) for owner in range(4)
        ),
        "access_rows": tuple(
            EconomicAccessRow(
                owner_token=f"eio-{owner:016x}",
                tick=window * 32 + 3,
                window_index=window,
                accessible_infrastructure_count=owner,
                accessible_storage_count=window,
                location_known=True,
            )
            for owner in range(4)
        ),
        "credit_rows": tuple(
            EconomicCreditClaimRow(
                owner_token=f"eio-{owner:016x}",
                tick=window * 32 + 3,
                window_index=window,
                claimed_principal_quantity=owner,
                observed_repayment_quantity=0,
                claimed_relationship_count=1,
            )
            for owner in range(4)
        ),
        "control_rows": tuple(
            EconomicControlClaimRow(
                owner_token=f"eio-{owner:016x}",
                tick=window * 32 + 3,
                window_index=window,
                claimed_resource_control_count=owner,
                claimed_storage_control_count=0,
            )
            for owner in range(4)
        ),
        "cohort_memberships": tuple(
            EconomicCohortMembership(
                owner_token=f"eio-{owner:016x}",
                generation_index=0,
                first_tick=0,
            )
            for owner in range(4)
        ),
        "society_memberships": tuple(
            EconomicSocietyMembership(
                owner_token=f"eio-{owner:016x}",
                society_token="eis-0000000000000001",
                window_indexes=(window,),
            )
            for owner in range(4)
        ),
    }


def test_harvest_composes_layers_and_rows() -> None:
    analysis = harvest_economic_inequality_analysis(**_fixture())
    assert analysis.policy_version == ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION
    assert analysis.coverage is EconomicInequalityCoverage.COMPLETE
    assert analysis.owner_count == 4
    assert analysis.observed_owner_count == 4
    assert analysis.dimension_rows
    assert analysis.cohort_rows
    assert analysis.society_rows
    assert EconomicInequalityLayer.OBJECTIVE_POSSESSION in analysis.layers
    assert EconomicInequalityLayer.OBJECTIVE_ACCESS in analysis.layers
    assert EconomicInequalityLayer.OWNER_CLAIM in analysis.layers
    assert EconomicInequalityLayer.ANALYTICAL_COMPARISON in analysis.layers
    assert analysis.window_count == 1


def test_empty_evidence_is_empty_not_zero_filled() -> None:
    analysis = harvest_economic_inequality_analysis()
    assert analysis.dimension_rows == ()
    assert analysis.cohort_rows == ()
    assert analysis.society_rows == ()
    assert analysis.coverage is EconomicInequalityCoverage.MISSING
    assert analysis == empty_economic_inequality_analysis()


def test_window_end_filters_later_windows() -> None:
    fixture = _fixture(0)
    second = _fixture(1)
    merged = {name: fixture[name] + second[name] for name in fixture}
    analysis = harvest_economic_inequality_analysis(**merged, window_end=31)
    assert {row.window_index for row in analysis.dimension_rows} == {0}


def test_row_caps_mark_partial_coverage() -> None:
    policy = EconomicInequalityAnalysisPolicy(max_dimension_rows=2)
    analysis = harvest_economic_inequality_analysis(**_fixture(), policy=policy)
    assert len(analysis.dimension_rows) == 2
    assert analysis.coverage is EconomicInequalityCoverage.PARTIAL
    assert "economic_inequality_dimension_truncated" in analysis.notices


def test_owner_cap_is_deterministic() -> None:
    policy = EconomicInequalityAnalysisPolicy(max_owners=2)
    analysis = harvest_economic_inequality_analysis(**_fixture(), policy=policy)
    assert analysis.owner_count == 2
    assert all(row.observed_owner_count <= 2 for row in analysis.dimension_rows)
    assert "economic_inequality_owners_truncated" in analysis.notices


def test_digest_is_stable_and_input_sensitive() -> None:
    analysis = harvest_economic_inequality_analysis(**_fixture())
    assert economic_inequality_analysis_digest(analysis) == (
        economic_inequality_analysis_digest(analysis)
    )
    other = harvest_economic_inequality_analysis(**_fixture(1))
    assert economic_inequality_analysis_digest(analysis) != (
        economic_inequality_analysis_digest(other)
    )


def test_invalid_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_policy"):
        harvest_economic_inequality_analysis(**_fixture(), policy=object())  # type: ignore[arg-type]
