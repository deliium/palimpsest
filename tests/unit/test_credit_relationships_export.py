"""Token-only owner export rows for credit analysis."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from agents.cognition.credit_relationships import (
    apply_credit_relationship_update,
)
from simulation.credit_relationships_export import (
    CreditOwnerRow,
    credit_owner_export,
)
from tests.unit.test_credit_relationships_helpers import OWNER, claim


def _ledger():
    return apply_credit_relationship_update(
        owner_id=OWNER,
        tick=2,
        claims=(claim(),),
    )


def test_export_emits_neutral_owner_rows() -> None:
    rows = credit_owner_export((_ledger(),))
    assert len(rows) == 1
    row = rows[0]
    assert type(row) is CreditOwnerRow
    assert row.owner_token == "agent-1"
    assert row.anchor_token.startswith("crd-")
    assert row.counterparty_token.startswith("credpeer-")
    assert "agent-2" not in row.counterparty_token
    assert row.window_index == 0
    assert row.claim_count == 1
    assert row.coverage == "complete"


def test_empty_ledgers_export_nothing() -> None:
    assert credit_owner_export(()) == ()


def test_no_raw_counterparty_or_item_id_is_exported() -> None:
    row = credit_owner_export((_ledger(),))[0]
    material = repr(row)
    assert "body-" not in material
    assert "item-" not in material


def test_rows_are_deterministically_sorted() -> None:
    from agents.models import AgentId

    first = _ledger()
    second = apply_credit_relationship_update(
        owner_id=AgentId("agent-0"),
        tick=2,
        claims=(claim(owner_value="agent-0"),),
    )
    rows = credit_owner_export((first, second))
    assert [row.owner_token for row in rows] == ["agent-0", "agent-1"]


def test_export_rejects_foreign_types() -> None:
    with pytest.raises(ValueError):
        credit_owner_export((object(),))
