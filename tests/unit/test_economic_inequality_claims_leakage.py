# mypy: ignore-errors
"""Leakage guards for detached credit and control claim rows."""

from __future__ import annotations

from dataclasses import fields

from analysis.economic_inequality_contract import (
    ECONOMIC_INEQUALITY_FORBIDDEN_KEYS,
)
from analysis.economic_inequality_rows import (
    EconomicControlClaimRow,
    EconomicCreditClaimRow,
)

_FORBIDDEN_ROW_FIELDS = frozenset(
    {
        "counterparty_token",
        "counterparty_id",
        "item_id",
        "item_ids",
        "item_kind",
        "principal_kind",
        "repayment_kind",
        "holder_id",
        "resulting_holder_id",
        "custody",
        "location_id",
        "observed_item_count",
        "observed_tool_count",
        "accessible_infrastructure_count",
        "accessible_storage_count",
    }
)


def test_credit_rows_carry_no_counterparty_or_item_payload() -> None:
    names = {field.name for field in fields(EconomicCreditClaimRow)}
    assert names & _FORBIDDEN_ROW_FIELDS == set()
    assert names & ECONOMIC_INEQUALITY_FORBIDDEN_KEYS == set()
    assert "claimed_principal_quantity" in names
    assert "observed_repayment_quantity" in names


def test_control_rows_carry_no_possession_payload() -> None:
    names = {field.name for field in fields(EconomicControlClaimRow)}
    assert names & _FORBIDDEN_ROW_FIELDS == set()
    assert names & ECONOMIC_INEQUALITY_FORBIDDEN_KEYS == set()
    assert "claimed_resource_control_count" in names
    assert "claimed_storage_control_count" in names
