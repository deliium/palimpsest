"""Closed V4-22 credit relationship contract: enums, policy, identifiers."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agents.cognition.credit_relationships import (
    CREDIT_ANCHOR_PREFIX,
    CREDIT_FORBIDDEN_FIELD_NAMES,
    CREDIT_HEX_LEN,
    CREDIT_NOTICE_CODES,
    CREDIT_RELATIONSHIP_LOCKED_POLICY,
    CREDIT_RELATIONSHIPS_POLICY_VERSION,
    CREDIT_ROW_PREFIX,
    CreditAct,
    CreditClaimSource,
    CreditCollateralKind,
    CreditCondition,
    CreditDirection,
    CreditExpectationLevel,
    CreditRelationshipError,
    CreditRelationshipPolicy,
    CreditStatus,
    credit_anchor,
    credit_row_id,
    default_credit_relationship_policy,
    require_credit_anchor,
    require_credit_row_id,
)
from agents.models import AgentId
from world.values import ItemKind

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "agents" / "cognition" / "credit_relationships.py"


def test_policy_version_and_locked_policy_are_exact() -> None:
    assert CREDIT_RELATIONSHIPS_POLICY_VERSION == "credit-relationships.v1"
    assert dict(CREDIT_RELATIONSHIP_LOCKED_POLICY) == {
        "max_rows": 32,
        "max_claims_per_row": 16,
        "max_revisions_per_row": 8,
        "max_counterparties": 8,
        "max_notices": 8,
        "due_horizon_ticks": 64,
        "grace_ticks": 8,
        "stale_after_ticks": 128,
        "accept_min_willingness_milli": 500,
        "strong_min_confidence_milli": 750,
        "weak_max_confidence_milli": 449,
        "max_principal_quantity": 16,
        "max_repayment_quantity": 16,
        "max_collateral_quantity": 16,
        "ratio_max_milli": 64_000,
        "confidence_base": 200,
        "confidence_per_own_claim": 150,
        "confidence_per_received_claim": 100,
        "confidence_per_promise": 100,
    }
    policy = default_credit_relationship_policy()
    assert type(policy) is CreditRelationshipPolicy
    assert policy.max_rows == 32
    with pytest.raises(FrozenInstanceError):
        policy.max_rows = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    (
        (CreditDirection, ("owner_debtor", "owner_creditor")),
        (
            CreditStatus,
            (
                "proposed",
                "accepted",
                "open",
                "partially_repaid",
                "repaid",
                "defaulted",
                "forgiven",
                "disputed",
                "withdrawn",
                "declined",
                "expired",
            ),
        ),
        (
            CreditAct,
            (
                "propose",
                "accept",
                "decline",
                "repay",
                "default",
                "renegotiate",
                "forgive",
                "dispute",
                "withdraw",
            ),
        ),
        (
            CreditCondition,
            (
                "on_receipt",
                "by_deadline",
                "after_return",
                "shared_witness",
                "unspecified",
            ),
        ),
        (
            CreditCollateralKind,
            (
                "none",
                "item_pledge",
                "service_pledge",
                "custody_pledge",
                "reputation_pledge",
                "unspecified",
            ),
        ),
        (CreditExpectationLevel, ("none", "weak", "expected", "strong")),
        (CreditClaimSource, ("self_authored", "communicated")),
    ),
)
def test_enum_members_are_exact(
    enum_type: type[object], expected: tuple[str, ...]
) -> None:
    assert tuple(member.value for member in enum_type) == expected  # type: ignore[attr-defined]


def test_notice_codes_are_exact() -> None:
    assert CREDIT_NOTICE_CODES == {
        "credit_ledger_truncated",
        "credit_terms_unresolved",
        "credit_claim_rejected",
        "credit_terms_mismatch",
        "credit_anchor_ambiguous",
        "credit_frame_malformed",
        "credit_counterparty_unresolved",
        "credit_overdue",
        "credit_repayment_ambiguous",
        "credit_repayment_unmatched",
    }


def test_forbidden_field_names_are_exact() -> None:
    assert CREDIT_FORBIDDEN_FIELD_NAMES == {
        "bank",
        "banker",
        "loan",
        "interest",
        "interest_rate",
        "apr",
        "credit_score",
        "credit_limit",
        "deposit",
        "reserve",
        "money",
        "currency",
        "legal_tender",
        "collateral_lien",
        "enforcement",
        "collection",
        "allocation",
        "quota",
        "planner",
        "ranking",
        "recommendation",
        "default_probability",
    }


def test_policy_rejects_tampered_cap() -> None:
    with pytest.raises(CreditRelationshipError) as error:
        CreditRelationshipPolicy(max_rows=1)
    assert error.value.reason_code == "credit_invalid_policy"
    with pytest.raises(CreditRelationshipError):
        CreditRelationshipPolicy(weak_max_confidence_milli=900)


def test_anchor_is_symmetric_for_swapped_parties() -> None:
    first = credit_anchor(
        party_a="agent-a",
        party_b="agent-b",
        principal_kind=ItemKind.FOOD,
        repayment_kind=ItemKind.WATER,
        opened_tick=4,
    )
    second = credit_anchor(
        party_a="agent-b",
        party_b="agent-a",
        principal_kind=ItemKind.FOOD,
        repayment_kind=ItemKind.WATER,
        opened_tick=4,
    )
    assert first == second
    assert first.startswith(CREDIT_ANCHOR_PREFIX)
    assert len(first) == len(CREDIT_ANCHOR_PREFIX) + CREDIT_HEX_LEN
    assert require_credit_anchor(first) == first


def test_anchor_differs_by_tick_or_kind() -> None:
    base = credit_anchor(
        party_a="agent-a",
        party_b="agent-b",
        principal_kind=ItemKind.FOOD,
        repayment_kind=ItemKind.WATER,
        opened_tick=4,
    )
    assert base != credit_anchor(
        party_a="agent-a",
        party_b="agent-b",
        principal_kind=ItemKind.FOOD,
        repayment_kind=ItemKind.WATER,
        opened_tick=5,
    )
    assert base != credit_anchor(
        party_a="agent-a",
        party_b="agent-b",
        principal_kind=ItemKind.MATERIAL,
        repayment_kind=ItemKind.WATER,
        opened_tick=4,
    )
    assert base != credit_anchor(
        party_a="agent-a",
        party_b="agent-b",
        principal_kind=ItemKind.FOOD,
        repayment_kind=ItemKind.TOOL,
        opened_tick=4,
    )


@pytest.mark.parametrize(
    "value",
    ("", "crd-", "crd-0123", "xyz-0123456789abcdef", "crd-" + "g" * 16),
)
def test_require_anchor_rejects_malformed(value: str) -> None:
    with pytest.raises(CreditRelationshipError):
        require_credit_anchor(value)


def test_row_id_separates_owners() -> None:
    anchor = credit_anchor(
        party_a="agent-a",
        party_b="agent-b",
        principal_kind=ItemKind.FOOD,
        repayment_kind=ItemKind.WATER,
        opened_tick=4,
    )
    first = credit_row_id(AgentId("agent-a"), anchor)
    second = credit_row_id(AgentId("agent-b"), anchor)
    assert first != second
    assert first.startswith(CREDIT_ROW_PREFIX)
    assert require_credit_row_id(first) == first
    assert credit_row_id(AgentId("agent-a"), anchor) == first


def test_require_row_id_rejects_malformed() -> None:
    for value in ("", "cred-", "crd-0123456789abcdef", "cred-" + "z" * 16):
        with pytest.raises(CreditRelationshipError):
            require_credit_row_id(value)


def test_module_imports_stay_inside_the_owner_layer() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    forbidden = (
        "simulation",
        "analysis",
        "experiments",
        "persistence",
        "api",
        "observer",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert not name.startswith(forbidden), name


def test_dataclass_fields_never_use_a_forbidden_name() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ):
                if statement.target.id in CREDIT_FORBIDDEN_FIELD_NAMES:
                    offenders.append(f"{node.name}.{statement.target.id}")
    assert offenders == []
