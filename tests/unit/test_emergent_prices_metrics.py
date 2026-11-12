"""Four emergent-price metric families with exact keys and orders."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_analysis import (
    empty_emergent_prices_analysis,
    harvest_emergent_prices_analysis,
)
from analysis.emergent_prices_contract import (
    PriceCoverage,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceUnitSource,
)
from analysis.emergent_prices_metrics import (
    assemble_emergent_price_metrics,
    compute_market_price_convergence,
    compute_price_distribution_dispersion,
    compute_price_expectation_structure,
    compute_price_reference_unit_alignment,
)
from analysis.emergent_prices_rows import (
    PriceMarketMembershipInput,
    PriceOwnerExpectationInput,
    PriceOwnerQuoteInput,
)
from analysis.market_institutions_contract import market_venue_token
from analysis.models import MetricAvailability
from analysis.specifications import (
    MARKET_PRICE_CONVERGENCE_KEYS,
    PRICE_DISTRIBUTION_DISPERSION_KEYS,
    PRICE_EXPECTATION_STRUCTURE_KEYS,
    PRICE_REFERENCE_UNIT_ALIGNMENT_KEYS,
    MetricFamilyId,
    metric_specification,
)
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

A = "mktc-aaaaaaaaaaaaaaaa"
B = "mktc-bbbbbbbbbbbbbbbb"


def _analysis():
    events = [
        completed(f"event-a-{index}", tick=index, origin="loc-a")
        for index in range(4)
    ]
    events.extend(
        completed(f"event-b-{index}", tick=10 + index, origin="loc-b")
        for index in range(4)
    )
    expectations = (
        PriceOwnerExpectationInput(
            owner_token="owner-1",
            window_index=0,
            item_kind="food",
            unit_kind="water",
            unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
            expected_ratio_milli=1_000,
            confidence_milli=800,
            level="strong",
            valuation_reservation=1,
            observation_count=4,
            quote_count=0,
            first_tick=0,
            last_tick=3,
            coverage=PriceCoverage.COMPLETE,
        ),
    )
    quotes = (
        PriceOwnerQuoteInput(
            owner_token="owner-1",
            venue_id=market_venue_token("loc-a"),
            window_index=0,
            item_kind="food",
            unit_kind="water",
            direction=PriceQuoteDirection.GIVE_FOR_UNIT,
            ratio_milli=1_000,
            confidence_milli=500,
            source=PriceQuoteSource.OBSERVED_OFFER,
            source_tick=1,
            first_tick=1,
            last_tick=1,
            coverage=PriceCoverage.COMPLETE,
        ),
    )
    memberships = (
        PriceMarketMembershipInput(
            market_token=A,
            venue_id=market_venue_token("loc-a"),
            window_index=0,
            coverage=PriceCoverage.COMPLETE,
        ),
        PriceMarketMembershipInput(
            market_token=B,
            venue_id=market_venue_token("loc-b"),
            window_index=0,
            coverage=PriceCoverage.COMPLETE,
        ),
    )
    return harvest_emergent_prices_analysis(
        committed_events=events,
        expectation_inputs=expectations,
        quote_inputs=quotes,
        membership_inputs=memberships,
    )


@pytest.mark.parametrize(
    ("calculator", "family", "keys"),
    (
        (
            compute_price_expectation_structure,
            MetricFamilyId.PRICE_EXPECTATION_STRUCTURE,
            PRICE_EXPECTATION_STRUCTURE_KEYS,
        ),
        (
            compute_price_distribution_dispersion,
            MetricFamilyId.PRICE_DISTRIBUTION_DISPERSION,
            PRICE_DISTRIBUTION_DISPERSION_KEYS,
        ),
        (
            compute_price_reference_unit_alignment,
            MetricFamilyId.PRICE_REFERENCE_UNIT_ALIGNMENT,
            PRICE_REFERENCE_UNIT_ALIGNMENT_KEYS,
        ),
        (
            compute_market_price_convergence,
            MetricFamilyId.MARKET_PRICE_CONVERGENCE,
            MARKET_PRICE_CONVERGENCE_KEYS,
        ),
    ),
)
def test_family_keys_and_order(calculator, family, keys) -> None:
    document = calculator(_analysis(), run_id="run-1", input_revision="rev-1")
    assert document.metric_family == family.value
    assert set(document.values) == set(keys)
    spec = metric_specification(family)
    assert spec.value_keys == keys
    assert document.availability in {
        MetricAvailability.PRESENT,
        MetricAvailability.PARTIAL,
    }


def test_assembly_returns_catalog_order() -> None:
    documents = assemble_emergent_price_metrics(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    assert [document.metric_family for document in documents] == [
        MetricFamilyId.PRICE_EXPECTATION_STRUCTURE.value,
        MetricFamilyId.PRICE_DISTRIBUTION_DISPERSION.value,
        MetricFamilyId.PRICE_REFERENCE_UNIT_ALIGNMENT.value,
        MetricFamilyId.MARKET_PRICE_CONVERGENCE.value,
    ]


def test_empty_analysis_emits_unknown_documents() -> None:
    empty = empty_emergent_prices_analysis()
    for calculator in (
        compute_price_expectation_structure,
        compute_price_distribution_dispersion,
        compute_price_reference_unit_alignment,
        compute_market_price_convergence,
    ):
        document = calculator(empty, run_id="run-1", input_revision="rev-1")
        assert document.availability is MetricAvailability.UNKNOWN
        assert document.values == {}


def test_values_are_counts_and_integer_milli() -> None:
    documents = assemble_emergent_price_metrics(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    for document in documents:
        for value in document.values.values():
            assert type(value) in {int, str}


def test_forbidden_key_is_rejected() -> None:
    from analysis.specifications import PRICE_EXPECTATION_STRUCTURE_KEYS

    assert "price" not in PRICE_EXPECTATION_STRUCTURE_KEYS
    assert "canonical_price" not in PRICE_EXPECTATION_STRUCTURE_KEYS
