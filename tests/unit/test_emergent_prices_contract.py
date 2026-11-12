"""Closed V4-21 emergent price contract: enums, policy, ids."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import FrozenInstanceError, fields
from enum import Enum
from pathlib import Path

import pytest

from agents.cognition.emergent_prices import (
    EMERGENT_PRICE_LOCKED_POLICY,
    EMERGENT_PRICE_NOTICE_CODES,
    EMERGENT_PRICES_POLICY_VERSION,
    PRICE_BELIEF_HEX_LEN,
    PRICE_BELIEF_PREFIX,
    PRICE_FORBIDDEN_FIELD_NAMES,
    EmergentPriceError,
    EmergentPricePolicy,
    PriceExpectationLevel,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceUnitSource,
    default_emergent_price_policy,
    price_belief_id,
    require_price_belief_id,
)
from agents.models import AgentId
from world.values import ItemKind

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_policy_version_and_locked_policy_are_exact() -> None:
    assert EMERGENT_PRICES_POLICY_VERSION == "emergent-prices.v1"
    assert dict(EMERGENT_PRICE_LOCKED_POLICY) == {
        "max_rows": 32,
        "max_observations_per_row": 32,
        "max_quotes_per_row": 8,
        "max_counterparties": 8,
        "max_units": 8,
        "max_notices": 8,
        "stale_after_ticks": 64,
        "expected_min_observations": 2,
        "strong_min_confidence_milli": 750,
        "quote_min_confidence_milli": 250,
        "medium_min_received": 2,
        "ratio_max_milli": 64_000,
        "confidence_base_per_evidence": 150,
        "confidence_base_cap": 600,
    }
    policy = default_emergent_price_policy()
    assert type(policy) is EmergentPricePolicy
    assert policy.max_rows == 32
    with pytest.raises(FrozenInstanceError):
        policy.max_rows = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    (
        (
            PriceUnitSource,
            (
                "owner_reference",
                "observed_medium",
                "exchange_counterpart",
                "quoted",
                "unknown",
            ),
        ),
        (PriceQuoteDirection, ("give_for_unit", "unit_for_give")),
        (
            PriceQuoteSource,
            ("observed_offer", "communicated", "self_authored"),
        ),
        (PriceExpectationLevel, ("none", "weak", "expected", "strong")),
    ),
)
def test_enums_have_exactly_the_documented_members(
    enum_type: type[Enum], expected: tuple[str, ...]
) -> None:
    assert tuple(member.value for member in enum_type) == expected


def test_notice_and_forbidden_field_sets_are_closed() -> None:
    assert EMERGENT_PRICE_NOTICE_CODES == {
        "price_ledger_truncated",
        "price_unit_unresolved",
        "price_valuation_stale",
        "price_quote_malformed",
        "price_evidence_unpaired",
    }
    assert {
        "price",
        "canonical_price",
        "price_index",
        "clearing_price",
        "rate",
        "money",
        "currency",
        "numeraire",
        "bid",
        "ask",
        "spread",
        "fee",
        "commission",
        "tax",
        "debt",
        "credit_limit",
        "market_score",
        "ranking",
        "severity",
        "recommendation",
        "allocation",
        "quota",
        "central_planner",
        "unit_of_account",
        "medium_of_exchange",
        "store_of_value",
    } <= PRICE_FORBIDDEN_FIELD_NAMES
    assert not (
        {field.name for field in fields(EmergentPricePolicy)}
        & PRICE_FORBIDDEN_FIELD_NAMES
    )


def test_belief_id_is_deterministic_and_owner_local() -> None:
    owner = AgentId("agent-1")
    peer = AgentId("agent-2")
    first = price_belief_id(owner, ItemKind.FOOD, "water")
    assert first == price_belief_id(owner, ItemKind.FOOD, "water")
    assert first.startswith(PRICE_BELIEF_PREFIX)
    assert len(first) == len(PRICE_BELIEF_PREFIX) + PRICE_BELIEF_HEX_LEN
    assert first != price_belief_id(peer, ItemKind.FOOD, "water")
    assert first != price_belief_id(owner, ItemKind.WATER, "water")
    require_price_belief_id(first)


def test_belief_id_is_stable_across_process_restarts() -> None:
    code = (
        "from agents.cognition.emergent_prices import price_belief_id;"
        "from agents.models import AgentId;"
        "from world.values import ItemKind;"
        "print(price_belief_id(AgentId('agent-1'), ItemKind.FOOD, 'water'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == price_belief_id(
        AgentId("agent-1"), ItemKind.FOOD, "water"
    )


def test_invalid_identifiers_fail_closed() -> None:
    with pytest.raises(EmergentPriceError):
        price_belief_id(AgentId("agent-1"), ItemKind.FOOD, "")
    with pytest.raises(EmergentPriceError):
        require_price_belief_id("prcb-zzzz")


def test_contract_module_has_no_upstream_package_imports() -> None:
    import ast

    module = ROOT / "src" / "agents" / "cognition" / "emergent_prices.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
    assert not imported & {
        "simulation",
        "analysis",
        "experiments",
        "persistence",
        "api",
        "observer",
    }
