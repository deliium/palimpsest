# mypy: ignore-errors
"""Eight economic-inequality metric family computations."""

from __future__ import annotations

import pytest

from analysis.economic_inequality_analysis import (
    harvest_economic_inequality_analysis,
)
from analysis.economic_inequality_metrics import (
    compute_credit_relationship_inequality,
    compute_economic_inequality_cohorts,
    compute_economic_inequality_society_comparison,
    compute_infrastructure_access_inequality,
    compute_organizational_resource_control_inequality,
    compute_productive_tool_access_inequality,
    compute_resource_possession_inequality,
    compute_storage_access_inequality,
)
from analysis.economic_inequality_rows import (
    EconomicCohortMembership,
    EconomicSocietyMembership,
)
from analysis.models import MetricAvailability

_RUN = "run-economic-inequality-metrics"
_REVISION = "rev-1"


def _analysis(owners: int = 16) -> object:
    from analysis.economic_inequality_rows import (
        EconomicAccessRow,
        EconomicControlClaimRow,
        EconomicCreditClaimRow,
        EconomicPossessionRow,
    )

    possession = tuple(
        EconomicPossessionRow(
            owner_token=f"eio-{owner:016x}",
            tick=4,
            window_index=0,
            observed_item_count=owner,
            observed_tool_count=owner % 2,
        )
        for owner in range(owners)
    )
    access = tuple(
        EconomicAccessRow(
            owner_token=f"eio-{owner:016x}",
            tick=4,
            window_index=0,
            accessible_infrastructure_count=owner % 3,
            accessible_storage_count=owner % 2,
            location_known=True,
        )
        for owner in range(owners)
    )
    credit = tuple(
        EconomicCreditClaimRow(
            owner_token=f"eio-{owner:016x}",
            tick=4,
            window_index=0,
            claimed_principal_quantity=owner % 4,
            observed_repayment_quantity=owner % 2,
            claimed_relationship_count=owner % 3,
        )
        for owner in range(owners)
    )
    control = tuple(
        EconomicControlClaimRow(
            owner_token=f"eio-{owner:016x}",
            tick=4,
            window_index=0,
            claimed_resource_control_count=owner % 3,
            claimed_storage_control_count=owner % 2,
        )
        for owner in range(owners)
    )
    cohorts = tuple(
        EconomicCohortMembership(
            owner_token=f"eio-{owner:016x}",
            generation_index=owner // 4,
            first_tick=0,
        )
        for owner in range(owners)
    )
    societies = tuple(
        EconomicSocietyMembership(
            owner_token=f"eio-{owner:016x}",
            society_token=f"eis-{owner // 4:016x}",
            window_indexes=(0,),
        )
        for owner in range(owners)
    )
    return harvest_economic_inequality_analysis(
        possession_rows=possession,
        access_rows=access,
        credit_rows=credit,
        control_rows=control,
        cohort_memberships=cohorts,
        society_memberships=societies,
    )


_COMPUTERS = (
    compute_resource_possession_inequality,
    compute_productive_tool_access_inequality,
    compute_infrastructure_access_inequality,
    compute_storage_access_inequality,
    compute_credit_relationship_inequality,
    compute_organizational_resource_control_inequality,
    compute_economic_inequality_cohorts,
    compute_economic_inequality_society_comparison,
)


def test_all_eight_families_produce_documents() -> None:
    analysis = _analysis()
    documents = [
        compute(analysis, run_id=_RUN, input_revision=_REVISION)
        for compute in _COMPUTERS
    ]
    assert len({document.metric_family for document in documents}) == 8
    for document in documents:
        assert document.run_id == _RUN
        assert document.input_revision == _REVISION
        assert document.availability is MetricAvailability.PRESENT
        assert document.coverage is not None
        assert document.coverage.observed > 0


def test_dimension_documents_carry_distributions_and_indices() -> None:
    analysis = _analysis()
    document = compute_resource_possession_inequality(
        analysis, run_id=_RUN, input_revision=_REVISION
    )
    values = document.values
    assert values["gini_latest"] is not None
    assert values["theil_t_latest"] is not None
    assert values["atkinson_eps_1_latest"] is not None
    assert values["top_share_milli_latest"] is not None
    assert values["trend_direction"] in {
        "rising",
        "falling",
        "stable",
        "insufficient_samples",
        "unavailable",
    }
    assert values["coverage"] == "complete"


def test_comparison_documents_carry_no_ranking() -> None:
    analysis = _analysis()
    cohort = compute_economic_inequality_cohorts(
        analysis, run_id=_RUN, input_revision=_REVISION
    )
    society = compute_economic_inequality_society_comparison(
        analysis, run_id=_RUN, input_revision=_REVISION
    )
    for document in (cohort, society):
        assert "rank" not in document.values
        assert "score" not in document.values
    assert cohort.values["widening_count"] >= 0
    assert society.values["overlap_member_count"] >= 0


def test_missing_dimension_is_unknown_not_zero() -> None:
    analysis = harvest_economic_inequality_analysis()
    document = compute_resource_possession_inequality(
        analysis, run_id=_RUN, input_revision=_REVISION
    )
    assert document.availability is MetricAvailability.UNKNOWN
    assert dict(document.values) == {}


def test_insufficient_samples_is_unknown() -> None:
    from analysis.economic_inequality_rows import EconomicPossessionRow

    rows = tuple(
        EconomicPossessionRow(
            owner_token=f"eio-{owner:016x}",
            tick=0,
            window_index=0,
            observed_item_count=owner,
            observed_tool_count=0,
        )
        for owner in range(3)
    )
    analysis = harvest_economic_inequality_analysis(possession_rows=rows)
    document = compute_resource_possession_inequality(
        analysis, run_id=_RUN, input_revision=_REVISION
    )
    assert document.availability is MetricAvailability.UNKNOWN
    assert dict(document.values) == {}


def test_invalid_analysis_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_input"):
        compute_resource_possession_inequality(
            object(), run_id=_RUN, input_revision=_REVISION
        )  # type: ignore[arg-type]
