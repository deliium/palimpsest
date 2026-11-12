"""V4-21 analysis contract: enums, ids, forbidden keys, windows, caps."""

from __future__ import annotations

import subprocess
import sys
from enum import Enum
from pathlib import Path

import pytest

from analysis.emergent_prices_contract import (
    EMERGENT_PRICES_ANALYSIS_POLICY_VERSION,
    PRICE_ANALYSIS_ERROR_CODES,
    PRICE_DISTRIBUTION_PREFIX,
    PRICE_EXPECTATION_PREFIX,
    PRICE_FORBIDDEN_KEYS,
    PRICE_QUOTE_PREFIX,
    PRICE_RELATION_PREFIX,
    EmergentPriceAnalysisError,
    PriceAlignment,
    PriceCoverage,
    PriceDistributionStatus,
    PriceLayer,
    PricePairing,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceRelation,
    PriceSampleSource,
    PriceUnitSource,
    price_distribution_token,
    price_expectation_token,
    price_quote_token,
    price_relation_token,
)
from analysis.emergent_prices_policy import (
    EMERGENT_PRICE_ANALYSIS_LOCKED_POLICY,
    EmergentPricesAnalysisPolicy,
    default_emergent_prices_analysis_policy,
    window_bounds,
    window_index_for_tick,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    (
        (PriceCoverage, ("complete", "partial", "missing")),
        (
            PriceLayer,
            (
                "objective_exchange",
                "owner_expectation",
                "analytical_distribution",
                "comparison_view",
            ),
        ),
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
        (PriceQuoteSource, ("observed_offer", "communicated", "self_authored")),
        (
            PricePairing,
            ("paired", "heterogeneous", "same_kind", "out_of_range"),
        ),
        (
            PriceDistributionStatus,
            ("available", "insufficient_samples"),
        ),
        (PriceSampleSource, ("completed", "quoted")),
        (
            PriceRelation,
            (
                "converged",
                "partially_converged",
                "divergent",
                "insufficient_evidence",
            ),
        ),
        (
            PriceAlignment,
            ("consistent", "unresolved", "inconsistent", "not_applicable"),
        ),
    ),
)
def test_enums_have_exactly_the_documented_members(
    enum_type: type[Enum], expected: tuple[str, ...]
) -> None:
    assert tuple(member.value for member in enum_type) == expected


def test_tokens_and_error_codes_are_pinned() -> None:
    assert EMERGENT_PRICES_ANALYSIS_POLICY_VERSION == "emergent-prices.v1"
    assert (PRICE_EXPECTATION_PREFIX, PRICE_QUOTE_PREFIX) == ("prce-", "prcq-")
    assert (PRICE_DISTRIBUTION_PREFIX, PRICE_RELATION_PREFIX) == ("prcd-", "prcr-")
    assert PRICE_ANALYSIS_ERROR_CODES == {
        "price_analysis_invalid_policy",
        "price_analysis_invalid_row",
        "price_analysis_invalid_window",
        "price_analysis_cap_exceeded",
        "price_analysis_forbidden_key",
        "price_analysis_layer_leak",
        "price_analysis_missing_input",
    }
    assert {"price", "canonical_price", "money"} <= PRICE_FORBIDDEN_KEYS


def test_content_addressed_ids_are_stable_and_order_independent() -> None:
    expectation = price_expectation_token(
        "owner-1", "food", "water", 1, "owner_reference"
    )
    assert expectation == price_expectation_token(
        "owner-1", "food", "water", 1, "owner_reference"
    )
    assert expectation.startswith("prce-")
    assert len(expectation) == 21
    quote = price_quote_token(
        "owner-1",
        "mkt-ven-0123456789abcdef",
        "food",
        "water",
        "give_for_unit",
        "observed_offer",
        3,
        1,
    )
    assert quote.startswith("prcq-")
    other_quote = price_quote_token(
        "owner-1",
        "mkt-ven-0123456789abcdef",
        "food",
        "water",
        "give_for_unit",
        "observed_offer",
        4,
        1,
    )
    assert other_quote != quote
    distribution = price_distribution_token(
        "mkt-ven-0123456789abcdef",
        1,
        "food",
        "water",
        "exchange_counterpart",
        "completed",
    )
    assert distribution.startswith("prcd-")
    other_distribution = price_distribution_token(
        "mkt-ven-0123456789abcdef",
        1,
        "food",
        "water",
        "exchange_counterpart",
        "quoted",
    )
    assert other_distribution != distribution
    left = price_relation_token(
        1,
        "market",
        "mktc-bbbbbbbbbbbbbbbb",
        "mktc-aaaaaaaaaaaaaaaa",
        "food",
        "water",
        "exchange_counterpart",
        "completed",
    )
    right = price_relation_token(
        1,
        "market",
        "mktc-aaaaaaaaaaaaaaaa",
        "mktc-bbbbbbbbbbbbbbbb",
        "food",
        "water",
        "exchange_counterpart",
        "completed",
    )
    assert left == right
    assert left.startswith("prcr-")
    other_left = price_relation_token(
        1,
        "market",
        "mktc-bbbbbbbbbbbbbbbb",
        "mktc-aaaaaaaaaaaaaaaa",
        "food",
        "water",
        "exchange_counterpart",
        "quoted",
    )
    assert other_left != left


def test_ids_are_stable_across_processes() -> None:
    code = (
        "from analysis.emergent_prices_contract import price_expectation_token;"
        "print(price_expectation_token("
        "'owner-1','food','water',1,'owner_reference'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == price_expectation_token(
        "owner-1", "food", "water", 1, "owner_reference"
    )


def test_policy_is_locked_and_bounded() -> None:
    assert dict(EMERGENT_PRICE_ANALYSIS_LOCKED_POLICY) == {
        "window_ticks": 32,
        "max_windows": 512,
        "max_exchange_events": 200_000,
        "max_quote_events": 200_000,
        "max_expectation_rows": 4_096,
        "max_owner_quote_rows": 4_096,
        "max_distribution_rows": 8_192,
        "max_market_rows": 1_024,
        "max_relation_rows": 16_384,
        "max_owners": 4_096,
        "max_item_kinds": 1_024,
        "max_units": 64,
        "min_distribution_samples": 4,
        "convergence_high_milli": 750,
        "convergence_low_milli": 250,
        "max_ratio_milli": 64_000,
        "alignment_high_milli": 750,
        "alignment_low_milli": 250,
    }
    assert default_emergent_prices_analysis_policy().window_ticks == 32
    with pytest.raises(EmergentPriceAnalysisError):
        EmergentPricesAnalysisPolicy(window_ticks=0)
    with pytest.raises(EmergentPriceAnalysisError):
        EmergentPricesAnalysisPolicy(convergence_low_milli=900)


def test_window_helpers_fail_closed_past_the_cap() -> None:
    policy = default_emergent_prices_analysis_policy()
    assert window_index_for_tick(0, policy) == 0
    assert window_index_for_tick(63, policy) == 1
    assert window_bounds(1, policy) == (32, 64)
    with pytest.raises(EmergentPriceAnalysisError):
        window_index_for_tick(512 * 32, policy)
    with pytest.raises(EmergentPriceAnalysisError):
        window_bounds(512, policy)
