# mypy: ignore-errors
"""Detached credit and organizational-control claim aggregation."""

from __future__ import annotations

import pytest

from analysis.economic_inequality_claims import (
    EconomicClaimHarvest,
    control_claim_rows_from_operations,
    credit_claim_rows_from_events,
)
from analysis.economic_inequality_contract import EconomicInequalityCoverage
from analysis.organization_operations import (
    OrganizationControlRow,
    OrganizationOperationHarvestRows,
    OrganizationOperationOwnerRow,
)
from tests.unit.credit_relationships_analysis_helpers import (
    frame,
    talked,
)
from world.credit_relationships import CreditFrameAct

pytestmark = pytest.mark.unit


def test_credit_claims_aggregate_per_owner_and_window() -> None:
    events = [
        talked("evt-1", frame(principal_quantity=4), tick=2),
        talked(
            "evt-2",
            frame(
                act=CreditFrameAct.REPAY,
                principal_quantity=4,
                paid_quantity=1,
            ),
            tick=3,
        ),
    ]
    rows = credit_claim_rows_from_events(events)
    assert len(rows) == 1
    row = rows[0]
    assert row.claimed_principal_quantity == 4
    assert row.observed_repayment_quantity == 1
    assert row.claimed_relationship_count == 1
    assert row.window_index == 0
    assert row.source_layers[0].value == "owner_claim"


def _operation_harvest(
    *controls: OrganizationControlRow,
) -> OrganizationOperationHarvestRows:
    owner = OrganizationOperationOwnerRow(
        owner_id="body-a",
        concept_count=1,
        notices=(),
        policy_version="organization-operations.v1",
        control_count=len(controls),
    )
    return OrganizationOperationHarvestRows(owner=owner, controls=controls)


def test_control_claims_count_distinct_organizations() -> None:
    harvest = _operation_harvest(
        OrganizationControlRow(
            organization_id="org-1",
            domain="resource_control",
            last_tick=4,
            contest_count=0,
        ),
        OrganizationControlRow(
            organization_id="org-1",
            domain="resource_control",
            last_tick=5,
            contest_count=1,
        ),
        OrganizationControlRow(
            organization_id="org-2",
            domain="storage",
            last_tick=6,
            contest_count=0,
        ),
    )
    rows = control_claim_rows_from_operations([harvest])
    assert len(rows) == 1
    row = rows[0]
    assert row.claimed_resource_control_count == 1
    assert row.claimed_storage_control_count == 1
    assert row.contested_count == 1
    assert row.tick == 6
    assert row.window_index == 0


def test_empty_claims_are_empty_not_zero_filled() -> None:
    assert credit_claim_rows_from_events([]) == ()
    assert control_claim_rows_from_operations([]) == ()


def test_claim_harvest_validates_row_types() -> None:
    harvest = EconomicClaimHarvest()
    assert harvest.coverage is EconomicInequalityCoverage.MISSING
    with pytest.raises(ValueError, match="invalid_input"):
        control_claim_rows_from_operations([object()])  # type: ignore[list-item]
