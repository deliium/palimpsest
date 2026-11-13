# mypy: ignore-errors
"""Layer leakage guards for economic-inequality rows and snapshots."""

from __future__ import annotations

from dataclasses import fields

from analysis.economic_inequality_contract import (
    ECONOMIC_INEQUALITY_FORBIDDEN_KEYS,
)
from analysis.economic_inequality_rows import (
    EconomicAccessRow,
    EconomicCohortMembership,
    EconomicCohortRow,
    EconomicControlClaimRow,
    EconomicCreditClaimRow,
    EconomicDimensionWindowRow,
    EconomicPossessionRow,
    EconomicSocietyMembership,
    EconomicSocietyRow,
)
from experiments.economic_inequality_publication import (
    compose_economic_inequality_snapshot,
)
from tests.unit.test_economic_inequality_metrics import _analysis

_OBJECTIVE_FORBIDDEN = {
    "counterparty_token",
    "organization_id",
    "claimed_principal_quantity",
    "claimed_resource_control_count",
    "claimed_storage_control_count",
    "claimed_relationship_count",
}
_CLAIM_FORBIDDEN = {
    "item_id",
    "item_ids",
    "holder_id",
    "resulting_holder_id",
    "custody",
    "observed_item_count",
    "observed_tool_count",
    "accessible_infrastructure_count",
    "accessible_storage_count",
}
_ANALYTICAL_FORBIDDEN = {"owner_token", "owner_id", "member_id"}


def _names(row_type: type[object]) -> set[str]:
    return {field.name for field in fields(row_type)}


def test_objective_rows_carry_no_claim_payload() -> None:
    for row_type in (EconomicPossessionRow, EconomicAccessRow):
        assert _names(row_type) & _OBJECTIVE_FORBIDDEN == set()
        assert _names(row_type) & ECONOMIC_INEQUALITY_FORBIDDEN_KEYS == set()


def test_claim_rows_carry_no_custody_payload() -> None:
    for row_type in (EconomicCreditClaimRow, EconomicControlClaimRow):
        assert _names(row_type) & _CLAIM_FORBIDDEN == set()
        assert _names(row_type) & ECONOMIC_INEQUALITY_FORBIDDEN_KEYS == set()


def test_analytical_rows_carry_no_owner_identity() -> None:
    for row_type in (
        EconomicDimensionWindowRow,
        EconomicCohortRow,
        EconomicSocietyRow,
    ):
        assert _names(row_type) & _ANALYTICAL_FORBIDDEN == set()
    for row_type in (EconomicCohortMembership, EconomicSocietyMembership):
        assert "owner_token" in _names(row_type)


def test_snapshot_rows_carry_no_owner_tokens() -> None:
    snapshot = compose_economic_inequality_snapshot(_analysis(), run_id="run-1")
    for row in (*snapshot.dimensions, *snapshot.cohorts, *snapshot.societies):
        assert "owner_token" not in _names(type(row))
        assert "eio-" not in repr(row)
    assert "eio-" not in repr(snapshot.dimensions)
