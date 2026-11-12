"""Closed V4-22 detached credit analysis contract."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.credit_relationships_contract import (
    CREDIT_ALIGNMENT,
    CREDIT_ALIGNMENT_PREFIX,
    CREDIT_ANALYSIS_ERROR_CODES,
    CREDIT_ANALYSIS_FORBIDDEN_KEYS,
    CREDIT_ANALYSIS_HEX_LEN,
    CREDIT_ANALYSIS_NOTICE_CODES,
    CREDIT_CLAIM_PREFIX,
    CREDIT_COUNTERPARTY_PREFIX,
    CREDIT_DISTRIBUTION_PREFIX,
    CREDIT_LAYER_FORBIDDEN_PREFIXES,
    CREDIT_OWNER_PREFIX,
    CREDIT_PEER_PREFIX,
    CREDIT_PERFORMANCE_PREFIX,
    CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION,
    CreditAlignment,
    CreditAnalysisLayer,
    CreditClaimAct,
    CreditClaimDirection,
    CreditCoverage,
    CreditDistributionStatus,
    CreditPerformanceOutcome,
    CreditSampleSource,
    credit_alignment_token,
    credit_claim_token,
    credit_counterparty_token,
    credit_distribution_token,
    credit_owner_token,
    credit_peer_token,
    credit_performance_token,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "analysis" / "credit_relationships_contract.py"


def test_policy_version_and_prefixes_are_exact() -> None:
    assert CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION == "credit-relationships.v1"
    assert CREDIT_OWNER_PREFIX == "credo-"
    assert CREDIT_PERFORMANCE_PREFIX == "credp-"
    assert CREDIT_DISTRIBUTION_PREFIX == "credd-"
    assert CREDIT_COUNTERPARTY_PREFIX == "credcp-"
    assert CREDIT_PEER_PREFIX == "credpeer-"
    assert CREDIT_CLAIM_PREFIX == "credcl-"
    assert CREDIT_ALIGNMENT_PREFIX == "creda-"
    assert CREDIT_ANALYSIS_HEX_LEN == 16


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    (
        (CreditCoverage, ("complete", "partial", "missing")),
        (
            CreditAnalysisLayer,
            (
                "objective_claim",
                "owner_credit",
                "analytical_performance",
                "comparison_view",
            ),
        ),
        (CreditSampleSource, ("proposed", "agreed")),
        (
            CreditDistributionStatus,
            ("available", "insufficient_samples"),
        ),
        (
            CreditPerformanceOutcome,
            (
                "active",
                "partially_repaid",
                "repaid",
                "defaulted",
                "forgiven",
                "disputed",
                "expired",
                "insufficient_evidence",
            ),
        ),
        (
            CreditAlignment,
            ("consistent", "unresolved", "inconsistent", "not_applicable"),
        ),
        (
            CreditClaimAct,
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
        (CreditClaimDirection, ("owner_debtor", "owner_creditor")),
    ),
)
def test_enum_members_are_exact(
    enum_type: type[object], expected: tuple[str, ...]
) -> None:
    assert tuple(member.value for member in enum_type) == expected  # type: ignore[attr-defined]


def test_alignment_set_matches_enum() -> None:
    assert CREDIT_ALIGNMENT == frozenset(CreditAlignment)


def test_forbidden_keys_are_exact() -> None:
    assert CREDIT_ANALYSIS_FORBIDDEN_KEYS == {
        "bank",
        "banker",
        "loan",
        "interest",
        "interest_rate",
        "apr",
        "credit_score",
        "credit_limit",
        "default_probability",
        "money",
        "currency",
        "legal_tender",
        "deposit",
        "reserve",
        "enforceable_debt",
        "enforcement",
        "collection",
        "allocation",
        "quota",
        "canonical_credit",
        "ranking",
        "recommendation",
    }


def test_layer_prefixes_are_exact() -> None:
    assert CREDIT_LAYER_FORBIDDEN_PREFIXES[CreditAnalysisLayer.OBJECTIVE_CLAIM] == {
        CREDIT_OWNER_PREFIX,
        CREDIT_PERFORMANCE_PREFIX,
        CREDIT_DISTRIBUTION_PREFIX,
        CREDIT_COUNTERPARTY_PREFIX,
        CREDIT_ALIGNMENT_PREFIX,
    }
    assert CREDIT_LAYER_FORBIDDEN_PREFIXES[CreditAnalysisLayer.OWNER_CREDIT] == {
        CREDIT_PERFORMANCE_PREFIX,
        CREDIT_DISTRIBUTION_PREFIX,
        CREDIT_COUNTERPARTY_PREFIX,
        CREDIT_ALIGNMENT_PREFIX,
    }
    assert CREDIT_LAYER_FORBIDDEN_PREFIXES[
        CreditAnalysisLayer.ANALYTICAL_PERFORMANCE
    ] == {"event_token", "raw_event_token"}
    assert CREDIT_LAYER_FORBIDDEN_PREFIXES[CreditAnalysisLayer.COMPARISON_VIEW] == {
        "event_token",
        "raw_event_token",
    }


def test_notice_and_error_codes_are_exact() -> None:
    assert CREDIT_ANALYSIS_NOTICE_CODES == {
        "credit_claim_malformed",
        "credit_evidence_truncated",
        "credit_ratio_out_of_range",
        "credit_direction_conflict",
        "credit_performance_truncated",
        "credit_distribution_truncated",
        "credit_counterparty_truncated",
        "credit_owner_truncated",
        "credit_alignment_truncated",
        "credit_terms_mismatch",
        "credit_missing_owner_rows",
        "credit_missing_evidence",
    }
    assert CREDIT_ANALYSIS_ERROR_CODES == {
        "credit_analysis_invalid_policy",
        "credit_analysis_invalid_row",
        "credit_analysis_invalid_window",
        "credit_analysis_cap_exceeded",
        "credit_analysis_forbidden_key",
        "credit_analysis_layer_leak",
        "credit_analysis_missing_input",
    }


def test_tokens_are_deterministic_with_exact_prefix_and_length() -> None:
    assert credit_owner_token("owner", "crd-abc", 1) == credit_owner_token(
        "owner", "crd-abc", 1
    )
    assert len(credit_owner_token("owner", "crd-abc", 1)) == len(
        CREDIT_OWNER_PREFIX
    ) + CREDIT_ANALYSIS_HEX_LEN
    assert credit_performance_token("crd-abc", 1).startswith(
        CREDIT_PERFORMANCE_PREFIX
    )
    assert credit_distribution_token("food", "water", "agreed", 1).startswith(
        CREDIT_DISTRIBUTION_PREFIX
    )
    assert credit_peer_token("agent-1").startswith(CREDIT_PEER_PREFIX)
    assert credit_claim_token("evt-1", "propose", "owner_debtor").startswith(
        CREDIT_CLAIM_PREFIX
    )
    assert credit_alignment_token("owner", "crd-abc", 1).startswith(
        CREDIT_ALIGNMENT_PREFIX
    )


def test_counterparty_token_is_symmetric() -> None:
    assert credit_counterparty_token("b", "a", 2) == credit_counterparty_token(
        "a", "b", 2
    )
    assert credit_counterparty_token("a", "b", 2) != credit_counterparty_token(
        "a", "b", 3
    )


def test_contract_imports_only_the_standard_library() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert not name.startswith(
                (
                    "agents",
                    "simulation",
                    "experiments",
                    "persistence",
                    "api",
                    "observer",
                )
            ), name
